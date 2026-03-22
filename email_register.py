
from __future__ import annotations

import json
import logging
import random
import re
import string
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# 邮箱配置（从 config.json 加载）
# ============================================================

_config_path = Path(__file__).parent / "config.json"
_conf: Dict[str, Any] = {}
if _config_path.exists():
    with _config_path.open("r", encoding="utf-8") as _f:
        _conf = json.load(_f)

# 邮箱提供商: "duckmail" (默认) 或 "cloudflare"
MAIL_PROVIDER = str(_conf.get("mail_provider", "duckmail")).strip().lower()

# DuckMail 配置
DUCKMAIL_API_BASE = str(_conf.get("duckmail_api_base", "https://api.duckmail.sbs"))
DUCKMAIL_BEARER = str(_conf.get("duckmail_bearer", ""))
PROXY = str(_conf.get("proxy", ""))

# Cloudflare Worker 临时邮箱配置
CF_MAIL_API_BASE = str(_conf.get("cf_mail_api_base", "")).rstrip("/")
CF_MAIL_TOKEN = str(_conf.get("cf_mail_token", ""))

# ============================================================
# 适配层：为 DrissionPage_example.py 提供简单接口
# ============================================================

_temp_email_cache: Dict[str, str] = {}


def get_email_and_token() -> Tuple[Optional[str], Optional[str]]:
    """
    创建临时邮箱并返回 (email, mail_token)。
    供 DrissionPage_example.py 调用。
    根据 mail_provider 配置自动选择 DuckMail 或 Cloudflare Worker。
    """
    if MAIL_PROVIDER == "cloudflare":
        email = create_temp_email_cf()
        if email:
            # CF 模式下用邮箱地址本身作为 "token" (查询邮件时使用)
            _temp_email_cache[email] = email
            return email, email
        return None, None
    else:
        email, _password, mail_token = create_temp_email()
        if email and mail_token:
            _temp_email_cache[email] = mail_token
            return email, mail_token
        return None, None


def get_oai_code(dev_token: str, email: str, timeout: int = 30) -> Optional[str]:
    """
    轮询获取 OTP 验证码。
    供 DrissionPage_example.py 调用。
    根据 mail_provider 配置自动选择 DuckMail 或 Cloudflare Worker。

    Returns:
        验证码字符串（去除连字符，如 "MM0SF3"）或 None
    """
    if MAIL_PROVIDER == "cloudflare":
        # CF 模式下 dev_token 实际是邮箱地址
        code = wait_for_verification_code_cf(email_address=dev_token, timeout=timeout)
    else:
        code = wait_for_verification_code(mail_token=dev_token, timeout=timeout)
    if code:
        code = code.replace("-", "")
    return code


# ============================================================
# DuckMail 核心函数
# ============================================================

def _create_duckmail_session():
    """创建 DuckMail 请求会话（优先 curl_cffi 绕 TLS 指纹）"""
    if curl_requests:
        session = curl_requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        if PROXY:
            session.proxies = {"http": PROXY, "https": PROXY}
        return session, True

    # fallback to requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    if PROXY:
        s.proxies = {"http": PROXY, "https": PROXY}
    return s, False


def _do_request(session, use_cffi, method, url, **kwargs):
    """统一请求，curl_cffi 加 impersonate 参数"""
    if use_cffi:
        kwargs.setdefault("impersonate", "chrome131")
    return getattr(session, method)(url, **kwargs)


def _generate_password(length=14):
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%"
    pwd = [random.choice(lower), random.choice(upper),
           random.choice(digits), random.choice(special)]
    all_chars = lower + upper + digits + special
    pwd += [random.choice(all_chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return "".join(pwd)


def create_temp_email() -> Tuple[str, str, str]:
    """创建 DuckMail 临时邮箱，返回 (email, password, mail_token)"""
    if not DUCKMAIL_BEARER:
        raise Exception("duckmail_bearer 未设置，无法创建临时邮箱")

    chars = string.ascii_lowercase + string.digits
    length = random.randint(8, 13)
    email_local = "".join(random.choice(chars) for _ in range(length))
    email = f"{email_local}@duckmail.sbs"
    password = _generate_password()

    api_base = DUCKMAIL_API_BASE.rstrip("/")
    bearer_headers = {"Authorization": f"Bearer {DUCKMAIL_BEARER}"}
    session, use_cffi = _create_duckmail_session()

    try:
        # 1. 创建账号
        res = _do_request(session, use_cffi, "post",
                          f"{api_base}/accounts",
                          json={"address": email, "password": password},
                          headers=bearer_headers, timeout=15)
        if res.status_code not in (200, 201):
            raise Exception(f"创建邮箱失败: {res.status_code} - {res.text[:200]}")

        # 2. 获取 mail token
        time.sleep(0.5)
        token_res = _do_request(session, use_cffi, "post",
                                f"{api_base}/token",
                                json={"address": email, "password": password},
                                timeout=15)
        if token_res.status_code == 200:
            mail_token = token_res.json().get("token")
            if mail_token:
                print(f"[*] DuckMail 临时邮箱创建成功: {email}")
                return email, password, mail_token

        raise Exception(f"获取邮件 Token 失败: {token_res.status_code}")
    except Exception as e:
        raise Exception(f"DuckMail 创建邮箱失败: {e}")


def fetch_emails(mail_token: str) -> List[Dict[str, Any]]:
    """获取 DuckMail 邮件列表"""
    try:
        api_base = DUCKMAIL_API_BASE.rstrip("/")
        headers = {"Authorization": f"Bearer {mail_token}"}
        session, use_cffi = _create_duckmail_session()
        res = _do_request(session, use_cffi, "get",
                          f"{api_base}/messages",
                          headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            return data.get("hydra:member") or data.get("member") or data.get("data") or []
    except Exception:
        pass
    return []


def fetch_email_detail(mail_token: str, msg_id: str) -> Optional[Dict]:
    """获取 DuckMail 单封邮件详情"""
    try:
        api_base = DUCKMAIL_API_BASE.rstrip("/")
        headers = {"Authorization": f"Bearer {mail_token}"}
        session, use_cffi = _create_duckmail_session()

        if isinstance(msg_id, str) and msg_id.startswith("/messages/"):
            msg_id = msg_id.split("/")[-1]

        res = _do_request(session, use_cffi, "get",
                          f"{api_base}/messages/{msg_id}",
                          headers=headers, timeout=15)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def wait_for_verification_code(mail_token: str, timeout: int = 120) -> Optional[str]:
    """轮询 DuckMail 等待验证码邮件"""
    start = time.time()
    seen_ids = set()

    while time.time() - start < timeout:
        messages = fetch_emails(mail_token)
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            msg_id = msg.get("id") or msg.get("@id")
            if not msg_id or msg_id in seen_ids:
                continue
            seen_ids.add(msg_id)

            detail = fetch_email_detail(mail_token, str(msg_id))
            if detail:
                content = detail.get("text") or detail.get("html") or ""
                code = extract_verification_code(content)
                if code:
                    print(f"[*] 从 DuckMail 提取到验证码: {code}")
                    return code
        time.sleep(3)
    return None


def extract_verification_code(content: str) -> Optional[str]:
    """
    从邮件内容提取验证码。
    Grok/x.ai 格式：MM0-SF3（3位-3位字母数字混合）或 6 位纯数字。
    """
    if not content:
        return None

    # 模式 1: Grok 格式 XXX-XXX
    m = re.search(r"(?<![A-Z0-9-])([A-Z0-9]{3}-[A-Z0-9]{3})(?![A-Z0-9-])", content)
    if m:
        return m.group(1)

    # 模式 2: 带标签的验证码
    m = re.search(r"(?:verification code|验证码|your code)[:\s]*[<>\s]*([A-Z0-9]{3}-[A-Z0-9]{3})\b", content, re.IGNORECASE)
    if m:
        return m.group(1)

    # 模式 3: HTML 样式包裹
    m = re.search(r"background-color:\s*#F3F3F3[^>]*>[\s\S]*?([A-Z0-9]{3}-[A-Z0-9]{3})[\s\S]*?</p>", content)
    if m:
        return m.group(1)

    # 模式 4: Subject 行 6 位数字
    m = re.search(r"Subject:.*?(\d{6})", content)
    if m and m.group(1) != "177010":
        return m.group(1)

    # 模式 5: HTML 标签内 6 位数字
    for code in re.findall(r">\s*(\d{6})\s*<", content):
        if code != "177010":
            return code

    # 模式 6: 独立 6 位数字
    for code in re.findall(r"(?<![&#\d])(\d{6})(?![&#\d])", content):
        if code != "177010":
            return code

    return None


# ============================================================
# Cloudflare Worker 临时邮箱 (基于 https://github.com/idinging/freemail)
# ============================================================

def _create_cf_mail_session():
    """创建 Cloudflare Worker 请求会话（带 Bearer Token）"""
    if curl_requests:
        session = curl_requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Authorization": f"Bearer {CF_MAIL_TOKEN}",
        })
        if PROXY:
            session.proxies = {"http": PROXY, "https": PROXY}
        return session, True

    # fallback to requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Authorization": f"Bearer {CF_MAIL_TOKEN}",
    })
    if PROXY:
        s.proxies = {"http": PROXY, "https": PROXY}
    return s, False


def create_temp_email_cf() -> Optional[str]:
    """通过 Cloudflare Worker 创建临时邮箱，返回 email 地址"""
    if not CF_MAIL_API_BASE or not CF_MAIL_TOKEN:
        raise Exception("cf_mail_api_base 或 cf_mail_token 未设置")

    session, use_cffi = _create_cf_mail_session()
    try:
        res = _do_request(session, use_cffi, "get",
                          f"{CF_MAIL_API_BASE}/api/generate",
                          timeout=15)
        if res.status_code == 200:
            data = res.json()
            email = data.get("email")
            if email:
                print(f"[*] CF Worker 临时邮箱创建成功: {email}")
                return email
        raise Exception(f"创建邮箱失败: {res.status_code} - {res.text[:200]}")
    except Exception as e:
        raise Exception(f"CF Worker 创建邮箱失败: {e}")


def fetch_emails_cf(email_address: str) -> List[Dict[str, Any]]:
    """从 Cloudflare Worker 获取邮件列表"""
    try:
        session, use_cffi = _create_cf_mail_session()
        res = _do_request(session, use_cffi, "get",
                          f"{CF_MAIL_API_BASE}/api/emails",
                          params={"mailbox": email_address},
                          timeout=15)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


def fetch_email_detail_cf(email_id) -> Optional[Dict]:
    """获取 Cloudflare Worker 单封邮件详情"""
    try:
        session, use_cffi = _create_cf_mail_session()
        res = _do_request(session, use_cffi, "get",
                          f"{CF_MAIL_API_BASE}/api/email/{email_id}",
                          timeout=15)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def wait_for_verification_code_cf(email_address: str, timeout: int = 120) -> Optional[str]:
    """轮询 Cloudflare Worker 等待验证码邮件"""
    print(f"[*] CF Worker 等待验证码邮件 ({email_address}, 最多 {timeout}s)...")
    start = time.time()

    while time.time() - start < timeout:
        messages = fetch_emails_cf(email_address)
        if messages and len(messages) > 0:
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                # CF Worker 可能已自动提取 verification_code
                code = msg.get("verification_code")
                if code:
                    print(f"[*] CF Worker 提取到验证码: {code}")
                    return str(code)
                # fallback: 获取邮件详情并解析
                msg_id = msg.get("id")
                if msg_id:
                    detail = fetch_email_detail_cf(msg_id)
                    if detail:
                        content = (
                            detail.get("content")
                            or detail.get("html_content")
                            or detail.get("text")
                            or detail.get("html")
                            or ""
                        )
                        code = extract_verification_code(content)
                        if code:
                            print(f"[*] CF Worker 从邮件详情提取到验证码: {code}")
                            return code

        elapsed = int(time.time() - start)
        print(f"[*] CF Worker 等待中... ({elapsed}s/{timeout}s)")
        time.sleep(3)

    print(f"[*] CF Worker 等待验证码超时 ({timeout}s)")
    return None
