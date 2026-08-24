"""为不支持API的新联赛生成合成赛程数据。

覆盖：荷甲、葡超、欧冠、韩职、日职
策略：基于真实球队列表 + 随机排程 + 日期分布
"""
import csv
import datetime
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from name_resolver import Resolver

# ========== 新联赛球队列表 ==========
LEAGUE_TEAMS = {
    "荷甲": [
        "Ajax", "PSV Eindhoven", "Feyenoord", "AZ Alkmaar", "FC Twente",
        "FC Utrecht", "Vitesse Arnhem", "Sparta Rotterdam", "Go Ahead Eagles",
        "NEC Nijmegen", "Fortuna Sittard", "PEC Zwolle", "Heracles Almelo",
        "FC Groningen", "SC Heerenveen", "Almere City FC", "RKC Waalwijk",
        "Volendam FC",
    ],
    "葡超": [
        "FC Porto", "SL Benfica", "Sporting CP", "SC Braga", "Vitória SC",
        "Rio Ave FC", "Moreirense FC", "Casa Pia AC", "Gil Vicente FC",
        "Famalicão", "Estoril Praia", "Boavista FC", "Chaves",
        "Arouca", "Estrela da Amadora", "Portimonense", "Vizela",
        "Santa Clara",
    ],
    "欧冠": [
        "Real Madrid CF", "FC Barcelona", "Manchester City FC", "Liverpool FC",
        "Bayern München", "Paris Saint-Germain FC", "Inter Milan", "AC Milan",
        "Juventus FC", "Borussia Dortmund", "Atlético de Madrid", "Napoli",
        "Arsenal FC", "Chelsea FC", "Benfica", "Porto",
        "RB Leipzig", "PSV Eindhoven", "Feyenoord", "Celtic FC",
    ],
    "韩职": [
        "Ulsan Hyundai", "Jeonbuk Hyundai Motors", "Pohang Steelers",
        "FC Seoul", "Jeju United", "Incheon United", "Gangwon FC",
        "Daegu FC", "Kyoto Sanga", "Gimcheon Sangmu",
        "Suwon Samsung Bluewings", "Busan IPark", "Seongnam FC",
        "Daejeon Hana Citizen",
    ],
    "日职": [
        "Yokohama F. Marinos", "Kawasaki Frontale", "Urawa Red Diamonds",
        "Vissel Kobe", "Cerezo Osaka", "Gamba Osaka", "Nagoya Grampus",
        "FC Tokyo", "Kashima Antlers", "Sanfrecce Hiroshima",
        "Shonan Bellmare", "Tokyo Verdy", "Avispa Fukuoka",
        "Sagan Tosu", "Kyoto Sanga",
    ],
}


def generate_fixtures(league: str, num_matches: int = 306, seed: int = 42) -> list:
    """生成单联赛赛程。"""
    teams = LEAGUE_TEAMS[league]
    rng = random.Random(seed)
    
    n = len(teams)
    # 生成对阵（双循环）
    matches = []
    for i in range(n):
        for j in range(i + 1, n):
            matches.append((teams[i], teams[j]))
            matches.append((teams[j], teams[i]))
    
    # 随机打乱
    rng.shuffle(matches)
    
    # 分配日期（2026-08-23 今晚起 ~ 2027-05-30）
    date_start = datetime.date(2026, 8, 23)
    date_end = datetime.date(2027, 5, 30)
    total_days = (date_end - date_start).days
    day_step = max(1, total_days // (len(matches) // 7 + 1))
    
    fixtures = []
    current_date = date_start
    match_idx = 0
    
    while match_idx < len(matches) and current_date <= date_end:
        # 每天最多放7场比赛（分散到周一到周日）
        matches_today = min(7, len(matches) - match_idx)
        for _ in range(matches_today):
            home, away = matches[match_idx]
            fixtures.append({
                "date": str(current_date),
                "league": league,
                "home": home,
                "away": away,
            })
            match_idx += 1
        current_date += datetime.timedelta(days=day_step)
    
    return fixtures


def main():
    """生成新联赛赛程并输出到 stdout（JSON格式）。"""
    all_fixtures = []
    
    for league in LEAGUE_TEAMS:
        fixtures = generate_fixtures(league)
        all_fixtures.extend(fixtures)
        print(f"[generate] {league}: {len(fixtures)} 场", file=sys.stderr)
    
    # 按日期排序
    all_fixtures.sort(key=lambda x: (x["date"], x["league"]))
    
    # 输出JSON
    print(json.dumps(all_fixtures, ensure_ascii=False, indent=2))
    print(f"\n总计: {len(all_fixtures)} 场新赛程", file=sys.stderr)


if __name__ == "__main__":
    main()
