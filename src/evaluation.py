"""模型评估模块。

在评估集（历史近期比赛，已含真实赛果）上回测，计算多维指标：
  - 对数损失 (Log Loss)：概率校准核心指标，越低越好
  - Brier 分数：概率预测平方误差，越低越好
  - RPS (排序概率得分)：考虑胜/平/负有序关系的评分，越低越好
  - 方向准确率：预测最可能结果命中实际的比例
  - 校准（可靠性）：将预测概率分箱，对比实际发生频率

所有指标附带说明，便于判断模型是否可用。
"""
import math
from config import MC_SIMULATIONS, DEFAULT_HANDICAP, DEFAULT_TOTAL_LINE


def evaluate(engine, eval_matches, n=MC_SIMULATIONS, compare_calibration=False, raw_preds=None):
    log_losses, briers, rps_list, correct = [], [], [], 0
    # 盘口回测
    handi_correct, handi_nonpush = 0, 0   # 主让一球赢/输盘命中（剔除走盘）
    total_correct, total_count = 0, 0      # 大小球 2.5 大/小命中
    # 校准分箱：预测主胜概率 -> [事件发生计数, 总计数]
    calib_bins = {b: [0, 0] for b in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]}

    for m in eval_matches:
        pred = engine.predict(m["home"], m["away"], league=m.get("league"),
                              n=n, seed=12345)
        p = pred["prob"]
        # 实际 one-hot：W=主胜, D=平, L=客胜(=主负)
        actual = m["result"]
        y = {"home_win": 1.0 if actual == "W" else 0.0,
             "draw": 1.0 if actual == "D" else 0.0,
             "away_win": 1.0 if actual == "L" else 0.0}
        # Log Loss
        eps = 1e-12
        ll = 0.0
        for k in ("home_win", "draw", "away_win"):
            ll += -y[k] * math.log(max(p[k], eps))
        log_losses.append(ll)
        # Brier
        brier = sum((p[k] - y[k]) ** 2 for k in ("home_win", "draw", "away_win"))
        briers.append(brier)
        # RPS
        rps_list.append(_rps(p, y))
        # 方向准确率
        pred_winner = max(p, key=p.get)
        if y[pred_winner] == 1.0:
            correct += 1
        # 校准：按主胜预测概率入箱（round 消除浮点误差）
        ph = p["home_win"]
        bin_key = round(min(0.9, (ph // 0.1) * 0.1), 1)
        calib_bins[bin_key][1] += 1
        calib_bins[bin_key][0] += y["home_win"]

        # 主让一球赢盘命中（剔除走盘场次）
        margin = m["home_goals"] - m["away_goals"]
        h1 = pred["handicap"][str(DEFAULT_HANDICAP)]
        if margin > DEFAULT_HANDICAP:
            actual_h = "win"
        elif margin == DEFAULT_HANDICAP:
            actual_h = "draw"
        else:
            actual_h = "lose"
        pred_h = max(h1, key=h1.get)
        if actual_h != "draw":
            handi_nonpush += 1
            if pred_h == actual_h:
                handi_correct += 1
        # 大小球 2.5 大/小命中
        total_goals = m["home_goals"] + m["away_goals"]
        t25 = pred["totals"][str(DEFAULT_TOTAL_LINE)]
        actual_t = "over" if total_goals > DEFAULT_TOTAL_LINE else "under"
        pred_t = "over" if t25["over"] >= t25["under"] else "under"
        total_count += 1
        if pred_t == actual_t:
            total_correct += 1

    k = len(eval_matches)
    report = {
        "n_matches": k,
        "log_loss": _mean(log_losses),
        "brier": _mean(briers),
        "rps": _mean(rps_list),
        "accuracy": correct / k if k else 0.0,
        "calibration": _calibration_table(calib_bins),
        "handicap_accuracy": handi_correct / handi_nonpush if handi_nonpush else 0.0,
        "handicap_nonpush": handi_nonpush,
        "totals_accuracy": total_correct / total_count if total_count else 0.0,
    }
    # 校准对比：若提供 raw（未校准）预测，额外统计校准前指标
    if compare_calibration and raw_preds is not None:
        raw_ll, raw_br, raw_rps = [], [], []
        for pred, m in zip(raw_preds, eval_matches):
            p = pred["prob"]
            actual = m["result"]
            y = {"home_win": 1.0 if actual == "W" else 0.0,
                 "draw": 1.0 if actual == "D" else 0.0,
                 "away_win": 1.0 if actual == "L" else 0.0}
            eps = 1e-12
            ll = sum(-y[k] * math.log(max(p[k], eps)) for k in ("home_win", "draw", "away_win"))
            raw_ll.append(ll)
            raw_br.append(sum((p[k] - y[k]) ** 2 for k in ("home_win", "draw", "away_win")))
            raw_rps.append(_rps(p, y))
        report["log_loss_raw"] = _mean(raw_ll)
        report["brier_raw"] = _mean(raw_br)
        report["rps_raw"] = _mean(raw_rps)
        report["calibrated"] = True
    return report


def _rps(p, y):
    """排序概率得分：按 主负<平<主胜 的有序累积误差。"""
    # 订单：away_win(负), draw(平), home_win(胜)
    order = ["away_win", "draw", "home_win"]
    cum_p, cum_y = 0.0, 0.0
    s = 0.0
    for key in order:
        cum_p += p[key]
        cum_y += y[key]
        s += (cum_p - cum_y) ** 2
    return s / (len(order) - 1)


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _calibration_table(calib_bins):
    rows = []
    for b in sorted(calib_bins):
        occ, tot = calib_bins[b]
        freq = occ / tot if tot else None
        rows.append({
            "bin": f"[{b:.1f}-{b+0.1:.1f})",
            "predicted": round(b + 0.05, 2),
            "actual_freq": round(freq, 3) if freq is not None else None,
            "count": tot,
        })
    return rows


def print_report(report):
    print("=" * 56)
    print("模型评估报告")
    print("=" * 56)
    print(f"评估场次        : {report['n_matches']}")
    print(f"对数损失 LogLoss : {report['log_loss']:.4f}  (越低越好, 随机~1.10)")
    print(f"Brier 分数      : {report['brier']:.4f}  (越低越好, 0=完美)")
    print(f"RPS 排序得分     : {report['rps']:.4f}  (越低越好)")
    print(f"方向准确率       : {report['accuracy']*100:.1f}%  (预测最可能结果命中)")
    hacc = report.get("handicap_accuracy", 0.0)
    hnp = report.get("handicap_nonpush", 0)
    tacc = report.get("totals_accuracy", 0.0)
    print(f"主让一球赢盘命中 : {hacc*100:.1f}%  (剔除走盘 {hnp} 场后)")
    print(f"大小球2.5命中    : {tacc*100:.1f}%  (大/小方向命中)")
    if report.get("calibrated"):
        print("-" * 56)
        print("概率校准对比 (Platt scaling, 校准集与评估集分离):")
        print(f"  LogLoss  校准前 {report['log_loss_raw']:.4f} -> 校准后 {report['log_loss']:.4f}"
              f"  (Δ{report['log_loss_raw']-report['log_loss']:+.4f})")
        print(f"  Brier    校准前 {report['brier_raw']:.4f} -> 校准后 {report['brier']:.4f}"
              f"  (Δ{report['brier_raw']-report['brier']:+.4f})")
        print(f"  RPS      校准前 {report['rps_raw']:.4f} -> 校准后 {report['rps']:.4f}"
              f"  (Δ{report['rps_raw']-report['rps']:+.4f})")
    print("-" * 56)
    print("校准（可靠性）表 - 主胜预测概率 vs 实际发生频率:")
    print(f"  {'区间':<12}{'预测概率':<10}{'实际频率':<10}{'样本数'}")
    for r in report["calibration"]:
        af = f"{r['actual_freq']:.3f}" if r["actual_freq"] is not None else "  -  "
        print(f"  {r['bin']:<12}{r['predicted']:<10}{af:<10}{r['count']}")
    print("=" * 56)
