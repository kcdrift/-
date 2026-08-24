"""把重新生成的 5 新联赛合成赛程合并进 upcoming_fixtures.csv。

保留现有真实 5 大联赛赛程（23 号起），追加荷甲/葡超/欧冠/韩职/日职（23 号起），
按 (date, league, home, away) 去重，写回 CSV。
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
csv_path = os.path.join(RAW, "upcoming_fixtures.csv")
new_path = os.path.join(RAW, "new_leagues_v2.json")

NEW5 = ["荷甲", "葡超", "欧冠", "韩职", "日职"]
REAL5 = ["英超", "西甲", "德甲", "意甲", "法甲"]

existing = list(csv.DictReader(open(csv_path, encoding="utf-8")))
new = json.load(open(new_path, encoding="utf-8"))

seen = {(r["date"], r["league"], r["home"], r["away"]) for r in existing}
combined = list(existing)
added = 0
for r in new:
    k = (r["date"], r["league"], r["home"], r["away"])
    if k not in seen:
        combined.append({"date": r["date"], "league": r["league"],
                         "home": r["home"], "away": r["away"]})
        seen.add(k)
        added += 1

combined.sort(key=lambda x: (x["date"], x["league"]))

with open(csv_path, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["date", "league", "home", "away"])
    w.writeheader()
    w.writerows(combined)

real5 = sum(1 for r in combined if r["league"] in REAL5)
new5 = sum(1 for r in combined if r["league"] in NEW5)
ds = sorted(set(r["date"] for r in combined))
print(f"合并完成：总 {len(combined)} 场（真实5大联赛 {real5} + 新5联赛 {new5}，本次新增 {added}）")
print(f"日期范围：{ds[0]} .. {ds[-1]}（共 {len(ds)} 个比赛日）")
print(f"新5联赛每日首场（验证从今晚23号起）：")
first_dates = {}
for r in combined:
    if r["league"] in NEW5 and r["league"] not in first_dates:
        first_dates[r["league"]] = r["date"]
for lg in NEW5:
    print(f"  {lg}: 首场 {first_dates.get(lg, '无')}")
