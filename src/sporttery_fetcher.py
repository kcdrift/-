"""中国体彩网（sporttery.cn）竞彩赔率爬虫。

完全免费、无需 API key、无请求限额。
数据源：https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry

返回格式与 The Odds API 兼容：
  fixtures: list[{date, league, home, away, home_cn, away_cn}]
  odds_map: dict[(league, home, away, date)] -> {
      h2h: {home_win, draw, away_win},
      handicap: {line, home_odds, away_odds},
      totals: {line, over_odds, under_odds},
  }

注意：体彩只覆盖竞彩开售的场次（通常五大联赛 + 部分欧冠/日职/韩职等），
非每日都有大量比赛。
"""
import json
import urllib.request


URL = "https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry"

# 体彩联赛简称 -> 项目联赛中文名
LEAGUE_MAP = {
    "英超": "英超",
    "西甲": "西甲",
    "德甲": "德甲",
    "意甲": "意甲",
    "法甲": "法甲",
    "荷甲": "荷甲",
    "葡超": "葡超",
    "日职": "日职",
    "韩职": "韩职",
    "欧冠": "欧冠",
    "欧联": "欧联杯",
    "美职": "美职",
    "巴甲": "巴甲",
    "瑞超": "瑞超",
    "芬超": "芬超",
    "英冠": "英冠",
    "德国杯": "德国杯",
}


def fetch_raw():
    """拉取原始 JSON。无 key、无认证。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.sporttery.cn/",
    }
    req = urllib.request.Request(URL, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_matches(raw):
    """解析为 (fixtures, odds_map)。"""
    value = raw.get("value", {})
    match_groups = value.get("matchInfoList", [])

    fixtures, odds_map = [], {}

    for group in match_groups:
        sub_matches = group.get("subMatchList", [])
        for m in sub_matches:
            league_cn = m.get("leagueAbbName", "")
            # 只保留支持的联赛
            if league_cn not in LEAGUE_MAP:
                continue
            league = LEAGUE_MAP[league_cn]

            home_cn = m.get("homeTeamAbbName", "")
            away_cn = m.get("awayTeamAbbName", "")
            date = m.get("matchDate", "")
            time = m.get("matchTime", "")
            match_num = m.get("matchNumStr", "")

            # 用中文队名做 key（与内部预测引擎对齐）
            key = (league, home_cn, away_cn, date)

            # had: 胜平负 (h/d/a)
            had = m.get("had") or {}
            h_odds = had.get("h")
            d_odds = had.get("d")
            a_odds = had.get("a")

            # hhad: 让球胜平负 (h/d/a + goalLine)
            hhad = m.get("hhad") or {}
            hhad_line = hhad.get("goalLineValue", "")
            hhad_h = hhad.get("h")
            hhad_d = hhad.get("d")
            hhad_a = hhad.get("a")

            # ttg: 总进球 (s0-s7)
            ttg = m.get("ttg") or {}
            s0 = ttg.get("s0")
            s1 = ttg.get("s1")
            s2 = ttg.get("s2")
            s3 = ttg.get("s3")
            s4 = ttg.get("s4")
            s5 = ttg.get("s5")

            odds = {}

            # 胜平负
            if h_odds and d_odds and a_odds:
                try:
                    odds["h2h"] = {
                        "home_win": float(h_odds),
                        "draw": float(d_odds),
                        "away_win": float(a_odds),
                    }
                except (ValueError, TypeError):
                    pass

            # 让球盘（从 hhad 推导）
            if hhad_h and hhad_d and hhad_a and hhad_line:
                try:
                    line_val = float(hhad_line.replace("+", ""))
                    odds["handicap"] = {
                        "line": line_val,
                        "home_odds": float(hhad_h),
                        "away_odds": float(hhad_a),
                    }
                except (ValueError, TypeError):
                    pass

            # 大小球（从 ttg 推导 2.5 线）
            if s1 and s2:
                try:
                    # 总进球 >=3 = 大2.5，<=2 = 小2.5
                    # 近似：over = s1+s2+s3+... / total, under = s0+s1 / total
                    # 简化：直接用 s1(1球) 和 s2(2球) 推算
                    odds["totals"] = {
                        "line": 2.5,
                        "over_odds": float(s2),  # 近似
                        "under_odds": float(s1),  # 近似
                    }
                except (ValueError, TypeError):
                    pass

            fixtures.append({
                "date": date,
                "time": time,
                "league": league,
                "home": home_cn,
                "away": away_cn,
                "match_num": match_num,
            })

            if odds:
                odds_map[key] = odds

    return fixtures, odds_map


def fetch_live():
    """一站式：抓体彩 -> 返回 (fixtures, odds_map)。"""
    raw = fetch_raw()
    if not raw.get("success") or raw.get("errorCode") != "0":
        raise RuntimeError(f"体彩 API 错误: {raw.get('errorMessage', 'unknown')}")
    return parse_matches(raw)


if __name__ == "__main__":
    fixtures, odds_map = fetch_live()
    print(f"✓ 抓到 {len(fixtures)} 场，{len(odds_map)} 场有盘口")
    leagues = set(f["league"] for f in fixtures)
    print(f"  联赛: {sorted(leagues)}")
    for k, v in list(odds_map.items())[:3]:
        print(f"  {k}: {v}")
