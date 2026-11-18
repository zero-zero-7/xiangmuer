"""四序颐养 · 账号体系 / 管理后台 / 审核 / 举报 等业务接口

挂载方式（app.py）：
    import api_v2
    app.include_router(api_v2.router)

约定：
    - 角色：user（普通用户）/ admin（管理员）
    - 用户状态：normal / banned（封禁）/ canceled（已注销）
    - 内容状态：pending（待审核）/ approved（已通过）/ rejected（已驳回）/ offline（已下架）
"""
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

import os as _os
if _os.getenv("DATABASE_URL", "").startswith("sqlite"):
    import db_local as db
else:
    import db
import wechat
from security import hash_password, verify_password

router = APIRouter(prefix="/api")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fa5]{3,20}$")
CANCEL_DAYS = 7


def now_str(delta_seconds: int = 0) -> str:
    return (datetime.now() + timedelta(seconds=delta_seconds)).strftime("%Y-%m-%d %H:%M:%S")


def day_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ------------------------------------------------------------------ 依赖
def token_of(x_auth_token: Optional[str] = Header(default=None),
             authorization: Optional[str] = Header(default=None)) -> str:
    token = x_auth_token
    if not token and authorization:
        token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "未登录")
    row = db.query("SELECT token FROM sessions WHERE token = ?", (token,), one=True)
    if not row:
        raise HTTPException(401, "登录已失效")
    return token


def user_of(token: str = Depends(token_of)) -> dict:
    row = db.query(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (token,), one=True)
    if not row:
        raise HTTPException(401, "用户不存在")
    row = refresh_user_state(row)
    return row


def admin_of(user: dict = Depends(user_of)) -> dict:
    if (user.get("role") or "user") != "admin":
        raise HTTPException(403, "仅管理员可操作")
    if user.get("status") == "banned":
        raise HTTPException(403, "管理员账号已被封禁")
    return user


def refresh_user_state(user: dict) -> dict:
    status = user.get("status") or "normal"
    until = user.get("ban_until") or ""
    if status == "banned" and until and until < now_str():
        db.execute("UPDATE users SET status='normal', ban_until='', ban_reason='' WHERE id = ?",
                   (user["id"],))
        db.execute("UPDATE ban_records SET lifted_at = ? WHERE user_id = ? AND lifted_at = ''",
                   (now_str(), user["id"]))
        db.execute("INSERT INTO messages(user_id, type, avatar, name, text, time_label, unread,"
                   " created_at) VALUES(?,?,?,?,?,?,?,?)",
                   (user["id"], "system", "系", "系统通知", "您的临时封禁已到期，账号功能已恢复。",
                    "刚刚", 1, now_str()))
        user["status"] = "normal"
        user["ban_until"] = ""
    if user.get("cancel_at") and user["cancel_at"] < now_str() and status != "canceled":
        finalize_cancel(user["id"])
        user["status"] = "canceled"
    return user


def guard_interact(user: dict):
    if user.get("status") == "banned":
        raise HTTPException(403, "账号已被封禁，暂时无法互动")
    if user.get("cancel_at"):
        raise HTTPException(403, "账号正在注销冷静期，请先撤销注销")
    if user.get("status") == "canceled":
        raise HTTPException(403, "账号已注销")


def public(u: dict) -> dict:
    return {
        "id": u["id"], "nickname": u["nickname"], "avatar": u.get("avatar") or "颐",
        "tag": u.get("tag") or "", "points": int(u.get("points") or 0),
        "phone": u.get("phone") or "", "username": u.get("username") or "",
        "role": u.get("role") or "user", "status": u.get("status") or "normal",
        "ban_until": u.get("ban_until") or "", "ban_reason": u.get("ban_reason") or "",
        "cancel_at": u.get("cancel_at") or "", "bio": u.get("bio") or "",
    }


def new_session(user_id: int) -> str:
    token = secrets.token_hex(16)
    db.execute("INSERT INTO sessions(token, user_id, created_at) VALUES(?,?,?)",
               (token, user_id, now_str()))
    return token


def notify(user_id: int, text: str, name: str = "系统通知", link: str = ""):
    db.execute("INSERT INTO messages(user_id, type, avatar, name, text, time_label, unread,"
               " link, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
               (user_id, "system", "系", name, text, "刚刚", 1, link, now_str()))


def finalize_cancel(uid: int):
    """冷静期结束：清除内容与评论，昵称显示为已注销账户。"""
    db.execute("DELETE FROM comments WHERE user_id = ?", (uid,))
    db.execute("DELETE FROM posts WHERE user_id = ?", (uid,))
    db.execute("DELETE FROM post_likes WHERE user_id = ?", (uid,))
    db.execute("DELETE FROM app_favorites WHERE user_id = ?", (uid,))
    db.execute("DELETE FROM notes WHERE user_id = ?", (uid,))
    db.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
    db.execute("UPDATE users SET nickname = '已注销账户', avatar = '注', status = 'canceled',"
               " username = NULL, password_hash = '', phone = NULL, tag = '已注销' WHERE id = ?",
               (uid,))
    db.execute("UPDATE cancel_records SET status = 'done' WHERE user_id = ? AND status = 'pending'",
               (uid,))


# ------------------------------------------------------------------ 请求模型
class RegisterIn(BaseModel):
    username: str
    password: str
    nickname: str = ""
    phone: str = ""


class PasswordLoginIn(BaseModel):
    account: str
    password: str


class WechatAuthorizeIn(BaseModel):
    redirect: str = ""


class AuditIn(BaseModel):
    action: str
    reason: str = ""


class PinIn(BaseModel):
    pinned: int = 1


class BanIn(BaseModel):
    days: int = 0
    reason: str = "违规内容"


class ReportHandleIn(BaseModel):
    action: str
    note: str = ""


class TagIn(BaseModel):
    name: str
    dimension: str = "condition"


class GroupIn(BaseModel):
    name: str


class GroupMoveIn(BaseModel):
    group_id: int = 0


class UploadLimitIn(BaseModel):
    content_id: str = ""
    url: str = ""


# ------------------------------------------------------------------ 注册 / 登录
@router.post("/auth/register")
def register(body: RegisterIn):
    username = (body.username or "").strip()
    password = body.password or ""
    if not USERNAME_RE.match(username):
        raise HTTPException(400, "用户名 3-20 位，支持中英文、数字、下划线")
    if len(password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    if db.query("SELECT id FROM users WHERE username = ?", (username,), one=True):
        raise HTTPException(400, "该用户名已被注册")
    phone = (body.phone or "").strip()
    if phone and db.query("SELECT id FROM users WHERE phone = ?", (phone,), one=True):
        raise HTTPException(400, "该手机号已绑定其他账号")
    nickname = (body.nickname or "").strip() or username
    uid = db.execute(
        "INSERT INTO users(nickname, avatar, tag, points, phone, username, password_hash,"
        " role, status, created_at) VALUES(?,?,?,?,?,?,?, 'user', 'normal', ?)",
        (nickname[:32], "颐", "入门阶段", 0, phone or None, username,
         hash_password(password), now_str()))
    db.execute("INSERT IGNORE INTO settings(user_id) VALUES(?)", (uid,))
    notify(uid, "欢迎加入四序颐养，愿你顺时而居、颐养身心。", "欢迎通知")
    user = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    return {"token": new_session(uid), "user": public(user)}


@router.post("/auth/password")
def password_login(body: PasswordLoginIn):
    account = (body.account or "").strip()
    if not account:
        raise HTTPException(400, "请输入用户名或手机号")
    user = db.query("SELECT * FROM users WHERE username = ? OR phone = ?",
                    (account, account), one=True)
    if not user or not verify_password(body.password or "", user.get("password_hash") or ""):
        raise HTTPException(400, "账号或密码不正确")
    user = refresh_user_state(user)
    if user.get("status") == "canceled":
        raise HTTPException(403, "该账号已注销")
    return {"token": new_session(user["id"]), "user": public(user)}


@router.get("/auth/me")
def auth_me(user: dict = Depends(user_of)):
    return {"user": public(user)}


# ------------------------------------------------------------------ 微信登录
def _safe_redirect(url: str) -> str:
    url = (url or "").strip()
    return url if url.startswith(("http://", "https://")) else ""


def _result_page(title: str, message: str, ok: bool = True) -> HTMLResponse:
    color = "#3A6B6B" if ok else "#B4552D"
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title></head>
<body style="margin:0;background:#F6F1E7;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;color:#2E3A38">
<div style="max-width:420px;margin:0 auto;padding:80px 24px;text-align:center">
  <div style="width:64px;height:64px;margin:0 auto 20px;border-radius:16px;background:{color};color:#fff;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:700">四</div>
  <h1 style="font-size:20px;margin:0 0 12px">{title}</h1>
  <p style="font-size:14px;line-height:1.9;color:#6B7C79;margin:0">{message}</p>
</div></body></html>"""
    return HTMLResponse(html)


def _wechat_user(info: dict, token_info: dict) -> dict:
    """按 openid 查找已有用户，没有则创建真实微信账号"""
    openid = (info.get("openid") or token_info.get("openid") or "").strip()
    if not openid:
        raise RuntimeError("微信未返回 openid")
    row = db.query("SELECT * FROM users WHERE wechat_openid = ?", (openid,), one=True)
    if row:
        row = refresh_user_state(row)
        if row.get("status") == "canceled":
            raise RuntimeError("该微信账号已注销")
        return row
    nick = (info.get("nickname") or "").strip()[:16] or "微信用户" + openid[-4:]
    uid = db.execute(
        "INSERT INTO users(nickname, avatar, tag, points, phone, username, password_hash,"
        " role, status, created_at, wechat_openid, wechat_unionid)"
        " VALUES(?,?,?,?,NULL,NULL,'','user','normal',?,?,?)",
        (nick, nick[:1] or "颐", "入门阶段", 0, now_str(), openid,
         info.get("unionid") or token_info.get("unionid") or ""))
    db.execute("INSERT IGNORE INTO settings(user_id) VALUES(?)", (uid,))
    notify(uid, "欢迎加入四序颐养，愿你顺时而居、颐养身心。", "欢迎通知")
    return db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)


@router.get("/auth/wechat/status")
def wechat_status():
    return {"configured": wechat.is_configured(), "mode": wechat.mode_text(),
            "appid": wechat.APPID, "scope": wechat.SCOPE}


@router.post("/auth/wechat/authorize")
def wechat_authorize(body: WechatAuthorizeIn, request: Request):
    if not wechat.is_configured():
        raise HTTPException(503, "微信登录未配置：请在 server/.env 填写 WECHAT_APPID 和 "
                                 "WECHAT_APPSECRET 后重启后端")
    state = wechat.new_state(_safe_redirect(body.redirect))
    fallback = str(request.base_url).rstrip("/") + "/api/auth/wechat/callback"
    url = wechat.authorize_url(wechat.redirect_uri(fallback), state)
    return {"state": state, "url": url, "qr": wechat.qr_svg(url),
            "in_wechat": wechat.is_wechat_browser(request.headers.get("user-agent", "")),
            "expires_in": wechat.STATE_TTL}


@router.get("/auth/wechat/callback")
def wechat_callback(code: str = "", state: str = ""):
    rec = wechat.get_state(state)
    if not rec:
        return _result_page("授权已过期", "请回到应用重新发起微信登录。", ok=False)
    if not code:
        wechat.resolve(state, error="你取消了微信授权")
        return _result_page("已取消授权", "你可以关闭本页，回到应用重新登录。", ok=False)
    try:
        token_info = wechat.exchange_code(code)
        if wechat.SCOPE == "snsapi_base":
            info = token_info
        else:
            info = wechat.fetch_userinfo(token_info["access_token"], token_info["openid"])
        user = _wechat_user(info, token_info)
    except Exception as e:
        wechat.resolve(state, error=str(e))
        return _result_page("登录失败", str(e), ok=False)
    token = new_session(user["id"])
    wechat.resolve(state, token=token, user=public(user))
    target = rec.get("redirect") or ""
    if target:
        sep = "&" if "?" in target else "?"
        return RedirectResponse(target + sep + "wx_state=" + state, status_code=302)
    return _result_page("登录成功", f"已登录「{user['nickname']}」，请回到电脑继续操作。")


@router.get("/auth/wechat/poll")
def wechat_poll(state: str = ""):
    rec = wechat.get_state(state)
    if not rec:
        return {"status": "expired", "token": "", "user": {},
                "error": "二维码已过期，请重新发起"}
    return {"status": rec["status"], "token": rec.get("token") or "",
            "user": rec.get("user") or {}, "error": rec.get("error") or ""}


# ------------------------------------------------------------------ 我的投稿
@router.get("/my/posts")
def my_posts(user: dict = Depends(user_of)):
    rows = db.query(
        "SELECT id, title, cat, likes, comments, status, reject_reason, pinned, time_label,"
        " created_at FROM posts WHERE user_id = ? ORDER BY id DESC", (user["id"],))
    label = {"pending": "审核中", "approved": "已通过", "rejected": "已驳回", "offline": "已下架"}
    return [{
        "id": r["id"], "title": r["title"], "cat": r["cat"],
        "likes": int(r["likes"] or 0), "comments": int(r["comments"] or 0),
        "status": r["status"] or "approved", "status_text": label.get(r["status"] or "approved", ""),
        "reject_reason": r["reject_reason"] or "", "pinned": bool(r["pinned"]),
        "time": r["time_label"] or "", "route": f"#/detail/fun/{r['id']}",
    } for r in rows]


# ------------------------------------------------------------------ 评论点赞 / 删除任意评论（管理员）
@router.post("/comments/{cid}/like")
def like_comment(cid: int, user: dict = Depends(user_of)):
    guard_interact(user)
    row = db.query("SELECT id, likes FROM comments WHERE id = ?", (cid,), one=True)
    if not row:
        raise HTTPException(404, "评论不存在")
    exists = db.query("SELECT id FROM likes WHERE user_id = ? AND target_type = 'comment'"
                      " AND target_id = ?", (user["id"], str(cid)), one=True)
    if exists:
        db.execute("DELETE FROM likes WHERE id = ?", (exists["id"],))
        db.execute("UPDATE comments SET likes = CASE WHEN likes > 0 THEN likes - 1 ELSE 0 END"
                   " WHERE id = ?", (cid,))
        on = False
    else:
        db.execute("INSERT INTO likes(user_id, target_type, target_id, created_at)"
                   " VALUES(?, 'comment', ?, ?)", (user["id"], str(cid), now_str()))
        db.execute("UPDATE comments SET likes = likes + 1 WHERE id = ?", (cid,))
        on = True
    likes = db.query("SELECT likes FROM comments WHERE id = ?", (cid,), one=True)
    return {"on": on, "likes": int(likes["likes"] or 0)}


# ------------------------------------------------------------------ 收藏分组
@router.get("/collect-groups")
def collect_groups(user: dict = Depends(user_of)):
    rows = db.query("SELECT id, name FROM collect_groups WHERE user_id = ? ORDER BY sort, id",
                    (user["id"],))
    out = [{"id": 0, "name": "默认分组"}]
    for r in rows:
        cnt = db.query("SELECT COUNT(*) AS c FROM app_favorites WHERE user_id = ? AND group_id = ?",
                       (user["id"], r["id"]), one=True)
        out.append({"id": r["id"], "name": r["name"], "count": int(cnt["c"] or 0)})
    return out


@router.post("/collect-groups")
def create_group(body: GroupIn, user: dict = Depends(user_of)):
    name = (body.name or "").strip()
    if not 1 <= len(name) <= 12:
        raise HTTPException(400, "分组名称 1-12 个字")
    if db.query("SELECT id FROM collect_groups WHERE user_id = ? AND name = ?",
                (user["id"], name), one=True):
        raise HTTPException(400, "分组已存在")
    gid = db.execute("INSERT INTO collect_groups(user_id, name, sort, created_at)"
                     " VALUES(?,?,?,?)", (user["id"], name, 0, now_str()))
    return {"id": gid, "name": name}


@router.delete("/collect-groups/{gid}")
def remove_group(gid: int, user: dict = Depends(user_of)):
    db.execute("DELETE FROM collect_groups WHERE id = ? AND user_id = ?", (gid, user["id"]))
    db.execute("UPDATE app_favorites SET group_id = 0 WHERE group_id = ? AND user_id = ?",
               (gid, user["id"]))
    return {"ok": True}


@router.post("/favorites/{content_id}/group")
def move_favorite(content_id: str, body: GroupMoveIn, user: dict = Depends(user_of)):
    if body.group_id:
        g = db.query("SELECT id FROM collect_groups WHERE id = ? AND user_id = ?",
                     (body.group_id, user["id"]), one=True)
        if not g:
            raise HTTPException(404, "分组不存在")
    db.execute("UPDATE app_favorites SET group_id = ? WHERE user_id = ? AND content_id = ?",
               (body.group_id, user["id"], content_id))
    return {"ok": True}


# ------------------------------------------------------------------ 注销（冷静期 7 天）
@router.post("/account/cancel")
def request_cancel(user: dict = Depends(user_of)):
    if user.get("cancel_at"):
        raise HTTPException(400, "已在注销冷静期中")
    effective = (datetime.now() + timedelta(days=CANCEL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute("INSERT INTO cancel_records(user_id, requested_at, effective_at, status, created_at)"
               " VALUES(?,?,?, 'pending', ?)", (user["id"], now_str(), effective, now_str()))
    db.execute("UPDATE users SET cancel_at = ? WHERE id = ?", (effective, user["id"]))
    return {"ok": True, "effective_at": effective, "days": CANCEL_DAYS}


@router.post("/account/cancel/revoke")
def revoke_cancel(user: dict = Depends(user_of)):
    db.execute("UPDATE users SET cancel_at = '' WHERE id = ?", (user["id"],))
    db.execute("UPDATE cancel_records SET status = 'canceled' WHERE user_id = ? AND status = 'pending'",
               (user["id"],))
    return {"ok": True}


@router.get("/account/cancel")
def cancel_status(user: dict = Depends(user_of)):
    row = db.query("SELECT requested_at, effective_at, status FROM cancel_records"
                   " WHERE user_id = ? ORDER BY id DESC", (user["id"],), one=True)
    return row or {}


# ------------------------------------------------------------------ 管理后台
@router.get("/admin/overview")
def admin_overview(admin: dict = Depends(admin_of)):
    def one(sql, params=()):
        return int((db.query(sql, params, one=True) or {}).get("c") or 0)
    return {
        "users": one("SELECT COUNT(*) AS c FROM users WHERE status <> 'canceled'"),
        "new_users_today": one("SELECT COUNT(*) AS c FROM users WHERE created_at LIKE ?",
                               (day_str() + "%",)),
        "official": one("SELECT COUNT(*) AS c FROM content_items"),
        "user_contents": one("SELECT COUNT(*) AS c FROM posts"),
        "pending": one("SELECT COUNT(*) AS c FROM posts WHERE status = 'pending'"),
        "approved": one("SELECT COUNT(*) AS c FROM posts WHERE status = 'approved'"),
        "offline": one("SELECT COUNT(*) AS c FROM posts WHERE status = 'offline'"),
        "likes": one("SELECT COALESCE(SUM(likes),0) AS c FROM posts"),
        "comments": one("SELECT COUNT(*) AS c FROM comments"),
        "reports": one("SELECT COUNT(*) AS c FROM reports WHERE status = 'pending'"),
        "banned": one("SELECT COUNT(*) AS c FROM users WHERE status = 'banned'"),
    }


@router.get("/admin/contents")
def admin_contents(status: str = "", admin: dict = Depends(admin_of)):
    sql = ("SELECT p.*, u.nickname AS author_nick, u.status AS author_status"
           " FROM posts p LEFT JOIN users u ON u.id = p.user_id")
    params = []
    if status:
        sql += " WHERE p.status = ?"
        params.append(status)
    sql += " ORDER BY p.pinned DESC, p.id DESC LIMIT 200"
    rows = db.query(sql, params)
    label = {"pending": "待审核", "approved": "已通过", "rejected": "已驳回", "offline": "已下架"}
    out = []
    for r in rows:
        out.append({
            "id": r["id"], "title": r["title"], "cat": r["cat"],
            "category_id": r.get("category_id") or "", "author": r["author_nick"] or r["author"],
            "author_id": r["user_id"], "author_status": r["author_status"] or "normal",
            "time": r["time_label"], "likes": int(r["likes"] or 0),
            "comments": int(r["comments"] or 0), "views": int(r.get("views") or 0),
            "status": r.get("status") or "approved",
            "status_text": label.get(r.get("status") or "approved", ""),
            "reject_reason": r.get("reject_reason") or "",
            "pinned": bool(r.get("pinned")),
            "route": f"#/detail/fun/{r['id']}",
        })
    return out


@router.post("/admin/contents/{pid}/audit")
def audit_content(pid: int, body: AuditIn, admin: dict = Depends(admin_of)):
    post = db.query("SELECT * FROM posts WHERE id = ?", (pid,), one=True)
    if not post:
        raise HTTPException(404, "内容不存在")
    if body.action not in ("approve", "reject"):
        raise HTTPException(400, "action 只能是 approve / reject")
    if body.action == "approve":
        db.execute("UPDATE posts SET status = 'approved', reject_reason = '', audit_at = ?"
                   " WHERE id = ?", (now_str(), pid))
        if post["user_id"]:
            notify(post["user_id"], f"你的投稿《{post['title']}》已通过审核，已在颐养社区展示。",
                   "审核通知", f"#/detail/fun/{pid}")
    else:
        reason = (body.reason or "").strip() or "内容不符合社区规范"
        db.execute("UPDATE posts SET status = 'rejected', reject_reason = ?, audit_at = ?"
                   " WHERE id = ?", (reason[:200], now_str(), pid))
        if post["user_id"]:
            notify(post["user_id"], f"你的投稿《{post['title']}》未通过审核：{reason}",
                   "审核通知", "#/activity/posts")
    db.execute("INSERT INTO audit_records(target_type, target_id, admin_id, action, reason,"
               " created_at) VALUES('post', ?, ?, ?, ?, ?)",
               (str(pid), admin["id"], body.action, body.reason or "", now_str()))
    return {"ok": True}


@router.post("/admin/contents/{pid}/pin")
def pin_content(pid: int, body: PinIn, admin: dict = Depends(admin_of)):
    db.execute("UPDATE posts SET pinned = ?, pinned_at = ? WHERE id = ?",
               (1 if body.pinned else 0, now_str() if body.pinned else "", pid))
    db.execute("INSERT INTO audit_records(target_type, target_id, admin_id, action, reason,"
               " created_at) VALUES('post', ?, ?, ?, '', ?)",
               (str(pid), admin["id"], "pin" if body.pinned else "unpin", now_str()))
    return {"ok": True, "pinned": bool(body.pinned)}


@router.post("/admin/contents/{pid}/offline")
def offline_content(pid: int, body: AuditIn, admin: dict = Depends(admin_of)):
    post = db.query("SELECT * FROM posts WHERE id = ?", (pid,), one=True)
    if not post:
        raise HTTPException(404, "内容不存在")
    reason = (body.reason or "").strip() or "内容已下架"
    db.execute("UPDATE posts SET status = 'offline', reject_reason = ?, audit_at = ? WHERE id = ?",
               (reason[:200], now_str(), pid))
    if post["user_id"]:
        notify(post["user_id"], f"你的内容《{post['title']}》已被下架：{reason}", "下架通知",
               "#/activity/posts")
    db.execute("INSERT INTO audit_records(target_type, target_id, admin_id, action, reason,"
               " created_at) VALUES('post', ?, ?, 'offline', ?, ?)",
               (str(pid), admin["id"], reason[:200], now_str()))
    return {"ok": True}


@router.post("/admin/contents/{pid}/restore")
def restore_content(pid: int, admin: dict = Depends(admin_of)):
    db.execute("UPDATE posts SET status = 'approved', reject_reason = '' WHERE id = ?", (pid,))
    return {"ok": True}


@router.delete("/admin/contents/{pid}")
def admin_delete_content(pid: int, admin: dict = Depends(admin_of)):
    post = db.query("SELECT title, user_id FROM posts WHERE id = ?", (pid,), one=True)
    if not post:
        return {"ok": True}
    db.execute("DELETE FROM posts WHERE id = ?", (pid,))
    db.execute("DELETE FROM comments WHERE post_id = ?", (pid,))
    db.execute("DELETE FROM post_sections WHERE post_id = ?", (pid,))
    if post["user_id"]:
        notify(post["user_id"], f"你的内容《{post['title']}》因违反社区规范已被删除。", "处理通知")
    db.execute("INSERT INTO audit_records(target_type, target_id, admin_id, action, reason,"
               " created_at) VALUES('post', ?, ?, 'delete', '', ?)",
               (str(pid), admin["id"], now_str()))
    return {"ok": True}


@router.get("/admin/users")
def admin_users(q: str = "", admin: dict = Depends(admin_of)):
    sql = ("SELECT id, nickname, avatar, phone, username, role, status, ban_until, ban_reason,"
           " points, created_at FROM users")
    params = []
    if q:
        sql += " WHERE nickname LIKE ? OR phone LIKE ? OR username LIKE ?"
        params = [f"%{q}%"] * 3
    sql += " ORDER BY id DESC LIMIT 200"
    rows = db.query(sql, params)
    for r in rows:
        cnt = db.query("SELECT COUNT(*) AS c FROM posts WHERE user_id = ?", (r["id"],), one=True)
        r["posts"] = int(cnt["c"] or 0)
        r["ban_until"] = r.get("ban_until") or ""
        r["ban_reason"] = r.get("ban_reason") or ""
    return rows


@router.post("/admin/users/{uid}/ban")
def ban_user(uid: int, body: BanIn, admin: dict = Depends(admin_of)):
    target = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    if not target:
        raise HTTPException(404, "用户不存在")
    if target.get("role") == "admin" and target["id"] != admin["id"]:
        raise HTTPException(403, "不能封禁其他管理员")
    until = "" if body.days <= 0 else (datetime.now() + timedelta(days=body.days)).strftime("%Y-%m-%d %H:%M:%S")
    reason = (body.reason or "").strip()[:200] or "违反社区规范"
    db.execute("UPDATE users SET status = 'banned', ban_until = ?, ban_reason = ? WHERE id = ?",
               (until, reason, uid))
    db.execute("INSERT INTO ban_records(user_id, admin_id, reason, until, created_at)"
               " VALUES(?,?,?,?,?)", (uid, admin["id"], reason, until, now_str()))
    tail = f"预计 {until} 自动解封" if until else "永久封禁"
    notify(uid, f"你的账号已被封禁：{reason}（{tail}），封禁期间无法点赞、评论、投稿。", "封禁通知")
    return {"ok": True, "until": until}


@router.post("/admin/users/{uid}/unban")
def unban_user(uid: int, admin: dict = Depends(admin_of)):
    db.execute("UPDATE users SET status = 'normal', ban_until = '', ban_reason = '' WHERE id = ?",
               (uid,))
    db.execute("UPDATE ban_records SET lifted_at = ? WHERE user_id = ? AND lifted_at = ''",
               (now_str(), uid))
    notify(uid, "你的账号已解除封禁，感谢理解与配合。", "解封通知")
    return {"ok": True}


@router.get("/admin/reports")
def admin_reports(status: str = "pending", admin: dict = Depends(admin_of)):
    sql = ("SELECT r.*, u.nickname AS reporter FROM reports r"
           " LEFT JOIN users u ON u.id = r.user_id")
    params = []
    if status:
        sql += " WHERE r.status = ?"
        params.append(status)
    sql += " ORDER BY r.id DESC LIMIT 200"
    rows = db.query(sql, params)
    out = []
    for r in rows:
        target = {}
        tid = r.get("target_id") or ""
        if r.get("target_type") == "post" and tid:
            pid = tid.replace("p", "")
            target = db.query("SELECT id, title, status FROM posts WHERE id = ?", (pid,), one=True) or {}
        if r.get("target_type") == "comment" and tid:
            cid = tid.replace("c", "")
            target = db.query("SELECT id, content, post_id FROM comments WHERE id = ?", (cid,), one=True) or {}
        out.append({
            "id": r["id"], "reason": r["reason"], "target_type": r["target_type"],
            "target_id": tid, "reporter": r["reporter"] or "匿名用户",
            "status": r.get("status") or "pending", "result": r.get("result") or "",
            "time": r["created_at"], "target": target,
        })
    return out


@router.post("/admin/reports/{rid}/handle")
def handle_report(rid: int, body: ReportHandleIn, admin: dict = Depends(admin_of)):
    rep = db.query("SELECT * FROM reports WHERE id = ?", (rid,), one=True)
    if not rep:
        raise HTTPException(404, "举报不存在")
    action = body.action or "ignore"
    tid = (rep.get("target_id") or "").replace("p", "").replace("c", "")
    if action == "delete":
        if rep.get("target_type") == "post":
            db.execute("DELETE FROM posts WHERE id = ?", (tid,))
            db.execute("DELETE FROM comments WHERE post_id = ?", (tid,))
        elif rep.get("target_type") == "comment":
            db.execute("DELETE FROM comments WHERE id = ?", (tid,))
    elif action == "offline":
        db.execute("UPDATE posts SET status = 'offline' WHERE id = ?", (tid,))
    elif action == "ban":
        owner = None
        if rep.get("target_type") == "post":
            p = db.query("SELECT user_id FROM posts WHERE id = ?", (tid,), one=True)
            owner = p["user_id"] if p else None
        elif rep.get("target_type") == "comment":
            c = db.query("SELECT user_id FROM comments WHERE id = ?", (tid,), one=True)
            owner = c["user_id"] if c else None
        if owner:
            db.execute("UPDATE users SET status = 'banned', ban_until = '', ban_reason = ?"
                       " WHERE id = ?", (rep.get("reason") or "违规内容", owner))
            db.execute("INSERT INTO ban_records(user_id, admin_id, reason, until, created_at)"
                       " VALUES(?,?,?,'',?)", (owner, admin["id"], rep.get("reason") or "违规内容",
                                               now_str()))
            notify(owner, f"你的账号因「{rep.get('reason')}」被永久封禁。", "封禁通知")
    db.execute("UPDATE reports SET status = 'handled', handled_by = ?, result = ?, handled_at = ?"
               " WHERE id = ?", (admin["id"], f"{action} {body.note}".strip(), now_str(), rid))
    if rep.get("user_id"):
        notify(rep["user_id"], "你的举报已处理，感谢你共同维护社区环境。", "举报反馈")
    return {"ok": True}


# ------------------------------------------------------------------ 分类 / 标签维护
@router.get("/admin/categories")
def admin_categories(admin: dict = Depends(admin_of)):
    return db.query("SELECT id, name, icon, descr, sort, active FROM categories ORDER BY sort, id")


@router.post("/admin/categories/{cid}/toggle")
def toggle_category(cid: str, admin: dict = Depends(admin_of)):
    row = db.query("SELECT active FROM categories WHERE id = ?", (cid,), one=True)
    if not row:
        raise HTTPException(404, "分类不存在")
    db.execute("UPDATE categories SET active = ? WHERE id = ?",
               (0 if int(row["active"] or 0) else 1, cid))
    return {"ok": True}


@router.get("/admin/tags")
def admin_tags(admin: dict = Depends(admin_of)):
    return db.query("SELECT id, name, dimension, sort, active FROM tags"
                    " ORDER BY dimension, sort, id")


@router.post("/admin/tags")
def add_tag(body: TagIn, admin: dict = Depends(admin_of)):
    name = (body.name or "").strip()
    dim = body.dimension if body.dimension in ("crowd", "solar", "condition") else "condition"
    if not 1 <= len(name) <= 12:
        raise HTTPException(400, "标签名称 1-12 个字")
    if db.query("SELECT id FROM tags WHERE name = ? AND dimension = ?", (name, dim), one=True):
        raise HTTPException(400, "该标签已存在")
    tid = db.execute("INSERT INTO tags(name, dimension, sort, active, created_at)"
                     " VALUES(?,?,?,1,?)", (name, dim, 99, now_str()))
    return {"id": tid, "name": name, "dimension": dim, "active": 1}


@router.delete("/admin/tags/{tid}")
def remove_tag(tid: int, admin: dict = Depends(admin_of)):
    db.execute("DELETE FROM tags WHERE id = ?", (tid,))
    return {"ok": True}


@router.get("/admin/feedback")
def admin_feedback(admin: dict = Depends(admin_of)):
    return db.query("SELECT f.id, f.content, f.contact, f.created_at, u.nickname"
                    " FROM feedback f LEFT JOIN users u ON u.id = f.user_id"
                    " ORDER BY f.id DESC LIMIT 100")


@router.get("/admin/audit-records")
def admin_audit_records(admin: dict = Depends(admin_of)):
    return db.query("SELECT a.*, u.nickname AS admin_name FROM audit_records a"
                    " LEFT JOIN users u ON u.id = a.admin_id ORDER BY a.id DESC LIMIT 100")
