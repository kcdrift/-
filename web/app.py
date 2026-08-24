"""Web 展示界面：纯标准库 http.server，无需第三方依赖。

启动后访问 http://127.0.0.1:8080
  - GET /                     展示界面
  - GET /api/predictions      返回预测列表，支持 ?league=英超&date=2026-08-25 筛选
  - GET /api/filters          返回可选联赛与日期，供前端下拉框

预测在启动时一次性计算并缓存，API 仅做筛选，响应迅速。
"""
import json
import os
import sys
import gzip
import io

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass
import math
import random
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config
from src import data_collector, preprocessing, elo, poisson_model, prediction_engine, odds_fetcher
from src import sporttery_fetcher
from src.team_resolver import resolve_to_training
from src.calibration import PlattCalibrator
from web.team_translations import translate_match, ALL_TRANSLATIONS

_state = {"predictions": [], "fixtures": [], "leagues": [], "dates": [], "cold_predictions": []}


def _norm_line(x):
    """盘口线规范化：2.0 -> 2（整型），2.5 保持。保证与 handicap/totals 的整型键匹配。"""
    xf = float(x)
    return int(xf) if xf == int(xf) else round(xf, 2)


def _attach_odds(p, real=None):
    """为单场预测附实际盘口水位 + 价值投注检测（+EV）。

    使用 src.value_betting 引擎：先剥离庄家 margin（overround），再比较模型概率
    与市场隐含概率，标记 +EV（ev>0）选项。覆盖 1X2 / 让球 / 大小球三市场。
    real 为真实 odds dict（CSV 或实时 API），None 时合成演示水位。
    """
    # 无训练模型（日职/韩职/欧冠等）：仅展示真实盘口，不做价值检测，
    # 避免拿假概率去跟市场赔率比，误导出 +EV。
    if p.get("no_model") or not p.get("prob"):
        if not real:
            return {"source": "none", "no_model": True,
                    "message": p.get("message", "暂无训练数据·不可作准")}
        res = {"source": "real", "no_model": True,
               "message": p.get("message", "暂无训练数据·不可作准")}
        h2h = real.get("h2h")
        if h2h and h2h.get("home_win") and h2h.get("draw") and h2h.get("away_win"):
            res["h2h"] = {"home_win_odds": h2h["home_win"],
                          "draw_odds": h2h["draw"],
                          "away_win_odds": h2h["away_win"]}
        hc = real.get("handicap")
        if hc and hc.get("home_odds") and hc.get("away_odds"):
            res["handicap"] = {"line": _norm_line(float(hc["line"])),
                               "home_odds": round(float(hc["home_odds"]), 2),
                               "away_odds": round(float(hc["away_odds"]), 2)}
        tt = real.get("totals")
        if tt and tt.get("over_odds") and tt.get("under_odds"):
            res["totals"] = {"line": _norm_line(float(tt["line"])),
                             "over_odds": round(float(tt["over_odds"]), 2),
                             "under_odds": round(float(tt["under_odds"]), 2)}
        return res
    from src.value_betting import detect_1x2, detect_handicap, detect_totals
    margin_dist = p.get("margin_dist", {})
    total_dist = p.get("total_dist", {})
    md_sum = sum(margin_dist.values()) or 1
    td_sum = sum(total_dist.values()) or 1
    prob = p.get("prob", {})
    mw = prob.get("home_win", 0.0)
    md_ = prob.get("draw", 0.0)
    ma = prob.get("away_win", 0.0)

    def model_handicap_win(line):
        return sum(c for m, c in margin_dist.items() if m > line) / md_sum

    def model_total_over(line):
        return sum(c for g, c in total_dist.items() if g > line) / td_sum

    if real:
        res = {"source": "real"}
        # 1X2（胜平负，最核心市场）
        h2h = real.get("h2h")
        if h2h and h2h.get("home_win") and h2h.get("draw") and h2h.get("away_win"):
            det = detect_1x2({"home_win": mw, "draw": md_, "away_win": ma}, h2h)
            res["h2h"] = {
                "home_win_odds": h2h["home_win"], "draw_odds": h2h["draw"],
                "away_win_odds": h2h["away_win"], "margin": det["margin"],
                "home_win_value": det["home_win"]["value"], "home_win_ev": det["home_win"]["ev"],
                "home_win_is_value": det["home_win"]["is_value"],
                "draw_value": det["draw"]["value"], "draw_ev": det["draw"]["ev"],
                "draw_is_value": det["draw"]["is_value"],
                "away_win_value": det["away_win"]["value"], "away_win_ev": det["away_win"]["ev"],
                "away_win_is_value": det["away_win"]["is_value"],
            }
        # 让球盘
        hc = real.get("handicap")
        if hc and hc.get("home_odds") and hc.get("away_odds"):
            line = float(hc["line"])
            hwm = model_handicap_win(line)
            det = detect_handicap({"home_win": hwm, "away_win": 1 - hwm},
                                  line, float(hc["home_odds"]), float(hc["away_odds"]))
            res["handicap"] = {
                "line": _norm_line(line),
                "home_odds": round(float(hc["home_odds"]), 2),
                "away_odds": round(float(hc["away_odds"]), 2),
                "home_model_prob": round(hwm, 4), "away_model_prob": round(1 - hwm, 4),
                "home_value": det["home"]["value"], "home_ev": det["home"]["ev"],
                "home_is_value": det["home"]["is_value"],
                "away_value": det["away"]["value"], "away_ev": det["away"]["ev"],
                "away_is_value": det["away"]["is_value"],
            }
        # 大小球
        tt = real.get("totals")
        if tt and tt.get("over_odds") and tt.get("under_odds"):
            line = float(tt["line"])
            tom = model_total_over(line)
            det = detect_totals({"over": tom, "under": 1 - tom},
                                line, float(tt["over_odds"]), float(tt["under_odds"]))
            res["totals"] = {
                "line": _norm_line(line),
                "over_odds": round(float(tt["over_odds"]), 2),
                "under_odds": round(float(tt["under_odds"]), 2),
                "over_model_prob": round(tom, 4), "under_model_prob": round(1 - tom, 4),
                "over_value": det["over"]["value"], "over_ev": det["over"]["ev"],
                "over_is_value": det["over"]["is_value"],
                "under_value": det["under"]["value"], "under_ev": det["under"]["ev"],
                "under_is_value": det["under"]["is_value"],
            }
        if "h2h" not in res and "handicap" not in res and "totals" not in res:
            return _synthetic_odds(p)
        return res
    return _synthetic_odds(p)


def _synthetic_odds(p):
    """合成演示水位（确定性 seed，重启一致）。

    让球/大小球用确定性随机扰动；1X2 由模型概率 + 6% margin 反推（确定性），
    价值应≈0（模型对自己造的赔率无 edge），与真实引擎口径一致，不虚假标 +EV。
    """
    from src.value_betting import detect_1x2
    prob = p.get("prob", {})
    mw = prob.get("home_win", 1/3)
    md_ = prob.get("draw", 1/3)
    ma = prob.get("away_win", 1/3)
    margin = 1.06
    # 合成 h2h 赔率（基于模型概率 + margin）
    h2h = {
        "home_win": round(1.0 / (mw * margin), 2),
        "draw": round(1.0 / (md_ * margin), 2),
        "away_win": round(1.0 / (ma * margin), 2),
    }
    det = detect_1x2({"home_win": mw, "draw": md_, "away_win": ma}, h2h)
    h_win = max(p.get("handicap", {}).get("1", {}).get("win", 0.3), 0.01)
    t_over = max(p.get("totals", {}).get("2.5", {}).get("over", 0.5), 0.01)
    seed = abs(hash((p["home"], p["away"], p["date"], "odds"))) % (2 ** 32)
    rnd = random.Random(seed)
    hc_line, tt_line = _norm_line(1.0), _norm_line(2.5)
    ho = round(1.0 / (h_win * margin) + rnd.uniform(-0.04, 0.04), 2)
    ao = round(1.0 / ((1 - h_win) * margin) + rnd.uniform(-0.04, 0.04), 2)
    oo = round(1.0 / (t_over * margin) + rnd.uniform(-0.04, 0.04), 2)
    uo = round(1.0 / ((1 - t_over) * margin) + rnd.uniform(-0.04, 0.04), 2)
    return {
        "source": "synthetic",
        "h2h": {
            "home_win_odds": h2h["home_win"], "draw_odds": h2h["draw"],
            "away_win_odds": h2h["away_win"], "margin": det["margin"],
            "home_win_value": det["home_win"]["value"], "home_win_ev": det["home_win"]["ev"],
            "home_win_is_value": det["home_win"]["is_value"],
            "draw_value": det["draw"]["value"], "draw_ev": det["draw"]["ev"],
            "draw_is_value": det["draw"]["is_value"],
            "away_win_value": det["away_win"]["value"], "away_win_ev": det["away_win"]["ev"],
            "away_win_is_value": det["away_win"]["is_value"],
        },
        "handicap": {
            "line": hc_line, "home_odds": ho, "away_odds": ao,
            "home_model_prob": round(h_win, 4), "away_model_prob": round(1 - h_win, 4),
            "home_value": round(h_win - 1.0 / ho, 4),
            "away_value": round((1 - h_win) - 1.0 / ao, 4),
        },
        "totals": {
            "line": tt_line, "over_odds": oo, "under_odds": uo,
            "over_model_prob": round(t_over, 4), "under_model_prob": round(1 - t_over, 4),
            "over_value": round(t_over - 1.0 / oo, 4),
            "under_value": round((1 - t_over) - 1.0 / uo, 4),
        },
    }


def _build(odds_csv=None, live=False, api_key=None, historical_csv=None):
    # 模型训练优先用真实历史（historical_csv），否则合成演示数据。
    # 实时 API 不提供历史赛果，live 仅替换未来赛程+盘口。
    if historical_csv and os.path.exists(historical_csv):
        historical, _ = data_collector.load_from_csv(historical_csv, has_result=True)
        print(f"[web] 使用真实历史训练：{historical_csv}")
    elif os.path.exists(config.REAL_HISTORICAL_CSV):
        historical, _ = data_collector.load_from_csv(config.REAL_HISTORICAL_CSV, has_result=True)
        print(f"[web] 使用真实历史训练（默认真实源）：{config.REAL_HISTORICAL_CSV}")
    else:
        historical, _ = data_collector.collect()
        print("[web] 未找到真实历史 CSV，回退合成演示数据（不具实战价值）")
    train_set, calib_set, eval_set, _ = preprocessing.preprocess(historical)
    # 按联赛拟合
    models = {}
    by_league = {}
    for m in train_set:
        by_league.setdefault(m["league"], []).append(m)
    for lg, ms in by_league.items():
        models[lg] = poisson_model.PoissonModel().fit(ms)
    default_model = poisson_model.PoissonModel().fit(train_set)
    er = elo.EloRating()
    for m in train_set:
        er.update(m["home"], m["away"], m["home_goals"], m["away_goals"])
    engine = prediction_engine.PredictionEngine(models, er, train_set, default_model)
    # 校准器优先级：① 反哺产出的校准器文件（CALIB_FILE，由 review --recalibrate 生成）
    #               ② 否则在校准集（与评估集独立）上拟合，缓解过自信
    if os.path.exists(config.CALIB_FILE):
        try:
            cal = PlattCalibrator.load(config.CALIB_FILE)
            engine.set_calibrator(cal)
            print(f"[web] 加载反哺校准器：{config.CALIB_FILE}（样本 {cal.n} 场）")
        except Exception as e:
            print(f"[web][warn] 加载反哺校准器失败，改用校准集拟合：{e}")
            cal = None
    else:
        cal = None
    if cal is None and calib_set:
        raw_preds = [engine.predict(m["home"], m["away"], league=m.get("league"),
                                    n=5000, seed=12345, _use_calib=False) for m in calib_set]
        cal = PlattCalibrator().fit([p["prob"] for p in raw_preds],
                                    [m["result"] for m in calib_set])
        engine.set_calibrator(cal)

    # 赛程逻辑：live模式下优先用体彩数据为主生成fixtures，否则用CSV
    if live:
        try:
            # 优先用中国体彩网（免费、无限制、实时）
            live_fx, live_odds = sporttery_fetcher.fetch_live()
            odds_map = live_odds or {}
            print(f"[web] 体彩模式：抓到 {len(live_fx)} 场，{len(odds_map)} 场有盘口")

            # 以体彩数据为主生成fixtures（中文队名，用于预测和展示）
            fixtures = []
            for m in live_fx:
                fixtures.append({
                    "date": m.get("date", ""),
                    "time": m.get("time", ""),
                    "league": m.get("league", ""),
                    "home": m.get("home", ""),      # 中文队名（体彩主）
                    "away": m.get("away", ""),
                    "home_cn": m.get("home", ""),
                    "away_cn": m.get("away", ""),
                })
            print(f"[web] 以体彩为主生成fixtures：{len(fixtures)} 场")
        except Exception as e:
            print(f"[web][warn] 体彩抓取失败：{e}")
            # 回退到The Odds API或CSV
            try:
                live_fx, live_odds = odds_fetcher.fetch_live(api_key)
                odds_map = live_odds or {}
                fixtures = live_fx or []
                print(f"[web] The Odds API模式：{len(fixtures)} 场")
            except Exception as e2:
                print(f"[web][warn] The Odds API也失败：{e2}，用合成数据")
                fixtures = []
                odds_map = None
    elif os.path.exists(config.UPCOMING_FIXTURES_CSV):
        # 非live模式：加载CSV赛程
        _, all_fixtures = data_collector.load_from_csv(config.UPCOMING_FIXTURES_CSV, has_result=False)
        print(f"[web] 加载未来赛程（{config.UPCOMING_FIXTURES_CSV}）：{len(all_fixtures)} 场")
        from datetime import date, timedelta
        cutoff = str(date.today() + timedelta(days=14))
        fixtures = [f for f in all_fixtures if f.get("date", "") <= cutoff]
        print(f"[web] 截取近期赛程（≤{cutoff}）：{len(fixtures)} 场")
        odds_map = None
    else:
        _, fixtures = data_collector.collect()
        print("[web] 未找到赛程CSV，回退合成演示赛程")
        odds_map = None

    preds = []
    for fx in fixtures:
        lg = fx.get("league")
        # 赛程可能是中文队名（体彩模式）或英文队名（CSV模式）
        home_raw = fx.get("home", "")
        away_raw = fx.get("away", "")
        
        # 检测是否是中文队名（体彩模式）
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in home_raw + away_raw)
        if has_chinese:
            # 中文队名 -> 翻译为英文 -> 解析到训练名
            from web.team_translations import translate_team
            home_en = translate_team(home_raw)
            away_en = translate_team(away_raw)
            home = resolve_to_training(lg, home_en)
            away = resolve_to_training(lg, away_en)
        else:
            # 英文队名 -> 直接解析
            home = resolve_to_training(lg, home_raw)
            away = resolve_to_training(lg, away_raw)
        
        # 体彩模式：保留中文队名用于展示
        if has_chinese:
            fx["home_cn"] = home_raw
            fx["away_cn"] = away_raw
        else:
            # 英文队名模式：尝试翻译为中文（若翻译失败则保留英文）
            try:
                translated = translate_match({"home": home_raw, "away": away_raw})
                fx["home_cn"] = translated.get("home", home_raw)
                fx["away_cn"] = translated.get("away", away_raw)
            except Exception:
                fx["home_cn"] = home_raw
                fx["away_cn"] = away_raw
        try:
            pred = engine.predict(home, away, league=lg, n=5000, _use_calib=True)
        except ValueError:
            # 无训练模型（日职/韩职/欧冠）：占位预测，仅附真实盘口，不作预测
            pred = {
                "home": home, "away": away, "league": lg,
                "date": fx.get("date", ""),
                "no_model": True,
                "message": "暂无训练数据·不可作准",
                "prob": None, "most_likely_scores": [], "correct_scores": [],
                "confidence": {"level": "低", "score": 0.0},
                "lambda_home": None, "lambda_away": None, "elo_diff": None,
            }
        # 关联日期/联赛 + 盘口水位（盘口 key 用原始 odds/fixture 名，与 odds_map 对齐）
        pred["date"] = fx.get("date", "")
        pred["league"] = lg
        # 盘口匹配：体彩模式用中文队名，CSV模式用英文队名
        if has_chinese:
            key = (lg, home_raw, away_raw, fx.get("date", ""))
        else:
            key = (lg, fx.get("home", home), fx.get("away", away), fx.get("date", ""))
        real = odds_map.get(key) if odds_map else None
        pred["odds"] = _attach_odds(pred, real)
        # 模型概率已并入 odds 结构，分布大字段不再下发前端
        pred.pop("margin_dist", None)
        pred.pop("total_dist", None)
        preds.append(pred)
    leagues = sorted({p["league"] for p in preds})
    dates = sorted({p["date"] for p in preds})
    _state["predictions"] = preds
    # 先添加中文队名（翻译层）
    translated = [translate_match(p) for p in _state["predictions"]]
    _state["predictions"] = translated
    # 再计算冷门预测（使用中文队名），并嵌入每场预测
    from src.cold_prediction import analyze_cold_matches
    try:
        cold_results = analyze_cold_matches(_state["predictions"])
        # 将冷门信息嵌入到对应的预测中
        cold_map = {c['match_id']: c for c in cold_results}
        for p in _state["predictions"]:
            match_id = f"{p.get('home', '')}_vs_{p.get('away', '')}"
            cold_info = cold_map.get(match_id)
            if cold_info:
                p['cold_level'] = cold_info['cold_level']
                p['cold_probabilities'] = cold_info['cold_probabilities']
                p['cold_recommendation'] = cold_info['recommendation']
        _state["cold_predictions"] = cold_results
        high_count = sum(1 for c in cold_results if c['cold_level'] == '高')
        med_count = sum(1 for c in cold_results if c['cold_level'] == '中')
        low_count = sum(1 for c in cold_results if c['cold_level'] == '低')
        print(f"[web] 冷门分析完成：共{len(cold_results)}场，高风险{high_count}场，中风险{med_count}场，低风险{low_count}场")
    except Exception as e:
        print(f"[web][warn] 冷门分析失败：{e}")
    _state["fixtures"] = fixtures
    _state["leagues"] = leagues
    _state["dates"] = dates
    print(f"[web] 已生成 {len(preds)} 场预测，联赛 {leagues}")


def _filtered(league=None, date=None):
    out = _state["predictions"]
    if league:
        out = [p for p in out if p["league"] == league]
    if date:
        out = [p for p in out if p["date"] == date]
    return out


def _get_cold_predictions():
    """返回冷门预测结果。"""
    return _state.get("cold_predictions", [])


def _load_review():
    """读取赛后对比报告（review 命令产出），供 /api/review 返回。"""
    if not os.path.exists(config.REVIEW_FILE):
        return {"available": False}
    try:
        with open(config.REVIEW_FILE, "r", encoding="utf-8") as f:
            report = json.load(f)
        return {"available": True, "report": report,
                "config": {"default_handicap": config.DEFAULT_HANDICAP,
                           "default_total_line": config.DEFAULT_TOTAL_LINE}}
    except Exception as e:
        return {"available": False, "error": str(e)}


def _build_analytics():
    """构建分析数据：联赛分布、日期趋势、价值投注统计。"""
    preds = _state["predictions"]
    if not preds:
        return {"error": "无预测数据"}

    # 1. 联赛分布
    league_dist = {}
    for p in preds:
        lg = p.get("league", "未知")
        if lg not in league_dist:
            league_dist[lg] = {"total": 0, "home_win": 0, "draw": 0, "away_win": 0, "high_conf": 0}
        league_dist[lg]["total"] += 1
        pr = p.get("prob", {})
        if pr.get("home_win", 0) > pr.get("draw", 0) and pr.get("home_win", 0) > pr.get("away_win", 0):
            league_dist[lg]["home_win"] += 1
        elif pr.get("draw", 0) > pr.get("home_win", 0) and pr.get("draw", 0) > pr.get("away_win", 0):
            league_dist[lg]["draw"] += 1
        else:
            league_dist[lg]["away_win"] += 1
        if p.get("confidence", {}).get("level") == "高":
            league_dist[lg]["high_conf"] += 1

    # 2. 日期趋势（近30天每日场次）
    from collections import defaultdict
    date_trend = defaultdict(int)
    today = datetime.date.today()
    for p in preds:
        d = p.get("date", "")
        if d:
            try:
                dt = datetime.date.fromisoformat(d)
                if dt >= today - datetime.timedelta(days=30):
                    date_trend[d] += 1
            except:
                pass
    date_labels = sorted(date_trend.keys())
    date_values = [date_trend[d] for d in date_labels]

    # 3. 价值投注统计（仅真实盘口；合成盘口无真实价值不统计）
    value_bets = {
        "home_value": [], "away_value": [], "over_value": [], "under_value": [],
        "h2h_home_value": [], "h2h_draw_value": [], "h2h_away_value": [],
        "value_bet_count": 0,   # 含任意 +EV 选项的场次
    }
    for p in preds:
        odds = p.get("odds", {})
        if odds.get("source") == "real":
            hc = odds.get("handicap", {})
            tt = odds.get("totals", {})
            h2h = odds.get("h2h", {})
            has_value = False
            if hc:
                value_bets["home_value"].append(hc.get("home_value", 0))
                value_bets["away_value"].append(hc.get("away_value", 0))
                if hc.get("home_is_value") or hc.get("away_is_value"):
                    has_value = True
            if tt:
                value_bets["over_value"].append(tt.get("over_value", 0))
                value_bets["under_value"].append(tt.get("under_value", 0))
                if tt.get("over_is_value") or tt.get("under_is_value"):
                    has_value = True
            if h2h:
                value_bets["h2h_home_value"].append(h2h.get("home_win_value", 0))
                value_bets["h2h_draw_value"].append(h2h.get("draw_value", 0))
                value_bets["h2h_away_value"].append(h2h.get("away_win_value", 0))
                if h2h.get("home_win_is_value") or h2h.get("draw_is_value") or h2h.get("away_win_is_value"):
                    has_value = True
            if has_value:
                value_bets["value_bet_count"] += 1

    # 4. 高置信度比赛汇总
    high_conf_matches = [p for p in preds if p.get("confidence", {}).get("level") == "高"]
    high_conf_summary = {
        "count": len(high_conf_matches),
        "by_league": {},
        "top_picks": []
    }
    for p in high_conf_matches:
        lg = p.get("league", "")
        high_conf_summary["by_league"][lg] = high_conf_summary["by_league"].get(lg, 0) + 1
        pr = p.get("prob", {})
        max_prob = max(pr.values())
        high_conf_summary["top_picks"].append({
            "home": p.get("home_cn", p.get("home", "")),
            "away": p.get("away_cn", p.get("away", "")),
            "league": lg,
            "max_prob": round(max_prob * 100, 1),
            "prediction": "主胜" if pr.get("home_win") == max_prob else ("平局" if pr.get("draw") == max_prob else "客胜")
        })
    high_conf_summary["top_picks"].sort(key=lambda x: -x["max_prob"])
    high_conf_summary["top_picks"] = high_conf_summary["top_picks"][:20]

    return {
        "league_distribution": league_dist,
        "date_trend": {"labels": date_labels[-30:], "values": date_values[-30:]},
        "value_bets": value_bets,
        "high_confidence": high_conf_summary,
        "total_fixtures": len(preds),
        "date_range": {"start": min(p.get("date", "") for p in preds if p.get("date")),
                       "end": max(p.get("date", "") for p in preds if p.get("date"))}
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        # 启用GZIP压缩，减少传输体积
        accept_gzip = 'gzip' in self.headers.get('Accept-Encoding', '')
        if accept_gzip and len(body) > 1024:
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as f:
                f.write(body)
            compressed = buf.getvalue()
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Vary', 'Accept-Encoding')
            self.send_header("Content-Length", str(len(compressed)))
            self.end_headers()
            self.wfile.write(compressed)
        else:
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def _send_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path in ("/", "/index.html"):
            self._send_file(os.path.join(ROOT, "web", "templates", "index.html"),
                            "text/html; charset=utf-8")
        elif path == "/mobile" or path == "/mobile/":
            self._send_file(os.path.join(ROOT, "web", "mobile", "index.html"),
                            "text/html; charset=utf-8")
        elif path.startswith("/mobile/"):
            # 静态文件服务（JSON、CSS等）
            file_path = os.path.join(ROOT, "web", "mobile", path[len("/mobile/"):])
            if os.path.exists(file_path):
                mime_type = "application/json" if file_path.endswith('.json') else "text/html"
                self._send_file(file_path, mime_type)
            else:
                self.send_error(404)
        elif path == "/api/predictions":
            league = qs.get("league", [None])[0]
            date = qs.get("date", [None])[0]
            self._send_json(_filtered(league, date))
        elif path == "/api/filters":
            teams = {}
            for p in _state["predictions"]:
                teams.setdefault(p["league"], set()).add(p["home"])
                teams.setdefault(p["league"], set()).add(p["away"])
            teams = {lg: sorted(v) for lg, v in teams.items()}
            self._send_json({"leagues": _state["leagues"],
                             "dates": _state["dates"],
                             "teams": teams})
        elif path == "/api/review":
            self._send_json(_load_review())
        elif path == "/api/analytics":
            self._send_json(_build_analytics())
        elif path == "/api/cold-predictions":
            self._send_json(_get_cold_predictions())
        elif path == "/api/reload":
            # 重载静态数据文件
            import json as _json
            static_path = os.path.join(ROOT, "web", "mobile", "static_data.json")
            if os.path.exists(static_path):
                with open(static_path, "r", encoding="utf-8") as _f:
                    _data = _json.load(_f)
                _state["predictions"] = _data
                _state["leagues"] = sorted({p["league"] for p in _data})
                _state["dates"] = sorted({p["date"] for p in _data})
                self._send_json({"status": "ok", "count": len(_data), "leagues": _state["leagues"]})
            else:
                self._send_json({"status": "error", "message": "static_data.json not found"})
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


def run(host=None, port=None, odds_csv=None,  live=False,
        api_key=None, historical_csv=None):
    # 云平台（Render/Railway 等）注入 PORT；本地默认 config 值
    if host is None:
        host = os.environ.get("HOST", config.WEB_HOST)
    if port is None:
        port = int(os.environ.get("PORT", config.WEB_PORT))
    if not _state["predictions"]:
        _build(odds_csv=odds_csv, live=live, api_key=api_key,
               historical_csv=historical_csv)
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"足彩预测界面已启动: http://{host}:{port}"
          f"{'（实时赔率模式）' if live else ''}")
    print("按 Ctrl+C 停止")
    # 自动打开浏览器（训练已完成，数据就绪，避免空白页）
    try:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="足彩预测界面")
    ap.add_argument("--live", action="store_true",
                    help="接实时盘口（真实赔率 +EV 检测，消耗 API 额度）")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    args = ap.parse_args()
    # api_key 留空 -> odds_fetcher 自动读 ODDS_API_KEY 环境变量；
    # 若 env 也未设置，则从项目根 .env 兜底读取，避免后台启动时 export 失效导致 live 退化为合成。
    if args.live and not os.environ.get("ODDS_API_KEY"):
        # 优先读 exe 所在目录的 .env（打包后别人把 key 放 exe 旁边即可），
        # 再回退项目根目录 .env（源码运行场景）。
        _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        _env_candidates = [os.path.join(_exe_dir, ".env"), os.path.join(ROOT, ".env")]
        _env_path = next((p for p in _env_candidates if os.path.exists(p)), None)
        if _env_path is None:
            print("[web][warn] 未找到 .env，实时盘口将无 key 可用")
        try:
            with open(_env_path, "r", encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line.startswith("ODDS_API_KEY="):
                        os.environ["ODDS_API_KEY"] = _line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    run(host=args.host, port=args.port, live=args.live, api_key=None)
