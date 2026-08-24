"""一键赛后对比 + 反哺批处理。

自动配对最新的 fetch 预测 → 对齐真实赛果 → 计算命中指标 → 出报告 → 回灌模型。

用法（在项目根目录执行）：
  python scripts/review_pipeline.py
        # 用 data/raw/actuals.csv + 自动配对最新 fetch 预测
  python scripts/review_pipeline.py --actual 我的赛果.csv
  python scripts/review_pipeline.py --pred 指定预测.json
  python scripts/review_pipeline.py --no-reinforce      # 只出报告，不回灌 Elo
  python scripts/review_pipeline.py --no-recalibrate    # 不重算校准器

自动配对预测文件的优先级：
  1) --pred 显式指定
  2) data/processed/fetch_predictions.json（fetch 默认输出）
  3) data/processed/ 下 fetch_predictions_*.json 中修改时间最新的一份

反哺（默认开启，可用 --no-* 关闭）：
  --reinforce    ：真实赛果回灌 Elo 评级（elo_ratings.json），下次训练自动加载
  --recalibrate  ：本批赛果重算 Platt 校准器（calibrator.json），下次训练自动加载
多次赛后 review 滚动反哺，模型随真实数据越滚越准。
"""
import os
import sys
import glob
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config
from src import review


def find_latest_pred(pred_arg):
    """按优先级定位预测 JSON。"""
    if pred_arg:
        return pred_arg
    default = os.path.join(config.PROCESSED_DIR, "fetch_predictions.json")
    if os.path.exists(default):
        return default
    cands = sorted(
        glob.glob(os.path.join(config.PROCESSED_DIR, "fetch_predictions_*.json")),
        key=os.path.getmtime, reverse=True)
    return cands[0] if cands else None


def main():
    ap = argparse.ArgumentParser(
        description="一键赛后对比 + 模型反哺",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--actual", default=os.path.join(config.RAW_DIR, "actuals.csv"),
                    help="真实赛果 CSV（默认 data/raw/actuals.csv，参考 actuals_template.csv）")
    ap.add_argument("--pred", default=None,
                    help="预测 JSON（默认自动配对最新 fetch 预测）")
    ap.add_argument("--out", default=config.REVIEW_FILE,
                    help="报告输出路径（默认 data/processed/review_report.json）")
    ap.add_argument("--no-reinforce", action="store_true",
                    help="不回灌 Elo 评级（只出报告）")
    ap.add_argument("--no-recalibrate", action="store_true",
                    help="不重算 Platt 校准器（只出报告）")
    args = ap.parse_args()

    pred_path = find_latest_pred(args.pred)
    if not pred_path or not os.path.exists(pred_path):
        print("⚠️ 找不到预测文件。请先生成预测：")
        print("     python main.py fetch --csv 真实历史.csv --live")
        print("   或用 --pred 指定预测 JSON 路径。")
        sys.exit(1)

    if not os.path.exists(args.actual):
        print(f"⚠️ 真实赛果 CSV 不存在：{args.actual}")
        print(f"   请参考 data/raw/actuals_template.csv 填写，保存为同路径后重试。")
        sys.exit(1)

    print(f"[1/3] 预测文件 : {pred_path}")
    print(f"[1/3] 真实赛果 : {args.actual}")

    report, meta, reinforced = review.run_review(
        pred_path, args.actual, out_path=args.out,
        do_reinforce=not args.no_reinforce,
        do_recalibrate=not args.no_recalibrate)

    print(review.print_report(report))

    print(f"\n[2/3] 报告已保存 : {args.out}")
    if reinforced:
        if "elo" in reinforced:
            print(f"[3/3] ✓ Elo 已回灌   : {reinforced['elo']}（下次 fetch/serve 自动加载）")
        if "calibrator" in reinforced:
            print(f"[3/3] ✓ 校准器已重算 : {reinforced['calibrator']}（下次 fetch/serve 自动加载）")
    else:
        print("[3/3] 未执行反哺（使用了 --no-reinforce / --no-recalibrate）")

    print("\n提示：界面 http://127.0.0.1:8080 顶栏「赛后对比」会自动读取此报告做可视化。")


if __name__ == "__main__":
    main()
