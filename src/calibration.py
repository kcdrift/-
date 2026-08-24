"""概率校准层：Platt scaling。

模型（尤其合成数据）容易「过自信」：预测主胜 0.85，实际只发生 0.45。
Platt scaling 用 sigmoid 逐类（one-vs-rest）拟合校准映射，把预测概率
拉回接近真实发生频率，令下游胜平负概率、置信度更可信。

特征用 logit(p) = ln(p/(1-p))（标准 Platt 形式），比直接用 p 更稳定。

用法：
  cal = PlattCalibrator().fit(raw_preds, actuals)
  calibrated = cal.calibrate({"home_win": .., "draw": .., "away_win": ..})

注意：校准应在预留的评估集（或独立校准集）上拟合，避免训练集泄漏。
"""
import math

CLASSES = ("home_win", "draw", "away_win")
_ACT_MAP = {"home_win": "W", "draw": "D", "away_win": "L"}


def _sigmoid(z):
    # 防止 exp 溢出
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _logit(x):
    x = min(max(x, 1e-6), 1.0 - 1e-6)
    return math.log(x / (1.0 - x))


class PlattCalibrator:
    def __init__(self, iters=400, lr=0.3):
        self.params = {}     # cls -> (a, b)
        self.iters = iters
        self.lr = lr
        self.n = 0           # 校准集样本数，用于决定校准信任度

    def is_fitted(self):
        return bool(self.params)

    def fit(self, raw_preds, actuals):
        """raw_preds: list[dict]，每项为 {"home_win":..,"draw":..,"away_win":..}
           actuals:   list[str]，每项为 "W"/"D"/"L"
        """
        self.n = len(raw_preds)
        for cls in CLASSES:
            xs, ys = [], []
            for pred, act in zip(raw_preds, actuals):
                xs.append(pred[cls])
                ys.append(1.0 if _ACT_MAP[cls] == act else 0.0)
            self.params[cls] = self._fit_one(xs, ys)
        return self

    def _fit_one(self, xs, ys):
        a, b = 0.0, 0.0
        feats = [_logit(x) for x in xs]
        n = len(feats) or 1
        for _ in range(self.iters):
            ga = gb = 0.0
            for f, y in zip(feats, ys):
                p = _sigmoid(a * f + b)
                ga += (p - y) * f
                gb += (p - y)
            a -= self.lr * ga / n
            b -= self.lr * gb / n
        return a, b

    def calibrate(self, prob):
        out = {}
        for cls in CLASSES:
            a, b = self.params.get(cls, (1.0, 0.0))
            out[cls] = _sigmoid(a * _logit(prob[cls]) + b)
        s = sum(out.values())
        if s <= 0:
            return {c: prob[c] for c in CLASSES}
        cal = {c: out[c] / s for c in CLASSES}
        # 小样本校准集易过拟合（某类缺失被压到 0，如平局）。按样本数混合原始概率做保底：
        # 样本 >=50 完全信任校准（演示数据 657 场即此情形，LogLoss 成果不受影响）；
        # 样本极小则更多回退到原始蒙特卡洛概率，避免平局被压没。
        trust = min(1.0, self.n / 50.0)
        if trust >= 1.0:
            return cal
        final = {c: trust * cal[c] + (1 - trust) * prob[c] for c in CLASSES}
        s2 = sum(final.values()) or 1.0
        return {c: final[c] / s2 for c in CLASSES}

    def save(self, path):
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "params": {k: list(v) for k, v in self.params.items()},
                "n": self.n,
                "iters": self.iters,
                "lr": self.lr,
            }, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path):
        import json
        obj = cls()
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        obj.params = {k: tuple(v) for k, v in d.get("params", {}).items()}
        obj.n = d.get("n", 0)
        obj.iters = d.get("iters", 400)
        obj.lr = d.get("lr", 0.3)
        return obj
