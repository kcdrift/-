

## 2026-08-23 18:00 紧急修复：移动端让球盘/大小球显示 0% 问题
- **问题**：龙爷截图反馈手机版打开后，让球盘和大小球全部显示 0%，数据不齐。
- **根因**： 和  中的 handicap/totals 字段数值几乎全为 0.0002（约等于 1/5000），但同场比赛通过 API  实时返回的 handicap/totals 完全正常（如主让1球 win=0.6542）。
- **差异来源**：
  -  的  在 serve 启动时会重新用  计算预测，结果正确。
  -  是之前 batch 生成时产出的旧错误数据， handicap/totals 几乎为 0。
  - 移动端 HTML 默认读取 ，该文件由错误数据翻译而来，因此显示 0%。
- **紧急修复**：
  - 用 Python 直接从本地 API 拉取 3109 条正确预测，覆盖写入  和 。
  - 在  中将  从  改为 ，强制浏览器绕过缓存重新加载。
- **验证**：
  - 本地文件：， ✅
  - 公网访问：https://struck-era-counting-screensavers.trycloudflare.com/mobile/static_data.json?v=2 数据正确 ✅
- **后续**：正在后台重新运行 [preprocess] 训练集 3665 场，校准集 785 场，评估集 785 场，剔除 0 条
[train] 已拟合 5 个联赛泊松模型 + 1 个全量兜底
[train] 参数已保存: d:\足彩\data\artifacts\poisson_params.json / d:\足彩\data\artifacts\elo_ratings.json
[fetch] 使用真实未来赛程（默认真实源）：d:\足彩\data\raw\upcoming_fixtures.csv（3109 场）

[fetch] 共 3109 场预测（赛程来源：real）
Atalanta BC vs US Sassuolo Calcio | 主胜78% 平16% 客胜6% | 比分[3-0(9%)  2-0(9%)  3-1(8%)] | 置信中
   盘口：合成演示水位（无 --live 或抓取失败）
Frosinone Calcio vs Juventus FC | 主胜19% 平25% 客胜56% | 比分[0-1(12%)  0-2(12%)  1-1(10%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Torino FC vs AC Milan | 主胜30% 平30% 客胜40% | 比分[0-1(15%)  0-0(12%)  1-1(12%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Venezia FC vs US Lecce | 主胜45% 平32% 客胜23% | 比分[1-0(18%)  0-0(15%)  1-1(13%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Angers SCO vs Lille OSC | 主胜22% 平29% 客胜49% | 比分[0-1(17%)  1-1(12%)  0-2(11%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Le Havre AC vs AS Monaco FC | 主胜22% 平24% 客胜54% | 比分[1-2(10%)  1-1(10%)  0-2(9%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Paris Saint-Germain FC vs Stade Rennais FC 1901 | 主胜71% 平19% 客胜9% | 比分[3-1(9%)  2-1(9%)  2-0(8%)] | 置信中
   盘口：合成演示水位（无 --live 或抓取失败）
Brighton & Hove Albion FC vs Aston Villa FC | 主胜39% 平27% 客胜34% | 比分[1-1(11%)  1-2(9%)  2-1(8%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Manchester City FC vs AFC Bournemouth | 主胜64% 平21% 客胜14% | 比分[2-1(10%)  2-0(9%)  3-1(8%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Newcastle United FC vs Liverpool FC | 主胜31% 平26% 客胜44% | 比分[1-1(10%)  1-2(9%)  2-1(7%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Club Atlético de Madrid vs Villarreal CF | 主胜56% 平24% 客胜20% | 比分[2-1(10%)  1-1(9%)  2-0(9%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Elche CF vs FC Barcelona | 主胜33% 平27% 客胜40% | 比分[1-1(12%)  0-1(9%)  1-2(8%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Getafe CF vs Real Racing Club de Santander | 主胜32% 平30% 客胜39% | 比分[1-1(13%)  0-1(12%)  0-0(9%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
AS Roma vs ACF Fiorentina | 主胜47% 平28% 客胜25% | 比分[1-1(12%)  1-0(10%)  2-1(9%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Bologna FC 1909 vs SS Lazio | 主胜46% 平29% 客胜26% | 比分[1-1(13%)  1-0(12%)  2-1(9%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Fulham FC vs Chelsea FC | 主胜32% 平26% 客胜41% | 比分[1-1(11%)  1-2(9%)  0-1(9%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
CA Osasuna vs Levante UD | 主胜53% 平25% 客胜22% | 比分[2-1(10%)  1-1(9%)  2-0(7%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Málaga CF vs RC Deportivo La Coruña | 主胜45% 平28% 客胜27% | 比分[1-1(11%)  2-1(9%)  1-0(8%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Nagoya Grampus vs Kawasaki Frontale | 主胜45% 平26% 客胜29% | 比分[1-1(10%)  2-1(9%)  1-0(8%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）
Sagan Tosu vs Avispa Fukuoka | 主胜45% 平26% 客胜30% | 比分[1-1(10%)  2-1(9%)  1-2(8%)] | 置信低
   盘口：合成演示水位（无 --live 或抓取失败）

[fetch] 预测结果已保存：d:\足彩\data\processed\fetch_predictions.json
[fetch] 界面版（真实训练+实时盘口）：python main.py serve --csv data/raw/historical_real.csv --live 以重建 ，确保自动化任务数据源正确。

