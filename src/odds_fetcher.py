"""实时赔率抓取（The Odds API，免费层可用）。

本模块把「外部博彩市场水位」接入项目，免手填 CSV。
设计要点：
  - 使用 The Odds API v4（https://api.the-odds-api.com），免费层每月 500 次请求。
  - 拉取 soccer 五大联赛的 h2h（胜平负）/ spreads（让球）/ totals（大小球）市场，
    decimal 水位（含本金），ISO 时间。
  - 把 API 返回的英文队名 / sport key 映射成本项目的中文联赛名与队名。
  - 让球线符号约定与项目一致：主让正数（line = -api_home_point）。
  - 无 API key / 网络异常时抛出清晰异常，由调用方优雅回退到合成数据。

用法：
  from src.odds_fetcher import fetch_live
  fixtures, odds_map = fetch_live(api_key)          # api_key 也可经 env ODDS_API_KEY
  # 或离线测试映射：
  from src.odds_fetcher import to_internal
  fixtures, odds_map = to_internal(json.load(open("sample.json")))
"""
import json
import os
import urllib.request
import urllib.parse

BASE = "https://api.the-odds-api.com/v4"

# The Odds API 的 soccer sport key -> 本项目联赛中文名
# 注意：免费档不一定含欧冠权限；缺权限时 fetch_raw 会抛 HTTP 错，由调用方回退。
SPORT_MAP = {
    "soccer_epl": "英超",
    "soccer_spain_la_liga": "西甲",
    "soccer_germany_bundesliga": "德甲",
    "soccer_italy_serie_a": "意甲",
    "soccer_france_ligue_one": "法甲",
    # 新联赛（荷甲/葡超有真实模型；日职/韩职/欧冠仅显示真实盘口，不作预测）
    "soccer_netherlands_eredivisie": "荷甲",
    "soccer_portugal_primeira_liga": "葡超",
    "soccer_japan_j_league": "日职",
    "soccer_korea_kleague1": "韩职",
    "soccer_uefa_champs_league": "欧冠",
}

# 英文队名 -> 中文队名（覆盖五大联赛主力队；未收录者保留英文原名）
TEAM_MAP = {
    "Manchester United": "曼联", "Manchester City": "曼城", "Liverpool": "利物浦",
    "Chelsea": "切尔西", "Arsenal": "阿森纳", "Tottenham": "热刺",
    "Newcastle": "纽卡斯尔", "Aston Villa": "阿斯顿维拉", "West Ham": "西汉姆",
    "Everton": "埃弗顿", "Leicester": "莱斯特城", "Brighton": "布莱顿",
    "Wolves": "狼队", "Crystal Palace": "水晶宫", "Brentford": "布伦特福德",
    "Fulham": "富勒姆", "Bournemouth": "伯恩茅斯", "Nottingham Forest": "诺丁汉森林",
    "Leeds": "利兹联", "Southampton": "南安普顿",
    "Real Madrid": "皇家马德里", "Barcelona": "巴塞罗那", "Atletico Madrid": "马德里竞技",
    "Sevilla": "塞维利亚", "Villarreal": "比利亚雷亚尔", "Real Sociedad": "皇家社会",
    "Athletic Club": "毕尔巴鄂", "Valencia": "瓦伦西亚", "Betis": "贝蒂斯",
    "Osasuna": "奥萨苏纳", "Celta Vigo": "塞尔塔", "Girona": "赫罗纳",
    "Getafe": "赫塔菲", "Espanyol": "西班牙人", "Alaves": "阿拉维斯",
    "Mallorca": "马洛卡", "Cadiz": "加的斯", "Granada": "格拉纳达",
    "Rayo Vallecano": "巴列卡诺",
    "Bayern Munich": "拜仁慕尼黑", "Borussia Dortmund": "多特蒙德", "Bayer Leverkusen": "勒沃库森",
    "RB Leipzig": "莱比锡", "Frankfurt": "法兰克福", "Wolfsburg": "沃尔夫斯堡",
    "Monchengladbach": "门兴", "Stuttgart": "斯图加特", "Union Berlin": "柏林联合",
    "Freiburg": "弗赖堡", "Mainz": "美因茨", "Hoffenheim": "霍芬海姆",
    "Werder Bremen": "不莱梅", "Koln": "科隆", "Augsburg": "奥格斯堡",
    "Bochum": "波鸿", "Heidenheim": "海登海姆", "Darmstadt": "达姆施塔特",
    "Juventus": "尤文图斯", "Inter": "国际米兰", "AC Milan": "AC米兰",
    "Napoli": "那不勒斯", "Roma": "罗马", "Lazio": "拉齐奥",
    "Atalanta": "亚特兰大", "Fiorentina": "佛罗伦萨", "Bologna": "博洛尼亚",
    "Torino": "都灵", "Sassuolo": "萨索洛", "Udinese": "乌迪内斯",
    "Verona": "维罗纳", "Empoli": "恩波利", "Sampdoria": "桑普多利亚",
    "Genoa": "热那亚", "Salernitana": "萨勒尼塔纳", "Monza": "蒙扎",
    "Lecce": "莱切", "Cagliari": "卡利亚里",
    "Paris Saint-Germain": "巴黎圣日耳曼", "Marseille": "马赛", "Monaco": "摩纳哥",
    "Lyon": "里昂", "Lille": "里尔", "Rennes": "雷恩", "Nice": "尼斯",
    "Lens": "朗斯", "Strasbourg": "斯特拉斯堡", "Montpellier": "蒙彼利埃",
    "Nantes": "南特", "Brest": "布雷斯特", "Reims": "兰斯",
    "Toulouse": "图卢兹", "Lorient": "洛里昂", "Clermont": "克莱蒙",
    "Metz": "梅斯", "Auxerre": "欧塞尔",
}


def _map_team(name):
    return TEAM_MAP.get((name or "").strip(), (name or "").strip())


def fetch_raw(api_key, sport_keys=None, regions="eu", markets="h2h,spreads,totals"):
    """拉取原始 JSON 列表（每场一个元素）。

    无 api_key 抛 ValueError；网络/HTTP 异常原样上浮，由调用方处理回退。
    """
    if not api_key:
        raise ValueError("缺少 API key：实时赔率需 The Odds API key（设 env ODDS_API_KEY 或 --odds-api-key）。")
    if sport_keys is None:
        sport_keys = list(SPORT_MAP.keys())
    out = []
    for sk in sport_keys:
        qs = urllib.parse.urlencode({
            "apiKey": api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        })
        url = f"{BASE}/sports/{sk}/odds?{qs}"
        req = urllib.request.Request(url, headers={"User-Agent": "zucai-predictor/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # 401/429 等：附信息上浮
            raise RuntimeError(f"拉取 {sk} 失败 HTTP {e.code}: {e.reason}") from e
        except Exception as e:
            raise RuntimeError(f"拉取 {sk} 网络异常: {e}") from e
        if isinstance(data, list):
            out.extend(data)
    return out


def _pick_odds(bookmakers, market_key):
    """从 bookmakers 列表里挑第一个含该 market 的庄家，返回其 outcomes。"""
    for b in bookmakers or []:
        for m in b.get("markets", []):
            if m.get("key") == market_key:
                return m.get("outcomes")
    return None


def to_internal(raw):
    """原始 matches 列表 -> (fixtures, odds_map)。

    fixtures: list[{date, league, home, away}]（中文名）
    odds_map: dict[(league,home,away,date)] -> {
        h2h: {home_win, draw, away_win},                       # 胜平负 decimal 赔率
        handicap: {line, home_odds, away_odds},                # 让球盘（主让正数）
        totals: {line, over_odds, under_odds},                 # 大小球
    }
    仅收录本项目支持联赛；缺某市场的场次只在 odds_map 留存在的那部分。
    """
    fixtures, odds_map = [], {}
    for m in raw or []:
        sk = m.get("sport_key")
        league = SPORT_MAP.get(sk)
        if not league:
            continue
        home_api = m.get("home_team", "")
        away_api = m.get("away_team", "")
        # 预测与盘口匹配一律用英文原名（与历史训练同名，经 norm_team 对齐）；
        # 中文名仅作展示用（home_cn/away_cn）。
        home_en, away_en = home_api, away_api
        home_cn, away_cn = _map_team(home_api), _map_team(away_api)
        ct = m.get("commence_time", "")
        date = ct[:10] if ct else ""
        fixtures.append({"date": date, "league": league, "home": home_en,
                         "away": away_en, "home_cn": home_cn, "away_cn": away_cn})

        bms = m.get("bookmakers", [])
        h2h = _pick_odds(bms, "h2h")
        spreads = _pick_odds(bms, "spreads")
        totals = _pick_odds(bms, "totals")
        odds = {}
        # 胜平负（1X2）：h2h outcomes 形如
        #   [{name: home, price: x}, {name: Draw, price: y}, {name: away, price: z}]
        if h2h:
            hw = dw = aw = None
            for o in h2h:
                nm = (o.get("name") or "").strip()
                if nm == home_api:
                    hw = o.get("price")
                elif nm == away_api:
                    aw = o.get("price")
                elif nm.lower() == "draw":
                    dw = o.get("price")
            if hw is not None and dw is not None and aw is not None:
                odds["h2h"] = {
                    "home_win": float(hw),
                    "draw": float(dw),
                    "away_win": float(aw),
                }
        # 让球：spreads outcomes 形如
        #   [{name: home, point: -0.5, price: x}, {name: away, point: 0.5, price: y}]
        # API 主队 point 为负 = 主让；本项目用主让正数，故 line = -point。
        if spreads:
            hp = ap = ho = ao = None
            for o in spreads:
                if o.get("name") == home_api:
                    hp, ho = o.get("point"), o.get("price")
                else:
                    ap, ao = o.get("point"), o.get("price")
            if hp is not None and ho is not None and ao is not None:
                odds["handicap"] = {
                    "line": -float(hp),
                    "home_odds": float(ho),
                    "away_odds": float(ao),
                }
        # 大小球：totals outcomes 形如
        #   [{name: Over, point: 2.5, price: x}, {name: Under, point: 2.5, price: y}]
        if totals:
            op = oo = up = uo = None
            for o in totals:
                if o.get("name") == "Over":
                    op, oo = o.get("point"), o.get("price")
                else:
                    up, uo = o.get("point"), o.get("price")
            if op is not None and oo is not None and uo is not None:
                odds["totals"] = {
                    "line": float(op),
                    "over_odds": float(oo),
                    "under_odds": float(uo),
                }
        if odds:
            odds_map[(league, home_en, away_en, date)] = odds
    return fixtures, odds_map


def fetch_live(api_key=None, **kw):
    """一站式：抓实时 -> 映射为 (fixtures, odds_map)。

    api_key 缺省读 env ODDS_API_KEY。异常（无 key / 网络）直接上浮，由调用方决定回退。
    """
    if api_key is None:
        api_key = os.environ.get("ODDS_API_KEY")
    raw = fetch_raw(api_key, **kw)
    return to_internal(raw)
