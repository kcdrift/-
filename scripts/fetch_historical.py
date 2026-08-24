"""抓取 openfootball/football.json 真实历史赛果，转换为项目 CSV 契约。

数据源（免 key、公共领域、真实全季）：
  https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{code}.json
  code: en.1 英超 / es.1 西甲 / de.1 德甲 / it.1 意甲 / fr.1 法甲

输出 CSV 列（与 data_collector.load_from_csv 契约一致，UTF-8 BOM）：
  date,league,home,away,home_goals,away_goals

用法：
  python scripts/fetch_historical.py
  python scripts/fetch_historical.py --out data/raw/historical_real.csv \
      --seasons 2025-26,2024-25,2023-24
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BASE = "https://raw.githubusercontent.com/openfootball/football.json/master"
# 联赛代码 -> 项目联赛标签（与 config.LEAGUES / 按联赛拟合的 key 对齐）
LEAGUE_MAP = {
    "en.1": "英超",
    "es.1": "西甲",
    "de.1": "德甲",
    "it.1": "意甲",
    "fr.1": "法甲",
    "nl.1": "荷甲",
    "pt.1": "葡超",
}
# 取最近 N 个完整赛季（由近及远尝试）
DEFAULT_SEASONS = ["2025-26", "2024-25", "2023-24", "2022-23"]
TAKE_SEASONS = 3
UA = {"User-Agent": "Mozilla/5.0 (football-quant; +local-training)"}


def _http_get_json(url, retries=3, timeout=30):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # 网络/解析异常
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"下载失败 {url}: {last}")


def _ft_of(m):
    """鲁棒提取全场比分 [主, 客]。openfootball 三种写法：
       - {"ft":[a,b],"ht":[..]}  (dict)
       - [a,b]                    (list，直接是 ft)
       - [[ht_h,ht_a],[ft_h,ft_a]] (list of lists)
       未赛为 null / [null,null] -> 返回 None。
    """
    sc = m.get("score")
    if sc is None:
        return None
    if isinstance(sc, dict):
        ft = sc.get("ft")
        return ft
    if isinstance(sc, list):
        if len(sc) == 2 and isinstance(sc[0], int):
            return sc  # [a,b]
        if len(sc) == 2 and isinstance(sc[0], list):
            return sc[1]  # [[ht],[ft]]
    return None


def parse_season(season, code, league_zh):
    """返回该联赛该赛季的已赛场次列表（dict）。"""
    url = f"{BASE}/{season}/{code}.json"
    try:
        d = _http_get_json(url)
    except Exception as e:
        print(f"  [skip] {league_zh} {season} ({code}): {e}")
        return []
    ms = d.get("matches") or []
    rows = []
    for m in ms:
        ft = _ft_of(m)
        if ft is None or ft[0] is None or ft[1] is None:
            continue  # 跳过未赛/缺比分
        h, a = m.get("team1"), m.get("team2")
        date = m.get("date")
        if not (h and a and date):
            continue
        rows.append({
            "date": date,
            "league": league_zh,
            "home": h,
            "away": a,
            "home_goals": int(ft[0]),
            "away_goals": int(ft[1]),
        })
    return rows


def fetch(out_path, seasons, take=TAKE_SEASONS):
    # 仅保留真实存在的赛季（由近及远），取前 take 个
    usable = []
    for season in seasons:
        ok = False
        for code in LEAGUE_MAP:
            try:
                _http_get_json(f"{BASE}/{season}/{code}.json")
                ok = True
                break
            except Exception:
                pass
        if ok:
            usable.append(season)
        if len(usable) >= take:
            break
    if not usable:
        print("[error] 没有可用的赛季（网络或仓库结构变化）")
        return 0

    print(f"[fetch] 采用赛季（由近及远）：{usable}")
    all_rows = []
    for season in usable:
        for code, zh in LEAGUE_MAP.items():
            rows = parse_season(season, code, zh)
            print(f"  {zh} {season}: {len(rows)} 场已赛")
            all_rows.extend(rows)

    # 去重（同 联赛+主+客+日期 应唯一，保险）
    seen = set()
    dedup = []
    for r in all_rows:
        k = (r["league"], r["home"], r["away"], r["date"])
        if k in seen:
            continue
        seen.add(k)
        dedup.append(r)
    dedup.sort(key=lambda r: (r["league"], r["date"]))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "league", "home", "away", "home_goals", "away_goals"])
        for r in dedup:
            w.writerow([r["date"], r["league"], r["home"], r["away"],
                        r["home_goals"], r["away_goals"]])
    print(f"[fetch] 共写入 {len(dedup)} 场 -> {out_path}")
    return len(dedup)


def main():
    ap = argparse.ArgumentParser(description="抓取 openfootball 真实历史赛果 -> CSV")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "raw", "historical_real.csv"))
    ap.add_argument("--seasons", default=",".join(DEFAULT_SEASONS),
                    help="候选赛季，逗号分隔，由近及远，取前 N 个存在的")
    ap.add_argument("--take", type=int, default=TAKE_SEASONS)
    args = ap.parse_args()
    seasons = [s.strip() for s in args.seasons.split(",") if s.strip()]
    n = fetch(args.out, seasons, args.take)
    if n == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
