"""每日赛程自动更新：抓取真实未来赛程 -> 队名解析 -> data/raw/upcoming_fixtures.csv。

数据源（按优先级）：
  1) football-data.org（若设环境变量 FOOTBALL_DATA_API_KEY）：返回整季 SCHEDULED 赛程，覆盖最全。
  2) TheSportsDB（默认，免 key）：eventsnextleague 返回临近未来赛程（免费测试档较稀疏，但真实、每日更新）。

无论哪源，队名都经 name_resolver 对齐到真实历史 canonical 名，消除跨源同名失真。
未匹配到的队名（如当季新升班马尚未进入历史样本）会被跳过并告警，避免未知队导致预测崩溃。

输出 CSV（与 data_collector.load_from_csv(has_result=False) 契约一致，UTF-8 BOM）：
  date,league,home,away

健壮性：
  - 单联赛抓取失败不影响其他联赛；全部失败且已有旧文件时不截断（保留上次好数据）。
  - 网络异常重试。

用法：
  python scripts/update_fixtures.py
  FOOTBALL_DATA_API_KEY=xxx python scripts/update_fixtures.py
"""
import csv
import datetime
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from name_resolver import Resolver  # noqa: E402

OUT = os.path.join(ROOT, "data", "raw", "upcoming_fixtures.csv")
UA = {"User-Agent": "Mozilla/5.0 (football-quant; +daily-fixtures)"}

# 联赛映射：(TheSportsDB id, 项目联赛标签, TheSportsDB 联赛名, football-data.org 竞赛代码)
LEAGUES = [
    (4328, "英超", "English Premier League", "PL"),
    (4335, "西甲", "Spanish La Liga", "PD"),
    (4331, "德甲", "German Bundesliga", "BL1"),
    (4332, "意甲", "Italian Serie A", "SA"),
    (4334, "法甲", "French Ligue 1", "FL1"),
]


def _get_json(url, headers=None, retries=3, timeout=30):
    last = None
    h = dict(UA)
    if headers:
        h.update(headers)
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"请求失败 {url}: {last}")


def _from_thesportsdb(resolver, log):
    """返回 [(date,league,home,away), ...]，来自 TheSportsDB eventsnextleague。"""
    rows = []
    today = datetime.date.today()
    for lid, zh, tsname, _ in LEAGUES:
        try:
            d = _get_json(f"https://www.thesportsdb.com/api/v1/json/3/eventsnextleague.php?id={lid}")
        except Exception as e:
            log(f"  [warn] TheSportsDB {zh} 抓取失败：{e}")
            continue
        for e in (d.get("events") or []):
            date = e.get("dateEvent")
            home, away = e.get("strHomeTeam"), e.get("strAwayTeam")
            if not (date and home and away):
                continue
            try:
                md = datetime.date.fromisoformat(date)
            except Exception:
                continue
            if md < today:
                continue  # 仅保留未来
            (rh, ra), (sh, sa) = resolver.resolve_pairs(home, away, zh)
            if sh == "unmatched" or sa == "unmatched":
                log(f"  [skip] {zh} {date} {home} vs {away}：队名未匹配({sh}/{sa})，跳过")
                continue
            rows.append((date, zh, rh, ra))
    return rows


def _from_football_data(resolver, api_key, log):
    """返回未来赛程，来自 football-data.org（需 key，覆盖最全）。"""
    rows = []
    today = datetime.date.today()
    hdr = {"X-Auth-Token": api_key}
    for _, zh, _, code in LEAGUES:
        try:
            d = _get_json(
                f"https://api.football-data.org/v4/competitions/{code}/matches"
                f"?status=SCHEDULED", headers=hdr)
        except Exception as e:
            log(f"  [warn] football-data {zh} 抓取失败：{e}")
            continue
        for m in (d.get("matches") or []):
            utc = m.get("utcDate")
            home = (m.get("homeTeam") or {}).get("name")
            away = (m.get("awayTeam") or {}).get("name")
            if not (utc and home and away):
                continue
            date = utc[:10]
            try:
                md = datetime.date.fromisoformat(date)
            except Exception:
                continue
            if md < today:
                continue
            (rh, ra), (sh, sa) = resolver.resolve_pairs(home, away, zh)
            if sh == "unmatched" or sa == "unmatched":
                log(f"  [skip] {zh} {date} {home} vs {away}：队名未匹配，跳过")
                continue
            rows.append((date, zh, rh, ra))
    return rows


def update(out=OUT, log=print):
    resolver = Resolver()
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if api_key:
        log("[update] 使用 football-data.org（已检测到 API key）")
        rows = _from_football_data(resolver, api_key, log)
    else:
        log("[update] 使用 TheSportsDB（免 key；设 FOOTBALL_DATA_API_KEY 可获整季完整赛程）")
        rows = _from_thesportsdb(resolver, log)

    # 全部失败且已有旧文件 -> 保留旧数据，不截断
    if not rows:
        if os.path.exists(out):
            log(f"[update] 未获取到任何赛程，保留旧文件：{out}")
            return 0
        log("[update] 未获取到任何赛程且无旧文件，写出空表。")
        rows = []

    # 按日期排序、去重
    rows = sorted(set(rows), key=lambda r: (r[1], r[0]))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "league", "home", "away"])
        for r in rows:
            w.writerow(r)
    log(f"[update] 写出 {len(rows)} 场未来赛程 -> {out}")
    return len(rows)


def main():
    update()


if __name__ == "__main__":
    main()
