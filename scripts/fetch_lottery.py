"""抓取中国体彩网(竞彩)足球历史赛果真实比分 -> 项目 CSV 契约。

数据源（竞彩官方开奖，真实全场比分）：
  https://cp.zgzcw.com/dc/getKaijiangFootBall.action?startTime=YYYY-MM-DD&endTime=YYYY-MM-DD
  服务端渲染 HTML 表格，含 全场比分。支持 POST 翻页(pageForm.jumpPage)。

覆盖联赛（竞彩选取部分场次，非全联赛）：
  日职 / 韩职 / 欧冠 / 荷甲 / 葡超 / 英超 / 西甲 / 德甲 / 意甲 / 法甲 等

联赛名归一：
  韩K联->韩职, 日职联->日职, 欧冠杯->欧冠

队名：竞彩返中文队名，需归一为英文，与 odds API fixtures / 训练键一致。
  欧冠队=欧洲豪门，复用 web.team_translations 反查；日职/韩职用本文件映射表。

输出 CSV 列：date,league,home,away,home_goals,away_goals （英文队名）
"""
import argparse
import csv
import html as _html
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BASE = "https://cp.zgzcw.com/dc/getKaijiangFootBall.action"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# 联赛名归一
LEAGUE_NORM = {
    "韩K联": "韩职",
    "韩职": "韩职",
    "日职联": "日职",
    "日职": "日职",
    "欧冠杯": "欧冠",
    "欧冠": "欧冠",
    "荷甲": "荷甲",
    "葡超": "葡超",
    "英超": "英超",
    "西甲": "西甲",
    "德甲": "德甲",
    "意甲": "意甲",
    "法甲": "法甲",
}

# 日职 中文->英文（竞彩常用名）
J1_CN_EN = {
    "鹿岛鹿角": "Kashima Antlers",
    "浦和红钻": "Urawa Red Diamonds",
    "大阪钢巴": "Gamba Osaka",
    "川崎前锋": "Kawasaki Frontale",
    "横滨水手": "Yokohama F. Marinos",
    "广岛三箭": "Sanfrecce Hiroshima",
    "名古屋鲸八": "Nagoya Grampus",
    "FC东京": "FC Tokyo",
    "东京FC": "FC Tokyo",
    "神户胜利船": "Vissel Kobe",
    "鸟栖沙岩": "Sagan Tosu",
    "清水鼓动": "Shimizu S-Pulse",
    "柏太阳神": "Kashiwa Reysol",
    "湘南海洋": "Shonan Bellmare",
    "札幌冈萨多": "Hokkaido Consadole Sapporo",
    "福冈黄蜂": "Avispa Fukuoka",
    "京都不死鸟": "Kyoto Sanga",
    "磐田喜悦": "Jubilo Iwata",
    "大阪樱花": "Cerezo Osaka",
    "横滨FC": "Yokohama FC",
    "新泻天鹅": "Albirex Niigata",
    "东京绿茵": "Tokyo Verdy",
    "大坂钢巴": "Gamba Osaka",
    "湘南丽海": "Shonan Bellmare",
}

# 韩职 中文->英文
K1_CN_EN = {
    "全北现代": "Jeonbuk Hyundai Motors",
    "蔚山现代": "Ulsan Hyundai",
    "首尔FC": "FC Seoul",
    "水原三星": "Suwon Samsung Bluewings",
    "浦项制铁": "Pohang Steelers",
    "济州联": "Jeju United",
    "济州SK": "Jeju United",
    "大田市民": "Daejeon Hana Citizen",
    "江原FC": "Gangwon FC",
    "仁川联": "Incheon United",
    "大邱FC": "Daegu FC",
    "光州FC": "Gwangju FC",
    "金泉尚武": "Gimcheon Sangmu",
    "水原FC": "Suwon FC",
    "城南FC": "Seongnam FC",
    "安养FC": "FC Anyang",
    "釜山偶像": "Busan IPark",
}


def _cn_to_en(league_zh, name):
    """竞彩中文队名 -> 英文（与训练键一致）。返 None 表示未覆盖。"""
    if league_zh == "日职":
        return J1_CN_EN.get(name)
    if league_zh == "韩职":
        return K1_CN_EN.get(name)
    if league_zh == "欧冠":
        # 欧冠=欧洲豪门，复用 web.team_translations 反查
        try:
            from web.team_translations import ALL_TRANSLATIONS
            inv = {v: k for k, v in ALL_TRANSLATIONS.items()}
            return inv.get(name)
        except Exception:
            return None
    # 其余联赛（荷甲/葡超等）暂不用竞彩源
    return None


def _http_get(start, end, page):
    url = BASE + "?" + urllib.parse.urlencode({
        "startTime": start, "endTime": end, "jumpPage": str(page),
    })
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def _norm_date(dt, ref_start):
    # "08-23 02:45" + ref_start("2024-08-01") -> 推断年份（处理跨年赛季）
    m = re.search(r"(\d{2})-(\d{2})", dt or "")
    if not m:
        return ""
    mm, dd = m.group(1), m.group(2)
    sy = int(ref_start[:4])
    md = f"{mm}-{dd}"
    if md >= ref_start[5:]:
        return f"{sy}-{mm}-{dd}"
    return f"{sy + 1}-{mm}-{dd}"


def _parse_html(html, ref_start):
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 6:
            continue
        c = [_html.unescape(re.sub(r"<[^>]+>", " ", t)).strip() for t in tds]
        lg_raw, dt, h, score, a = c[1], c[2], c[3], c[4], c[5]
        if not lg_raw or lg_raw in ("编号", "赛事"):
            continue
        lg = LEAGUE_NORM.get(lg_raw)
        if not lg:
            continue
        m = re.match(r"^\s*([0-9]+)\s*:\s*([0-9]+)", score)
        if not m:
            continue  # 未出比分/无效
        out.append({
            "league": lg, "date": _norm_date(dt, ref_start),
            "home_cn": h, "away_cn": a,
            "home_goals": int(m.group(1)), "away_goals": int(m.group(2)),
        })
    return out


def fetch_range(start, end, leagues=None, max_pages=40):
    """翻页抓某日期范围全部赛果，返回 list[dict]（含中文队名）。"""
    rows = []
    for page in range(1, max_pages + 1):
        html = _http_get(start, end, page)
        page_rows = _parse_html(html, start)
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(page_rows) < 15:  # 末页
            break
        time.sleep(0.4)
    if leagues:
        rows = [r for r in rows if r["league"] in leagues]
    return rows


def fetch_and_map(start, end, leagues, out_path=None):
    """抓 + 中→英映射，返回 (rows_en, stats)。stats 含未映射队名。"""
    raw = fetch_range(start, end, leagues)
    rows_en = []
    unmapped = {}
    for r in raw:
        he = _cn_to_en(r["league"], r["home_cn"])
        ae = _cn_to_en(r["league"], r["away_cn"])
        if not he or not ae:
            unmapped.setdefault(r["league"], set()).add(r["home_cn"] if not he else r["away_cn"])
            continue
        rows_en.append({
            "date": r["date"],  # 已在 _parse_html 推断年份
            "league": r["league"],
            "home": he, "away": ae,
            "home_goals": r["home_goals"], "away_goals": r["away_goals"],
        })
    stats = {"raw": len(raw), "mapped": len(rows_en), "unmapped": {k: sorted(v) for k, v in unmapped.items()}}
    return rows_en, stats


def main():
    ap = argparse.ArgumentParser(description="抓取竞彩真实赛果 -> CSV")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--leagues", default="日职,韩职,欧冠",
                    help="逗号分隔，目标联赛")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "raw", "lottery_real.csv"))
    args = ap.parse_args()
    leagues = [x.strip() for x in args.leagues.split(",") if x.strip()]
    rows, stats = fetch_and_map(args.start, args.end, leagues)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "league", "home", "away", "home_goals", "away_goals"])
        for r in rows:
            w.writerow([r["date"], r["league"], r["home"], r["away"],
                        r["home_goals"], r["away_goals"]])
    print(f"[lottery] 原始 {stats['raw']} 场 -> 映射成功 {stats['mapped']} 场 -> {args.out}")
    if stats["unmapped"]:
        print("[lottery] 未映射队名(将丢弃):")
        for lg, names in stats["unmapped"].items():
            print(f"  {lg}: {names}")


if __name__ == "__main__":
    main()
