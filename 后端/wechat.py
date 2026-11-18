"""微信登录 OAuth 客户端（公众号/测试号网页授权，或开放平台网站应用扫码）

配置文件：server/.env 或项目根目录 .env，也可直接设置环境变量
    WECHAT_APPID=wx1234567890abcdef
    WECHAT_APPSECRET=0123456789abcdef0123456789abcdef
    WECHAT_MODE=mp                       # mp=公众号网页授权（默认）；open=开放平台网站应用
    WECHAT_REDIRECT_URI=https://你的域名/api/auth/wechat/callback
    WECHAT_SCOPE=snsapi_userinfo         # open 模式固定为 snsapi_login

未配置 WECHAT_APPID / WECHAT_APPSECRET 时 is_configured() 为 False，
接口会明确返回“未配置”，不会生成任何伪造账号。
"""
import io
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = Path(__file__).resolve().parent


def load_env():
    """读取 .env（不覆盖已有环境变量）"""
    for path in (BASE / ".env", BASE.parent / ".env"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

APPID = os.getenv("WECHAT_APPID", "").strip()
APPSECRET = os.getenv("WECHAT_APPSECRET", "").strip()
MODE = os.getenv("WECHAT_MODE", "mp").strip().lower() or "mp"
REDIRECT_URI = os.getenv("WECHAT_REDIRECT_URI", "").strip()
SCOPE = os.getenv("WECHAT_SCOPE", "snsapi_userinfo").strip() or "snsapi_userinfo"

STATE_TTL = 600          # state 有效期（秒）
_PENDING = {}            # state -> {created, redirect, status, token, user, error}
_LOCK = threading.Lock()


def is_configured() -> bool:
    return bool(APPID and APPSECRET)


def redirect_uri(fallback: str = "") -> str:
    return REDIRECT_URI or fallback


def mode_text() -> str:
    if not is_configured():
        return "未配置"
    return "开放平台扫码" if MODE == "open" else "公众号网页授权"


# ------------------------------------------------------------------ state
def new_state(redirect: str = "") -> str:
    state = secrets.token_urlsafe(18)
    now = time.time()
    with _LOCK:
        for k in [k for k, v in _PENDING.items() if now - v["created"] > STATE_TTL]:
            _PENDING.pop(k, None)
        _PENDING[state] = {"created": now, "redirect": redirect, "status": "pending"}
    return state


def get_state(state: str):
    with _LOCK:
        rec = _PENDING.get(state)
        if not rec:
            return None
        if time.time() - rec["created"] > STATE_TTL:
            _PENDING.pop(state, None)
            return None
        return rec


def resolve(state: str, token: str = "", user: dict = None, error: str = ""):
    with _LOCK:
        rec = _PENDING.get(state)
        if not rec:
            return
        if error:
            rec.update(status="error", error=error)
        else:
            rec.update(status="ok", token=token, user=user or {})


# ------------------------------------------------------------------ 微信接口
def authorize_url(callback: str, state: str) -> str:
    if MODE == "open":
        params = {
            "appid": APPID, "redirect_uri": callback, "response_type": "code",
            "scope": "snsapi_login", "state": state,
        }
        return "https://open.weixin.qq.com/connect/qrconnect?" + urlencode(params) + "#wechat_redirect"
    params = {
        "appid": APPID, "redirect_uri": callback, "response_type": "code",
        "scope": SCOPE, "state": state, "connect_redirect": "1",
    }
    return "https://open.weixin.qq.com/connect/oauth2/authorize?" + urlencode(params) + "#wechat_redirect"


def _get_json(url: str) -> dict:
    try:
        with urlopen(url, timeout=10) as resp:
            raw = resp.read().decode("utf-8", "ignore")
    except HTTPError as e:
        raise RuntimeError(f"微信接口返回 HTTP {e.code}")
    except (URLError, OSError):
        raise RuntimeError("无法连接微信服务器，请检查服务器网络")
    try:
        return json.loads(raw)
    except ValueError:
        raise RuntimeError("微信接口返回了无法解析的数据")


def exchange_code(code: str) -> dict:
    """用 code 换取 access_token / openid / unionid"""
    data = _get_json("https://api.weixin.qq.com/sns/oauth2/access_token?" + urlencode({
        "appid": APPID, "secret": APPSECRET, "code": code, "grant_type": "authorization_code",
    }))
    if data.get("errcode"):
        raise RuntimeError(f"微信授权失败({data['errcode']})：{data.get('errmsg') or 'code 无效或已过期'}")
    if not data.get("openid"):
        raise RuntimeError("微信未返回 openid")
    return data


def fetch_userinfo(access_token: str, openid: str) -> dict:
    """拉取昵称、头像、unionid（scope=snsapi_userinfo 时可用）"""
    data = _get_json("https://api.weixin.qq.com/sns/userinfo?" + urlencode({
        "access_token": access_token, "openid": openid, "lang": "zh_CN",
    }))
    if data.get("errcode"):
        raise RuntimeError(f"获取微信用户信息失败({data['errcode']})：{data.get('errmsg') or ''}")
    return data


# ------------------------------------------------------------------ 二维码
def qr_svg(text: str) -> str:
    """把授权链接渲染成 SVG 二维码；没装 qrcode 库时返回空字符串"""
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return ""
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=9, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


def is_wechat_browser(user_agent: str) -> bool:
    return "micromessenger" in (user_agent or "").lower()
