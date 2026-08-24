"""生成 5 新联赛合成赛程（今晚23号起）+ 合并进 upcoming_fixtures.csv。"""
import csv
import datetime
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
CSV_PATH = os.path.join(RAW, "upcoming_fixtures.csv")
OUT_JSON = os.path.join(RAW, "new_leagues_v2.json")

NEW5 = ["荷甲", "葡超", "欧冠", "韩职", "日职"]
REAL5 = ["英超", "西甲", "德甲", "意甲", "法甲"]

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


def generate_fixtures(league: str, seed: int = 42) -> list:
    teams = LEAGUE_TEAMS[league]
    rng = random.Random(seed)
    n = len(teams)
    matches = []
    for i in range(n):
        for j in range(i + 1, n):
            matches.append((teams[i], teams[j]))
            matches.append((teams[j], teams[i]))
    rng.shuffle(matches)
    date_start = datetime.date(2026, 8, 23)   # 今晚 23 号起
    date_end = datetime.date(2027, 5, 30)
    total_days = (date_end - date_start).days
    day_step = max(1, total_days // (len(matches) // 7 + 1))
    fixtures = []
    current_date = date_start
    match_idx = 0
    while match_idx < len(matches) and current_date <= date_end:
        matches_today = min(7, len(matches) - match_idx)
        for _ in range(matches_today):
            home, away = matches[match_idx]
            fixtures.append({"date": str(current_date), "league": league,
                             "home": home, "away": away})
            match_idx += 1
        current_date += datetime.timedelta(days=day_step)
    return fixtures


def main():
    all_new = []
    for lg in NEW5:
        fixtures = generate_fixtures(lg)
        all_new.extend(fixtures)
        print(f"[gen] {lg}: {len(fixtures)} 场", file=sys.stderr)
    all_new.sort(key=lambda x: (x["date"], x["league"]))
    os.makedirs(RAW, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_new, f, ensure_ascii=False, indent=2)
    print(f"[gen] 共写 {len(all_new)} 场新联赛赛程到 {OUT_JSON}", file=sys.stderr)

    # 合并
    existing = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    seen = {(r["date"], r["league"], r["home"], r["away"]) for r in existing}
    combined = list(existing)
    added = 0
    for r in all_new:
        k = (r["date"], r["league"], r["home"], r["away"])
        if k not in seen:
            combined.append({"date": r["date"], "league": r["league"],
                             "home": r["home"], "away": r["away"]})
            seen.add(k)
            added += 1
    combined.sort(key=lambda x: (x["date"], x["league"]))
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "league", "home", "away"])
        w.writeheader()
        w.writerows(combined)

    real5 = sum(1 for r in combined if r["league"] in REAL5)
    new5 = sum(1 for r in combined if r["league"] in NEW5)
    ds = sorted(set(r["date"] for r in combined))
    print(f"\n✅ 合并完成：总 {len(combined)} 场（真实5大联赛 {real5} + 新5联赛 {new5}，本次新增 {added}）")
    print(f"📅 日期范围：{ds[0]} .. {ds[-1]}（共 {len(ds)} 个比赛日）")
    first_dates = {}
    for r in combined:
        if r["league"] in NEW5 and r["league"] not in first_dates:
            first_dates[r["league"]] = r["date"]
    print(f"🏆 新5联赛每日首场（验证从今晚23号起）：")
    for lg in NEW5:
        print(f"  {lg}: 首场 {first_dates.get(lg, '无')}")


if __name__ == "__main__":
    main()
