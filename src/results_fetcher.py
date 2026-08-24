"""足球数据.org API 赛果抓取模块

免费API key，覆盖五大联赛+欧冠+日职/韩职等。
提供历史比分、今日赛果、赛事详情。

使用方式：
  from src.results_fetcher import fetch_completed_matches
  matches = fetch_completed_matches(days=3)  # 获取最近3天完赛场次
"""
import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone


API_BASE = "https://api.football-data.org/v4"

# 自动加载 .env 文件
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(_ROOT, ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)

TOKEN = os.environ.get("FOOTBALL_DATA_API_KEY", "")


# 联赛代码映射（项目用中文名 -> football-data.org 代码）
LEAGUE_MAP = {
    "英超": "PL",
    "西甲": "PD",
    "德甲": "BL1",
    "意甲": "SA",
    "法甲": "FL1",
    "欧冠": "CL",
    "欧联": "EC",
    "日职": "JL1",
    "韩职": "KL1",
    "荷甲": "DED",
    "葡超": "PPL",
    "巴甲": "BSA",
    "美职": "MLS",
    "瑞超": "SPL",
}


def _request(url):
    """发起GET请求，返回JSON"""
    headers = {"X-Auth-Token": TOKEN}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError("API Key无效或配额已耗尽")
        raise RuntimeError(f"HTTP {e.code}: {e.reason}")


def _parse_team(team_dict):
    """解析球队信息为中文/英文双格式"""
    short = team_dict.get("shortName", "")
    full = team_dict.get("name", "")
    tla = team_dict.get("tla", "")
    return {
        "short": short,
        "full": full,
        "tla": tla,
    }


def _parse_match(match):
    """解析单场比赛为标准格式"""
    home = _parse_team(match.get("homeTeam", {}))
    away = _parse_team(match.get("awayTeam", {}))

    score = match.get("score", {})
    ft = score.get("fullTime", {})

    return {
        "date": match.get("utcDate", "")[:10],
        "league": match.get("competition", {}).get("code", ""),
        "home": home["short"],
        "away": away["short"],
        "home_full": home["full"],
        "away_full": away["full"],
        "home_goals": ft.get("home"),
        "away_goals": ft.get("away"),
        "ht_home_goals": score.get("halfTime", {}).get("home"),
        "ht_away_goals": score.get("halfTime", {}).get("away"),
        "status": match.get("status", ""),
        "finished": match.get("status") == "FINISHED",
    }


def fetch_league_matches(league_code, days_back=3):
    """获取指定联赛最近N天的比赛（含已完赛）"""
    today = datetime.now(timezone.utc).date()
    from_date = (today - timedelta(days=days_back)).isoformat()
    to_date = today.isoformat()

    url = f"{API_BASE}/competitions/{league_code}/matches?dateFrom={from_date}&dateTo={to_date}"
    data = _request(url)
    return [_parse_match(m) for m in data.get("matches", [])]


def fetch_all_relevant_leagues(days_back=3):
    """获取所有适用联赛的完赛场次"""
    all_matches = []
    for proj_name, league_code in LEAGUE_MAP.items():
        try:
            matches = fetch_league_matches(league_code, days_back)
            for m in matches:
                m["league_cn"] = proj_name
            all_matches.extend(matches)
            print(f"  {proj_name}: {len(matches)}场")
        except Exception as e:
            print(f"  {proj_name}: 跳过 ({e})")
    return all_matches


def fetch_finished_matches(days_back=3):
    """仅返回已完赛场次（有比分）"""
    all_matches = fetch_all_relevant_leagues(days_back)
    return [m for m in all_matches if m["finished"] and m["home_goals"] is not None]


def save_to_actuals(matches, output_path=None):
    """保存为CSV格式，供 review_pipeline.py 使用"""
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "actuals.csv")
    import csv
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "league", "home", "away", "home_goals", "away_goals", "ht_home_goals", "ht_away_goals"])
        for m in matches:
            writer.writerow([
                m["date"],
                m.get("league_cn", m["league"]),
                m["home"],
                m["away"],
                m["home_goals"],
                m["away_goals"],
                m.get("ht_home_goals", ""),
                m.get("ht_away_goals", ""),
            ])
    return output_path


if __name__ == "__main__":
    print("=== 抓取最近3天完赛场次 ===")
    matches = fetch_finished_matches(days_back=3)
    print(f"\n共 {len(matches)} 场已完赛")
    if matches:
        print("\n前5场:")
        for m in matches[:5]:
            print(f"  {m['date']} {m['league_cn']}: {m['home']} {m['home_goals']}:{m['away_goals']} {m['away']}")
        # 保存到CSV
        path = save_to_actuals(matches)
        print(f"\n已保存到: {path}")
