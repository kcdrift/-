"""跨源队名解析器：将任意数据源（TheSportsDB / football-data.org 等）的队名，
对齐到本项目真实历史 CSV（openfootball）中的 canonical 队名。

为什么要这一步（龙爷红线）：真实队名若与合成同名队、或跨数据源命名不一致
（如 "Manchester City" vs "Manchester City FC"、"Bayern Munich" vs "FC Bayern München"），
会导致模型找不到该队的攻防强度 -> 概率失真 / KeyError。统一映射到 canonical 即可消除。

策略：
  1) 以 historical_real.csv 的队名为 canonical（按联赛）。
  2) 归一化（去变音、去 fc/cf/club 等后缀、去年份数字）后精确匹配。
  3) 否则用 (token Jaccard ∪ difflib) 最佳模糊匹配，阈值 0.6。
  4) 仍匹配不上 -> 返回 None 并标记 unmatched（调用方应跳过，避免未知队崩溃）。
  5) 可审计的别名映射 team_alias.json：手动覆盖优先，跨运行累积。
"""
import csv
import json
import os
import re
import sys
import unicodedata
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST_CSV = os.path.join(ROOT, "data", "raw", "historical_real.csv")
ALIAS_PATH = os.path.join(ROOT, "data", "raw", "team_alias.json")

# 归一化时剥离的无意义后缀 token（队名常见冗余）
_STOP = {"fc", "cf", "ac", "bc", "sc", "afc", "us", "as", "ca", "cd", "usc", "os",
         "rc", "club", "f", "cfc", "utc", "sv", "rv", "fk", "bk", "vk"}


def normalize(s):
    """队名 -> 归一化键：去变音、小写、去标点、剥后缀、去纯数字/尾数字 token。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))  # 去变音
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    toks = [t for t in s.split() if t]
    # 剥尾部冗余后缀
    while toks and toks[-1] in _STOP:
        toks.pop()
    # 剥首部冗余（如 "real" 保留原意，这里不剥；仅剥纯噪声）
    # 去掉纯数字 / 以数字结尾的 token（年份、编号：1846 / 05 / 63）
    toks = [t for t in toks if not re.fullmatch(r"\d+", t) and not re.search(r"\d$", t)]
    return " ".join(toks).strip()


class Resolver:
    def __init__(self, hist_csv=HIST_CSV, alias_path=ALIAS_PATH):
        self.league_teams = {}     # league -> set(canonical)
        self.norm_index = {}       # league -> {norm: canonical}
        self.alias_path = alias_path
        self.manual = self._load_alias()
        self.load(hist_csv)
        # 将手动覆盖并入索引（手动优先）
        for (lg, src), canon in self.manual.items():
            self.norm_index.setdefault(lg, {})[normalize(src)] = canon

    def load(self, path):
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                lg, h = r.get("league"), r.get("home")
                if lg and h:
                    self.league_teams.setdefault(lg, set()).add(h)
        for lg, ts in self.league_teams.items():
            for t in ts:
                self.norm_index.setdefault(lg, {})[normalize(t)] = t

    def _load_alias(self):
        if os.path.exists(self.alias_path):
            try:
                return json.load(open(self.alias_path, encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def resolve(self, name, league):
        if not name:
            return None, "empty"
        key = (league, name)
        if key in self.manual:
            return self.manual[key], "manual"
        idx = self.norm_index.get(league, {})
        n = normalize(name)
        if not n:
            return None, "empty"
        if n in idx:
            return idx[n], "exact"
        best, bestscore = None, 0.0
        for cn, canon in idx.items():
            a, b = set(n.split()), set(cn.split())
            jac = len(a & b) / len(a | b) if (a | b) else 0.0
            seq = SequenceMatcher(None, n, cn).ratio()
            score = max(jac, seq)
            if score > bestscore:
                bestscore, best = score, canon
        if best and bestscore >= 0.6:
            return best, f"fuzzy:{bestscore:.2f}"
        return None, "unmatched"

    def resolve_pairs(self, home, away, league):
        (rh, sh), (ra, sa) = self.resolve(home, league), self.resolve(away, league)
        return (rh or home, ra or away), (sh, sa)

    def add_manual(self, league, src, canon):
        """记录手动覆盖并写盘（审计 + 跨运行累积）。"""
        self.manual[(league, src)] = canon
        self.norm_index.setdefault(league, {})[normalize(src)] = canon
        os.makedirs(os.path.dirname(self.alias_path), exist_ok=True)
        with open(self.alias_path, "w", encoding="utf-8") as f:
            json.dump({f"{k[0]}|{k[1]}": v for k, v in self.manual.items()},
                      f, ensure_ascii=False, indent=2)


def _alias_load_flat(path):
    """读取 team_alias.json 的扁平格式（供外部复用）。"""
    if not os.path.exists(path):
        return {}
    try:
        d = json.load(open(path, encoding="utf-8"))
        return {(k.split("|", 1)[0], k.split("|", 1)[1]): v for k, v in d.items()}
    except Exception:
        return {}


if __name__ == "__main__":
    # 简单自检：解析一批常见异名，打印对齐结果
    r = Resolver()
    tests = [
        ("英超", "Manchester City"), ("英超", "Bournemouth"), ("英超", "Tottenham"),
        ("西甲", "Atlético Madrid"), ("西甲", "Villarreal"), ("西甲", "Barcelona"),
        ("德甲", "Bayern Munich"), ("德甲", "Borussia Monchengladbach"),
        ("意甲", "Juventus"), ("法甲", "Lille"), ("法甲", "Paris Saint-Germain"),
    ]
    for lg, nm in tests:
        canon, how = r.resolve(nm, lg)
        print(f"  {lg:>3} {nm:28s} -> {str(canon):30s} [{how}]")
