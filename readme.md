<p align="center">
  <a href="https://www.ipwo.net/?ref=githubReinerBRO">
    <img src="downloads/IPWO.png" alt="IPWO住宅代理" width="720">
  </a>
</p>

> [IPWO住宅代理](https://www.ipwo.net/?ref=githubReinerBRO) 覆盖 195+ 地区动态住宅代理、静态住宅代理和不限量住宅代理，支持 HTTP、HTTPS 及 SOCKS5 协议，可与 Grok 等 AI 工具及自动化项目结合使用。
>
> 适用于浏览器自动化、AI 应用、API 访问及多地区网络环境等开发场景。支持免费测试，专属折扣码：`0205`

---

# Grok 账号批量注册工具

基于 [DrissionPage](https://github.com/g1879/DrissionPage) 的 Grok (x.ai) 账号自动注册脚本，使用 [DuckMail](https://duckmail.sbs) 临时邮箱接收验证码，通过 Chrome 扩展修复 CDP `MouseEvent.screenX/screenY` 缺陷绕过 Cloudflare Turnstile。

注册完成后自动推送 SSO token 到 [grok2api](https://github.com/chenyme/grok2api) 号池。

## 特性

- DuckMail 临时邮箱（`curl_cffi` TLS 指纹伪装）
- Cloudflare Turnstile 自动绕过（Chrome 扩展 patch `MouseEvent.screenX/screenY`）
- 无头服务器支持（Xvfb 虚拟显示器，自动检测 Linux 环境）
- 中英文界面自动适配
- 自动推送 SSO token 到 grok2api（支持 append 合并模式）

---

## 环境要求

- Python 3.10+
- Chromium 或 Chrome 浏览器
- [DuckMail](https://duckmail.sbs) 账号（用于创建临时邮箱）
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

编辑 `config.json`：

```json
{
    "run": { "count": 10 },
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

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `run.count` | int | 注册轮数，`0` 为无限循环，可通过 `--count` 覆盖 |
| `duckmail_api_base` | string | DuckMail API 地址，默认 `https://api.duckmail.sbs` |
| `duckmail_bearer` | string | DuckMail Bearer Token（[获取方式](#获取-duckmail-bearer-token)） |
| `proxy` | string | DuckMail API 请求代理（可选） |
| `browser_proxy` | string | 浏览器代理，无头服务器需翻墙时填写（可选） |
| `api.endpoint` | string | grok2api 管理接口地址，留空跳过推送 |
| `api.token` | string | grok2api 的 `app_key` |
| `api.append` | bool | `true` 合并线上已有 token，`false` 覆盖 |

---

## 获取 DuckMail Bearer Token

1. 打开 [duckmail.sbs](https://duckmail.sbs) 并注册登录
2. 打开浏览器开发者工具 (F12) → Network
3. 刷新页面，找到任意发往 `api.duckmail.sbs` 的请求
4. 复制请求头中 `Authorization: Bearer <token>` 里的 token
5. 填入 `config.json` 的 `duckmail_bearer` 字段

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
├── DrissionPage_example.py     # 主脚本
├── email_register.py           # DuckMail 临时邮箱封装
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
- [DuckMail](https://duckmail.sbs) — 临时邮箱服务
