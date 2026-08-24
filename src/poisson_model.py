"""泊松得分模型（标准泊松回归 MLE，攻击/防守因子参数化）。

模型参数（每联赛独立拟合）：
  - 每队攻击力 attack_i、防守力 defense_i（基准队固定为 0 以保证可辨识）
  - 主场优势 gamma
  - 联赛基准强度 mu（固定为常数）

lambda 参数化（标准泊松回归）：
  lambda_home = exp(mu + attack_home - defense_away + gamma)
  lambda_away = exp(mu + attack_away - defense_home)

以闭合实力因子法作初值，用 Adam 梯度上升做最大似然估计（含轻微 L2 正则
防过拟合）。相比闭合解，MLE 对低比分与极端队更稳健，波胆分布更贴真实频率。
"""
import math
import json
from src.utils import norm_team


def _poisson_logpmf(lam, k):
    """泊松对数概率质量（log 空间，避免溢出）。"""
    if k < 0:
        return -1e18
    if lam <= 0:
        return 0.0 if k == 0 else -1e18
    return -lam + k * math.log(lam) - math.lgamma(k + 1)


class PoissonModel:
    def __init__(self):
        self.league = None
        self.league_avg_home = 1.0
        self.league_avg_away = 1.0
        self.mu = 0.0
        self.gamma = 0.0
        self.attack = {}
        self.defense = {}
        self._base = None          # 可辨识基准队
        self._shrinkage = 5.0

    def fit(self, matches, shrinkage=5.0, reg=1e-3, iters=120):
        """matches: list of dict{home, away, home_goals, away_goals, [date]}

        以闭合实力因子法作 warm start，Adam 梯度上升做泊松回归 MLE。
        """
        hg_sum = ag_sum = 0.0
        home_gf = {}   # team -> [goals scored at home, count]
        away_gf = {}   # team -> [goals scored away, count]
        home_gc = {}   # team -> [goals conceded at home, count]
        away_gc = {}   # team -> [goals conceded away, count]
        for m in matches:
            h, a = norm_team(m["home"]), norm_team(m["away"])
            hg, ag = m["home_goals"], m["away_goals"]
            hg_sum += hg
            ag_sum += ag
            home_gf.setdefault(h, [0.0, 0]); home_gf[h][0] += hg; home_gf[h][1] += 1
            away_gf.setdefault(a, [0.0, 0]); away_gf[a][0] += ag; away_gf[a][1] += 1
            home_gc.setdefault(h, [0.0, 0]); home_gc[h][0] += ag; home_gc[h][1] += 1
            away_gc.setdefault(a, [0.0, 0]); away_gc[a][0] += hg; away_gc[a][1] += 1

        n = len(matches) or 1
        self.league_avg_home = hg_sum / n
        self.league_avg_away = ag_sum / n
        avg = (self.league_avg_home + self.league_avg_away) / 2.0
        self.mu = math.log(avg) if avg > 0 else 0.0
        self.gamma = math.log(self.league_avg_home / self.league_avg_away) \
            if self.league_avg_away > 0 else 0.0

        teams = sorted(set(home_gf) | set(away_gf))
        self._base = teams[0] if teams else None

        # warm start：闭合实力因子作初值，加速收敛且稳
        for t in teams:
            hgf = home_gf.get(t, [0.0, 0])
            agf = away_gf.get(t, [0.0, 0])
            hgc = home_gc.get(t, [0.0, 0])
            agc = away_gc.get(t, [0.0, 0])
            hf = hgf[0] / hgf[1] if hgf[1] else self.league_avg_home
            hc = hgc[0] / hgc[1] if hgc[1] else self.league_avg_home
            self.attack[t] = math.log(max(hf, 1e-6) / max(self.league_avg_home, 1e-6))
            # defense 表示防守强度（高=好），与 lambda 中减号约定一致：
            # 失球越少 -> defense 越大 -> 对手 lambda 越小
            self.defense[t] = math.log(max(self.league_avg_home, 1e-6) / max(hc, 1e-6))
        if self._base is not None:
            self.attack[self._base] = 0.0
            self.defense[self._base] = 0.0

        self._optimize_params(matches, reg, iters)
        self._shrinkage = shrinkage
        return self

    def _lambda(self, home, away):
        home, away = norm_team(home), norm_team(away)
        ah = self.attack.get(home, 0.0)
        da = self.defense.get(away, 0.0)
        aa = self.attack.get(away, 0.0)
        dh = self.defense.get(home, 0.0)
        lh = math.exp(self.mu + ah - da + self.gamma)
        la = math.exp(self.mu + aa - dh)
        return max(0.05, lh), max(0.05, la)

    def lambdas(self, home, away):
        return self._lambda(home, away)

    def _optimize_params(self, matches, reg, iters):
        """Adam 梯度上升优化 attack/defense/gamma（标准泊松回归 MLE）。"""
        keys = []
        for t in self.attack:
            if t == self._base:
                continue
            keys.append(("a", t))
            keys.append(("d", t))
        keys.append(("g",))
        m = {k: 0.0 for k in keys}
        v = {k: 0.0 for k in keys}
        beta1, beta2, eps, lr = 0.9, 0.999, 1e-8, 0.1

        for step in range(iters):
            grad = {k: 0.0 for k in keys}
            for mm in matches:
                h, a = norm_team(mm["home"]), norm_team(mm["away"])
                i, j = int(mm["home_goals"]), int(mm["away_goals"])
                ah = self.attack.get(h, 0.0)
                da = self.defense.get(a, 0.0)
                aa = self.attack.get(a, 0.0)
                dh = self.defense.get(h, 0.0)
                lh = math.exp(self.mu + ah - da + self.gamma)
                la = math.exp(self.mu + aa - dh)
                # 泊松部分梯度
                gi = (-1.0 + i / lh) * lh
                gd_a = (1.0 - i / lh) * lh
                gj = (-1.0 + j / la) * la
                gd_d = (1.0 - j / la) * la
                gg = (-1.0 + i / lh) * lh
                if h != self._base:
                    grad[("a", h)] += gi
                    grad[("d", h)] += gd_d
                if a != self._base:
                    grad[("a", a)] += gj
                    grad[("d", a)] += gd_a
                grad[("g",)] += gg
            # L2 正则梯度 + Adam 更新
            for k in keys:
                if k[0] == "a":
                    reg_grad = reg * self.attack[k[1]]
                elif k[0] == "d":
                    reg_grad = reg * self.defense[k[1]]
                else:
                    reg_grad = reg * self.gamma
                g = grad[k] - reg_grad
                m[k] = beta1 * m[k] + (1 - beta1) * g
                v[k] = beta2 * v[k] + (1 - beta2) * g * g
                mhat = m[k] / (1 - beta1 ** (step + 1))
                vhat = v[k] / (1 - beta2 ** (step + 1))
                delta = lr * mhat / (math.sqrt(vhat) + eps)
                if k[0] == "a":
                    self.attack[k[1]] += delta
                elif k[0] == "d":
                    self.defense[k[1]] += delta
                else:
                    self.gamma += delta

    def save(self, path, league=None):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "league": league,
                "league_avg_home": self.league_avg_home,
                "league_avg_away": self.league_avg_away,
                "mu": self.mu,
                "gamma": self.gamma,
                "attack": self.attack,
                "defense": self.defense,
                "base": self._base,
                "shrinkage": self._shrinkage,
            }, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path):
        obj = cls()
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        obj.league = d.get("league")
        obj.league_avg_home = d["league_avg_home"]
        obj.league_avg_away = d["league_avg_away"]
        obj.mu = d.get("mu", 0.0)
        obj.gamma = d.get("gamma", 0.0)
        obj.attack = d["attack"]
        obj.defense = d["defense"]
        obj._base = d.get("base")
        obj._shrinkage = d.get("shrinkage", 5.0)
        return obj
