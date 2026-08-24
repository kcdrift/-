"""合法数据源整合模块（简化版）

数据源：
1. TheSportsDB（免费，无key，每联赛1场补充）
2. openfootball GitHub（开源历史数据）
3. 合成数据兜底（当网络不可用时）

策略：优先真实数据，降级到合成数据
"""
import json
import csv
import os
import sys
import time
import random

# 新联赛球队列表（用于合成数据）
LEAGUE_TEAMS = {
    "荷甲": ["Ajax", "PSV Eindhoven", "Feyenoord", "AZ Alkmaar", "FC Twente",
              "FC Utrecht", "Vitesse Arnhem", "Sparta Rotterdam", "Go Ahead Eagles",
              "NEC Nijmegen", "Fortuna Sittard", "PEC Zwolle", "Heracles Almelo",
              "FC Groningen", "SC Heerenveen", "Almere City FC", "RKC Waalwijk",
              "Volendam FC"],
    "葡超": ["FC Porto", "SL Benfica", "Sporting CP", "SC Braga", "Vitória SC",
             "Rio Ave FC", "Moreirense FC", "Casa Pia AC", "Gil Vicente FC",
             "Famalicão", "Estoril Praia", "Boavista FC", "Chaves",
             "Arouca", "Estrela da Amadora", "Portimonense", "Vizela",
             "Santa Clara"],
    "欧冠": ["Real Madrid CF", "FC Barcelona", "Manchester City FC", "Liverpool FC",
             "Bayern München", "Paris Saint-Germain FC", "Inter Milan", "AC Milan",
             "Juventus FC", "Borussia Dortmund", "Atlético de Madrid", "Napoli",
             "Arsenal FC", "Chelsea FC", "Benfica", "Porto",
             "RB Leipzig", "PSV Eindhoven", "Feyenoord", "Celtic FC"],
    "韩职": ["Ulsan Hyundai", "Jeonbuk Hyundai Motors", "Pohang Steelers",
              "FC Seoul", "Jeju United", "Incheon United", "Gangwon FC",
              "Daegu FC", "Kyoto Sanga", "Gimcheon Sangmu",
              "Suwon Samsung Bluewings", "Busan IPark", "Seongnam FC",
              "Daejeon Hana Citizen"],
    "日职": ["Yokohama F. Marinos", "Kawasaki Frontale", "Urawa Red Diamonds",
              "Vissel Kobe", "Cerezo Osaka", "Gamba Osaka", "Nagoya Grampus",
              "FC Tokyo", "Kashima Antlers", "Sanfrecce Hiroshima",
              "Shonan Bellmare", "Tokyo Verdy", "Avispa Fukuoka",
              "Sagan Tosu", "Kyoto Sanga"],
}


def generate_synthetic_fixtures():
    """生成合成赛程数据（当真实数据不可用时兜底）。"""
    rng = random.Random(42)
    fixtures = []
    date_start = __import__('datetime').date(2026, 8, 25)

    for league, teams in LEAGUE_TEAMS.items():
        n_teams = len(teams)
        # 双循环生成对阵
        matches = []
        for i in range(n_teams):
            for j in range(i + 1, n_teams):
                matches.append((teams[i], teams[j]))
                matches.append((teams[j], teams[i]))

        # 随机打乱并分配日期
        rng.shuffle(matches)
        dates = []
        for w in range(40):  # 40周
            base = date_start + __import__('datetime').timedelta(weeks=w)
            for d in [2, 3, 4]:  # 周二/三/四
                dates.append(base + __import__('datetime').timedelta(days=d))

        for idx, (home, away) in enumerate(matches[:len(dates)]):
            fixtures.append({
                "date": str(dates[idx]),
                "league": league,
                "home": home,
                "away": away,
                "source": "synthetic"
            })

    return fixtures


def try_fetch_thesportsdb():
    """尝试从 TheSportsDB 抓取数据。"""
    try:
        import urllib.request
        leagues = {
            "英超": "4328", "西甲": "4335", "德甲": "4331",
            "意甲": "4332", "法甲": "4334", "荷甲": "4343",
            "葡超": "4344", "欧冠": "4480", "韩职": "4491", "日职": "4492"
        }

        fixtures = []
        for lg, lid in leagues.items():
            url = f"https://www.thesportsdb.com/api/v1/json/3/eventsnextleague.php?id={lid}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode('utf-8'))
            events = data.get("events", [])
            for e in events:
                date = e.get("dateEvent")
                home = e.get("strHomeTeam")
                away = e.get("strAwayTeam")
                if date and home and away:
                    fixtures.append({
                        "date": date[:10],
                        "league": lg,
                        "home": home,
                        "away": away,
                        "source": "thesportsdb"
                    })
            print(f"  {lg}: {len([f for f in fixtures if f['league']==lg])} 场")

        return fixtures if fixtures else None
    except Exception as e:
        print(f"[thesportsdb] 抓取失败: {e}")
        return None


def main():
    """主函数：抓取数据并合并。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(root, "data", "raw", "upcoming_fixtures_legal.csv")

    print("[fetch] 尝试真实数据源...")
    real_fixtures = try_fetch_thesportsdb()

    if real_fixtures:
        print(f"[fetch] 真实数据: {len(real_fixtures)} 场")
    else:
        print("[fetch] 使用合成数据兜底...")
        real_fixtures = generate_synthetic_fixtures()
        print(f"[fetch] 合成数据: {len(real_fixtures)} 场")

    # 合并现有数据
    existing = []
    existing_path = os.path.join(root, "data", "raw", "upcoming_fixtures.csv")
    if os.path.exists(existing_path):
        with open(existing_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            existing = list(reader)

    # 合并去重
    seen = {(r['date'], r['home'], r['away']) for r in existing}
    for f in real_fixtures:
        key = (f['date'], f['home'], f['away'])
        if key not in seen:
            seen.add(key)
            existing.append(f)

    # 排序
    existing.sort(key=lambda x: (x['date'], x['league']))

    # 保存
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'league', 'home', 'away', 'source'])
        writer.writeheader()
        writer.writerows(existing)

    print(f"\n[save] 已保存到 {out_path}")

    # 统计
    leagues = {}
    sources = {}
    for r in existing:
        lg = r.get('league', '')
        src = r.get('source', 'unknown')
        leagues[lg] = leagues.get(lg, 0) + 1
        sources[src] = sources.get(src, 0) + 1

    print(f"\n总计: {len(existing)} 场")
    print("联赛分布:")
    for lg, cnt in sorted(leagues.items(), key=lambda x: -x[1]):
        print(f"  {lg}: {cnt}")
    print("\n数据源:")
    for src, cnt in sources.items():
        print(f"  {src}: {cnt}")


if __name__ == "__main__":
    main()
