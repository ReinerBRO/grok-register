# Grok 账号批量注册工具

基于 [DrissionPage](https://github.com/g1879/DrissionPage) 的 Grok (x.ai) 账号自动注册脚本，支持 [Cloudflare Worker 临时邮箱 (freemail)](https://github.com/idinging/freemail) 和 [DuckMail](https://duckmail.sbs) 两种邮箱服务接收验证码，通过 Chrome 扩展修复 CDP `MouseEvent.screenX/screenY` 缺陷绕过 Cloudflare Turnstile。

注册完成后自动推送 SSO token 到 [grok2api](https://github.com/chenyme/grok2api) 号池。

## 特性

- **双邮箱提供商支持**：Cloudflare Worker 临时邮箱 / DuckMail，通过配置一键切换
- Cloudflare Turnstile 自动绕过（Chrome 扩展 patch `MouseEvent.screenX/screenY`）
- `curl_cffi` TLS 指纹伪装
- 无头服务器支持（Xvfb 虚拟显示器，自动检测 Linux 环境）
- 中英文界面自动适配
- 自动推送 SSO token 到 grok2api（支持 append 合并模式）

---

## 环境要求

- Python 3.10+
- Chromium 或 Chrome 浏览器
- 临时邮箱服务（二选一）：
  - [Cloudflare Worker 临时邮箱 (freemail)](https://github.com/idinging/freemail)（推荐，自建部署）
  - [DuckMail](https://duckmail.sbs) 账号
- 可选：[grok2api](https://github.com/chenyme/grok2api) 实例（用于自动导入 SSO token）

---

## 安装

```bash
pip install -r requirements.txt
```

无头服务器（Linux）额外安装：

```bash
apt install -y xvfb
pip install PyVirtualDisplay
# 推荐用 playwright 装 chromium（避免 snap 版 AppArmor 限制）
pip install playwright && python -m playwright install chromium && python -m playwright install-deps chromium
```

---

## 配置文件（config.json）

```bash
cp config.example.json config.json
```

编辑 `config.json`，根据使用的邮箱服务选择对应配置：

### 方式一：Cloudflare Worker 临时邮箱（推荐）

```json
{
    "run": { "count": 10 },
    "mail_provider": "cloudflare",
    "cf_mail_api_base": "https://your-cf-worker.example.com",
    "cf_mail_token": "<your_cf_mail_bearer_token>",
    "proxy": "",
    "browser_proxy": "",
    "api": {
        "endpoint": "",
        "token": "",
        "append": true
    }
}
```

### 方式二：DuckMail 临时邮箱

```json
{
    "run": { "count": 10 },
    "mail_provider": "duckmail",
    "duckmail_api_base": "https://api.duckmail.sbs",
    "duckmail_bearer": "<your_duckmail_bearer_token>",
    "proxy": "",
    "browser_proxy": "",
    "api": {
        "endpoint": "",
        "token": "",
        "append": true
    }
}
```

> **提示**：`mail_provider` 不填或缺省时默认为 `"duckmail"`，兼容旧版配置。

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `run.count` | int | 注册轮数，`0` 为无限循环，可通过 `--count` 覆盖 |
| `mail_provider` | string | 邮箱提供商：`"cloudflare"` 或 `"duckmail"`（默认） |
| `cf_mail_api_base` | string | Cloudflare Worker 邮箱服务 API 地址 |
| `cf_mail_token` | string | Cloudflare Worker 邮箱服务 Bearer Token |
| `duckmail_api_base` | string | DuckMail API 地址，默认 `https://api.duckmail.sbs` |
| `duckmail_bearer` | string | DuckMail Bearer Token（[获取方式](#获取-duckmail-bearer-token)） |
| `proxy` | string | 邮箱 API 请求代理（可选） |
| `browser_proxy` | string | 浏览器代理，无头服务器需翻墙时填写（可选） |
| `api.endpoint` | string | grok2api 管理接口地址，留空跳过推送 |
| `api.token` | string | grok2api 的 `app_key` |
| `api.append` | bool | `true` 合并线上已有 token，`false` 覆盖 |

---

## 邮箱服务配置

### Cloudflare Worker 临时邮箱 (freemail)

使用 [freemail](https://github.com/idinging/freemail) 项目在 Cloudflare 上自建临时邮箱服务。部署方法参见 freemail 项目文档。

该服务提供以下 API：
- `GET /api/generate` — 自动创建临时邮箱，返回邮箱地址
- `GET /api/emails?mailbox=<address>` — 获取指定邮箱的邮件列表
- `GET /api/email/<id>` — 获取单封邮件详情

配置项：
1. 将 `mail_provider` 设为 `"cloudflare"`
2. 填写 `cf_mail_api_base`（Worker 部署地址）
3. 填写 `cf_mail_token`（Bearer Token）

### 获取 DuckMail Bearer Token

1. 打开 [duckmail.sbs](https://duckmail.sbs) 并注册登录
2. 打开浏览器开发者工具 (F12) → Network
3. 刷新页面，找到任意发往 `api.duckmail.sbs` 的请求
4. 复制请求头中 `Authorization: Bearer <token>` 里的 token
5. 将 `mail_provider` 设为 `"duckmail"`，填入 `duckmail_bearer` 字段

---

## 启动方式

```bash
# 按 config.json 中 run.count 执行（默认 10 轮）
python DrissionPage_example.py

# 指定轮数
python DrissionPage_example.py --count 50

# 无限循环
python DrissionPage_example.py --count 0
```

无头服务器会自动启用 Xvfb，无需额外配置。

---

## 输出文件

```
sso/
  sso_<timestamp>.txt     ← 每行一个 SSO token
logs/
  run_<timestamp>.log     ← 每轮注册的邮箱、密码和结果
```

目录在首次运行时自动创建。

---

## 文件结构

```
├── DrissionPage_example.py     # 主脚本（浏览器自动化）
├── email_register.py           # 邮箱服务封装（支持 Cloudflare Worker / DuckMail）
├── config.json                 # 配置文件（不入库）
├── config.example.json         # 配置模板
├── requirements.txt            # Python 依赖
├── turnstilePatch/             # Chrome 扩展（Turnstile patch）
│   ├── manifest.json
│   └── script.js
├── sso/                        # SSO token 输出（自动创建）
└── logs/                       # 运行日志（自动创建）
```

---

## 无头服务器部署注意

- snap 版 chromium 在 root 下有 AppArmor 限制，推荐用 playwright 安装的 chromium
- 服务器直连 x.ai 可能被墙，需在 `browser_proxy` 填写代理地址
- 脚本自动检测 Linux 环境并启用 Xvfb + playwright chromium 路径

---

## 致谢

- [kevinr229/grok-maintainer](https://github.com/kevinr229/grok-maintainer) — 原始项目
- [grok2api](https://github.com/chenyme/grok2api) — Grok API 代理
- [freemail](https://github.com/idinging/freemail) — Cloudflare Worker 临时邮箱服务
- [DuckMail](https://duckmail.sbs) — 临时邮箱服务
