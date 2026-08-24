# 足彩量化预测项目

基于 **Elo 评级 + 泊松攻防模型 + 蒙特卡洛模拟 + Platt 校准** 的足球胜平负 / 让球盘 / 大小球概率预测工具，带模型评估与 Web 展示界面。

## 方法论

| 环节 | 说明 |
|---|---|
| Elo 评级 | 主客场加权，输出双方期望胜率；仅对主/客胜做轻度正则（占比 0.2），平局直接取蒙特卡洛原始频率（避免强队差距大时平局被截断为 0） |
| 泊松攻防模型 | 按联赛独立拟合（league-relative，shrinkage 防发散），估计双方期望进球 λ |
| 蒙特卡洛模拟 | 默认 20000 次采样比分（上下半场各按 λ 半值独立采样，全场分布不变），统计胜平负频率、让球盘赢/走/输、大小球大/小、波胆分布、总进球单双、半全场组合 |
| Platt 校准 | 在独立**校准集**（与评估集分离）上拟合 sigmoid（logit 特征），缓解过自信，拉回真实频率 |

## 目录结构

```
D:\足彩
├── config.py                 # 联赛清单、蒙特卡洛次数、置信度阈值、盘口线、端口
├── main.py                   # CLI：serve / fetch / review / demo / evaluate / collect / train / predict
├── src/
│   ├── elo.py                # Elo 评级
│   ├── poisson_model.py      # 泊松攻防强度（按联赛拟合）
│   ├── data_collector.py     # 历史+赛程采集（合成 or 真实 CSV）
│   ├── preprocessing.py      # 清洗、特征工程、训练/校准/评估三分切分
│   ├── prediction_engine.py  # 整合模型，输出胜平负/比分/盘口/置信度
│   ├── calibration.py        # Platt scaling 概率校准
│   ├── evaluation.py         # LogLoss/Brier/RPS/准确率/校准 多维评估
│   ├── review.py             # 赛后对比分析（对齐预测与真实赛果、命中指标、反哺模型）
│   └── utils.py              # 泊松采样、熵、归一化、top 比分
├── web/
│   ├── app.py                # 纯标准库 http.server 界面 + API
│   └── templates/index.html  # 前端（筛选 / 详情展开 / 阈值高亮 / 概率分布图 / 赛后对比 tab）
├── data/
│   ├── raw/                  # 合成数据落盘 + 真实 CSV 示例（*_sample.csv）+ actuals_template.csv 赛果模板
│   ├── processed/            # 预处理产物（fetch_predictions.json / review_report.json）
│   └── artifacts/            # 模型参数（泊松 / Elo / calibrator 反哺）
├── scripts/
│   ├── review_pipeline.py    # 一键赛后对比 + 反哺批处理（自动配对最新预测）
│   ├── fetch_historical.py   # 抓 openfootball 真实历史赛果 -> historical_real.csv（训练用）
│   ├── update_fixtures.py    # 每日抓真实未来赛程 -> upcoming_fixtures.csv（TheSportsDB/football-data.org）
│   └── name_resolver.py      # 跨源队名解析器（对齐真实历史 canonical 队名，消除同名失真）
└── requirements.txt
```

## 数据格式

### 历史比赛 CSV（含赛果，用于训练/评估）

列：`date, league, home, away, home_goals, away_goals [, result]`

- `date`：YYYY-MM-DD
- `league`：联赛名（如 英超/西甲，或 Premier League 等任意名；按名独立建模）
- `home` / `away`：队名
- `home_goals` / `away_goals`：整数进球
- `result`（可选）：W/D/L，有则优先采用，无则按比分推算

### 未来赛程 CSV（无赛果，用于预测）

列：`date, league, home, away`

> 示例见 `data/raw/historical_sample.csv` 与 `data/raw/fixtures_sample.csv`，照格式填即可。

## 真实数据接入（生产推荐）

项目默认现在以**真实数据**驱动：只要 `data/raw/historical_real.csv`（真实历史）与 `data/raw/upcoming_fixtures.csv`（真实未来赛程）存在，`serve` / `fetch` / `train` / `predict` 会自动优先使用，不再回退合成演示数据，从根本上消除「真实队名撞合成同名队导致概率失真」。

### 1) 抓取真实历史赛果（一次性，可重跑）

数据源 [openfootball/football.json](https://github.com/openfootball/football.json)（公共领域、全季、免 key）。取最近 3 个完整赛季 × 五大联赛，鲁棒解析比分（list / dict / null），输出项目 CSV 契约：

```bash
python scripts/fetch_historical.py                              # 默认取 2025-26/2024-25/2023-24 -> data/raw/historical_real.csv
python scripts/fetch_historical.py --seasons 2024-25,2023-24,2022-23   # 自定义赛季
```

实测产出约 5200+ 场真实赛果（英超/西甲/意甲 380、德甲/法甲 306 场/季，因 18 队正确），直接喂 `train` / `serve` / `fetch`。

### 2) 每日自动更新真实赛程（从今天起）

脚本 `scripts/update_fixtures.py` 抓取五大联赛真实未来赛程，经 `scripts/name_resolver.py` 把任意数据源队名对齐到真实历史 canonical 队名（消除跨源同名失真），写到 `data/raw/upcoming_fixtures.csv`：

**当前数据源（双源合并策略）**：
- **openfootball/football.json 2026-27**：完整EPL赛程（~337场），其他联赛新季数据尚未发布。
- **TheSportsDB eventsnextleague**：其他联赛真实未来赛程（免费档每联赛1场）。
- **未来增强**：设置 `FOOTBALL_DATA_API_KEY` 环境变量后，脚本将优先使用 football-data.org 获取完整五联赛赛程。

**注册 football-data.org API Key（推荐）**：
1. 访问 https://www.football-data.org/register 免费注册
2. 获取 API Key
3. 复制 `.env.example` 为 `.env`，填入你的 key：
   ```bash
   cp .env.example .env
   # 编辑 .env，填入 FOOTBALL_DATA_API_KEY=你的key
   ```
4. 重启后脚本自动检测并使用完整版数据源

**健壮性**：单联赛失败不影响其他；全部失败保留上次好数据不截断；队名未匹配（如当季新升班马尚未进历史样本）会被跳过并告警，避免未知队致预测崩溃。

已配置**每日平台自动化任务**（每日 06:00 起，从 2026-08-23）：自动跑 `update_fixtures.py` + `fetch` 重生成预测，无需手动。手动触发：

```bash
python scripts/update_fixtures.py
FOOTBALL_DATA_API_KEY=xxx python scripts/update_fixtures.py   # 完整整季赛程
```

### 3) 队名解析器（跨源对齐，龙爷红线）

`scripts/name_resolver.py`：以真实历史 CSV 队名为 canonical，对输入队名做「去变音 + 剥 fc/cf/club 等后缀 + 去年份数字」归一化后精确匹配，否则用 (token Jaccard ∪ difflib) 模糊匹配（阈值 0.6），仍未匹配返回 None。审计映射落 `data/raw/team_alias.json`（手动覆盖优先、跨运行累积）。自检：`python scripts/name_resolver.py`。

> 实测对齐：Manchester City→Manchester City FC、Bayern Munich→FC Bayern München、Lille→Lille OSC、Atlético Madrid→Club Atlético de Madrid 等均正确。

## 运行

```bash
cd D:\足彩
python main.py serve                                              # 界面 http://127.0.0.1:8080（演示数据，已含校准）
python main.py demo                                               # 一站式演示：采集→训练→预测→评估
python main.py evaluate                                           # 评估报告（含校准前后 LogLoss/Brier/RPS 对比）
python main.py collect --csv data/raw/historical_sample.csv       # 加载真实历史并预览
python main.py evaluate --csv data/raw/historical_sample.csv      # 用真实历史评估
python main.py serve --csv data/raw/historical_sample.csv --fixtures data/raw/fixtures_sample.csv   # 真实数据预测界面
python main.py serve --odds data/raw/odds_sample.csv                        # 接入真实盘口水位（界面详情页显示价值信号）
python main.py fetch --csv data/raw/historical_sample.csv --live            # 一条指令：真实历史训练+实时抓赛程/盘口+预测+价值信号（CLI 速览，结果存 data/processed/fetch_predictions.json）
python main.py serve --csv data/raw/historical_sample.csv --live            # 同上加界面（真实训练+实时盘口一条龙）
python main.py review --pred data/processed/fetch_predictions.json --actual data/raw/真实赛果.csv                 # 赛后对比：对齐预测与真实赛果，算命中率/Brier/LogLoss+逐场对照（存 data/processed/review_report.json）
python main.py review --pred data/processed/fetch_predictions.json --actual data/raw/真实赛果.csv --reinforce --recalibrate   # 同上 + 回灌 Elo + 重算校准器（反哺下一轮）
```

## Windows 一键启动器（足彩一键启动.bat）

不想敲命令？项目根目录已放 `足彩一键启动.bat`，**双击即开菜单**：

- `1` 赛后对比 Review —— 自动配对最新预测 + 真实赛果，出命中报告并反哺模型（离线，最常用）
- `2` 启动界面 Web —— 本地 http://127.0.0.1:8080 双 Tab（赛前预测 / 赛后对比）
- `3` 抓取数据 Fetch —— 真实历史训练 + 实时盘口（需 The Odds API key）
- `0` 退出（或直接关窗口）

要点：
- 启动器自动探测 Python（优先 `py` → `python` → WorkBuddy managed python），免手动配环境。
- 选 1 前，先把真实赛果填到 `data/raw/actuals.csv`（参考 `data/raw/actuals_template.csv`）。
- 选 2 在新窗口启 Web 服务并自动开浏览器；关掉那个黑窗口即停服务。
- 选 3 需真实历史 CSV（训练用，消除真实队名撞合成队）；API key 留空则只抓历史 + 演示赛程。
- 菜单防呆：连续 20 次无效输入自动退出，不会卡死。

## 模型输出（每场）

- 胜平负概率（校准后）
- 最可能比分 Top3（含概率）
- 波胆（正确比分）Top6：全场比分蒙特卡洛分布，列最常见 6 项及各自概率
- 总进球单双：全场总进球为奇数 / 偶数的概率
- 半全场：上/下半场各独立按 λ 半值采样，组合成 9 种（胜胜/胜平/胜负/平胜/平平/平负/负胜/负平/负负）
- 让球盘：主让 `0 / 0.5 / 1 / 1.5 / 2` 的赢盘 / 走盘 / 输盘概率
- 大小球：`1.5 / 2.5 / 3.5` 的大球 / 小球概率
- 置信度：综合「概率集中度 + 信息熵 + 数据量」给 高 / 中 / 低 三级 + 0~1 分数

## 评估指标

- **对数损失 LogLoss**：概率校准核心，越低越好（随机约 1.10）
- **Brier 分数**：平方误差，越低越好（0=完美）
- **RPS**：考虑胜平负有序关系的排序概率得分，越低越好
- **方向准确率**：预测最可能结果命中实际比例
- **盘口回测**：主让一球赢盘命中率（剔除走盘）、大小球 2.5 大/小命中率
- **可靠性表**：预测概率分箱 vs 实际发生频率

## 注意事项

- **生产默认真实数据**：只要 `data/raw/historical_real.csv`（真实历史）与 `data/raw/upcoming_fixtures.csv`（真实未来赛程）存在，`serve / fetch / train / predict` 会自动优先使用真实源，不再回退合成演示数据——从根本上消除「真实队名撞合成同名队导致概率失真」。
- **手动切回合成**：`python main.py serve --demo` 或 `--csv` 显式指向合成数据文件。
- **独立校准集**：历史按时间顺序切为 训练集(70%) / 校准集(15%) / 评估集(15%)，Platt 校准器仅在校准集拟合、评估集独立回测，杜绝乐观估计。当前评估指标（LogLoss≈1.02）为真实水平。
- **每日自动更新**：已配置平台自动化任务（每日 06:00），自动抓取真实未来赛程并重新生成预测。也可手动跑 `python scripts/update_fixtures.py`。
- **数据源说明**：当前使用 openfootball (EPL完整) + TheSportsDB (其他联赛补充) 双源合并策略。如需完整五联赛赛程，请注册 [football-data.org](https://www.football-data.org/register) 免费API并填入 `.env` 文件。
- 模型基于历史统计，输出为概率估计，**不构成投注建议**。

## 真实盘口水位导入（价值信号）

详情页可对比「模型概率」与「市场水位隐含概率」，算出**价值差**（模型概率 − 1/水位）。
价值为正 = 模型比市场更看好该方向（潜在价值投注）；为负 = 市场更看好。

通过 `--odds` 接入真实盘口水位 CSV（不提供则用合成演示水位）：

```
python main.py serve --odds data/raw/odds_sample.csv
```

CSV 列（date/league/home/away 需与赛程精确匹配，odds 为含本金 decimal 格式，如 1.85）：

| 列 | 含义 |
|---|---|
| `date`,`league`,`home`,`away` | 匹配键，须与赛程一致 |
| `handicap_line` | 让球线（如 1 表示主让1球，0.5 主让半球） |
| `handicap_home_odds` / `handicap_away_odds` | 上盘 / 下盘水位 |
| `total_line` | 大小球界线（如 2.5） |
| `over_odds` / `under_odds` | 大球 / 小球水位 |

示例见 `data/raw/odds_sample.csv`。价值信号为概率估计，**不构成投注建议**。

## 实时赔率 API 抓取（--live，免手填 CSV）

通过 [The Odds API](https://the-odds-api.com) v4 免费层（每月 500 次）自动拉取五大联赛实时盘口水位，免去手填 CSV。模块见 `src/odds_fetcher.py`。

```
# 设好 key 后直接实时抓取（缺 key 自动回退合成数据，不崩）
export ODDS_API_KEY=你的key
python main.py serve --live
# 或显式传 key
python main.py serve --live --odds-api-key 你的key
```

实现要点：
- 拉取 `soccer_epl / la_liga / bundesliga / serie_a / ligue_one` 的 `h2h / spreads / totals` 市场，decimal 水位、ISO 时间。
- sport key 与英文队名映射到本项目中文联赛 / 队名（`SPORT_MAP` / `TEAM_MAP`，五大联赛主力队已收录，未收录者保留英文原名）。
- 让球线符号与项目一致：`line = -api_home_point`（API 主队 point 为负 = 主让）。
- 模型概率按**实时盘口线**从蒙特卡洛分布（净胜球 / 总进球）现算，支持任意盘口线（含 0.25 / 0.75 等整数半档），不限于预设 5 档；`spreads` / `totals` 任一项缺失则仅该项回退合成。
- **优雅降级**：无 key / 网络异常 / 抓到 0 场 → 自动回退到合成赛程 + CSV 盘口（若提供），界面照常可用。
- 模型训练默认用合成历史（API 不提供历史赛果），但 `serve --csv` 与 `fetch --csv` 均支持接入真实历史；**实战请用真实历史 CSV 训练**，否则真实队名会命中合成同名队、强度为合成随机值，价值信号仅供管线验证、不具实战意义。

API 返回形状示例见 `data/raw/odds_api_sample.json`（同时用于离线测试映射逻辑）。

## 赛后对比分析（review）—— 验证准确率 + 反哺模型

比赛结束后，用本功能把「预测」与「官方真实比分」逐场对齐，计算命中指标并反哺模型，让下一轮更准。模块见 `src/review.py`，Web 界面见「🔍 赛后对比」页签。

### 用法

```bash
# 1) 先有预测文件：跑 fetch 生成 data/processed/fetch_predictions.json（或用任意预测 JSON）
python main.py fetch --csv 真实历史.csv --live
# 2) 准备真实赛果 CSV（列：date,league,home,away,home_goals,away_goals，可选 ht_home_goals,ht_away_goals 半场比分）
# 3) 对比 + 报告
python main.py review --pred data/processed/fetch_predictions.json --actual data/raw/真实赛果.csv
# 反哺模型（回灌 Elo 评级 + 重算 Platt 校准器，下次 fetch/serve 自动加载）
python main.py review --pred data/processed/fetch_predictions.json --actual data/raw/真实赛果.csv --reinforce --recalibrate
```

真实赛果 CSV 列：`date, league, home, away, home_goals, away_goals [, ht_home_goals, ht_away_goals]`。

### 对齐与指标

- **对齐键**：`(联赛, 主队, 客队, 日期)` 四元组逐场匹配；未对齐项单独列出，不计入指标但报告出来（便于排查队名/日期不一致）。
- **命中指标**：胜负方向准确率、比分精确命中率（真实比分命中波胆 Top6）、最可能比分命中率（命中 Top3）、让球盘命中率（默认主让 `DEFAULT_HANDICAP=1`）、大小球命中率（默认线 `DEFAULT_TOTAL_LINE=2.5`）、单双命中率、半全场命中率（需真实半场比分，否则 N/A）。
- **概率质量**：Brier 分数、LogLoss（越接近 0 越准）。
- **分层**：按联赛、按置信度（高/中/低）分层，验证「置信度高 → 命中率高」的区分度是否成立。
- **逐场对照**：每场列出 预测 W/D/L 概率、真实比分、方向/比分/让球/大小/单双/半全场 命中标记（✓/✗）。

### 一键批处理（推荐）：`scripts/review_pipeline.py`

把「配对预测 → 出报告 → 反哺」三条命令合成一条，自动定位最新预测文件。

```bash
# 0) 参考模板填好真实赛果，保存为 data/raw/actuals.csv
#    （模板见 data/raw/actuals_template.csv，含 # 注释说明，可直接当赛果喂）
cp data/raw/actuals_template.csv data/raw/actuals.csv
# 编辑 actuals.csv：删掉示例行，填入你的真实赛果

# 1) 一键：自动配对最新 fetch 预测 → 出报告 → 回灌 Elo + 重算校准（默认全开）
python scripts/review_pipeline.py
# 指定赛果 / 预测
python scripts/review_pipeline.py --actual data/raw/actuals.csv
python scripts/review_pipeline.py --pred data/processed/fetch_predictions.json
# 只出报告不反哺
python scripts/review_pipeline.py --no-reinforce --no-recalibrate
```

**自动配对预测文件的优先级**：`--pred` 显式指定 → `data/processed/fetch_predictions.json`（fetch 默认输出）→ `data/processed/fetch_predictions_*.json` 中修改时间最新的一份。

**反哺（默认开启，可用 `--no-*` 关闭）**：
- `--reinforce`：真实赛果回灌 Elo 评级（`data/artifacts/elo_ratings.json`），下次 `fetch`/`serve` 训练时自动加载。
- `--recalibrate`：本批赛果重算 Platt 校准器（`data/artifacts/calibrator.json`），下次 `fetch`/`serve` 优先加载。
- 多次赛后 review 滚动反哺，模型随真实数据越滚越准。

运行后报告保存至 `data/processed/review_report.json`，界面「🔍 赛后对比」页签自动读取做可视化。

### 报告与界面

- 命令行打印结构化表格 + 存盘 `data/processed/review_report.json`（含 `meta` / `summary` / `by_league` / `by_confidence` / `matches`）。
- Web 界面「🔍 赛后对比」页签自动读取该报告，可视化展示：准确率汇总、按联赛、按置信度分层、逐场对照表；未生成报告时提示运行命令。
- 接口：`GET /api/review` 返回 `{available, report, config}`；`config` 带默认盘口线，供前端标注。

### 反哺机制（加强未来预测算力）

- `--reinforce`：用真实赛果回灌 Elo 评级（`EloRating.update`），真实战绩计入球队实力，下次训练自动加载更新后的评级（`data/artifacts/elo_ratings.json`）。
- `--recalibrate`：把本批真实赛果并入校准样本，重算 Platt 校准器（`data/artifacts/calibrator.json`），压缩「预测概率 vs 实际频率」偏差；`serve` / `fetch` 训练时优先加载该反哺校准器。
- 多次赛后 review 累积反哺，模型随真实数据滚动变准。
