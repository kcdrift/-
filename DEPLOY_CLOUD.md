# 足彩预测系统 · 免费云端部署指南（不常开电脑 · 固定域名 · 实时）

## 结论先讲
你「免费 + 稳定 + 不常开电脑」三个条件，同时满足的只有**云端托管**（Render / Railway / Fly.io 一类）。
- ✅ 免费：有免费额度
- ✅ 域名固定：`xxx.onrender.com`（注册后永久不变，不用来回换）
- ✅ 不用你电脑常开：服务跑在云平台
- ✅ 实时：Flask 常驻，盘口实时拉取
- ⚠️ 唯一代价：境外节点拉不到「中国体彩」，**盘口源自动降级为 The Odds API（海外真实赔率，同样是真钱市场价）**。预测引擎不变，历史命中率（方向 60% / 比分 70%）不受影响。

> 若你非要「体彩源」又要「免费」，目前无解——体彩网是境内源，免费境外平台进不去；本地隧道方案必须买域名 + 电脑常开（你要的「不常开」就破了）。

---

## 已为你备好的部分（不用你做）
- `web/app.py` 已支持云平台注入的 `PORT` 环境变量 + `0.0.0.0`（已本地验证：注入 PORT=9001 正常起服务，返回 212 场预测）。
- `render.yaml` / `requirements.txt`：Render 部署配置，项目零第三方依赖，部署极简。
- Git 仓库已在 `D:\足彩` 初始化并提交（commit `daaafce`），密钥 `.env` 已排除。

---

## 你只需做 3 步（按顺序）

### 第 1 步：把代码推到 GitHub（一次性）
1. 注册 / 登录 github.com（免费）。
2. 新建一个空仓库，例如 `zucai-predict`。
3. 在本地项目目录 `D:\足彩` 执行（把 `<你的用户名>/<仓库名>` 换成你的）：
   ```bash
   git remote add origin https://github.com/<你的用户名>/<仓库名>.git
   git branch -M main
   git push -u origin main
   ```
   （若提示登录，按弹窗用你的 GitHub 账号授权即可。）

### 第 2 步：Render 连 GitHub 部署（一次性）
1. 打开 https://dashboard.render.com 注册 / 登录（可用 GitHub 直接授权）。
2. 点 **New → Web Service**，选 **Build and deploy from a Git repository** → 授权并选你刚推的仓库。
3. 配置（Render 会自动读 `render.yaml`，一般无需改）：
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：`python web/app.py`
   - **Instance Type**：选 **Free**
4. 展开 **Environment → Add Environment Variable**，加一条：
   - `ODDS_API_KEY` = 你的 The Odds API key（没有的话去 https://www.theoddsapi.com 免费注册，免费层够用；不填也能跑，只是盘口退化为纯模型合成）
5. 点 **Deploy**。约 1–2 分钟构建完，得到固定网址 `https://<服务名>.onrender.com`。

### 第 3 步：验证
打开 `https://<服务名>.onrender.com`，能看到预测页面且盘口为真实赔率即成功。

---

## 关于「稳定」的现实提示
- **Render 免费版会在无访问约 15 分钟后休眠**，首次访问要冷启动（约 30 秒）。若你要它「随时秒开」，有两个办法：
  1. **升级付费**（约 $7/月，永远在线）——最省心。
  2. **免费保活**：用 WorkBuddy 设一个「每 10 分钟访问一次你的网址」的定时任务（轻量 ping），能大幅减少休眠。但这依赖 WorkBuddy 在线，非 100% 保证；若你要 7×24 稳定，建议直接升级付费档。
- 域名固定不变：无论免费还是付费，`<服务名>.onrender.com` 永久同一个，换机器/重部署都不影响。

---

## 数据更新说明
- 盘口：部署后实时拉取，**无需你操作**。
- 赛程/历史模型：随代码一起部署；若日后想更新赛果复盘，重新 `git push` 即可重新部署（或开 Render 的 Auto-Deploy）。
- 本地 `scripts/build_static_site.py` 是用于「Cloudflare Pages 静态版」的快照生成，本方案（实时版）不需要。

---

## 备选：Railway（同样免费 + 固定域名）
若 Render 排队/受限，可改用 https://railway.app ：连 GitHub 后选仓库，Build/Start 同上述，域名形如 `xxx.up.railway.app`。配置方式几乎一样。
