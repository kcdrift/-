"""足彩量化预测项目 - 全局配置

所有可调参数集中在此，方便复现与调优。
"""
import os

# ---- 路径 ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
ARTIFACTS_DIR = os.path.join(DATA_DIR, "artifacts")
WEB_DIR = os.path.join(BASE_DIR, "web")

# ---- 数据文件 ----
HISTORICAL_FILE = os.path.join(RAW_DIR, "historical_matches.json")
FIXTURES_FILE = os.path.join(RAW_DIR, "upcoming_fixtures.json")
ELO_FILE = os.path.join(ARTIFACTS_DIR, "elo_ratings.json")
POISSON_FILE = os.path.join(ARTIFACTS_DIR, "poisson_params.json")
CALIB_FILE = os.path.join(ARTIFACTS_DIR, "calibrator.json")  # 反哺后校准器（reinforce/recalibrate 产出）
REVIEW_FILE = os.path.join(PROCESSED_DIR, "review_report.json")  # 赛后对比报告（review 命令产出）

# ---- 真实数据（生产用）路径 ----
# 真实历史赛果（openfootball 抓取，fetch_historical.py 产出），训练用，消除合成同名队冲突
REAL_HISTORICAL_CSV = os.path.join(RAW_DIR, "historical_real.csv")
# 真实未来赛程（每日更新，update_fixtures.py 产出），与真实历史同源队名，无跨源失真
UPCOMING_FIXTURES_CSV = os.path.join(RAW_DIR, "upcoming_clean_v4_20260824_002319.csv")

# ---- 合成数据（演示用）配置 ----
# 真实俱乐部名，便于直观查看；如需接真实数据，用 data_collector.load_from_csv 替换。
LEAGUES = {
    "英超": [
        "曼联", "曼城", "利物浦", "切尔西", "阿森纳", "热刺", "纽卡斯尔", "阿斯顿维拉",
        "西汉姆", "埃弗顿", "莱斯特城", "布莱顿", "狼队", "水晶宫", "布伦特福德",
        "富勒姆", "伯恩茅斯", "诺丁汉森林", "利兹联", "南安普顿",
    ],
    "西甲": [
        "皇家马德里", "巴塞罗那", "马德里竞技", "塞维利亚", "比利亚雷亚尔", "皇家社会",
        "毕尔巴鄂", "瓦伦西亚", "贝蒂斯", "奥萨苏纳", "塞尔塔", "赫罗纳", "赫塔菲",
        "西班牙人", "阿拉维斯", "马洛卡", "加的斯", "格拉纳达", "巴列卡诺", "巴伦西亚竞技",
    ],
    "德甲": [
        "拜仁慕尼黑", "多特蒙德", "勒沃库森", "莱比锡", "法兰克福", "沃尔夫斯堡", "门兴",
        "斯图加特", "柏林联合", "弗赖堡", "美因茨", "霍芬海姆", "不莱梅", "科隆",
        "奥格斯堡", "波鸿", "海登海姆", "达姆施塔特",
    ],
    "意甲": [
        "尤文图斯", "国际米兰", "AC米兰", "那不勒斯", "罗马", "拉齐奥", "亚特兰大",
        "佛罗伦萨", "博洛尼亚", "都灵", "萨索洛", "乌迪内斯", "维罗纳", "恩波利",
        "桑普多利亚", "热那亚", "萨勒尼塔纳", "蒙扎", "莱切", "卡利亚里",
    ],
    "法甲": [
        "巴黎圣日耳曼", "马赛", "摩纳哥", "里昂", "里尔", "雷恩", "尼斯", "朗斯",
        "斯特拉斯堡", "蒙彼利埃", "南特", "布雷斯特", "兰斯", "图卢兹", "洛里昂",
        "克莱蒙", "梅斯", "欧塞尔",
    ],
}
SEASONS = 5                 # 生成几个赛季的历史
SEASON_START_YEAR = 2021    # 起始赛季年
LEAGUE_AVG_HOME = 1.45      # 联赛场均主场进球（用于合成数据基准）
LEAGUE_AVG_AWAY = 1.10      # 联赛场均客场进球

# ---- 模型参数 ----
MC_SIMULATIONS = 20000      # 蒙特卡洛模拟次数（每场）
ELO_DEFAULT = 1500          # Elo 初始分
ELO_K = 32                  # Elo K 因子
ELO_HOME_ADV = 60           # Elo 主场优势分
POISSON_MAX_ITER = 200      # 泊松固定点迭代上限
POISSON_TOL = 1e-6          # 收敛阈值
POISSON_REG = 0.001         # 正则项，防止除零/过拟合

# ---- 盘口配置（亚洲让球盘 + 大小球）----
# 让球数正数表示主队让球（如 1 = 主让一球：主队净胜≥2 全赢、净胜1 走盘、其余输）
HANDICAPS = [0, 0.5, 1, 1.5, 2]
TOTALS_LINES = [1.5, 2.5, 3.5]   # 大小球线（总进球）
DEFAULT_HANDICAP = 1             # 评估 / 前端默认盘口：主让一球
DEFAULT_TOTAL_LINE = 2.5         # 评估 / 前端默认大小球线

# ---- 置信度阈值（合成 confidence_score ∈ (0,1)）----
CONF_HIGH = 0.55
CONF_MEDIUM = 0.42

# ---- Web 服务 ----
WEB_HOST = "0.0.0.0"  # 监听所有接口，支持局域网访问（手机/平板）
WEB_PORT = 8080
