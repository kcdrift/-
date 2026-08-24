# 固定域名部署方案（Cloudflare Tunnel + 本地常开）

目标：**实盘真实盘口 + 域名永久固定 + 实时同步**。本地 Flask 已在 8080 常开，Cloudflared 已安装（2026.8.2）。

## 整体链路
```
你的电脑（常开）                 Cloudflare              手机/任意网络
Flask :8080  ── cloudflared ──▶  Tunnel  ──▶  https://你的域名（永久不变）
   (体彩实时盘口)      (固定隧道)      (固定域名)
```

## 一、你需要做的事（我无法代劳：涉及付款与控制台操作）

1. **买一个域名**（约 60–100 元/年）
   - 推荐在 Cloudflare 控制台 `Registrar` 直接买 `.top` / `.site` / `.xyz`（最省事，买完自动接入 Cloudflare）。
   - 或在阿里云/腾讯云买，再到 Cloudflare 控制台 `Add Site` 改 NS 为 Cloudflare 的 nameserver。
   - 建议名：`zucai.top` / `zucai888.top` / `zucai666.site`（先查可注册）。

2. **确认域名在 Cloudflare 已是 Active**（NS 生效，通常几分钟到几小时）。

3. **创建 Cloudflare Tunnel 并拿 token**
   - Cloudflare 控制台 → `Zero Trust`（或 `Cloudflare One`）→ `Networks` → `Tunnels` → `Create a tunnel` → 选 `Cloudflared`。
   - 创建后进入 tunnel，复制页面给出的连接命令里的 **token**（一长串，形如 `eyJ...`）。
   - 这一步也会生成 Public Hostname 配置：把你的域名（如 `zucai.top` 或 `www.zucai.top`）指向 `http://localhost:8080`。

## 二、我来做 / 已完成

- ✅ `web/app.py` 已支持云平台 `$PORT` 与 `0.0.0.0`（上云/隧道通用）。
- ✅ 本地 Flask 已在 8080 常开（PID 68964）。
- ✅ `scripts/start_tunnel.bat`：自动检测 8080，拉起 Cloudflared 固定隧道（token 待填）。
- ⏳ 你给 token 后，我把 token 写入脚本并启动，验证 `https://你的域名` 可访问。

## 三、拿到 token 后的操作（你确认后我执行）

1. 把 token 发给我（或直接自己填进 `scripts/start_tunnel.bat` 的 `set TOKEN=` 行）。
2. 运行 `scripts/start_tunnel.bat`，隧道常驻，域名即固定可用。
3. 浏览器开 `https://你的域名` 验证：首页加载、盘口为体彩实时数据。

## 四、开机自启（让「常开」真正自动）

- 最简单：把 `start_tunnel.bat` 快捷方式放进 `shell:startup`（Win+R 输入）。
- 更稳（无登录也跑）：用 Task Scheduler 建一个「系统启动」触发任务，运行 `start_tunnel.bat`。我可以帮你写这条计划任务（需你确认）。

## 五、风险与注意

- **域名年费**：每年要续费，过期域名失效 + 隧道断开。
- **电脑必须常开**：隧道依赖你这台电脑上的 Flask。关机/断网 = 网站不可用。
- **不要删 `.workbuddy` 文件夹**：含项目数据与自动化，非缓存。
- **URL 不变性**：Named Tunnel 绑定域名，重启 Cloudflared / 重连都不会改变网址——正好满足「不要变来变去」。
