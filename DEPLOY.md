# 足彩预测站 · 公网部署指南（双保险）

> 目标：朋友用手机/移动网络随时打开固定网址看预测。两套方案并存，互不冲突。

## 当前产出状态
- `web/mobile/` 已是「静态前端 + JSON」形态，已验证可独立托管。
- `web/mobile/index.html`：手机端页面，优先读 `/api/predictions`（本地后端），不可用时自动回退 `snapshot.json`（无后端环境）。
- `web/mobile/snapshot.json`：最新快照（2026-08-24 生成，8 场，含中国体彩真实盘口）。
- 生成脚本：`scripts/build_static_site.py --live`（重新生成 `snapshot.json`，先自动备份旧档）。

---

## 路径1：Cloudflare Pages（静态 · 每日快照 · 推荐首选）

适合：固定 `xxx.pages.dev` 域名、免费、不用买域名、不用电脑常开、不用常驻服务器。
代价：盘口是「生成时的快照」，不是比赛进行中实时刷新（赛前预测/复盘够用）。

### 方式 A：Dashboard 直接上传（最稳，无需 CLI 登录）
1. 打开 Cloudflare 控制台 → 左侧 **Workers & Pages** → **Create** → **Pages** → **Upload assets**。
2. 项目名填 `zucai`（或自定义），把本地文件夹 `D:\足彩\web\mobile` 整个拖进去上传。
3. 部署完成后获得 `https://zucai.pages.dev`（子域名可改）。
4. 更新数据：本地跑 `python scripts/build_static_site.py --live` 重新生成 `snapshot.json`，再回来「Upload assets」重传 `web/mobile` 即可。

### 方式 B：GitHub 自动部署（省去每次手动上传）
1. 项目目录初始化 git（注意：`.gitignore` 排除 `.env` 与 `.workbuddy/`，避免泄露 key 与项目数据）。
2. Cloudflare Pages 连接 GitHub 仓库，`build command` 留空，`output directory` 填 `web/mobile`。
3. 之后每次 `git push` 自动重新部署。可配合本地定时任务每日重算 `snapshot.json` 再 push。

---

## 路径2：Render（实时 Flask · 原样跑后端）

适合：固定 `xxx.onrender.com` 域名、保持实时盘口、原样跑现有 Flask 后端。
代价：离开 Cloudflare 生态；免费实例会休眠（15 分钟无请求后），首次访问需几秒唤醒。

### 已改动（就绪）
- `web/app.py` 的 `run()` 已支持云平台注入的 `PORT` 环境变量并监听 `0.0.0.0`。
- `render.yaml` 已就绪（build/start 指令 + Python 3.13）。
- 项目零第三方依赖（纯标准库 + 本地模块），`requirements.txt` 已生成。

### 部署步骤
1. 把项目推到 GitHub（同上 `.gitignore` 排除 `.env`、`.workbuddy/`）。
2. Render 控制台 → **New** → **Web Service** → 连接该仓库。
3. 配置（或直接用 `render.yaml`）：
   - Build Command：`pip install -r requirements.txt`
   - Start Command：`python web/app.py`
   - 环境变量：`FOOTBALL_DATA_API_KEY`（可选，实时盘口用）。
4. 部署后获得 `https://zucai-football.onrender.com`。

### ⚠️ 已知风险（务必知道）
- **体彩网在海外服务器可能受限**：Render 节点在境外，访问 `webapi.sporttery.cn`（国内免费盘口）可能慢或被拒，实时盘口会退化为「合成演示盘口」。若需真实盘口，建议 Render 上改用 `football-data.org`（海外可访问），或仅在本地生成快照走路径1。
- **赛程时效性**：默认非 live 模式用本地 `data/raw/upcoming_clean_v4_*.csv`。若此 CSV 过期而你未重新生成并推送，Render 上看到的赛程会变旧。需本地定时重算并 push，或让 app 在缺赛程时自动抓 `football-data.org`。
- **休眠唤醒**：免费版长时间无访问会停，首访延迟数秒，属正常。

---

## 每日更新策略（两套通用）
本地起定时任务跑：`python scripts/build_static_site.py --live` 生成 `snapshot.json`。
- Pages：重传 `web/mobile`（或 git push 触发）。
- Render：把新赛程/快照推到 GitHub 触发重部署（或直接依赖 app 启动自动抓源）。

## 不推荐的做法
- 不要直接 `rm` / 清空个人目录；项目数据在 `D:\足彩`，请勿误删 `.workbuddy`。
- 旧 `web/mobile/static_data.json` 被某进程占用无法改名/删除，已改用 `snapshot.json`，旧文件暂不处理（无害，待解锁后清理）。
