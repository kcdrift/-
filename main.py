"""足彩量化预测 - 命令行入口。

用法：
  python main.py collect          采集数据（生成演示数据或接真实 CSV）
  python main.py train            训练模型（泊松 + Elo），保存参数
  python main.py evaluate         回测评估，输出评估报告
  python main.py demo             采集→训练→预测样例→评估 一站式演示
  python main.py serve            启动 Web 展示界面（默认 http://127.0.0.1:8080）
  python main.py predict          打印全部未来赛程的预测结果
  python main.py fetch --csv 真实历史.csv --live   真实历史训练 + 实时抓赛程/盘口 + 预测
  python main.py review --pred 预测.json --actual 真实赛果.csv [--reinforce] [--recalibrate]
                      赛后对比分析：对齐预测与真实比分，输出准确率汇总 + 逐场对照；
                      --reinforce 回灌 Elo，--recalibrate 重算校准，加强未来预测准确性。

可选参数：
  --csv PATH       从真实 CSV 加载历史（含 home_goals/away_goals 列）
  --fixtures PATH  从 CSV 加载未来赛程（仅 date/league/home/away 列）
  --odds PATH      从 CSV 加载真实盘口水位（handicap/totals 列）
  --live           实时抓取赛程+盘口（The Odds API，需 ODDS_API_KEY 或 --odds-api-key）
  --odds-api-key    The Odds API key（缺省读 env ODDS_API_KEY）
  --top N           fetch 打印前 N 场（默认 20）
  --pred PATH      review：预测 JSON 路径（默认 data/processed/fetch_predictions.json）
  --actual PATH    review：真实赛果 CSV 路径（date,league,home,away,home_goals,away_goals）
  --reinforce      review：用真实赛果回灌 Elo 评级（下次 fetch/serve 自动生效）
  --recalibrate    review：用本批赛果重算 Platt 校准器（覆盖 CALIB_FILE）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from src import data_collector, preprocessing, elo, poisson_model, prediction_engine, evaluation
from src.calibration import PlattCalibrator

# 校准拟合用的蒙特卡洛次数（不需太高，加速）
CALIB_N = 5000


def do_collect(args):
    historical, fixtures = data_collector.collect(use_csv=args.csv)
    print(f"[collect] 历史比赛 {len(historical)} 场，未来赛程 {len(fixtures)} 场")
    if not args.csv:
        print(f"          演示数据已保存: {config.HISTORICAL_FILE}")
        print(f"          演示赛程已保存: {config.FIXTURES_FILE}")
    return historical, fixtures


def build_model(historical):
    train_set, calib_set, eval_set, dropped = preprocessing.preprocess(historical)
    print(f"[preprocess] 训练集 {len(train_set)} 场，校准集 {len(calib_set)} 场，"
          f"评估集 {len(eval_set)} 场，剔除 {len(dropped)} 条")
    # 按联赛分别拟合泊松模型（不同联赛进球尺度不同，分联赛更准）
    models = {}
    by_league = {}
    for m in train_set:
        by_league.setdefault(m["league"], []).append(m)
    for lg, ms in by_league.items():
        models[lg] = poisson_model.PoissonModel().fit(ms)
    # 全量兜底模型
    default_model = poisson_model.PoissonModel().fit(train_set)
    default_model.save(config.POISSON_FILE, league="all")
    er = elo.EloRating()
    for m in train_set:
        er.update(m["home"], m["away"], m["home_goals"], m["away_goals"])
    er.save(config.ELO_FILE)
    print(f"[train] 已拟合 {len(models)} 个联赛泊松模型 + 1 个全量兜底")
    print(f"[train] 参数已保存: {config.POISSON_FILE} / {config.ELO_FILE}")
    return models, default_model, er, train_set, calib_set, eval_set, dropped


def load_fixtures(args):
    if args.fixtures:
        _, fixtures = data_collector.load_from_csv(args.fixtures, has_result=False)
    else:
        if os.path.exists(config.UPCOMING_FIXTURES_CSV):
            _, fixtures = data_collector.load_from_csv(config.UPCOMING_FIXTURES_CSV, has_result=False)
        elif os.path.exists(config.FIXTURES_FILE):
            with open(config.FIXTURES_FILE, "r", encoding="utf-8") as f:
                fixtures = json.load(f)
        else:
            _, fixtures = data_collector.collect()
    return fixtures


def do_train(args):
    # 保护真实反哺：未显式指定 --csv 时，优先用真实历史 CSV（避免误覆盖为合成）
    if not args.csv and os.path.exists(config.REAL_HISTORICAL_CSV):
        args.csv = config.REAL_HISTORICAL_CSV
    historical, _ = do_collect(args)
    build_model(historical)


def _fit_calibrator(engine, calib_set, n=CALIB_N):
    """在校准集（与评估集独立）上用未校准预测拟合 Platt 校准器。"""
    raw_preds = [engine.predict(m["home"], m["away"], league=m.get("league"),
                                n=n, seed=12345, _use_calib=False) for m in calib_set]
    cal = PlattCalibrator().fit([p["prob"] for p in raw_preds],
                                [m["result"] for m in calib_set])
    engine.set_calibrator(cal)
    return raw_preds


def _raw_preds_eval_set(engine, eval_set, n=CALIB_N):
    """生成评估集的未校准预测，用于评估报告中「校准前 vs 校准后」对比。"""
    return [engine.predict(m["home"], m["away"], league=m.get("league"),
                           n=n, seed=12345, _use_calib=False) for m in eval_set]


def do_evaluate(args):
    historical, _ = do_collect(args)
    models, default_model, er, train_set, calib_set, eval_set, _ = build_model(historical)
    engine = prediction_engine.PredictionEngine(models, er, train_set, default_model)
    # 校准器只在校准集上拟合；评估集完全不参与拟合，保证指标无乐观偏差
    _fit_calibrator(engine, calib_set)
    raw_eval = _raw_preds_eval_set(engine, eval_set)
    report = evaluation.evaluate(engine, eval_set, n=CALIB_N,
                                 compare_calibration=True, raw_preds=raw_eval)
    evaluation.print_report(report)
    return report


def do_predict(args):
    historical, _ = do_collect(args)
    models, default_model, er, train_set, calib_set, eval_set, _ = build_model(historical)
    fixtures = load_fixtures(args)
    engine = prediction_engine.PredictionEngine(models, er, train_set, default_model)
    _fit_calibrator(engine, calib_set)
    preds = engine.predict_fixtures(fixtures)
    for p in preds[:20]:
        _print_pred(p)
    print(f"... 共 {len(preds)} 场预测（完整结果见 Web 界面或 API）")


def _print_pred(p):
    pr = p["prob"]
    sc = p["most_likely_scores"]
    score_str = "  ".join(f"{s['home_goals']}-{s['away_goals']}({s['prob']*100:.0f}%)" for s in sc)
    print(f"{p['home']} vs {p['away']} | "
          f"主胜{pr['home_win']*100:.0f}% 平{pr['draw']*100:.0f}% 客胜{pr['away_win']*100:.0f}% | "
          f"比分[{score_str}] | 置信{p['confidence']['level']}")


def do_demo(args):
    print(">>> 一站式演示：采集 → 训练 → 样例预测 → 评估")
    historical, fixtures = do_collect(args)
    models, default_model, er, train_set, calib_set, eval_set, _ = build_model(historical)
    engine = prediction_engine.PredictionEngine(models, er, train_set, default_model)
    print("\n>>> 样例预测（前 8 场，已校准）")
    _fit_calibrator(engine, calib_set)
    for p in engine.predict_fixtures(fixtures)[:8]:
        _print_pred(p)
    print("\n>>> 模型评估（含校准对比，校准集与评估集分离）")
    raw_eval = _raw_preds_eval_set(engine, eval_set)
    report = evaluation.evaluate(engine, eval_set, n=CALIB_N,
                                 compare_calibration=True, raw_preds=raw_eval)
    evaluation.print_report(report)


def do_serve(args):
    from web.app import run
    # app 内部自行采集/训练，可选接入真实盘口水位 CSV；--live 则实时抓取；
    # --csv 作为真实历史训练（消除合成队名碰撞），界面端同样支持真实训练+实时盘口
    run(odds_csv=args.odds, live=args.live, api_key=args.odds_api_key,
        historical_csv=args.csv)


def do_fetch(args):
    """一条指令：真实历史训练 + 实时抓取赛程与盘口 + 预测 + 附价值信号。

    用法：
      python main.py fetch --csv 真实历史.csv --live [--odds-api-key KEY]
    说明：
      - --csv 真实历史（必填，训练用，消除真实队名撞合成同名队导致的概率失真）
      - --live 实时抓取赛程+盘口（The Odds API，需 ODDS_API_KEY 或 --odds-api-key）；
             无 key/网络异常则优雅回退到合成赛程，不崩。
      - 不 --live 时可用 --fixtures 指定赛程 CSV、--odds 指定盘口 CSV。
    结果：CLI 打印预测 + 价值信号，并保存 predictions 到 data/processed/fetch_predictions.json。
    """
    from web.app import _attach_odds  # 复用已验证的盘口价值计算
    import src.odds_fetcher as odds_fetcher

    # 1. 真实历史（训练用）—— 默认真实源；既无 --csv 也无真实 CSV 才报错
    if not args.csv and not os.path.exists(config.REAL_HISTORICAL_CSV):
        print("⚠️ 缺少 --csv 真实历史：实时模型必须用真实历史训练，否则真实队名会撞合成"
              "同名队、概率失真。")
        print("   用法：python main.py fetch --csv 真实历史.csv --live")
        print(f"   或先运行：python scripts/fetch_historical.py （生成 {config.REAL_HISTORICAL_CSV}）")
        return
    if not args.csv:
        args.csv = config.REAL_HISTORICAL_CSV
        print(f"[fetch] 未指定 --csv，使用默认真实历史：{args.csv}")
    if not os.path.exists(args.csv):
        print(f"⚠️ 历史 CSV 不存在：{args.csv}")
        return
    historical, _ = data_collector.load_from_csv(args.csv, has_result=True)
    if not historical:
        print("⚠️ 历史 CSV 无有效记录（需含 home_goals/away_goals 列）。")
        return
    models, default_model, er, train_set, calib_set, eval_set, dropped = build_model(historical)

    # 2. 实时抓取赛程 + 盘口（或无 --live 时走本地 CSV/演示赛程）
    src = "synthetic"
    odds_map = None
    if args.live:
        try:
            fixtures, odds_map = odds_fetcher.fetch_live(api_key=args.odds_api_key)
            src = "live"
            print(f"[fetch] 实时抓取 {len(fixtures)} 场赛程，{len(odds_map)} 场附盘口水位")
        except Exception as e:
            print(f"[fetch][warn] 实时抓取失败（{e}），回退演示赛程。")
            _, fixtures = data_collector.collect()
            src = "synthetic"
    elif args.fixtures:
        _, fixtures = data_collector.load_from_csv(args.fixtures, has_result=False)
        src = "real"
        if args.odds:
            odds_map = data_collector.load_odds_csv(args.odds)
        print(f"[fetch] 使用本地赛程 CSV：{args.fixtures}（{len(fixtures)} 场）")
    else:
        if os.path.exists(config.UPCOMING_FIXTURES_CSV):
            _, fixtures = data_collector.load_from_csv(config.UPCOMING_FIXTURES_CSV, has_result=False)
            src = "real"
            print(f"[fetch] 使用真实未来赛程（默认真实源）：{config.UPCOMING_FIXTURES_CSV}（{len(fixtures)} 场）")
        else:
            _, fixtures = data_collector.collect()
            src = "synthetic"
            print("[fetch] 使用演示赛程（未指定 --live / --fixtures，且无真实赛程 CSV）")

    # 3. 预测 + 校准
    engine = prediction_engine.PredictionEngine(models, er, train_set, default_model)
    _fit_calibrator(engine, calib_set)
    # 手动循环避免 predict_fixtures 方法内部状态问题
    preds = []
    for fx in fixtures:
        preds.append(engine.predict(fx["home"], fx["away"],
                                    league=fx.get("league"), n=CALIB_N, _use_calib=True))

    # 4. 关联日期/联赛 + 盘口价值
    for p in preds:
        fx = next((f for f in fixtures
                   if f["home"] == p["home"] and f["away"] == p["away"]), None)
        p["date"] = fx["date"] if fx else ""
        p["league"] = fx["league"] if fx else ""
        key = (p["league"], p["home"], p["away"], p["date"])
        real = odds_map.get(key) if odds_map else None
        p["odds"] = _attach_odds(p, real)
        # 显示/存盘用中文名（预测与盘口匹配已用英文原名完成，此处仅换显示）
        if fx:
            p["home"], p["away"] = fx.get("home_cn", p["home"]), fx.get("away_cn", p["away"])
        # 分布大字段已并入 odds 结构，剔除避免存盘过大
        p.pop("margin_dist", None)
        p.pop("total_dist", None)

    # 5. 打印
    print(f"\n[fetch] 共 {len(preds)} 场预测（赛程来源：{src}）")
    for p in preds[:args.top]:
        _print_pred(p)
        _print_odds(p)

    # 6. 存盘（供 serve 直接读，或人工复核）
    out = os.path.join(config.PROCESSED_DIR, "fetch_predictions.json")
    os.makedirs(config.PROCESSED_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False, indent=2)
    print(f"\n[fetch] 预测结果已保存：{out}")
    print(f"[fetch] 界面版（真实训练+实时盘口）：python main.py serve --csv {args.csv} --live")


def _print_odds(p):
    o = p.get("odds", {})
    if o.get("source") == "real":
        h = o["handicap"]
        t = o["totals"]
        hv = f"{h['home_value']*100:+.1f}/{h['away_value']*100:+.1f}%"
        tv = f"{t['over_value']*100:+.1f}/{t['under_value']*100:+.1f}%"
        print(f"   盘口：主让{h['line']} 上{h['home_odds']}/下{h['away_odds']} 价值{hv} | "
              f"大小{t['line']} 大{t['over_odds']}/小{t['under_odds']} 价值{tv}")
    else:
        print("   盘口：合成演示水位（无 --live 或抓取失败）")


def do_review(args):
    """赛后对比分析：对齐预测与真实赛果，计算命中指标，可选反哺模型。"""
    from src import review
    pred_path = args.pred or os.path.join(config.PROCESSED_DIR, "fetch_predictions.json")
    if not os.path.exists(pred_path):
        print(f"⚠️ 预测文件不存在：{pred_path}（先跑 fetch 生成，或指定 --pred）")
        return
    if not args.actual:
        print("⚠️ 缺少 --actual 真实赛果 CSV（列：date,league,home,away,home_goals,away_goals）。")
        return
    if not os.path.exists(args.actual):
        print(f"⚠️ 真实赛果 CSV 不存在：{args.actual}")
        return
    out_path = os.path.join(config.PROCESSED_DIR, "review_report.json")
    report, meta, reinforced = review.run_review(
        pred_path, args.actual, out_path=out_path,
        do_reinforce=args.reinforce, do_recalibrate=args.recalibrate)
    print(review.print_report(report))
    print(f"\n[review] 报告已保存：{out_path}")
    if reinforced:
        if "elo" in reinforced:
            print(f"[review] Elo 已回灌并保存：{reinforced['elo']}（下次 fetch/serve 自动加载）")
        if "calibrator" in reinforced:
            print(f"[review] 校准器已重算并保存：{reinforced['calibrator']}（下次 fetch/serve 自动加载）")


def main():
    parser = argparse.ArgumentParser(description="足彩量化预测项目")
    sub = parser.add_subparsers(dest="cmd")
    for name in ("collect", "train", "evaluate", "demo", "predict", "serve", "fetch", "review"):
        sp = sub.add_parser(name)
        sp.add_argument("--csv", default=None, help="真实历史 CSV 路径")
        sp.add_argument("--fixtures", default=None, help="未来赛程 CSV 路径")
        sp.add_argument("--odds", default=None, help="真实盘口水位 CSV 路径")
        sp.add_argument("--live", action="store_true",
                        help="实时抓取盘口水位（The Odds API，需 ODDS_API_KEY 或 --odds-api-key）")
        sp.add_argument("--odds-api-key", default=None,
                        help="The Odds API key（缺省读 env ODDS_API_KEY）")
        sp.add_argument("--top", type=int, default=20,
                        help="fetch 命令打印前 N 场（默认 20）")
        sp.add_argument("--pred", default=None, help="review：预测 JSON 路径")
        sp.add_argument("--actual", default=None, help="review：真实赛果 CSV 路径")
        sp.add_argument("--reinforce", action="store_true",
                        help="review：用真实赛果回灌 Elo 评级")
        sp.add_argument("--recalibrate", action="store_true",
                        help="review：用本批赛果重算 Platt 校准器")
    args = parser.parse_args()
    cmd = args.cmd or "demo"
    {
        "collect": do_collect, "train": do_train, "evaluate": do_evaluate,
        "demo": do_demo, "predict": do_predict, "serve": do_serve,
        "fetch": do_fetch, "review": do_review,
    }[cmd](args)


if __name__ == "__main__":
    main()
