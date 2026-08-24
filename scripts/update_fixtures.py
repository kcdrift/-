"""合并多源未来赛程：football-data.org（完整）+ openfootball + TheSportsDB。

数据源优先级（从高到低）：
  1) football-data.org（需设环境变量 FOOTBALL_DATA_API_KEY，覆盖最全，实时）
  2) openfootball/football.json 2026-27（EPL完整，其他联赛陆续补）
  3) TheSportsDB eventsnextleague（免费档每联赛1场补充）

输出 CSV：date,league,home,away（UTF-8 BOM，与 data_collector.load_from_csv 契约一致）
"""
import csv
import datetime
import json
import os
import sys
import time
import urllib.request

# 自动加载 .env 文件（兼容 Windows/Mac/Linux）
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#"):
                continue
            if "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from name_resolver import Resolver  # noqa: E402

OUT = os.path.join(ROOT, "data", "raw", "upcoming_fixtures.csv")
UA = {"User-Agent": "Mozilla/5.0 (football-quant; +daily-fixtures)"}

# football-data.org 联赛代码 → 项目联赛标签
FDOL_LEAGUES = {
    "PL": "英超",
    "PD": "西甲",
    "BL1": "德甲",
    "SA": "意甲",
    "FL1": "法甲",
}

# openfootball 当前赛季代码 → 项目联赛标签
OPENFOOTBALL_LEAGUES = {
    "en.1": "英超",
    "es.1": "西甲",
    "de.1": "德甲",
    "it.1": "意甲",
    "fr.1": "法甲",
}

# TheSportsDB 联赛 ID
THESPORTSDB_LEAGUES = [
    (4328, "英超", "English Premier League"),
    (4335, "西甲", "Spanish La Liga"),
    (4331, "德甲", "German Bundesliga"),
    (4332, "意甲", "Italian Serie A"),
    (4334, "法甲", "French Ligue 1"),
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
                return json.load(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"请求失败 {url}: {last}")


def _from_football_data(resolver, api_key, log):
    """从 football-data.org 抓完整五联赛未来赛程（需 API key）。"""
    rows = []
    today = str(datetime.date.today())
    hdr = {"X-Auth-Token": api_key}
    for code, zh in FDOL_LEAGUES.items():
        try:
            d = _get_json(
                f"https://api.football-data.org/v4/competitions/{code}/matches"
                f"?status=SCHEDULED", headers=hdr)
        except Exception as e:
            log(f"  [warn] football-data {zh} 抓取失败：{e}")
            continue
        for m in (d.get("matches") or []):
            utc = m.get("utcDate", "")[:10]
            home = (m.get("homeTeam") or {}).get("name")
            away = (m.get("awayTeam") or {}).get("name")
            if not (utc and home and away):
                continue
            if utc < today:
                continue
            (rh, ra), (sh, sa) = resolver.resolve_pairs(home, away, zh)
            if sh == "unmatched" or sa == "unmatched":
                log(f"  [skip] football-data {zh} {utc} {home} vs {away}：队名未匹配({sh}/{sa})")
                continue
            rows.append((utc, zh, rh, ra))
    return rows


def _from_openfootball(resolver, log):
    """从 openfootball/football.json 2026-27 抓当前赛季未赛场次。"""
    rows = []
    today = str(datetime.date.today())
    for code, zh in OPENFOOTBALL_LEAGUES.items():
        url = f"https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/{code}.json"
        try:
            d = _get_json(url)
        except Exception as e:
            log(f"  [warn] openfootball {zh}({code}) 抓取失败：{e}")
            continue
        ms = d.get("matches") or []
        def ft_of(m):
            sc = m.get("score")
            if sc is None:
                return None
            if isinstance(sc, dict):
                return sc.get("ft")
            if isinstance(sc, list):
                return sc[1] if len(sc) > 1 else (sc[0] if len(sc) == 2 else None)
            return None
        for m in ms:
            date = m.get("date")
            home, away = m.get("team1"), m.get("team2")
            if not (date and home and away):
                continue
            if date < today:
                continue
            ft = ft_of(m)
            if ft is not None:
                continue
            (rh, ra), (sh, sa) = resolver.resolve_pairs(home, away, zh)
            if sh == "unmatched" or sa == "unmatched":
                log(f"  [skip] openfootball {zh} {date} {home} vs {away}：队名未匹配({sh}/{sa})")
                continue
            rows.append((date, zh, rh, ra))
    return rows


def _from_thesportsdb(resolver, log):
    """从 TheSportsDB eventsnextleague 抓未来赛程（免费档每联赛1场）。"""
    rows = []
    today = datetime.date.today()
    for lid, zh, tsname in THESPORTSDB_LEAGUES:
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
                continue
            (rh, ra), (sh, sa) = resolver.resolve_pairs(home, away, zh)
            if sh == "unmatched" or sa == "unmatched":
                log(f"  [skip] TheSportsDB {zh} {date} {home} vs {away}：队名未匹配({sh}/{sa})")
                continue
            rows.append((date, zh, rh, ra))
    return rows


def merge_sources(fdol_rows, of_rows, ts_rows, log):
    """合并三个源，去重（优先顺序：football-data > openfootball > TheSportsDB）。"""
    seen = set()
    merged = []
    for source_rows in [fdol_rows, of_rows, ts_rows]:
        for r in source_rows:
            key = (r[0], r[2], r[3])
            if key not in seen:
                seen.add(key)
                merged.append(r)
    return sorted(merged, key=lambda r: (r[1], r[0]))


def update(out=OUT, log=print):
    resolver = Resolver()
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    
    if api_key:
        log(f"[update] 检测到 FOOTBALL_DATA_API_KEY，使用 football-data.org（完整五联赛）")
        fdol_rows = _from_football_data(resolver, api_key, log)
        log(f"[update] football-data.org 提供 {len(fdol_rows)} 场")
        
        # 即使有 football-data，也尝试 openfootball 补充（防临时故障）
        of_rows = _from_openfootball(resolver, log)
        log(f"[update] openfootball 补充 {len(of_rows)} 场")
        
        ts_rows = _from_thesportsdb(resolver, log)
        log(f"[update] TheSportsDB 补充 {len(ts_rows)} 场")
        
        rows = merge_sources(fdol_rows, of_rows, ts_rows, log)
    else:
        log("[update] 未检测到 FOOTBALL_DATA_API_KEY，使用 openfootball + TheSportsDB 双源合并")
        of_rows = _from_openfootball(resolver, log)
        log(f"[update] openfootball 提供 {len(of_rows)} 场")
        ts_rows = _from_thesportsdb(resolver, log)
        log(f"[update] TheSportsDB 提供 {len(ts_rows)} 场")
        rows = merge_sources([], of_rows, ts_rows, log)

    if not rows:
        if os.path.exists(out):
            log(f"[update] 未获取到任何赛程，保留旧文件：{out}")
            return 0
        log("[update] 未获取到任何赛程且无旧文件，写出空表。")
        rows = []

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "league", "home", "away"])
        for r in rows:
            w.writerow(r)
    log(f"[update] 写出 {len(rows)} 场未来赛程 -> {out}")
    
    # 统计今日场次
    today = str(datetime.date.today())
    today_count = sum(1 for r in rows if r[0] == today)
    log(f"[update] 今日({today})赛程: {today_count} 场")
    
    return len(rows)


def main():
    update()


if __name__ == "__main__":
    main()
