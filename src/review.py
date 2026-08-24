"""赛后对比分析：对齐预测与真实赛果，计算命中指标，并可反哺模型。

流程：
  1) load_predictions() 读 fetch 输出的预测 JSON（data/processed/fetch_predictions.json）
  2) load_actuals_csv() 读真实赛果 CSV（含主客队与比分，可选半场比分）
  3) align() 按 (联赛, 主队, 客队, 日期) 逐场对齐
  4) compute_metrics() 计算各项命中率 + Brier/LogLoss + 按联赛/置信度分层
  5) build_report()/print_report() 输出结构化报告（表格）
  6) reinforce()/recalibrate() 用真实赛果反哺模型（Elo 回灌 / 校准重算）

反哺目的：让下一轮预测更准——真实赛果回灌 Elo 评级，并把赛果并入校准样本，
压缩「预测概率 vs 实际频率」的偏差。
"""
import csv
import json
import math
import os
from collections import defaultdict

import config
from src import elo as elo_mod
from src.calibration import PlattCalibrator


# ---------------- 加载 ----------------
def load_predictions(path):
    """读取预测 JSON（fetch_predictions.json），应为 list[dict]。"""
    with open(path, "r", encoding="utf-8") as f:
        preds = json.load(f)
    if not isinstance(preds, list):
        raise ValueError("预测文件应为 JSON 数组（fetch_predictions.json）")
    return preds


def load_actuals_csv(path):
    """加载真实赛果 CSV。

    必填列：date, league, home, away, home_goals, away_goals
    可选列：ht_home_goals, ht_away_goals（半场比分，用于半全场对比）
    支持以 # 开头的注释行与空行（自动跳过），方便直接基于模板填写。
    返回 list[dict]。
    """
    import io
    kept = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            kept.append(line)
    out = []
    reader = csv.DictReader(io.StringIO("\n".join(kept)))
    for row in reader:
        rec = {
            "date": (row.get("date") or "").strip(),
            "league": (row.get("league") or "").strip(),
            "home": (row.get("home") or "").strip(),
            "away": (row.get("away") or "").strip(),
            "home_goals": int(row.get("home_goals") or 0),
            "away_goals": int(row.get("away_goals") or 0),
        }
        hth = row.get("ht_home_goals")
        hta = row.get("ht_away_goals")
        if hth not in (None, "") and hta not in (None, ""):
            try:
                rec["ht_home_goals"] = int(hth)
                rec["ht_away_goals"] = int(hta)
            except (ValueError, TypeError):
                pass
        out.append(rec)
    return out


# ---------------- 对齐 + 命中判定 ----------------
def _result_of(hg, ag):
    return "W" if hg > ag else ("L" if hg < ag else "D")


def _htft_of(hth, hta, fth, fta):
    hr = _result_of(hth, hta)
    fr = _result_of(fth, fta)
    return hr + fr  # 如 "WD"（半胜全场平）


def align(preds, actuals):
    """按 (联赛, 主队, 客队, 日期) 对齐。

    返回 (pairs, unmatched_preds, unmatched_actuals)。
    pairs 为逐场对照 dict；未对齐项单独返回，不计入指标但报告出来。
    """
    idx = {}
    for a in actuals:
        key = (a["league"], a["home"], a["away"], a["date"])
        idx[key] = a
    pairs = []
    unmatched_preds = []
    used_actual = set()
    for p in preds:
        key = (p.get("league", ""), p.get("home", ""), p.get("away", ""), p.get("date", ""))
        a = idx.get(key)
        if a is None:
            unmatched_preds.append(p)
            continue
        used_actual.add(key)
        pairs.append(_build_pair(p, a))
    unmatched_actuals = [a for a in actuals
                         if (a["league"], a["home"], a["away"], a["date"]) not in used_actual]
    return pairs, unmatched_preds, unmatched_actuals


def _build_pair(p, a):
    prob = p.get("prob", {})
    pw = prob.get("home_win", 0.0)
    pd = prob.get("draw", 0.0)
    pl = prob.get("away_win", 0.0)
    # 预测方向：三态 argmax（平局参与比较）
    pred_result = ("W" if (pw >= pd and pw >= pl)
                   else ("L" if (pl >= pw and pl >= pd) else "D"))

    hg, ag = a["home_goals"], a["away_goals"]
    actual_result = _result_of(hg, ag)
    margin = hg - ag
    total = hg + ag

    cs = p.get("correct_scores", [])
    top3 = p.get("most_likely_scores", [])
    cs_set = {(s["home_goals"], s["away_goals"]) for s in cs}
    top3_set = {(s["home_goals"], s["away_goals"]) for s in top3}
    hit_exact = (hg, ag) in cs_set          # 真实比分在波胆 Top6
    hit_top1 = (hg, ag) in top3_set         # 真实比分在最可能 Top3

    # 让球盘（默认线）：模型赢盘概率>0.5 押上盘，否则押下盘
    hc = p.get("handicap", {}).get(str(config.DEFAULT_HANDICAP))
    hc_win_p = hc["win"] if hc else 0.5
    bet_hc = "上" if hc_win_p > 0.5 else "下"
    hit_hc = (margin > config.DEFAULT_HANDICAP) if bet_hc == "上" else (margin < config.DEFAULT_HANDICAP)

    # 大小球（默认线）
    tt = p.get("totals", {}).get(str(config.DEFAULT_TOTAL_LINE))
    tt_over_p = tt["over"] if tt else 0.5
    bet_ou = "大" if tt_over_p > 0.5 else "小"
    hit_ou = ((bet_ou == "大" and total > config.DEFAULT_TOTAL_LINE) or
              (bet_ou == "小" and total < config.DEFAULT_TOTAL_LINE))

    # 单双
    oe = p.get("odd_even", {})
    pred_odd_p = oe.get("odd", 0.5)
    bet_odd = pred_odd_p > 0.5
    actual_odd = (total % 2 == 1)
    hit_oe = (bet_odd == actual_odd)

    # 半全场（需半场赛果）
    hit_htft = None
    actual_htft = None
    if "ht_home_goals" in a and "ht_away_goals" in a:
        actual_htft = _htft_of(a["ht_home_goals"], a["ht_away_goals"], hg, ag)
        htft = p.get("htft", {})
        if htft:
            pred_htft = max(htft, key=htft.get)
            hit_htft = (pred_htft == actual_htft)

    return {
        "home": p.get("home", ""), "away": p.get("away", ""),
        "league": p.get("league", ""), "date": p.get("date", ""),
        "pred_prob": {"home_win": pw, "draw": pd, "away_win": pl},
        "pred_result": pred_result,
        "pred_top1": top3[0] if top3 else None,
        "pred_correct_scores": cs,
        "pred_odd_even": oe,
        "pred_htft": p.get("htft", {}),
        "actual_hg": hg, "actual_ag": ag, "actual_result": actual_result,
        "actual_htft": actual_htft,
        "actual_margin": margin, "actual_total": total,
        "bet_hc": bet_hc, "bet_ou": bet_ou, "bet_odd": bet_odd,
        "hit_direction": pred_result == actual_result,
        "hit_exact": hit_exact, "hit_top1": hit_top1,
        "hit_handicap": hit_hc, "hit_ou": hit_ou, "hit_odd_even": hit_oe,
        "hit_htft": hit_htft,
        "confidence": p.get("confidence", {}),
    }


# ---------------- 指标 ----------------
def compute_metrics(pairs):
    n = len(pairs)
    if n == 0:
        return {"n": 0}

    def cnt(key):
        return sum(1 for x in pairs if x.get(key))

    direction = cnt("hit_direction")
    exact = cnt("hit_exact")
    top1 = cnt("hit_top1")
    hc = cnt("hit_handicap")
    ou = cnt("hit_ou")
    oe = cnt("hit_odd_even")
    htft_pairs = [x for x in pairs if x.get("hit_htft") is not None]
    htft_hits = sum(1 for x in htft_pairs if x["hit_htft"])

    # Brier / LogLoss（三分类）
    brier_sum = 0.0
    ll_sum = 0.0
    eps = 1e-12
    for x in pairs:
        pr = x["pred_prob"]
        ar = x["actual_result"]
        pt = {"W": pr["home_win"], "D": pr["draw"], "L": pr["away_win"]}[ar]
        brier_sum += ((pr["home_win"] - (1.0 if ar == "W" else 0.0)) ** 2 +
                      (pr["draw"] - (1.0 if ar == "D" else 0.0)) ** 2 +
                      (pr["away_win"] - (1.0 if ar == "L" else 0.0)) ** 2)
        ll_sum += -math.log(max(pt, eps))
    brier = brier_sum / n
    logloss = ll_sum / n

    # 按联赛
    by_league = {}
    lg_groups = defaultdict(list)
    for x in pairs:
        lg_groups[x["league"]].append(x)
    for lg, xs in lg_groups.items():
        nn = len(xs)
        by_league[lg] = {
            "n": nn,
            "direction": sum(1 for y in xs if y["hit_direction"]),
            "exact": sum(1 for y in xs if y["hit_exact"]),
            "ou": sum(1 for y in xs if y["hit_ou"]),
            "hc": sum(1 for y in xs if y["hit_handicap"]),
        }

    # 按置信度分层（验证置信度是否真有区分度）
    by_conf = {}
    conf_groups = defaultdict(list)
    for x in pairs:
        lvl = x.get("confidence", {}).get("level", "低")
        conf_groups[lvl].append(x)
    for lvl, xs in conf_groups.items():
        by_conf[lvl] = {
            "n": len(xs),
            "direction": sum(1 for y in xs if y["hit_direction"]),
        }

    # 如果没有匹配的场次，返回空的metrics
    if n == 0:
        return {
            "n": 0,
            "direction_hits": 0, "direction_acc": 0.0,
            "exact_hits": 0, "exact_acc": 0.0,
            "top1_hits": 0, "top1_acc": 0.0,
            "handicap_hits": 0, "handicap_acc": 0.0,
            "ou_hits": 0, "ou_acc": 0.0,
            "odd_even_hits": 0, "odd_even_acc": 0.0,
            "htft_n": 0, "htft_hits": 0, "htft_acc": None,
            "brier": 0.0, "logloss": 0.0,
            "by_league": {}, "by_confidence": {},
        }

    return {
        "n": n,
        "direction_hits": direction, "direction_acc": direction / n,
        "exact_hits": exact, "exact_acc": exact / n,
        "top1_hits": top1, "top1_acc": top1 / n,
        "handicap_hits": hc, "handicap_acc": hc / n,
        "ou_hits": ou, "ou_acc": ou / n,
        "odd_even_hits": oe, "odd_even_acc": oe / n,
        "htft_n": len(htft_pairs), "htft_hits": htft_hits,
        "htft_acc": (htft_hits / len(htft_pairs)) if htft_pairs else None,
        "brier": brier, "logloss": logloss,
        "by_league": by_league,
        "by_confidence": by_conf,
    }


# ---------------- 报告 ----------------
def build_report(pairs, metrics, meta=None):
    return {
        "meta": meta or {},
        "summary": {
            "场次": metrics["n"],
            "胜负方向准确率": round(metrics["direction_acc"], 4),
            "比分精确命中率": round(metrics["exact_acc"], 4),
            "最可能比分命中率": round(metrics["top1_acc"], 4),
            "让球盘命中率": round(metrics["handicap_acc"], 4),
            "大小球命中率": round(metrics["ou_acc"], 4),
            "单双命中率": round(metrics["odd_even_acc"], 4),
            "半全场命中率": (round(metrics["htft_acc"], 4)
                             if metrics["htft_acc"] is not None else None),
            "Brier分数": round(metrics["brier"], 4),
            "LogLoss": round(metrics["logloss"], 4),
        },
        "by_league": metrics["by_league"],
        "by_confidence": metrics["by_confidence"],
        "matches": pairs,
    }


def print_report(report):
    s = report["summary"]
    m = report.get("meta", {})
    L = []
    L.append("=" * 78)
    L.append("足彩预测 · 赛后对比分析报告")
    if m:
        L.append(f"预测文件 : {m.get('pred_file', '-')}")
        L.append(f"真实赛果 : {m.get('actual_file', '-')}")
        L.append(f"对齐场次 : {m.get('matched', 0)}  "
                 f"未对齐预测: {m.get('unmatched_preds', 0)}  "
                 f"未对齐真实: {m.get('unmatched_actuals', 0)}")
    L.append("=" * 78)
    L.append("【准确率汇总】")
    L.append(f"  胜负方向准确率   : {s['胜负方向准确率']*100:5.1f}%   (n={s['场次']})")
    L.append(f"  比分精确命中率   : {s['比分精确命中率']*100:5.1f}%   (真实比分命中波胆Top6)")
    L.append(f"  最可能比分命中率 : {s['最可能比分命中率']*100:5.1f}%   (真实比分命中Top3)")
    L.append(f"  让球盘命中率     : {s['让球盘命中率']*100:5.1f}%   (默认主让{config.DEFAULT_HANDICAP})")
    L.append(f"  大小球命中率     : {s['大小球命中率']*100:5.1f}%   (默认线{config.DEFAULT_TOTAL_LINE})")
    L.append(f"  单双命中率       : {s['单双命中率']*100:5.1f}%")
    htf = s.get("半全场命中率")
    L.append(f"  半全场命中率     : {('N/A（真实赛果缺半场比分）' if htf is None else f'{htf*100:5.1f}%')}")
    L.append(f"  Brier 分数       : {s['Brier分数']:.4f}   (越接近0越准)")
    L.append(f"  LogLoss          : {s['LogLoss']:.4f}   (越接近0越准)")

    L.append("")
    L.append("【按联赛】")
    L.append(f"  {'联赛':<6} {'场':>4} {'方向%':>7} {'比分%':>7} {'大小球%':>8} {'让球%':>7}")
    for lg, v in report["by_league"].items():
        nn = v["n"] or 1
        da = v["direction"] / nn * 100
        ea = v["exact"] / nn * 100
        oa = v["ou"] / nn * 100
        ha = v["hc"] / nn * 100
        L.append(f"  {lg:<6} {v['n']:>4} {da:>6.1f}% {ea:>6.1f}% {oa:>7.1f}% {ha:>6.1f}%")

    L.append("")
    L.append("【按置信度分层（验证置信度区分度：高应>低）】")
    L.append(f"  {'置信度':<6} {'场':>4} {'方向%':>7}")
    for lvl in ("高", "中", "低"):
        v = report["by_confidence"].get(lvl)
        if v:
            da = v["direction"] / (v["n"] or 1) * 100
            L.append(f"  {lvl:<6} {v['n']:>4} {da:>6.1f}%")

    L.append("")
    L.append("【逐场对照（前 30 场，完整见 JSON 报告）】")
    L.append(f"  {'日期':<11} {'联赛':<5} {'对阵':<18} {'预测W/D/L':<14} {'真实':<7} 方向比分让大小双")
    for x in report["matches"][:30]:
        vs = f"{x['home']}vs{x['away']}"
        pr = x["pred_prob"]
        pred_s = f"{pr['home_win']*100:.0f}/{pr['draw']*100:.0f}/{pr['away_win']*100:.0f}"
        actual_s = f"{x['actual_hg']}-{x['actual_ag']}"
        marks = "".join([
            "✓" if x["hit_direction"] else "✗",
            "✓" if x["hit_exact"] else "·",
            "✓" if x["hit_handicap"] else "✗",
            "✓" if x["hit_ou"] else "✗",
            "✓" if x["hit_odd_even"] else "✗",
        ])
        L.append(f"  {x['date']:<11} {x['league']:<5} {vs:<18} {pred_s:<14} {actual_s:<7} {marks}")
    L.append("=" * 78)
    return "\n".join(L)


# ---------------- 反哺模型（加强未来预测准确性）----------------
def reinforce_elo(pairs, elo_path=None):
    """用真实赛果回灌 Elo 评级：每场按真实比分 update。

    返回保存路径。下次 fetch/serve 训练时自动 load 更新后的评级。
    """
    ep = elo_path or config.ELO_FILE
    er = elo_mod.EloRating.load(ep) if os.path.exists(ep) else elo_mod.EloRating()
    for x in pairs:
        er.update(x["home"], x["away"], x["actual_hg"], x["actual_ag"])
    er.save(ep)
    return ep


def recalibrate(pairs, cal_path=None):
    """用本批真实赛果重算 Platt 校准器（二级校准）。

    注意：传入的是已校准预测概率，再做一次校准属于「再校准」，
    更适合作为「把新赛果并入校准集」的近似。多次 reinforce 建议累积校准样本。
    返回 (calibrator, path)。
    """
    cp = cal_path or getattr(config, "CALIB_FILE", None)
    raw_preds = [x["pred_prob"] for x in pairs]
    actuals = [x["actual_result"] for x in pairs]
    cal = PlattCalibrator().fit(raw_preds, actuals)
    if cp:
        cal.save(cp)
    return cal, cp


def run_review(pred_path, actual_path, out_path=None, do_reinforce=False,
               do_recalibrate=False):
    """一站式：加载→对齐→指标→报告→（可选反哺）→存盘。返回 (report, meta, reinforced)。"""
    preds = load_predictions(pred_path)
    actuals = load_actuals_csv(actual_path)
    pairs, up, ua = align(preds, actuals)
    metrics = compute_metrics(pairs)
    meta = {
        "pred_file": pred_path,
        "actual_file": actual_path,
        "matched": len(pairs),
        "unmatched_preds": len(up),
        "unmatched_actuals": len(ua),
    }
    report = build_report(pairs, metrics, meta)

    reinforced = {}
    if do_reinforce:
        reinforced["elo"] = reinforce_elo(pairs)
    if do_recalibrate:
        cal, cp = recalibrate(pairs)
        reinforced["calibrator"] = cp

    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return report, meta, reinforced
