"""数据采集模块。

提供两种数据来源：
  1) generate_synthetic()：生成演示用历史比赛 + 未来赛程（无需联网/API）。
  2) load_from_csv()：接入真实数据，CSV 列约定见函数 docstring。

无论哪种来源，对外统一返回：
  - historical: list[dict]  {date, league, home, away, home_goals, away_goals, result}
  - fixtures:   list[dict]  {date, league, home, away}   （无赛果，待预测）
"""
import json
import math
import random
from config import (LEAGUES, SEASONS, SEASON_START_YEAR, LEAGUE_AVG_HOME,
                    LEAGUE_AVG_AWAY, HISTORICAL_FILE, FIXTURES_FILE)


def _true_strengths(teams):
    """给每队生成真实攻防强度（log 尺度），含主场优势。

    注意：不再内部重置 random.seed，种子由 generate_synthetic 在开头统一设定一次，
    保证各联赛的强度分布互不相同（否则每联赛同排名队伍的强度会完全一样）。
    """
    att, deff = {}, {}
    for t in teams:
        att[t] = random.gauss(0.0, 0.20)
        deff[t] = random.gauss(0.0, 0.20)
    return att, deff


def generate_synthetic(seed=20240822):
    """生成多联赛多赛季历史 + 未来两周赛程。返回 (historical, fixtures)。"""
    random.seed(seed)
    historical, fixtures = [], []
    home_param = math.log(1.25)  # 主场约 +25% 期望进球

    for league, teams in LEAGUES.items():
        att, deff = _true_strengths(teams)
        # 每个赛季：主客场双循环
        for season in range(SEASONS):
            year = SEASON_START_YEAR + season
            # 赛季日期窗口（演示用：每年 8 月 ~ 次年 5 月）
            start = f"{year}-08-10"
            for rd in range(len(teams) - 1):
                # 轮次日期：简单线性排开
                from datetime import date, timedelta
                d = date.fromisoformat(start) + timedelta(days=rd * 7)
                ds = d.isoformat()
                # 简单轮转赛程（circle method 简化）
                sched = _round_robin(teams, rd)
                for home, away in sched:
                    lam_h = math.exp(att[home] - deff[away] + home_param) * LEAGUE_AVG_HOME
                    lam_a = math.exp(att[away] - deff[home]) * LEAGUE_AVG_AWAY
                    hg = _poisson(lam_h)
                    ag = _poisson(lam_a)
                    result = ("W" if hg > ag else ("L" if hg < ag else "D"))
                    historical.append({
                        "date": ds, "league": league, "home": home,
                        "away": away, "home_goals": hg, "away_goals": ag,
                        "result": result,
                    })

        # 未来赛程：从 2026-08-22 起两周
        from datetime import date, timedelta
        base = date(2026, 8, 22)
        for rd in range(2):
            d = base + timedelta(days=rd * 7 + 3)
            ds = d.isoformat()
            for home, away in _round_robin(teams, rd):
                fixtures.append({
                    "date": ds, "league": league, "home": home, "away": away,
                })

    return historical, fixtures


def _round_robin(teams, round_idx):
    """简化轮转，返回该轮 (home, away) 列表。"""
    n = len(teams)
    arr = list(teams)
    if n % 2 == 1:
        arr.append("轮空")
    m = len(arr)
    rot = round_idx % (m - 1)
    order = [arr[0]] + arr[1 + rot:] + arr[1:1 + rot]
    pairs = []
    for i in range(m // 2):
        a, b = order[i], order[m - 1 - i]
        if a == "轮空" or b == "轮空":
            continue
        # 主客场交替：偶数轮 a 主场，奇数轮 b 主场
        if round_idx % 2 == 0:
            pairs.append((a, b))
        else:
            pairs.append((b, a))
    return pairs


def _poisson(mu):
    if mu <= 0:
        return 0
    import math
    L = math.exp(-mu)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1


def load_from_csv(path, has_result=True):
    """从真实 CSV 加载。

    历史 CSV 列（has_result=True）：
        date, league, home, away, home_goals, away_goals [, result]
    赛程 CSV 列（has_result=False）：
        date, league, home, away

    返回 (historical, fixtures)。若文件同时含赛果则 historical 非空、fixtures 空；
    若 only_fixtures 则反之。这里按 has_result 分流。
    """
    import csv
    historical, fixtures = [], []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get("date")
            league = row.get("league")
            home = row.get("home")
            away = row.get("away")
            if not (date and league and home and away):
                continue
            # 优先使用 has_result 参数判断，若CSV含赛果列则覆盖
            has_goals = "home_goals" in row and row.get("home_goals")
            if has_result or has_goals:
                hg = int(row.get("home_goals", 0) or 0)
                ag = int(row.get("away_goals", 0) or 0)
                r = (row.get("result") or "").strip().upper()
                if r in ("W", "D", "L"):
                    result = r
                else:
                    result = "W" if hg > ag else ("L" if hg < ag else "D")
                historical.append({
                    "date": date, "league": league, "home": home,
                    "away": away, "home_goals": hg, "away_goals": ag,
                    "result": result,
                })
            else:
                fixtures.append({
                    "date": date, "league": league, "home": home, "away": away,
                })
    return historical, fixtures


def save_raw(historical, fixtures):
    with open(HISTORICAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historical, f, ensure_ascii=False, indent=2)
    with open(FIXTURES_FILE, "w", encoding="utf-8") as f:
        json.dump(fixtures, f, ensure_ascii=False, indent=2)


def _f(v, default=0.0):
    """安全转 float，空值/异常回 default。"""
    try:
        return float(v) if v not in (None, "") else default
    except (ValueError, TypeError):
        return default


def load_odds_csv(path):
    """加载真实盘口水位 CSV。

    列（表头任意顺序，UTF-8 含 BOM 自动处理）：
        date, league, home, away,
        handicap_line, handicap_home_odds, handicap_away_odds,
        total_line, over_odds, under_odds

    其中 odds 为 decimal 水位（如 0.92 表示上盘水位 0.92）。
    返回 dict，key = (league, home, away, date)，value = odds 结构。
    未提供真实数据时可留空，由 web 端合成演示水位。
    """
    import csv
    odds = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row.get("league"), row.get("home"), row.get("away"), row.get("date"))
            odds[key] = {
                "handicap": {
                    "line": _f(row.get("handicap_line")),
                    "home_odds": _f(row.get("handicap_home_odds")),
                    "away_odds": _f(row.get("handicap_away_odds")),
                },
                "totals": {
                    "line": _f(row.get("total_line")),
                    "over_odds": _f(row.get("over_odds")),
                    "under_odds": _f(row.get("under_odds")),
                },
            }
    return odds


def collect(use_csv=None, csv_has_result=True):
    """统一采集入口：use_csv 给定则加载真实数据，否则生成演示数据。"""
    if use_csv:
        historical, fixtures = load_from_csv(use_csv, csv_has_result)
    else:
        historical, fixtures = generate_synthetic()
        save_raw(historical, fixtures)
    return historical, fixtures
