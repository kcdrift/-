"""新联赛盘口队名 → 训练队名对齐。

背景：
  - 历史模型用 openfootball 训练名（如 "AFC Ajax"、"Feyenoord Rotterdam"、
    "PSV"、"FC Twente '65"、"PEC Zwolle"、"Sport Lisboa e Benfica"）。
  - 实时盘口（The Odds API）与生成赛程用较短的盘口名（如 "Ajax"、"Feyenoord"、
    "PSV Eindhoven"、"FC Twente"、"SC Braga"、"SL Benfica"）。
  - 两者 norm_team 后未必相等（"PSV Eindhoven"→psveindhoven vs "PSV"→psv），
    若不解析直接喂给模型，lambda 查不到该队 → 退化成联赛均值，等于假概率。

本模块只负责「荷甲 / 葡超」两联赛（有真实模型，必须对齐才能查 lambda）。
日职 / 韩职 / 欧冠无模型，盘口名直接展示，无需对齐。

resolve_to_training(league, name) 返回对齐后的训练名；无对应项则原样返回。
"""
# 盘口/赛程名 -> openfootball 训练名。两联赛分别列出，覆盖 The Odds API 与
# new_leagues.json 两种命名变体（实测两者略有差异）。
ODDS_TO_TRAINING = {
    "荷甲": {
        "Ajax": "AFC Ajax",
        "AZ Alkmaar": "AZ",
        "AZ": "AZ",
        "FC Twente": "FC Twente '65",
        "FC Twente Enschede": "FC Twente '65",
        "Feyenoord": "Feyenoord Rotterdam",
        "NEC Nijmegen": "NEC",
        "PEC Zwolle": "PEC Zwolle",
        "Vitesse Arnhem": "SBV Vitesse",
        "Volendam FC": "FC Volendam",
    },
    "葡超": {
        "Arouca": "FC Arouca",
        "Braga": "Sporting Clube de Braga",
        "SC Braga": "Sporting Clube de Braga",
        "CF Estrela": "CF Estrela da Amadora",
        "Estrela da Amadora": "CF Estrela da Amadora",
        "Nacional": "CD Nacional",
        "CD Nacional": "CD Nacional",
        "Chaves": "GD Chaves",
        "Estoril Praia": "GD Estoril Praia",
        "Famalicão": "FC Famalicão",
        "FC Porto": "FC Porto",
        "Portimonense": "Portimonense SC",
        "Rio Ave FC": "Rio Ave FC",
        "Santa Clara": "CD Santa Clara",
        "SL Benfica": "Sport Lisboa e Benfica",
        "Sporting CP": "Sporting Clube de Portugal",
        "Vitória SC": "Vitória Guimarães",
        "Vizela": "FC Vizela",
        "Gil Vicente FC": "Gil Vicente FC",
        "Moreirense FC": "Moreirense FC",
        "Boavista FC": "Boavista FC",
        "Casa Pia AC": "Casa Pia AC",
    },
}


def resolve_to_training(league, name):
    """将盘口/赛程队名对齐到模型训练名。无对应项则原样返回。"""
    mp = ODDS_TO_TRAINING.get(league)
    if mp and name in mp:
        return mp[name]
    return name
