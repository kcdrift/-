"""冷门预测模块：分析比赛爆冷概率

冷门派生：
1. 热门方（赔率低/预期进球高）未能获胜
2. 具体场景：
   - 主胜热门但平局/客胜概率高
   - 强队客场作战爆冷
   - 让球盘口深但最终无法打穿
"""
from typing import Dict, List, Tuple
import math


def calculate_cold_match_probability(
    match: Dict,
    model_prob_home: float,
    model_prob_draw: float,
    model_prob_away: float,
    odds: Dict = None
) -> Dict:
    """
    计算单场比赛的冷门派生概率

    Args:
        match: 比赛信息 dict
        model_prob_home: 模型预测主胜概率
        model_prob_draw: 模型预测平局概率
        model_prob_away: 模型预测客胜概率
        odds: 赔率数据（可选）

    Returns:
        冷门派生分析结果 dict
    """
    result = {
        'match_id': f"{match.get('home', '')}_vs_{match.get('away', '')}",
        'home': match.get('home', ''),
        'away': match.get('away', ''),
        'league': match.get('league', ''),
        'date': match.get('date', ''),
        'model_probs': {
            'home_win': round(model_prob_home * 100, 1),
            'draw': round(model_prob_draw * 100, 1),
            'away_win': round(model_prob_away * 100, 1),
        },
        'cold_probabilities': {},
        'cold_level': '低',
        'recommendation': ''
    }

    # 计算冷门概率
    # 1. 主胜热门但实际可能爆冷
    home_favorite = model_prob_home > 0.5
    away_cold = model_prob_away > 0.3 if home_favorite else model_prob_home > 0.3

    if home_favorite:
        # 主胜热门时的冷门派生
        draw_prob = model_prob_draw
        away_prob = model_prob_away
        cold_prob = max(draw_prob, away_prob)  # 最大非主胜概率

        result['cold_probabilities'] = {
            'draw_cold': round(draw_prob * 100, 1),  # 平局冷
            'away_cold': round(away_prob * 100, 1),   # 客胜冷
            'total_cold': round(cold_prob * 100, 1)    # 总冷门概率
        }

        # 判断冷门级别
        if cold_prob >= 0.4:
            result['cold_level'] = '高'
            result['recommendation'] = f'⚠️ 高风险冷门！{result["home"]}虽为主场热门，但爆冷概率达{cold_prob*100:.0f}%，建议防守'
        elif cold_prob >= 0.25:
            result['cold_level'] = '中'
            result['recommendation'] = f'⚡ 中等冷门风险，{result["home"]}优势不明显，可考虑平局/客胜选项'
        else:
            result['cold_level'] = '低'
            result['recommendation'] = f'✓ 冷门风险较低，{result["home"]}胜算较大'
    else:
        # 无明确热门时的冷门派生
        max_prob = max(model_prob_home, model_prob_draw, model_prob_away)
        cold_prob = 1 - max_prob  # 非最高概率即为冷门

        result['cold_probabilities'] = {
            'draw_cold': round(model_prob_draw * 100, 1),
            'away_cold': round(model_prob_away * 100, 1),
            'total_cold': round(cold_prob * 100, 1)
        }

        if cold_prob >= 0.5:
            result['cold_level'] = '高'
            result['recommendation'] = '⚠️ 势均力敌，冷门概率极高，不建议重仓任何一侧'
        elif cold_prob >= 0.35:
            result['cold_level'] = '中'
            result['recommendation'] = '⚡ 比赛走势不明，冷门风险中等'
        else:
            result['cold_level'] = '低'
            result['recommendation'] = '✓ 有明确热门方，冷门风险较低'

    return result


def analyze_cold_matches(predictions: List[Dict]) -> List[Dict]:
    """
    批量分析所有预测比赛的冷门派生

    Args:
        predictions: 预测列表

    Returns:
        冷门分析结果列表（按冷门概率排序）
    """
    results = []

    for pred in predictions:
        odds = pred.get('odds', {})
        prob = pred.get('prob', {})

        # 提取概率
        home_win = prob.get('home_win', 0.5) if isinstance(prob, dict) else 0.5
        draw = prob.get('draw', 0.25) if isinstance(prob, dict) else 0.25
        away_win = prob.get('away_win', 0.25) if isinstance(prob, dict) else 0.25

        # 确保概率归一化
        total = home_win + draw + away_win
        if total > 0:
            home_win /= total
            draw /= total
            away_win /= total

        # 使用中文队名（如有）
        match = {
            'home': pred.get('home_cn') or pred.get('home', ''),
            'away': pred.get('away_cn') or pred.get('away', ''),
            'league': pred.get('league', ''),
            'date': pred.get('date', ''),
        }

        # 计算冷门
        cold_result = calculate_cold_match_probability(
            match=match,
            model_prob_home=home_win,
            model_prob_draw=draw,
            model_prob_away=away_win,
            odds=odds
        )
        cold_result['prediction'] = pred  # 附加原预测
        results.append(cold_result)

    # 按冷门概率降序排列
    results.sort(key=lambda x: x['cold_probabilities'].get('total_cold', 0), reverse=True)

    return results


def get_cold_summary(cold_results: List[Dict]) -> Dict:
    """
    生成冷门分析汇总报告

    Args:
        cold_results: 冷门分析结果列表

    Returns:
        汇总报告 dict
    """
    total = len(cold_results)
    high_cold = [r for r in cold_results if r['cold_level'] == '高']
    medium_cold = [r for r in cold_results if r['cold_level'] == '中']
    low_cold = [r for r in cold_results if r['cold_level'] == '低']

    return {
        'total_matches': total,
        'high_risk': len(high_cold),
        'medium_risk': len(medium_cold),
        'low_risk': len(low_cold),
        'high_risk_ratio': f'{len(high_cold)/total*100:.1f}%' if total > 0 else '0%',
        'summary': f'共{total}场比赛，高风险{len(high_cold)}场({len(high_cold)/total*100:.1f}%)，中风险{len(medium_cold)}场，低风险{len(low_cold)}场'
    }
