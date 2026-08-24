"""生成 Cloudflare Pages 静态站数据。

把预测结果导出为 web/mobile/static_data.json，供前端在「无后端」环境下直接读取。
前端读取顺序：先试 /api/predictions（本地后端），失败则 fallback 到 static_data.json（Pages 环境）。

用法：
  python scripts/build_static_site.py            # 真实赛程 + 模型预测 + 合成演示盘口
  python scripts/build_static_site.py --live     # 叠加中国体彩网真实盘口（无需 key）
"""
import os
import sys
import json
import shutil
import argparse
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import web.app as app


def main():
    ap = argparse.ArgumentParser(description="生成静态站数据 static_data.json")
    ap.add_argument("--live", action="store_true",
                    help="叠加中国体彩网实时盘口（免费、无需 key）")
    args = ap.parse_args()

    out_path = os.path.join(ROOT, "web", "mobile", "snapshot.json")

    # 备份现有文件，防止生成失败丢失旧数据
    if os.path.exists(out_path):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(ROOT, "web", "mobile", f"static_data_backup_{ts}.json")
        shutil.copy2(out_path, backup)
        print(f"[backup] 已备份旧数据 -> {backup}")

    print("[build] 开始生成预测（真实历史训练）...")
    app._build(live=args.live, historical_csv=None)

    preds = app._state["predictions"]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False)

    leagues = sorted({p["league"] for p in preds})
    real_odds = sum(1 for p in preds
                    if p.get("odds", {}).get("source") == "real")
    print(f"[build] 写入 {out_path}")
    print(f"[build] 共 {len(preds)} 场，{len(leagues)} 个联赛：{leagues}")
    print(f"[build] 其中 {real_odds} 场含真实盘口，{len(preds) - real_odds} 场为合成演示盘口")


if __name__ == "__main__":
    main()
