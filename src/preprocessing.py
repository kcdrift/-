"""数据预处理与特征工程。

职责：
  - 清洗：去重、补全必填字段、类型校验、统一 result 标签
  - 特征工程：追加每队近期场均进球/失球、主客场胜率等轻量特征（供展示与可解释性）
  - 切分：按日期将历史分为 训练集 / 校准集 / 评估集 三段（时间顺序，避免未来信息泄漏）
    训练集用于拟合泊松+Elo；校准集用于拟合 Platt 校准器；评估集用于独立回测，
    三者互不重叠，保证校准效果评估不被乐观估计掩盖。
"""
from config import PROCESSED_DIR
import json
import os
from datetime import date


def _to_date(s):
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def clean(historical):
    """清洗历史比赛列表，返回清洗后列表 + 剔除记录。"""
    seen = set()
    cleaned, dropped = [], []
    for m in historical:
        home, away = m.get("home"), m.get("away")
        ds = m.get("date")
        hg, ag = m.get("home_goals"), m.get("away_goals")
        if not home or not away or home == away:
            dropped.append((m, "主客队缺失或相同"))
            continue
        if hg is None or ag is None:
            dropped.append((m, "比分缺失"))
            continue
        try:
            hg, ag = int(hg), int(ag)
        except (TypeError, ValueError):
            dropped.append((m, "比分非整数"))
            continue
        if _to_date(ds) is None:
            dropped.append((m, "日期格式错误"))
            continue
        key = (ds, home, away)
        if key in seen:
            dropped.append((m, "重复记录"))
            continue
        seen.add(key)
        result = "W" if hg > ag else ("L" if hg < ag else "D")
        cleaned.append({
            "date": ds, "league": m.get("league", "未知"),
            "home": home, "away": away,
            "home_goals": hg, "away_goals": ag, "result": result,
        })
    return cleaned, dropped


def add_team_features(matches):
    """为每场比赛追加主客队历史场均进球/失球（截至该场之前），用于可解释展示。"""
    # 按日期排序后滚动统计
    ordered = sorted(matches, key=lambda m: _to_date(m["date"]))
    stats = {}  # team -> {gf, ga, n}

    def rolling(team):
        s = stats.get(team)
        if not s or s["n"] == 0:
            return 0.0, 0.0
        return s["gf"] / s["n"], s["ga"] / s["n"]

    for m in ordered:
        hg, ag = m["home_goals"], m["away_goals"]
        m["home_avg_gf"], m["home_avg_ga"] = rolling(m["home"])
        m["away_avg_gf"], m["away_avg_ga"] = rolling(m["away"])
        # 更新统计（该场计入后续比赛的历史）
        for team, gf, ga in [(m["home"], hg, ag), (m["away"], ag, hg)]:
            s = stats.setdefault(team, {"gf": 0.0, "ga": 0.0, "n": 0})
            s["gf"] += gf
            s["ga"] += ga
            s["n"] += 1
    return ordered


def split_train_calib_eval(matches, train_ratio=0.7, calib_ratio=0.15):
    """按日期排序后尾部切分为三段，保证时间顺序：训练 < 校准 < 评估。

    训练集：最早期比赛，用于拟合泊松 + Elo
    校准集：次近期，用于拟合 Platt 校准器（压过自信）
    评估集：最近期，用于独立回测模型真实表现
    三段互不重叠，防止校准器在评估集上拟合造成的乐观估计。
    """
    ordered = sorted(matches, key=lambda m: _to_date(m["date"]))
    n = len(ordered)
    if n < 3:
        # 样本太少无法三分，整体作为训练（校准/评估留空）
        return ordered, [], []
    n_eval = max(1, int(round(n * (1.0 - train_ratio - calib_ratio))))
    n_calib = max(1, int(round(n * calib_ratio)))
    if n_eval + n_calib >= n:
        # 退化：保证训练集至少 1 条
        n_eval = max(1, n // 3)
        n_calib = max(1, n // 3)
    eval_set = ordered[-n_eval:]
    calib_set = ordered[-(n_eval + n_calib):-n_eval]
    train_set = ordered[:-(n_eval + n_calib)]
    return train_set, calib_set, eval_set


def preprocess(historical, train_ratio=0.7, calib_ratio=0.15):
    """完整预处理流水线。返回 (train_set, calib_set, eval_set, dropped)。"""
    cleaned, dropped = clean(historical)
    cleaned = add_team_features(cleaned)
    train_set, calib_set, eval_set = split_train_calib_eval(cleaned, train_ratio, calib_ratio)
    return train_set, calib_set, eval_set, dropped


def save_processed(train_set, calib_set, eval_set):
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    for name, data in (("train.json", train_set),
                       ("calib.json", calib_set),
                       ("eval.json", eval_set)):
        with open(os.path.join(PROCESSED_DIR, name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
