"""队名映射：football-data.org简写 -> 预测数据全称"""

TEAM_MAPPING = {
    # 意甲
    "atalanta": "Atalanta BC",
    "frosinone": "Frosinone Calcio",
    "genoa": "Genoa CFC",
    "inter": "FC Internazionale Milano",
    "juventus": "Juventus FC",
    "lecce": "US Lecce",
    "milan": "AC Milan",
    "monza": "AC Monza",
    "parma": "Parma Calcio 1913",
    "sassuolo": "US Sassuolo Calcio",
    "torino": "Torino FC",
    "udinese": "Udinese Calcio",
    "venezia": "Venezia FC",

    # 法甲
    "auxerre": "AJ Auxerre",
    "brest": "Stade Brestois 29",
    "le havre": "Le Havre AC",
    "le mans": "Le Mans FC",
    "lille": "Lille OSC",
    "lorient": "FC Lorient",
    "marseille": "Olympique de Marseille",
    "monaco": "AS Monaco FC",
    "nice": "OGC Nice",
    "olympique lyon": "Olympique Lyonnais",
    "psg": "Paris Saint-Germain FC",
    "rc lens": "RC Lens",
    "stade rennais": "Stade Rennais FC 1901",
    "strasbourg": "RC Strasbourg Alsace",
    "toulouse": "Toulouse FC",
    "troyes": "ES Troyes AC",

    # 英超
    "brighton": "Brighton & Hove Albion FC",
    "man city": "Manchester City FC",
    "newcastle": "Newcastle United FC",
    "arsenal": "Arsenal FC",
    "chelsea": "Chelsea FC",
    "liverpool": "Liverpool FC",
    "man united": "Manchester United FC",
    "tottenham": "Tottenham Hotspur FC",
    "aston villa": "Aston Villa FC",
    "west ham": "West Ham United FC",
    "leicester": "Leicester City FC",
    "wolves": "Wolverhampton Wanderers FC",
    "everton": "Everton FC",
    "crystal palace": "Crystal Palace FC",
    "fulham": "Fulham FC",
    "brentford": "Brentford FC",
    "nottingham": "Nottingham Forest FC",
    "bournemouth": "AFC Bournemouth",
    "ipswich": "Ipswich Town FC",
    "southampton": "Southampton FC",
    "sunderland": "Sunderland AFC",
    "leeds": "Leeds United FC",
    "hull": "Hull City AFC",
    "coventry": "Coventry City FC",

    # 西甲
    "atleti": "Club Atlético de Madrid",
    "real madrid": "Real Madrid CF",
    "barcelona": "FC Barcelona",
    "sevilla": "Sevilla FC",
    "betis": "Real Betis Balompié",
    "atletico": "Club Atlético de Madrid",
    "valencia": "Valencia CF",
    "villarreal": "Villarreal CF",
    "osasuna": "CA Osasuna",
    "celta": "RC Celta de Vigo",
    "marchena": "RCD Espanyol de Barcelona",
    "mallorca": "RCD Mallorca",
    "las palmas": "UD Las Palmas",
    "girona": "Girona FC",
    "rayo vallecano": "Rayo Vallecano de Madrid",
    "athletic": "Athletic Club",
    "getafe": "Getafe CF",
    "alaves": "Deportivo Alavés",
    "real sociedad": "Real Sociedad de Fútbol",
    "osasuna": "CA Osasuna",

    # 德甲
    "bayern": "FC Bayern München",
    "leverkusen": "Bayer 04 Leverkusen",
    "dortmund": "Borussia Dortmund",
    "monchengladbach": "Borussia Mönchengladbach",
    "leipzig": "RB Leipzig",
    "frankfurt": "Eintracht Frankfurt",
    "wolfsburg": "VfL Wolfsburg",
    "freiburg": "SC Freiburg",
    "augsburg": "FC Augsburg",
    "mainz": "1. FSV Mainz 05",
    "hoffenheim": "TSG 1899 Hoffenheim",
    "union berlin": "1. FC Union Berlin",
    "koeln": "1. FC Köln",
    "heidenheim": "1. FC Heidenheim 1846",
    "bochum": "VfL Bochum 1848",
    "stuttgart": "VfB Stuttgart",
    "werder bremer": "SV Werder Bremen",

    # 荷甲
    "psv": "PSV Eindhoven",
    "ajax": "AFC Ajax",
    "fejenord": "Feyenoord",
    "AZ": "AZ Alkmaar",
    "twente": "FC Twente",
    "utrecht": "FC Utrecht",
    "sittard": "Fortuna Sittard",
    "go ahead": "Go Ahead Eagles",
    "heracles": "Heracles Almelo",
    "heerenveen": "SC Heerenveen",
    "zwolle": "PEC Zwolle",
    "sparta": "Sparta Rotterdam",
    "nevnen": "NEC Nijmegen",
    "groningen": "FC Groningen",
    "cambuur": "SC Cambuur",
    "rkc": "RKC Waalwijk",
    "almere": "Almere City FC",

    # 葡超
    "porto": "FC Porto",
    "benfica": "SL Benfica",
    "sporting": "Sporting CP",
    "braga": "SC Braga",
    "aboica": "SC Abrols",
    "maritimo": "CSD Marítimo",
    "vistla": "Vitória SC",
    "arouca": "FC Arouca",
    "estoril": "Estoril Praia",
    "rio ave": "Rio Ave FC",
    "famalicao": "FC Famalicão",
    "santa clara": "Santa Clara",
    "visela": "GD Vizela",
    "acacademico": "Académico de Viseu",
    "boavista": "Boavista FC",
    "moreirense": "Moreirense FC",
    "chaves": "CF Chaves",

    # 巴甲
    "flamengo": "Clube de Regatas do Flamengo",
    "palmeiras": "SE Palmeiras",
    "sao paulo": "São Paulo FC",
    "corinthians": "Sport Club Corinthians Paulista",
    "saopaulo": "São Paulo FC",
    "fluminense": "Fluminense FC",
    "gremio": "Grêmio FBPA",
    "internacional": "SC Internacional",
    "atletico-mg": "Clube Atlético Mineiro",
    "cruzeiro": "Cruzeiro EC",
    "bahia": "Esporte Clube Bahia",
    "vasco": "CR Vasco da Gama",
    "botafogo": "Botafogo de Futebol e Regatas",
    "atletico-pr": "Club Athletico Paranaense",
    "fortaleza": "Fortaleza EC",
    "cordoba": "Coritiba Foot Ball Club",
    "bragantino": "Red Bull Bragantino",
    "cuiaba": "Cuiabá EC",
    "goias": "Goiás EC",
    "juventude": "Joinville EC",
    "chapecoense": "Associação Chapecoense de Futebol",
    "santos": "Santos FC",
    "mirassol": "Mirassol FC",
    "remo": "Clube do Remo",
    "mineiro": "America Mineiro",
}

def normalize_team(name):
    """标准化队名为预测数据格式"""
    if not name:
        return name
    key = name.strip().lower()
    return TEAM_MAPPING.get(key, name)

def normalize_fixture(home, away):
    """标准化一场比赛"""
    return normalize_team(home), normalize_team(away)

# 测试
if __name__ == "__main__":
    test_cases = [
        # 意甲
        ("atalanta", "sassuolo"),
        ("frosinone", "juventus"),
        ("milan", "torino"),
        # 法甲
        ("psg", "stade rennais"),
        # 英超
        ("arsenal", "coventry city"),
        ("man united", "hull city"),
        # 西甲
        ("atleti", "real madrid"),
        # 德甲
        ("bayern", "leverkusen"),
        # 荷甲
        ("sittard", "AZ"),
        ("psv", "groningen"),
        ("go ahead", "den haag"),
        # 葡超
        ("porto", "arouca"),
        ("sporting cp", "alverca"),
        # 巴甲
        ("flamengo", "palmeiras"),
        ("corinthians", "coritiba"),
    ]
    for h, a in test_cases:
        nh, na = normalize_fixture(h, a)
        print(f"{h} -> {nh}, {a} -> {na}")
