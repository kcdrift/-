"""五大联赛 + 新联赛球队中英文对照表（完整）

覆盖：英超、西甲、德甲、意甲、法甲、荷甲、葡超、欧冠、韩职、日职
共 ~150+ 支球队。
"""
import re
import unicodedata

# 英超 (20队)
ENGLISH_PREMIER_LEAGUE = {
    "Arsenal FC": "阿森纳",
    "Aston Villa FC": "阿斯顿维拉",
    "Brighton & Hove Albion FC": "布莱顿",
    "Chelsea FC": "切尔西",
    "Crystal Palace FC": "水晶宫",
    "Everton FC": "埃弗顿",
    "Fulham FC": "富勒姆",
    "Liverpool FC": "利物浦",
    "Manchester City FC": "曼城",
    "Manchester United FC": "曼联",
    "Newcastle United FC": "纽卡斯尔",
    "Nottingham Forest FC": "诺丁汉森林",
    "Tottenham Hotspur FC": "热刺",
    "West Ham United FC": "西汉姆联",
    "Brentford FC": "布伦特福德",
    "Wolverhampton Wanderers FC": "狼队",
    "AFC Bournemouth": "伯恩茅斯",
    "Leicester City FC": "莱斯特城",
    "Ipswich Town FC": "伊普斯维奇",
    "Southampton FC": "南安普顿",
    "Stoke City FC": "斯托克城",
    "Burnley AFC": "布伦利",
}

# 西甲 (20队)
SPANISH_LIGA = {
    "Real Madrid CF": "皇马",
    "FC Barcelona": "巴萨",
    "Atlético de Madrid": "马竞",
    "Athletic Club": "毕尔巴鄂竞技",
    "Real Sociedad de Fútbol": "皇家社会",
    "Real Betis Balompié": "贝蒂斯",
    "Villarreal CF": "比利亚雷亚尔",
    "Girona FC": "赫罗纳",
    "CA Osasuna": "奥萨苏纳",
    "RCD Mallorca": "马略卡",
    "Getafe CF": "赫塔费",
    "Deportivo Alavés": "阿拉维斯",
    "Celta de Vigo": "塞尔塔",
    "Rayo Vallecano": "巴列卡诺",
    "RCD Espanyol": "西班牙人",
    "RCD Espanyol de Barcelona": "西班牙人",
    "CD Leganés": "莱加内斯",
    "Real Valladolid CF": "巴拉多利德",
    "UD Las Palmas": "拉斯帕尔马斯",
    "FC Sevilla": "塞维利亚",
    "Sevilla FC": "塞维利亚",
}

# 德甲 (18队)
GERMAN_BUNDESLIGA = {
    "Bayern München": "拜仁慕尼黑",
    "Borussia Dortmund": "多特蒙德",
    "Bayer 04 Leverkusen": "勒沃库森",
    "RB Leipzig": "莱比锡红牛",
    "Eintracht Frankfurt": "法兰克福",
    "VfB Stuttgart": "斯图加特",
    "SC Freiburg": "弗赖堡",
    "Werder Bremen": "云达不莱梅",
    "Borussia Mönchengladbach": "门兴格拉德巴赫",
    "1. FSV Mainz 05": "美因茨",
    "TSG 1899 Hoffenheim": "霍芬海姆",
    "FC Augsburg": "奥格斯堡",
    "1. FC Union Berlin": "柏林联合",
    "1. FC Köln": "科隆",
    "VfL Wolfsburg": "沃尔夫斯堡",
    "SV Darmstadt 98": "达姆施塔特",
    "Heidenheim 1846": "海登海姆",
    "VfL Bochum 1848": "波鸿",
}

# 意甲 (20队)
ITALIAN_SERIE_A = {
    "AC Milan": "AC米兰",
    "Inter Milan": "国际米兰",
    "Juventus FC": "尤文图斯",
    "SSC Napoli": "那不勒斯",
    "AS Roma": "罗马",
    "SS Lazio": "拉齐奥",
    "Atalanta BC": "亚特兰大",
    "ACF Fiorentina": "佛罗伦萨",
    "Bologna FC 1909": "博洛尼亚",
    "Torino FC": "都灵",
    "Udinese Calcio": "乌迪内斯",
    "Genoa CFC": "热那亚",
    "US Sassuolo Calcio": "萨索洛",
    "Cagliari Calcio": "卡利亚里",
    "US Lecce": "莱切",
    "Empoli FC": "恩波利",
    "Hellas Verona FC": "维罗纳",
    "Frosinone Calcio": "弗罗西诺内",
    "Monza": "蒙扎",
    "US Salernitana 1919": "萨勒尼塔纳",
    "FC Internazionale Milano": "国际米兰",
    "Como 1907": "科莫",
    "Parma Calcio 1913": "帕尔马",
    "Venezia FC": "威尼斯",
}

# 法甲 (18队)
FRENCH_LIGUE1 = {
    "Paris Saint-Germain FC": "巴黎圣日耳曼",
    "Olympique de Marseille": "马赛",
    "Olympique Lyonnais": "里昂",
    "AS Monaco FC": "摩纳哥",
    "LOSC Lille": "里尔",
    "OGC Nice": "尼斯",
    "Stade Rennais FC 1901": "雷恩",
    "RC Strasbourg Alsace": "斯特拉斯堡",
    "FC Nantes": "南特",
    "Stade Brestois 29": "布雷斯特",
    "RC Lens": "朗斯",
    "Stade de Reims": "兰斯",
    "Montpellier HSC": "蒙彼利埃",
    "Toulouse FC": "图卢兹",
    "Angers SCO": "昂热",
    "AJ Auxerre": "欧塞尔",
    "Le Havre AC": "勒阿弗尔",
    "Clermont Foot 63": "克莱蒙",
}

# 荷甲 (18队)
# 荷甲 (openfootball 训练全名 -> 中文)
DUTCH_EREDIVISIE = {
    "AFC Ajax": "阿贾克斯",
    "AZ": "阿尔克马尔",
    "Almere City FC": "阿尔梅勒城",
    "FC Groningen": "格罗宁根",
    "FC Twente '65": "特温特",
    "FC Utrecht": "乌得勒支",
    "FC Volendam": "福伦丹",
    "Feyenoord Rotterdam": "费耶诺德",
    "Fortuna Sittard": "福图纳锡塔德",
    "Go Ahead Eagles": "前进之鹰",
    "Heracles Almelo": "赫拉克勒斯",
    "NAC Breda": "布雷达",
    "NEC": "奈梅亨",
    "PEC Zwolle": "兹沃勒",
    "PSV": "埃因霍温",
    "RKC Waalwijk": "瓦尔韦克",
    "SBV Excelsior": "精英",
    "SBV Vitesse": "维特斯",
    "SC Heerenveen": "海伦芬",
    "Sparta Rotterdam": "鹿特丹斯巴达",
    "Telstar 1963": "泰勒斯塔",
    "Willem II Tilburg": "威廉二世",
}

# 巴甲（新增）
BRAZILIAN_SERIE_A = {
    "Santos FC": "桑托斯",
    "Santos": "桑托斯",
    "Mirassol Futebol Clube": "米拉索尔",
    "Mirassol": "米拉索尔",
    "Botafogo de Futebol e Regatas": "博塔弗戈",
    "Botafogo": "博塔弗戈",
    "Flamengo": "弗拉门戈",
    "Palmeiras": "帕尔梅拉斯",
    "Atlético Mineiro": "米内罗竞技",
    "Corinthians": "科林蒂安",
    "São Paulo FC": "圣保罗",
    "Fluminense": "弗鲁米嫩塞",
    "Vasco da Gama": "瓦斯科达伽马",
    "Grêmio": "格雷米奥",
    "Internacional": "国际体育会",
    "Cruzeiro": "克鲁塞罗",
    "Bahia": "巴伊亚",
    "Fortaleza": "福塔莱萨",
    "Coritiba": "科里蒂巴",
    "Guarani": "瓜拉尼",
    "Ponte Preta": "庞特普雷塔",
    # 新增：巴竞技（帕拉纳竞技）
    "Atlético Paranaense": "帕拉纳竞技",
    "Atletico Paranaense": "帕拉纳竞技",
    "Atlètico Paranaense": "帕拉纳竞技",
    "巴竞技": "帕拉纳竞技",  # 直接映射（体彩网缩写）
    "Atlètico Paranaense": "帕拉纳竞技",
    "巴竞技": "帕拉纳竞技",
}

# 美职（新增）
MAJOR_LEAGUE_SOCCER = {
    "New England Revolution": "新英格兰革命",
    "New England": "新英格兰",
    "New York City FC": "纽约城",
    "New York City": "纽约城",
    "LA Galaxy": "洛杉矶银河",
    "Inter Miami CF": "迈阿密国际",
    "Inter Miami": "迈阿密国际",
    "Seattle Sounders FC": "西雅图音速",
    "Portland Timbers": "波特兰伐木工",
    "Atlanta United FC": "亚特兰大联",
    "Orlando City SC": "奥兰多城",
    "FC Dallas": "达拉斯FC",
    "Sporting Kansas City": "堪萨斯城Sporting",
    "Real Salt Lake": "皇家盐湖城",
    "Vancouver Whitecaps FC": "温哥华白帽",
    "Toronto FC": "多伦多FC",
    "Montreal Impact": "蒙特利尔冲击",
    "Chicago Fire FC": "芝加哥火焰",
    "Columbus Crew": "哥伦布机员",
    "Philadelphia Union": "费城联合",
    "D.C. United": "华盛顿联",
    "San Jose Earthquakes": "圣何塞地震",
    "Colorado Rapids": "科罗拉多急流",
    "Minnesota United FC": "明尼苏达联",
    "CF Montréal": "蒙特利尔CF",
}

# 更多西甲球队（新增）
SPANISH_LIGA_EXTENDED = {
    "Racing de Santander": "桑坦德竞技",
    "Racing Santander": "桑坦德竞技",
    "Racing Santander": "桑坦德",
    "Racing de sandober": "桑坦德竞技",
    "Málaga CF": "马拉加",
    "Málaga": "马拉加",
    "Deportivo La Coruña": "拉科鲁尼亚",
    "Deportivo La Coro": "拉科鲁尼亚",
    "Deportivo La Coruna": "拉科",
    "Real Saragossa": "萨拉戈萨",
    "Real Zaragoza": "萨拉戈萨",
    "Sporting de Gijón": "希洪竞技",
    "Sporting Gijon": "希洪竞技",
    "Real Oviedo": "奥维耶多",
    "Elche CF": "埃尔切",
    "Elche": "埃尔切",
    "Levante UD": "莱万特",
    "Levante": "莱万特",
}

# 葡超 (openfootball 训练全名 -> 中文)
PORTUGUESE_PRIMEIRA = {
    "AVS": "阿维斯",
    "Boavista FC": "博阿维斯塔",
    "CD Nacional": "国民队",
    "CD Santa Clara": "圣克拉拉",
    "CD Tondela": "通德拉",
    "CF Estrela da Amadora": "阿马多拉之星",
    "Casa Pia AC": "卡萨皮亚",
    "FC Alverca": "阿尔维卡",
    "FC Arouca": "阿罗卡",
    "FC Famalicão": "法马利康",
    "FC Porto": "波尔图",
    "FC Vizela": "维泽拉",
    "GD Chaves": "查维斯",
    "GD Estoril Praia": "埃斯托里尔",
    "Gil Vicente FC": "吉尔维森特",
    "Moreirense FC": "摩雷伦斯",
    "Portimonense SC": "波尔蒂芒人",
    "Rio Ave FC": "里奥阿维",
    "SC Farense": "法伦斯",
    "Sport Lisboa e Benfica": "本菲卡",
    "Sporting Clube de Braga": "布拉加",
    "Sporting Clube de Portugal": "葡萄牙体育",
    "Vitória Guimarães": "维多利亚吉马良斯",
}

# 欧冠 (常见球队)
CHAMPIONS_LEAGUE = {
    "Real Madrid CF": "皇马",
    "FC Barcelona": "巴萨",
    "Manchester City FC": "曼城",
    "Liverpool FC": "利物浦",
    "Bayern München": "拜仁慕尼黑",
    "Paris Saint-Germain FC": "巴黎圣日耳曼",
    "Inter Milan": "国际米兰",
    "AC Milan": "AC米兰",
    "Juventus FC": "尤文图斯",
    "Borussia Dortmund": "多特蒙德",
    "Atlético de Madrid": "马竞",
    "Napoli": "那不勒斯",
    "Arsenal FC": "阿森纳",
    "Chelsea FC": "切尔西",
    "Benfica": "本菲卡",
    "Porto": "波尔图",
    "RB Leipzig": "莱比锡红牛",
    "PSV Eindhoven": "埃因霍温",
    "Feyenoord": "费耶诺德",
    "Celtic FC": "凯尔特人",
}

# 韩职 (K League 1)
KOREAN_K_LEAGUE = {
    "Ulsan Hyundai": "蔚山现代",
    "Jeonbuk Hyundai Motors": "全北现代",
    "Pohang Steelers": "浦项制铁",
    "FC Seoul": "首尔FC",
    "Jeju United": "济州联",
    "Incheon United": "仁川联",
    "Gangwon FC": "江原FC",
    "Daegu FC": "大邱FC",
    "Kyoto Sanga": "京都不死鸟",
    "Gimcheon Sangmu": "金泉尚武",
    "Suwon Samsung Bluewings": "水原三星",
    "Busan IPark": "釜山IPark",
    "Seongnam FC": "城南FC",
    "Daejeon Hana Citizen": "大田市民",
}

# 日职 (J League)
JAPANESE_J_LEAGUE = {
    "Yokohama F. Marinos": "横滨水手",
    "Kawasaki Frontale": "川崎前锋",
    "Urawa Red Diamonds": "浦和红钻",
    "Vissel Kobe": "神户胜利船",
    "Cerezo Osaka": "大阪樱花",
    "Gamba Osaka": "大阪钢巴",
    "Nagoya Grampus": "名古屋鲸八",
    "FC Tokyo": "东京FC",
    "Kashima Antlers": "鹿岛鹿角",
    "Sanfrecce Hiroshima": "广岛三箭",
    "Shonan Bellmare": "湘南贝尔马雷",
    "Tokyo Verdy": "东京绿茵",
    "Avispa Fukuoka": "福冈黄蜂",
    "Sagan Tosu": "佐庆蓝闪电",
    "Kyoto Sanga": "京都不死鸟",
}

# 瑞典超（新增）
SWEDISH_SUPERLIGEN = {
    "Malmö FF": "马尔默",
    "Malmö": "马尔默",
    "Djurgårdens IF": "佐加顿斯",
    "Djurgarden": "佐加顿斯",
}

# 训练名（openfootball 全名）→ 中文。Web 预测时盘口名已解析回训练名，
# 故需保证训练名也能翻译为中文，否则会回退显示英文。
TRAINING_NAMES_CN = {
    # 荷甲（openfootball 训练名）
    "AFC Ajax": "阿贾克斯",
    "AZ": "阿尔克马尔",
    "Almere City FC": "阿尔梅勒城",
    "FC Groningen": "格罗宁根",
    "FC Twente '65": "特温特",
    "FC Utrecht": "乌德勒支",
    "FC Volendam": "福伦丹",
    "Feyenoord Rotterdam": "费耶诺德",
    "Fortuna Sittard": "福图纳锡塔德",
    "Go Ahead Eagles": "前进之鹰",
    "Heracles Almelo": "赫拉克勒斯",
    "NAC Breda": "布雷达",
    "NEC": "奈梅亨",
    "PEC Zwolle": "兹沃勒",
    "PSV": "埃因霍温",
    "RKC Waalwijk": "瓦尔韦克",
    "SBV Excelsior": "精英",
    "SBV Vitesse": "维特斯",
    "SC Heerenveen": "海伦芬",
    "Sparta Rotterdam": "斯巴达鹿特丹",
    "Telstar 1963": "泰勒星",
    "Willem II Tilburg": "威廉二世",
    # 葡超（openfootball 训练名）
    "AVS": "AVS",
    "Boavista FC": "博阿维斯塔",
    "CD Nacional": "国民队",
    "CD Santa Clara": "圣克拉拉",
    "CD Tondela": "通德拉",
    "CF Estrela da Amadora": "阿马多拉之星",
    "Casa Pia AC": "卡萨皮亚",
    "FC Alverca": "阿尔韦卡",
    "FC Arouca": "阿罗卡",
    "FC Famalicão": "法马利康",
    "FC Porto": "波尔图",
    "FC Vizela": "维泽拉",
    "GD Chaves": "查维斯",
    "GD Estoril Praia": "埃斯托里尔",
    "Gil Vicente FC": "吉维森特",
    "Moreirense FC": "摩雷伦斯",
    "Portimonense SC": "波尔蒂芒人",
    "Rio Ave FC": "里奥阿维",
    "SC Farense": "法鲁人",
    "Sport Lisboa e Benfica": "本菲卡",
    "Sporting Clube de Braga": "布拉加",
    "Sporting Clube de Portugal": "葡萄牙体育",
    "Vitória Guimarães": "吉马良斯",
}

# 合并所有字典
ALL_TRANSLATIONS = {
    **ENGLISH_PREMIER_LEAGUE,
    **SPANISH_LIGA,
    **SPANISH_LIGA_EXTENDED,
    **GERMAN_BUNDESLIGA,
    **ITALIAN_SERIE_A,
    **FRENCH_LIGUE1,
    **DUTCH_EREDIVISIE,
    **PORTUGUESE_PRIMEIRA,
    **BRAZILIAN_SERIE_A,
    **MAJOR_LEAGUE_SOCCER,
    **CHAMPIONS_LEAGUE,
    **KOREAN_K_LEAGUE,
    **JAPANESE_J_LEAGUE,
    **SWEDISH_SUPERLIGEN,
    **TRAINING_NAMES_CN,
}


_TEAM_STRIP = {
    "fc", "cf", "club", "sc", "ac", "afc", "as", "rc", "cd", "ud", "ca",
    "rcd", "f", "c", "real", "de", "la", "and",
}

# 常见缩写 -> 标准名（用于归一化匹配）
# 注意：key 必须是去掉所有分隔符后的形式，与 _tnorm 中去分隔符后拼接的逻辑一致
_TEAM_ABBREV = {
    "manutd": "manchesterunited", "manu": "manchesterunited",
    "manunited": "manchesterunited",
    "mancity": "manchestercity", "mcfc": "manchestercity",
    "stokecity": "stokecity", "stoke": "stokecity",
    "hullcity": "hullcity", "hull": "hullcity",
    "burnleyafc": "burnleyafc", "burnley": "burnleyafc",
    "leedsunited": "leedsunited", "leeds": "leedsunited",
    "norwichcity": "norwichcity", "norwich": "norwichcity",
    "newcastleunited": "newcastleunited", "newcastle": "newcastleunited",
    "liverpoolfc": "liverpoolfc", "liverpool": "liverpoolfc",
    "chelseafc": "chelseafc", "chelsea": "chelseafc",
    "arsenalfc": "arsenalfc", "arsenal": "arsenalfc",
    "tottenhamhotspur": "tottenhamhotspur", "spurs": "tottenhamhotspur",
    "tot": "tottenhamhotspur",
    "wolverhamptonwanderers": "wolverhamptonwanderers", "wolves": "wolverhamptonwanderers",
    "afcbournemouth": "afcbournemouth", "bournemouth": "afcbournemouth",
    "leicestercity": "leicestercity", "leicester": "leicestercity",
    "ipswichtown": "ipswichtown", "ipswich": "ipswichtown",
    "southamptonfc": "southamptonfc", "southampton": "southamptonfc",
    "astonvillafc": "astonvillafc", "astonvilla": "astonvillafc", "villa": "astonvillafc",
    "westhamunited": "westhamunited", "westham": "westhamunited",
    "chelseafc": "chelseafc", "blues": "chelseafc",
    # 意甲简写
    "frosinone": "frosinonecalcio", "juventus": "juventusfc", "milan": "acmilan",
    "intermilano": "intermilan", "atalanta": "atalantabc",
    "bologna": "bolognafc", "roma": "asroma", "lazio": "sslazio",
    "napoli": "sscnapoli", "fiorentina": "acffiorentina", "torino": "torinoqc",
    "genoa": "genoacfc", "sassuolo": "ussassuolocalcio", "lecce": "uslecce",
    "empoli": "empolifc", "verona": "hellasverona", "venezia": "veneziafc",
    # 巴甲简写
    "atleticoparanaense": "atleticoparanaense", "botafogo": "botafogo",
    "santos": "santos", "mirassol": "mirassol",
    # 瑞超简写
    "malmoff": "malmoff", "malmo": "malmoff",
    "djurgarden": "djurgardensifs",
    # 德甲补充（兼容 no umlaut）
    "bayernmunich": "bayernmunchen",
}


def _tnorm(name: str) -> str:
    """显示层队名归一（用于中文翻译匹配）：去重音、转小写、剔除
    fc/cf/club/sc/ac/afc/rcd 等前缀与 and/& 连接词，拼回无分隔串。
    令 'AFC Bournemouth' == 'Bournemouth'、'Brighton & Hove Albion FC'
    == 'Brighton and Hove Albion'，弥合盘口 API 简短名与翻译表全称差异。
    额外处理常见缩写（如 Man Utd → manchesterunited）。
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    # 先去除分隔符，拼接成连续字符串，再查缩写映射
    words = [w for w in re.split(r"[^a-z0-9]+", s) if w and w not in _TEAM_STRIP]
    joined = "".join(words)
    # 常见缩写归一化（盘口 API 常用简称）
    s = _TEAM_ABBREV.get(joined, joined)
    return s


# 归一键 -> 中文 映射（查表一次，避免每次请求重复计算）
_NORM_MAP = {_tnorm(k): v for k, v in ALL_TRANSLATIONS.items()}


def translate_team(english_name: str) -> str:
    """将英文队名翻译为中文，或将中文队名翻译为英文（用于匹配）"""
    if not english_name:
        return english_name

    # 检测是否是中文（包含中文字符）
    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in english_name)

    if has_chinese:
        # 中文输入：直接在翻译表中查找key（支持中文别名）
        if english_name in ALL_TRANSLATIONS:
            return ALL_TRANSLATIONS[english_name]
        # 否则尝试反向查找（英文→中文的value）
        for en, cn in ALL_TRANSLATIONS.items():
            if cn == english_name:
                return en
        return english_name
    else:
        # 英文输入：查找对应的中文
        # 优先用归一化查找
        norm = _tnorm(english_name)
        cn = _NORM_MAP.get(norm)
        if cn:
            return cn
        # 兜底：尝试直接匹配（大小写不敏感）
        key_lower = english_name.lower().strip()
        for k, v in ALL_TRANSLATIONS.items():
            if k.lower().strip() == key_lower:
                return v
        return english_name


def translate_match(match: dict) -> dict:
    """将单场比赛预测的 home/away 直接替换为中文队名（同时保留 *_en 原值）。"""
    result = match.copy()
    h_cn = translate_team(match["home"])
    a_cn = translate_team(match["away"])
    result["home_en"] = match["home"]
    result["away_en"] = match["away"]
    result["home"] = h_cn
    result["away"] = a_cn
    result["home_cn"] = h_cn
    result["away_cn"] = a_cn
    return result
