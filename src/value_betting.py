"""盘口价值检测（+EV / 价值投注）引擎。

核心思想：庄家赔率含 margin（overround，抽水），直接用 1/odds 会高估隐含概率。
必须先剥离 margin，才能公平比较「模型概率」与「市场真实认为的概率」。

方法：
  - 去水分隐含概率：implied = (1/odds) / sum(1/odds)   （basic normalization）
  - 价值 edge：value = model_prob - implied_prob          （>0 表示模型比市场乐观）
  - 期望收益 EV：ev = model_prob * odds - 1               （>0 即 +EV，长期期望为正）
  - +EV 标记：ev > 0
  - Kelly 分数（可选）：f = ev / (odds - 1)，高风险，建议 fractional（如 1/4）

诚实原则：
  - 本引擎只做「模型概率 vs 赔率」的客观比较，不保证盈利；+EV 仅代表长期期望为正，
    单注方差极大，短期必亏。
  - 庄家 margin 必须剥离，否则 +EV 检测会被抽水淹没（恒为负），形同废功能。
  - 真实 ROI 须在「模型比市场更准」前提下、用真实历史赔率回测；项目无历史赔率时
    仅能接实时赔率实盘，离线不可伪造 ROI。
"""
import math


def overround(odds_list):
    """庄家总水位（含抽水）。=1 表示无 margin；>1 表示抽水。"""
    return sum(1.0 / o for o in odds_list)


def remove_margin(odds_list):
    """basic normalization 去水分，返回 (implied_probs, margin)。
    implied_probs 和为 1，margin = overround - 1（抽水率）。
    """
    inv = [1.0 / o for o in odds_list]
    s = sum(inv)
    if s <= 0:
        return [0.0] * len(odds_list), 0.0
    return [x / s for x in inv], s - 1.0


def _outcome(model_p, odds, implied_p):
    """单个选项的价值指标。"""
    ev = model_p * odds - 1.0
    kelly = (ev / (odds - 1.0)) if odds > 1.0 else 0.0
    return {
        "model_prob": round(model_p, 4),
        "odds": odds,
        "implied_prob": round(implied_p, 4),
        "value": round(model_p - implied_p, 4),
        "ev": round(ev, 4),
        "is_value": ev > 0,
        "kelly": round(max(0.0, kelly), 4),
    }


def detect_1x2(model, odds):
    """胜平负（1X2）价值检测。

    model: {"home_win": p, "draw": p, "away_win": p}   （已校准模型概率，和=1）
    odds:  {"home_win": o, "draw": o, "away_win": o}    （decimal 赔率，含本金）
    返回每选项的 value/ev/is_value + 庄家 margin。
    """
    implied, margin = remove_margin([odds["home_win"], odds["draw"], odds["away_win"]])
    return {
        "margin": round(margin, 4),
        "home_win": _outcome(model["home_win"], odds["home_win"], implied[0]),
        "draw": _outcome(model["draw"], odds["draw"], implied[1]),
        "away_win": _outcome(model["away_win"], odds["away_win"], implied[2]),
    }


def detect_handicap(model_probs, line, home_odds, away_odds):
    """让球盘价值检测。

    model_probs: 模型对该盘口「主赢盘/客赢盘」概率 {"home_win": p, "away_win": p}
                 （来自 predict 的 handicap[line] 输出，已含走盘处理时为 输/赢/走三段，
                  此处取赢盘概率即可，走盘视为本金退回不计入 EV）
    line: 主让球数（如 -1 表示主让1）
    home_odds/away_odds: 主/客赢盘赔率
    """
    # 让球盘仅两结果（走盘不计入收益，按本金退回，ev 不变），用两赔率去水分
    implied, margin = remove_margin([home_odds, away_odds])
    return {
        "line": line,
        "margin": round(margin, 4),
        "home": _outcome(model_probs.get("home_win", 0.0), home_odds, implied[0]),
        "away": _outcome(model_probs.get("away_win", 0.0), away_odds, implied[1]),
    }


def detect_totals(model_probs, line, over_odds, under_odds):
    """大小球价值检测。

    model_probs: {"over": p, "under": p}  （来自 predict 的 totals[line]）
    line: 大小球线（如 2.5）
    over_odds/under_odds: 大/小赔率
    """
    implied, margin = remove_margin([over_odds, under_odds])
    return {
        "line": line,
        "margin": round(margin, 4),
        "over": _outcome(model_probs.get("over", 0.0), over_odds, implied[0]),
        "under": _outcome(model_probs.get("under", 0.0), under_odds, implied[1]),
    }


def best_value(detection):
    """从单次检测结果里挑出 is_value 的选项（按 ev 降序）。"""
    opts = []
    for key, v in detection.items():
        if key == "margin":
            continue
        if isinstance(v, dict) and v.get("is_value"):
            opts.append((key, v))
    opts.sort(key=lambda kv: -kv[1]["ev"])
    return opts
