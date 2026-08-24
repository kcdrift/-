"""Elo 评级模块。

标准足球 Elo：每场赛果（胜/平/负）按期望胜率更新积分。
主场优势以固定加成体现。用于：
  1) 实力对比展示（主胜/客胜期望）
  2) 预测置信度的辅助信号（评分差越大越有把握）
"""
from config import ELO_DEFAULT, ELO_K, ELO_HOME_ADV
from src.utils import norm_team


class EloRating:
    def __init__(self, default=ELO_DEFAULT, k=ELO_K, home_adv=ELO_HOME_ADV):
        self.ratings = {}
        self.default = default
        self.k = k
        self.home_adv = home_adv

    def get(self, team):
        return self.ratings.get(norm_team(team), self.default)

    def update(self, home, away, home_goals, away_goals):
        home, away = norm_team(home), norm_team(away)
        rh = self.get(home) + self.home_adv
        ra = self.get(away)
        eh = 1.0 / (1.0 + 10 ** ((ra - rh) / 400.0))
        ea = 1.0 - eh
        if home_goals > away_goals:
            sh, sa = 1.0, 0.0
        elif home_goals < away_goals:
            sh, sa = 0.0, 1.0
        else:
            sh, sa = 0.5, 0.5
        self.ratings[home] = self.get(home) + self.k * (sh - eh)
        self.ratings[away] = self.get(away) + self.k * (sa - ea)

    def win_prob(self, home, away):
        """返回 (主胜期望, 客胜期望)。平局由泊松模型给出，这里仅作实力对比。"""
        home, away = norm_team(home), norm_team(away)
        rh = self.get(home) + self.home_adv
        ra = self.get(away)
        eh = 1.0 / (1.0 + 10 ** ((ra - rh) / 400.0))
        return eh, 1.0 - eh

    def diff(self, home, away):
        home, away = norm_team(home), norm_team(away)
        return (self.get(home) + self.home_adv) - self.get(away)

    def save(self, path):
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.ratings, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path):
        import json
        obj = cls()
        with open(path, "r", encoding="utf-8") as f:
            obj.ratings = json.load(f)
        return obj
