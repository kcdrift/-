"""工具函数：泊松采样、熵、概率归一化、日期解析等。"""
import math
import random
import datetime
import re
import unicodedata


def poisson_sample(mu):
    """Knuth 算法：从 Poisson(mu) 采样一个整数（纯 Python，无需第三方库）。"""
    if mu <= 0:
        return 0
    L = math.exp(-mu)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1


def entropy(probs):
    """信息熵（以 e 为底）。输入概率列表，要求已归一化且非负。"""
    s = 0.0
    for p in probs:
        if p > 0:
            s -= p * math.log(p)
    return s


def normalize(probs):
    """将任意非负数列表归一化为概率分布。"""
    total = sum(probs)
    if total <= 0:
        n = len(probs)
        return [1.0 / n] * n
    return [p / total for p in probs]


def parse_date(s):
    """解析 'YYYY-MM-DD' 为 date 对象，失败返回 None。"""
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def top_scores(score_counts, n=3):
    """score_counts: dict[(gh, ga)] = count，返回前 n 个最常见比分（含概率）。"""
    total = sum(score_counts.values())
    if total <= 0:
        return []
    ranked = sorted(score_counts.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [{"home_goals": gh, "away_goals": ga,
             "prob": cnt / total} for (gh, ga), cnt in ranked]


def safe_log(x):
    return math.log(x) if x > 0 else 0.0


# 归一化时剔除的无意义词（俱乐部前缀/连接词），同队异写对齐靠佢哋
_TEAM_STRIP = {
    "fc", "cf", "club", "ud", "ca", "rcd", "cd", "sd", "ac", "as", "ad",
    "afc", "sc", "fk", "real", "and", "la", "de", "del",
}


def norm_team(name):
    """队名归一化：去重音、转小写、剔除 fc/cf/club/rcd 等前缀与 and/la/de 连接词，
    拼回无分隔字符串。令 'FC Barcelona' == 'Barcelona'、'Brighton & Hove Albion'
    == 'Brighton and Hove Albion'、'Club Atlético de Madrid' == 'Atletico Madrid'，
    训练（历史 CSV 英文名）与预测（盘口 API 英文名）异写可对齐到同一键。
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    words = [w for w in re.split(r"[^a-z0-9]+", s) if w and w not in _TEAM_STRIP]
    return "".join(words)
