"""临时验证 ODDS_API_KEY 真伪：读 .env，抓一个联赛盘口，成功即 key 有效。"""
import os
import sys

# 简陋读 .env（避免额外依赖）
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    for line in open(env_path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.odds_fetcher import fetch_raw

key = os.environ.get("ODDS_API_KEY")
if not key:
    print("FAIL: .env 无 ODDS_API_KEY")
    sys.exit(1)

try:
    # 只抓英超一个联赛，节省额度
    raw = fetch_raw(key, sport_keys=["soccer_epl"], regions="eu", markets="h2h")
    if isinstance(raw, list):
        print(f"OK: key 有效。英超抓到 {len(raw)} 场盘口。")
        if raw:
            m0 = raw[0]
            print(f"   样例：{m0.get('home_team')} vs {m0.get('away_team')} @ {m0.get('commence_time')}")
    else:
        print(f"OK: key 有效，返回结构={type(raw)}")
except Exception as e:
    msg = str(e)
    if "401" in msg or "403" in msg or "invalid" in msg.lower() or "Unauthorized" in msg:
        print(f"FAIL: key 无效或额度耗尽 -> {msg}")
    else:
        print(f"NETWORK/OTHER ERROR: {msg}")
