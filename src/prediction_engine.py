"""预测引擎：整合 Elo + 泊松 + 蒙特卡洛，输出胜平负概率、最可能比分、置信度。

对单场：
  1) 由泊松模型得到 lambda_home / lambda_away
  2) 蒙特卡洛模拟 N 次，统计胜/平/负频率与比分分布
  3) 结合 Elo 期望胜率做轻度校准（防止极端 lambda）
  4) 计算置信度（概率集中度 + 信息熵 + 数据量）
"""
import math
import random
from config import MC_SIMULATIONS, CONF_HIGH, CONF_MEDIUM, HANDICAPS, TOTALS_LINES
from src.utils import poisson_sample, entropy, normalize, top_scores, norm_team


class PredictionEngine:
    def __init__(self, models, elo_rating, matches_for_counts=None, default_model=None, calibrator=None):
        # models: dict[league] -> PoissonModel；default_model: 全量兜底模型
        self.models = models or {}
        self.default_model = default_model
        self.elo = elo_rating
        self.calibrator = calibrator
        self._calib_on = calibrator is not None and getattr(calibrator, "is_fitted", lambda: False)()
        # 统计每队训练样本数，用于数据置信度
        self.team_counts = {}
        if matches_for_counts:
            for m in matches_for_counts:
                self.team_counts[norm_team(m["home"])] = self.team_counts.get(norm_team(m["home"]), 0) + 1
                self.team_counts[norm_team(m["away"])] = self.team_counts.get(norm_team(m["away"]), 0) + 1

    def predict(self, home, away, league=None, n=MC_SIMULATIONS, seed=None, _use_calib=True, odds=None):
        if seed is not None:
            random.seed(seed)
        # 仅用按联赛独立训练的模型；未训练的联赛（如日职/韩职/欧冠）fallback 到全量兜底模型。
        # 这样新联赛至少能有合理概率，而不是报错或出假数据。
        pm = self.models.get(league) or self.default_model
        if pm is None:
            raise ValueError(f"无可用模型：league={league}")
        lam_h, lam_a = pm.lambdas(home, away)

        win = draw = loss = 0
        scores = {}
        # 让球盘计数：handi[h] = [赢盘, 走盘, 输盘]
        handi = {h: [0, 0, 0] for h in HANDICAPS}
        # 大小球计数：tot[t] = [大, 小]
        tot = {t: [0, 0] for t in TOTALS_LINES}
        # 单双：总进球奇偶计数
        even = odd = 0
        # 半全场：拆分上下半场各采一次（泊松无限可分，全场分布不变）
        htft = {}
        # 净胜球分布 / 总进球分布：供任意盘口线实时算模型概率（不限于预设档位）
        margins = {}
        tot_dist = {}
        for _ in range(n):
            gh1 = poisson_sample(lam_h / 2.0)
            gh2 = poisson_sample(lam_h / 2.0)
            ga1 = poisson_sample(lam_a / 2.0)
            ga2 = poisson_sample(lam_a / 2.0)
            gh = gh1 + gh2
            ga = ga1 + ga2
            scores[(gh, ga)] = scores.get((gh, ga), 0) + 1
            # 半全场：上半场结果 × 全场结果（近似，不参与 DC 修正）
            ht = "H" if gh1 > ga1 else ("A" if gh1 < ga1 else "D")
            ft = "H" if gh > ga else ("A" if gh < ga else "D")
            htft[ht + ft] = htft.get(ht + ft, 0) + 1

        # 比分联合分布（蒙特卡洛频率）
        scores_probs = {k: v / n for k, v in scores.items()}

        # 从分布统计胜/平/负及盘口（概率形式，和=1，口径一致）
        win = draw = loss = 0.0
        for (gh, ga), p in scores_probs.items():
            if gh > ga:
                win += p
            elif gh < ga:
                loss += p
            else:
                draw += p
            margin = gh - ga
            for h in HANDICAPS:
                if margin > h:
                    handi[h][0] += p
                elif margin == h:
                    handi[h][1] += p
                else:
                    handi[h][2] += p
            total = gh + ga
            for t in TOTALS_LINES:
                if total > t:
                    tot[t][0] += p
                else:
                    tot[t][1] += p
            margins[margin] = margins.get(margin, 0) + p
            tot_dist[total] = tot_dist.get(total, 0) + p
            if total % 2 == 0:
                even += p
            else:
                odd += p

        p_win = win
        p_draw = draw
        p_loss = loss

        # Elo 期望：用主胜期望与客胜期望做轻度正则
        elo_hw, elo_aw = self.elo.win_prob(home, away)
        # 蒙特卡洛三态已含真实平局频率；Elo 仅温和调整 win/loss（权重 0.2），
        # draw 直接采用蒙特卡洛频率，避免强队差距大时把平局截断为 0。
        ELO_W = 0.2
        blend_win = (1 - ELO_W) * p_win + ELO_W * elo_hw
        blend_loss = (1 - ELO_W) * p_loss + ELO_W * elo_aw
        # 重新归一化（draw 保住蒙特卡洛份额，只要 p_draw>0 则结果>0）
        s = blend_win + p_draw + blend_loss
        pw, pd, pl = blend_win / s, p_draw / s, blend_loss / s

        # 概率校准（Platt scaling）：把过自信预测拉回真实频率
        if _use_calib and self._calib_on:
            cal = self.calibrator.calibrate({"home_win": pw, "draw": pd, "away_win": pl})
            pw, pd, pl = cal["home_win"], cal["draw"], cal["away_win"]
        # 下限保护：避免校准把某个结果压到 0（如强队平局失真成 0%），重新归一化
        FLOOR = 0.01
        pw, pd, pl = max(pw, FLOOR), max(pd, FLOOR), max(pl, FLOOR)
        s = pw + pd + pl
        pw, pd, pl = pw / s, pd / s, pl / s

        top = top_scores(scores_probs, 3)
        p_even = even
        p_odd = odd
        htft_probs = {k: round(v / n, 4) for k, v in htft.items()}

        confidence = self._confidence(pw, pd, pl, home, away)

        # 让球盘：主队让 h 球，赢盘=净胜>h，走盘=净胜==h，输盘=净胜<h
        handicap = {}
        for h in HANDICAPS:
            w, d, l = handi[h]
            handicap[str(h)] = {"win": round(w, 4),
                                "draw": round(d, 4),
                                "lose": round(l, 4)}
        # 大小球：总进球 > t 为大，否则为小
        totals = {}
        for t in TOTALS_LINES:
            o, u = tot[t]
            totals[str(t)] = {"over": round(o, 4),
                              "under": round(u, 4)}

        return {
            "home": home,
            "away": away,
            "lambda_home": round(lam_h, 3),
            "lambda_away": round(lam_a, 3),
            "prob": {"home_win": round(pw, 4),
                     "draw": round(pd, 4),
                     "away_win": round(pl, 4)},
            "most_likely_scores": top,
            "correct_scores": top_scores(scores_probs, 6),
            "odd_even": {"odd": round(p_odd, 4), "even": round(p_even, 4)},
            "htft": htft_probs,
            "margin_dist": margins,
            "total_dist": tot_dist,
            "handicap": handicap,
            "totals": totals,
            "elo_diff": round(self.elo.diff(home, away), 1),
            "elo_home_win_exp": round(elo_hw, 4),
            "confidence": confidence,
            "odds": odds if odds else None,
            "value": self._value_detection(pw, pd, pl, handicap, totals, odds) if odds else None,
        }

    def _value_detection(self, pw, pd, pl, handicap, totals, odds):
        """盘口价值检测（+EV）：对比模型概率与赔率，剥离庄家 margin。

        无赔率时返回 None；有赔率则对 1X2 / 让球 / 大小球分别检测，标记 +EV 选项。
        """
        from src.value_betting import detect_1x2, detect_handicap, detect_totals
        out = {}
        h2h = odds.get("h2h")
        if h2h:
            out["1x2"] = detect_1x2(
                {"home_win": pw, "draw": pd, "away_win": pl}, h2h)
        hc_odds = odds.get("handicap")
        if hc_odds and handicap:
            line = hc_odds.get("line")
            hc = None
            for k in handicap:
                if abs(float(k) - float(line)) < 1e-6:
                    hc = handicap[k]
                    break
            if hc is not None:
                out["handicap"] = {str(line): detect_handicap(
                    {"home_win": hc["win"], "away_win": hc["lose"]},
                    line, hc_odds["home_odds"], hc_odds["away_odds"])}
        tt_odds = odds.get("totals")
        if tt_odds and totals:
            line = tt_odds.get("line")
            tt = None
            for k in totals:
                if abs(float(k) - float(line)) < 1e-6:
                    tt = totals[k]
                    break
            if tt is not None:
                out["totals"] = {str(line): detect_totals(
                    {"over": tt["over"], "under": tt["under"]},
                    line, tt_odds["over_odds"], tt_odds["under_odds"])}
        return out

    def _confidence(self, pw, pd, pl, home, away):
        """置信度综合：概率集中度(最大概率) + 熵 + 数据量。返回 (等级, 分数)。"""
        probs = [pw, pd, pl]
        max_p = max(probs)
        ent = entropy(probs)
        norm_ent = ent / math.log(3)  # 0(确定)~1(均匀)
        # 概率集中度得分
        concentration = max_p * (1.0 - 0.5 * norm_ent)
        # 数据量得分：样本越多越可信（封顶 30 场）
        ch = self.team_counts.get(norm_team(home), 0)
        ca = self.team_counts.get(norm_team(away), 0)
        data_conf = min(1.0, min(ch, ca) / 30.0)
        # 综合得分：集中度为主，数据量给下限保护
        score = concentration * (0.6 + 0.4 * data_conf)
        if score >= CONF_HIGH:
            level = "高"
        elif score >= CONF_MEDIUM:
            level = "中"
        else:
            level = "低"
        return {"level": level, "score": round(score, 3)}

    def set_calibrator(self, calibrator):
        """接入已拟合的校准器；is_fitted 后才生效。"""
        self.calibrator = calibrator
        self._calib_on = calibrator is not None and calibrator.is_fitted()

    def predict_fixtures(self, fixtures, n=MC_SIMULATIONS, _use_calib=True):
        out = []
        for fx in fixtures:
            out.append(self.predict(fx["home"], fx["away"],
                                    league=fx.get("league"), n=n, _use_calib=_use_calib))
        return out
