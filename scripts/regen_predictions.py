"""使用 football-data.org API 重新生成预测数据

流程：
1. 获取未来14天的赛程（五大联赛+欧冠）
2. 加载已训练的泊松模型
3. 生成预测并保存为 fetch_predictions.json
4. 同时获取历史赛果用于复盘
"""
import os
import sys
import json
import urllib.request
import csv
from datetime import datetime, timedelta, timezone

# 加载 .env
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(_ROOT, ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, _ROOT)

from src.poisson_model import PoissonModel
from src.prediction_engine import PredictionEngine
from src import elo as elo_mod
import config

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")
TOKEN = API_KEY

# 联赛代码映射
LEAGUE_MAP = {
    "PL": "英超",
    "PD": "西甲",
    "BL1": "德甲",
    "SA": "意甲",
    "FL1": "法甲",
    "CL": "欧冠",
}

def load_models():
    """加载已训练的泊松模型"""
    models = {}
    default_model = None
    
    # 加载默认模型（全量兜底）
    if os.path.exists(config.POISSON_FILE):
        default_model = PoissonModel().load(config.POISSON_FILE)
        print(f"  已加载默认模型 (league={default_model.league})")
    else:
        print("  警告: 未找到模型文件")
    
    return models, default_model

def load_elo():
    """加载Elo评级"""
    elo_obj = elo_mod.EloRating()
    if os.path.exists(config.ELO_FILE):
        with open(config.ELO_FILE, "r", encoding="utf-8") as f:
            ratings = json.load(f)
        for team, rating in ratings.items():
            elo_obj.ratings[team] = rating
        print(f"  已加载 {len(ratings)} 支球队的Elo评级")
    else:
        print("  警告: 未找到Elo评级文件")
    return elo_obj

def fetch_matches(days=14):
    """获取未来N天的比赛"""
    today = datetime.now(timezone.utc).date()
    from_date = today.isoformat()
    to_date = (today + timedelta(days=days)).isoformat()
    
    all_matches = []
    for code, name in LEAGUE_MAP.items():
        url = f"https://api.football-data.org/v4/competitions/{code}/matches?dateFrom={from_date}&dateTo={to_date}"
        req = urllib.request.Request(url, headers={"X-Auth-Token": TOKEN})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                matches = data.get("matches", [])
                for m in matches:
                    all_matches.append({
                        "date": m["utcDate"][:10],
                        "league": name,
                        "home": m["homeTeam"]["shortName"],
                        "away": m["awayTeam"]["shortName"],
                        "home_en": m["homeTeam"]["shortName"],
                        "away_en": m["awayTeam"]["shortName"],
                    })
                print(f"  {name}: {len(matches)}场")
        except Exception as e:
            print(f"  {name}: 错误 - {e}")
    
    return all_matches

def fetch_past_results(days=14):
    """获取最近N天的已完赛结果"""
    today = datetime.now(timezone.utc).date()
    from_date = (today - timedelta(days=days)).isoformat()
    to_date = today.isoformat()
    
    all_results = []
    for code, name in LEAGUE_MAP.items():
        url = f"https://api.football-data.org/v4/competitions/{code}/matches?dateFrom={from_date}&dateTo={to_date}"
        req = urllib.request.Request(url, headers={"X-Auth-Token": TOKEN})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                matches = data.get("matches", [])
                finished = [m for m in matches if m["status"] == "FINISHED"]
                for m in finished:
                    score = m.get("score", {})
                    ft = score.get("fullTime", {})
                    ht = score.get("halfTime", {})
                    all_results.append({
                        "date": m["utcDate"][:10],
                        "league": name,
                        "home": m["homeTeam"]["shortName"],
                        "away": m["awayTeam"]["shortName"],
                        "home_goals": ft.get("home", ""),
                        "away_goals": ft.get("away", ""),
                        "ht_home_goals": ht.get("home", ""),
                        "ht_away_goals": ht.get("away", ""),
                    })
                print(f"  {name}: {len(finished)}场完赛")
        except Exception as e:
            print(f"  {name}: 错误 - {e}")
    
    return all_results

def save_predictions(matches, models, default_model, elo_rating):
    """生成预测并保存"""
    # 加载历史比赛用于统计
    matches_for_counts = []
    if os.path.exists(config.REAL_HISTORICAL_CSV):
        with open(config.REAL_HISTORICAL_CSV, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                matches_for_counts.append(row)
    
    # 创建引擎
    engine = PredictionEngine(models, elo_rating, matches_for_counts, default_model)
    
    # 生成预测
    predictions = []
    for m in matches:
        try:
            pred = engine.predict(m["home"], m["away"], league=m["league"], n=5000, _use_calib=True)
            pred["date"] = m["date"]
            pred["league"] = m["league"]
            pred["home_en"] = m["home_en"]
            pred["away_en"] = m["away_en"]
            predictions.append(pred)
        except Exception as e:
            print(f"  预测失败 {m['home']} vs {m['away']}: {e}")
    
    # 保存
    pred_path = os.path.join(_ROOT, "data", "processed", "fetch_predictions.json")
    os.makedirs(os.path.dirname(pred_path), exist_ok=True)
    with open(pred_path, "w", encoding="utf-8") as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)
    
    return predictions

def save_actuals(results):
    """保存实际赛果到CSV"""
    output_path = os.path.join(_ROOT, "data", "raw", "actuals.csv")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "league", "home", "away", "home_goals", "away_goals", "ht_home_goals", "ht_away_goals"])
        for r in results:
            writer.writerow([
                r["date"], r["league"], r["home"], r["away"],
                r["home_goals"], r["away_goals"], r["ht_home_goals"], r["ht_away_goals"]
            ])
    return output_path

if __name__ == "__main__":
    print("=== 加载训练模型 ===")
    models, default_model = load_models()
    elo_rating = load_elo()
    
    print("\n=== 获取未来14天赛程 ===")
    matches = fetch_matches(days=14)
    print(f"\n共获取 {len(matches)} 场未来比赛")
    
    print("\n=== 获取最近14天赛果 ===")
    results = fetch_past_results(days=14)
    print(f"\n共获取 {len(results)} 场已完成比赛")
    
    print("\n=== 生成预测 ===")
    predictions = save_predictions(matches, models, default_model, elo_rating)
    print(f"\n共生成 {len(predictions)} 个预测")
    
    print("\n=== 保存赛果 ===")
    actuals_path = save_actuals(results)
    print(f"赛果已保存: {actuals_path}")
    
    # 检查匹配情况
    from collections import Counter
    pred_dates = Counter(p.get('date','') for p in predictions)
    actual_dates = Counter(r.get('date','') for r in results)
    common_dates = set(pred_dates.keys()) & set(actual_dates.keys())
    print(f"\n=== 匹配情况 ===")
    print(f"预测日期: {sorted(pred_dates.keys())}")
    print(f"实际日期: {sorted(actual_dates.keys())}")
    print(f"共同日期: {sorted(common_dates)}")
