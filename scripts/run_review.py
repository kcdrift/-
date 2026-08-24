"""赛后复盘模块：自动抓取赛果、对齐预测、计算命中率

流程：
1. 从 football-data.org 获取最近N天的完赛场次
2. 加载历史预测数据
3. 用队名映射对齐预测和实际
4. 计算命中率指标（胜负方向、波胆、让球、大小球等）
5. 输出报告并反哺模型
"""
import os
import sys
import json
import csv
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import review
from scripts.team_mapping import normalize_fixture

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")
TOKEN = API_KEY

# 联赛代码映射
LEAGUE_MAP = {
    "PL": "英超",
    "PD": "西甲",
    "BL1": "德甲",
    "SA": "意甲",
    "FL1": "法甲",
}

def fetch_results(days=14):
    """获取最近N天的完赛场次"""
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
                for m in matches:
                    if m["status"] == "FINISHED":
                        score = m.get("score", {})
                        ft = score.get("fullTime", {})
                        ht = score.get("halfTime", {})
                        all_results.append({
                            "date": m["utcDate"][:10],
                            "league": name,
                            "home": m["homeTeam"]["shortName"],
                            "away": m["awayTeam"]["shortName"],
                            "home_goals": ft.get("home", 0),
                            "away_goals": ft.get("away", 0),
                            "ht_home_goals": ht.get("home", ""),
                            "ht_away_goals": ht.get("away", ""),
                        })
                print(f"  {name}: {len([r for r in all_results if r['league']==name])}场完赛")
        except Exception as e:
            print(f"  {name}: 错误 - {e}")
    
    return all_results

def load_predictions():
    """加载预测数据（优先用最新文件）"""
    processed_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "processed")
    
    # 找最新的预测文件
    import glob
    pred_files = glob.glob(os.path.join(processed_dir, "fetch_predictions*.json"))
    if not pred_files:
        return []
    
    pred_files.sort(key=os.path.getmtime, reverse=True)
    pred_file = pred_files[0]
    
    with open(pred_file, "r", encoding="utf-8") as f:
        preds = json.load(f)
    
    print(f"加载预测: {pred_file} ({len(preds)}场)")
    return preds

def run_review(days=14):
    """运行完整复盘流程"""
    print("=" * 60)
    print("赛后复盘分析")
    print("=" * 60)
    
    # 1. 获取赛果
    print("\n[1/4] 获取最近{}天完赛场次...".format(days))
    actuals = fetch_results(days=days)
    print(f"共获取 {len(actuals)} 场完赛")
    
    if not actuals:
        print("无完赛场次，复盘跳过")
        return None
    
    # 2. 加载预测
    print("\n[2/4] 加载预测数据...")
    preds = load_predictions()
    
    if not preds:
        print("无预测数据，复盘跳过")
        return None
    
    # 3. 映射队名并对齐
    print("\n[3/4] 对齐预测与实际赛果...")
    for a in actuals:
        h, aw = normalize_fixture(a["home"], a["away"])
        a["home"], a["away"] = h, aw
    
    pairs, unmatched_preds, unmatched_actuals = review.align(preds, actuals)
    print(f"匹配成功: {len(pairs)}场")
    print(f"未匹配预测: {len(unmatched_preds)}场")
    print(f"未匹配实际: {len(unmatched_actuals)}场")
    
    if not pairs:
        print("无匹配比赛，复盘跳过")
        return None
    
    # 4. 计算指标并生成报告
    print("\n[4/4] 计算命中率指标...")
    metrics = review.compute_metrics(pairs)
    report = review.build_report(pairs, metrics)
    
    # 保存报告
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "processed")
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "review_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # 输出摘要
    s = report["summary"]
    print("\n" + "=" * 60)
    print("复盘结果摘要")
    print("=" * 60)
    print(f"匹配场次: {s['场次']}场")
    print(f"胜负方向准确率: {s['胜负方向准确率']*100:.1f}%")
    print(f"比分精确命中率: {s['比分精确命中率']*100:.1f}%")
    print(f"最可能比分命中率: {s['最可能比分命中率']*100:.1f}%")
    print(f"让球盘命中率: {s['让球盘命中率']*100:.1f}%")
    print(f"大小球命中率: {s['大小球命中率']*100:.1f}%")
    print(f"Brier分数: {s['Brier分数']:.4f}")
    print(f"LogLoss: {s['LogLoss']:.4f}")
    print(f"\n报告已保存: {report_path}")
    
    return report

if __name__ == "__main__":
    run_review(days=14)
