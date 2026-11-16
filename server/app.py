"""四序颐养 · 后端 API（FastAPI + MySQL）

启动：
    cd server
    python -m uvicorn app:app --host 127.0.0.1 --port 8001
打开：
    http://127.0.0.1:8001/
"""
import random
import secrets
import time as _time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import db
import seed as seed_mod
import migrate as migrate_mod
import api_v2

BASE = Path(__file__).resolve().parent
HTML_FILE = BASE.parent / "四序颐养.html"
HOT_SEARCH = ["八段锦", "失眠", "湿气", "足三里", "山药", "泡脚", "立冬养生", "体质测试"]

app = FastAPI(title="四序颐养 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ 工具
def now_str(offset_seconds: int = 0) -> str:
    return datetime.fromtimestamp(_time.time() + offset_seconds).strftime("%Y-%m-%d %H:%M:%S")


def useful_base(cid: str) -> int:
    h = 0
    for ch in cid:
        h = (h * 31 + ord(ch)) % 97
    return 30 + h


def content_route(fid: str, item: dict) -> str:
    pos = db.query(
        "SELECT COUNT(*) AS c FROM content_items x WHERE x.feature_id = ? AND "
        "(x.sort < ? OR (x.sort = ? AND x.id < ?))",
        (fid, item["sort"], item["sort"], item["id"]), one=True)
    return f"#/detail/{fid}/{int(pos['c'])}"


def post_route(post: dict, uid: int = 0) -> str:
    pos = db.query(
        "SELECT COUNT(*) AS c FROM posts x LEFT JOIN users u ON u.id = x.user_id"
        " WHERE ((x.status = 'approved' AND (u.status IS NULL OR u.status <> 'banned'))"
        "   OR x.user_id = ?)"
        "   AND (x.pinned > ? OR (x.pinned = ? AND (x.created_at > ?"
        "   OR (x.created_at = ? AND x.id > ?))))",
        (uid, int(post.get("pinned") or 0), int(post.get("pinned") or 0),
         post["created_at"], post["created_at"], post["id"]), one=True)
    return f"#/detail/fun/{int(pos['c'])}"


def visible_posts_sql(uid: int) -> tuple:
    """社区可见帖子：已通过且作者未被封禁 + 自己发布的全部状态。"""
    sql = ("SELECT p.*, u.status AS author_status FROM posts p"
           " LEFT JOIN users u ON u.id = p.user_id"
           " WHERE ((p.status = 'approved' AND (u.status IS NULL OR u.status <> 'banned'))"
           "   OR p.user_id = ?)")
    return sql, (uid,)


def public_user(u: dict) -> dict:
    return {
        "id": u.get("id"), "nickname": u.get("nickname"), "avatar": u.get("avatar"),
        "tag": u.get("tag"), "points": u.get("points"), "phone": u.get("phone"),
        "username": u.get("username") or "", "role": u.get("role") or "user",
        "status": u.get("status") or "normal", "ban_until": u.get("ban_until") or "",
        "ban_reason": u.get("ban_reason") or "", "cancel_at": u.get("cancel_at") or "",
    }


def auth_token(x_auth_token: Optional[str] = Header(default=None),
               authorization: Optional[str] = Header(default=None)) -> str:
    token = x_auth_token
    if not token and authorization:
        token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    if not db.query("SELECT token FROM sessions WHERE token = ?", (token,), one=True):
        raise HTTPException(status_code=401, detail="登录已失效")
    return token


def current_user(token: str = Depends(auth_token)) -> dict:
    row = db.query(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (token,), one=True)
    if not row:
        raise HTTPException(status_code=401, detail="用户不存在")
    return row


def uid_of(user: dict = Depends(current_user)) -> int:
    return int(user["id"])


def optional_uid(x_auth_token: Optional[str] = Header(default=None),
                 authorization: Optional[str] = Header(default=None)) -> int:
    """游客（未登录）返回 0，登录用户返回其 id；token 失效不报错。"""
    token = x_auth_token
    if not token and authorization:
        token = authorization.replace("Bearer ", "").strip()
    if not token:
        return 0
    row = db.query("SELECT user_id FROM sessions WHERE token = ?", (token,), one=True)
    return int(row["user_id"]) if row else 0


# ------------------------------------------------------------------ 内容组装
def content_items_full(fid: str) -> list:
    items = db.query(
        "SELECT id, feature_id, name, tag, summary, sort FROM content_items"
        " WHERE feature_id = ? ORDER BY sort, id", (fid,))
    if not items:
        return []
    ids = [it["id"] for it in items]
    ph = ",".join(["?"] * len(ids))
    secs = db.query(
        f"SELECT item_id, title, body FROM content_sections WHERE item_id IN ({ph})"
        " ORDER BY item_id, sort, id", ids)
    raw_links = db.query(
        f"SELECT item_id, title, source, url, kind, note FROM content_links"
        f" WHERE item_id IN ({ph}) OR (feature_id = ? AND (item_id IS NULL OR item_id = 0))"
        " ORDER BY item_id, kind, sort, id", ids + [fid])

    sec_map, item_links, feat_links = {}, {}, []
    seen_feat, seen_item = set(), set()
    for s in secs:
        sec_map.setdefault(s["item_id"], []).append({"title": s["title"], "body": s["body"]})
    for l in raw_links:
        payload = {"title": l["title"], "source": l["source"] or "", "url": l["url"],
                   "kind": l["kind"] or "article", "note": l["note"] or ""}
        if l["item_id"] is None or l["item_id"] == 0:
            if payload["url"] not in seen_feat:
                seen_feat.add(payload["url"])
                feat_links.append(payload)
        else:
            key = (l["item_id"], payload["url"])
            if key in seen_item:
                continue
            seen_item.add(key)
            item_links.setdefault(l["item_id"], []).append(payload)

    out = []
    for idx, it in enumerate(items):
        merged = list(item_links.get(it["id"], []))
        exist = {x["url"] for x in merged}
        merged += [x for x in feat_links if x["url"] not in exist]
        out.append({
            "id": it["id"], "content_id": f"c{it['id']}", "feature_id": it["feature_id"],
            "name": it["name"], "tag": it["tag"] or "", "summary": it["summary"] or "",
            "img": "", "author": "", "cat": "", "time": "", "likes": 0, "comments": 0,
            "sections": sec_map.get(it["id"], []), "links": merged,
        })
    return out


def post_payload(post: dict, uid: Optional[int] = None) -> dict:
    secs = db.query("SELECT title, body FROM post_sections WHERE post_id = ? ORDER BY sort, id",
                    (post["id"],))
    cmts = db.query(
        "SELECT c.id, c.user_id, c.nickname, c.content, c.likes, c.reply_to, c.time_label,"
        " c.parent_id, u.status AS author_status"
        " FROM comments c LEFT JOIN users u ON u.id = c.user_id"
        " WHERE c.post_id = ? AND (u.status IS NULL OR u.status <> 'banned' OR c.user_id = ?)"
        " ORDER BY c.id ASC", (post["id"], uid or 0))
    liked = bool(uid and db.query(
        "SELECT id FROM post_likes WHERE user_id = ? AND post_id = ?", (uid, post["id"]), one=True))
    return {
        "id": post["id"], "content_id": f"p{post['id']}", "feature_id": "fun",
        "name": post["title"], "tag": "", "summary": (post["body"] or "")[:60],
        "img": post.get("img") or "", "img_data": post.get("img_data") or "",
        "author": post.get("author") or "",
        "cat": post.get("cat") or "", "time": post.get("time_label") or "",
        "likes": int(post.get("likes") or 0), "comments": len(cmts),
        "status": post.get("status") or "approved",
        "status_text": {"pending": "审核中", "rejected": "已驳回",
                        "offline": "已下架"}.get(post.get("status") or "", ""),
        "reject_reason": post.get("reject_reason") or "",
        "pinned": bool(post.get("pinned")), "views": int(post.get("views") or 0),
        "sections": secs, "links": [], "liked": liked,
        "comment_list": [{
            "id": str(c["id"]), "nickname": c["nickname"] or "匿名",
            "content": c["content"] or "", "time": c["time_label"] or "刚刚",
            "likes": int(c["likes"] or 0), "reply_to": c["reply_to"] or "",
            "parent_id": str(c.get("parent_id") or 0),
            "mine": bool(uid and c["user_id"] == uid),
        } for c in cmts],
    }


# ------------------------------------------------------------------ 请求模型
class PhoneIn(BaseModel):
    phone: str


class LoginIn(BaseModel):
    phone: str
    code: str


class FavoriteIn(BaseModel):
    content_id: str
    title: str
    category: str = ""
    tag: str = ""


class NoteIn(BaseModel):
    title: str
    category: str = "日常养生"
    content: str


class PostIn(BaseModel):
    title: str
    body: str
    cat: str = "日常分享"
    img_data: str = ""


class CommentIn(BaseModel):
    content: str
    reply_to: str = ""
    parent_id: int = 0


class TizhiIn(BaseModel):
    type_name: str


class FeedbackIn(BaseModel):
    content: str
    contact: str = ""


class ReportIn(BaseModel):
    target_id: str = ""
    target_type: str = "post"
    reason: str


class SettingsIn(BaseModel):
    comment_notify: Optional[int] = None
    like_notify: Optional[int] = None
    system_notify: Optional[int] = None
    searchable: Optional[int] = None
    visibility: Optional[str] = None


class ChatIn(BaseModel):
    role: str = "user"
    html: str


# ------------------------------------------------------------------ 启动与页面
@app.on_event("startup")
def on_startup():
    db.init_schema()
    seed_mod.seed()
    migrate_mod.run()


app.include_router(api_v2.router)


@app.get("/")
def index():
    if not HTML_FILE.exists():
        raise HTTPException(404, "未找到 四序颐养.html")
    return FileResponse(HTML_FILE, media_type="text/html; charset=utf-8")


@app.get("/api/health")
def health():
    try:
        db.query("SELECT 1", one=True)
        return {"ok": True, "db": "mysql", "database": db.DB_CONF["database"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/hot-search")
def hot_search():
    return HOT_SEARCH


# ------------------------------------------------------------------ 认证
CODES: dict[str, tuple[str, float]] = {}


@app.post("/api/auth/demo")
def auth_demo():
    user = db.query("SELECT * FROM users WHERE phone = ?", ("13800000000",), one=True)
    if not user:
        uid = db.execute(
            "INSERT INTO users(nickname, avatar, tag, points, phone, created_at) VALUES(?,?,?,?,?,?)",
            ("养生修习者", "颐", "入门阶段", 1288, "13800000000", now_str()))
        db.execute("INSERT IGNORE INTO settings(user_id) VALUES(?)", (uid,))
        user = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    token = secrets.token_hex(16)
    db.execute("INSERT INTO sessions(token, user_id, created_at) VALUES(?,?,?)",
               (token, user["id"], now_str()))
    return {"token": token, "user": public_user(user)}


@app.post("/api/auth/send-code")
def send_code(body: PhoneIn):
    if not body.phone.isdigit() or len(body.phone) != 11:
        raise HTTPException(400, "请输入 11 位手机号")
    code = str(random.randint(100000, 999999))
    CODES[body.phone] = (code, _time.time() + 300)
    return {"ok": True, "code": code, "ttl": 300, "tip": "演示环境验证码直接返回"}


@app.post("/api/auth/login")
def auth_login(body: LoginIn):
    rec = CODES.get(body.phone)
    if not rec or rec[0] != body.code or rec[1] < _time.time():
        raise HTTPException(400, "验证码错误或已过期")
    CODES.pop(body.phone, None)
    user = db.query("SELECT * FROM users WHERE phone = ?", (body.phone,), one=True)
    if not user:
        uid = db.execute(
            "INSERT INTO users(nickname, avatar, tag, points, phone, created_at) VALUES(?,?,?,?,?,?)",
            (f"颐友{body.phone[-4:]}", "颐", "入门阶段", 0, body.phone, now_str()))
        db.execute("INSERT INTO settings(user_id) VALUES(?)", (uid,))
        user = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    token = secrets.token_hex(16)
    db.execute("INSERT INTO sessions(token, user_id, created_at) VALUES(?,?,?)",
               (token, user["id"], now_str()))
    return {"token": token, "user": public_user(user)}


@app.post("/api/auth/logout")
def auth_logout(token: str = Depends(auth_token)):
    db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    uid = int(user["id"])
    tizhi = db.query("SELECT type_name FROM tizhi WHERE user_id = ? ORDER BY id DESC", (uid,), one=True)
    settings = db.query("SELECT * FROM settings WHERE user_id = ?", (uid,), one=True) or {}
    unread = db.query("SELECT COUNT(*) AS c FROM messages WHERE user_id = ? AND unread = 1",
                      (uid,), one=True)
    fav = db.query("SELECT COUNT(*) AS c FROM app_favorites WHERE user_id = ?", (uid,), one=True)
    fp = db.query("SELECT COUNT(*) AS c FROM footprints WHERE user_id = ?", (uid,), one=True)
    posts = db.query("SELECT COUNT(*) AS c FROM posts WHERE user_id = ?", (uid,), one=True)
    return {
        "user": public_user(user),
        "tizhi": tizhi["type_name"] if tizhi else "",
        "settings": settings,
        "unread": int((unread or {}).get("c") or 0),
        "favorites": int((fav or {}).get("c") or 0),
        "footprints": int((fp or {}).get("c") or 0),
        "my_posts": int((posts or {}).get("c") or 0),
    }


# ------------------------------------------------------------------ 内容
@app.get("/api/features")
def features():
    return db.query("SELECT id, name, descr, icon FROM features ORDER BY sort, id")


@app.get("/api/features/{fid}/items-full")
def items_full(fid: str, uid: int = Depends(optional_uid)):
    if fid == "fun":
        sql, params = visible_posts_sql(uid)
        rows = db.query(sql + " ORDER BY p.pinned DESC, p.created_at DESC, p.id DESC", params)
        return [post_payload(r, uid) for r in rows]
    return content_items_full(fid)


@app.get("/api/search")
def search(q: str = ""):
    if not q:
        return {"items": []}
    rows = db.query(
        "SELECT ci.*, f.name AS feature_name FROM content_items ci"
        " JOIN features f ON ci.feature_id = f.id"
        " WHERE ci.name LIKE ? OR ci.summary LIKE ? ORDER BY ci.feature_id, ci.sort LIMIT 50",
        (f"%{q}%", f"%{q}%"))
    return {"items": rows}


# ------------------------------------------------------------------ 社区帖子
@app.get("/api/posts")
def posts(uid: int = Depends(optional_uid)):
    sql, params = visible_posts_sql(uid)
    rows = db.query(sql + " ORDER BY p.pinned DESC, p.created_at DESC, p.id DESC", params)
    return [post_payload(r, uid) for r in rows]


@app.post("/api/posts")
def create_post(body: PostIn, user: dict = Depends(current_user)):
    api_v2.guard_interact(user)
    title = body.title.strip()
    text = body.body.strip()
    if not title or len(text) < 10:
        raise HTTPException(400, "标题必填，正文不少于 10 字")
    uid = int(user["id"])
    mx = db.query("SELECT MAX(sort) AS m FROM posts", one=True)
    sort = int((mx or {}).get("m") or 0) + 1
    pid = db.execute(
        "INSERT INTO posts(user_id, author, title, body, cat, img, img_data, likes, comments,"
        " time_label, sort, created_at, status, pinned) VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'pending', 0)",
        (uid, user["nickname"], title[:160], text, body.cat, "", body.img_data or "",
         0, 0, "刚刚", sort, now_str()))
    db.execute("INSERT INTO post_sections(post_id, title, body, sort) VALUES(?,?,?,0)",
               (pid, "正文", text))
    admins = db.query("SELECT id FROM users WHERE role = 'admin'")
    for a in admins:
        api_v2.notify(a["id"], f"有新的用户投稿《{title[:40]}》待审核。", "审核通知", "#/admin")
    return post_payload(db.query("SELECT * FROM posts WHERE id = ?", (pid,), one=True), uid)


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: int, user: dict = Depends(current_user)):
    row = db.query("SELECT user_id FROM posts WHERE id = ?", (post_id,), one=True)
    if row and (row["user_id"] == int(user["id"]) or (user.get("role") or "") == "admin"):
        db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        db.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
        db.execute("DELETE FROM post_sections WHERE post_id = ?", (post_id,))
    return {"ok": True}


@app.post("/api/posts/{post_id}/like")
def like_post(post_id: int, user: dict = Depends(current_user)):
    api_v2.guard_interact(user)
    uid = int(user["id"])
    post = db.query("SELECT * FROM posts WHERE id = ?", (post_id,), one=True)
    if not post:
        raise HTTPException(404, "帖子不存在")
    liked = db.query("SELECT id FROM post_likes WHERE user_id = ? AND post_id = ?",
                     (uid, post_id), one=True)
    if liked:
        db.execute("DELETE FROM post_likes WHERE id = ?", (liked["id"],))
        db.execute("UPDATE posts SET likes = CASE WHEN likes > 0 THEN likes - 1 ELSE 0 END"
                   " WHERE id = ?", (post_id,))
        state = False
    else:
        db.execute("INSERT INTO post_likes(user_id, post_id, created_at) VALUES(?,?,?)",
                   (uid, post_id, now_str()))
        db.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
        state = True
    likes = db.query("SELECT likes FROM posts WHERE id = ?", (post_id,), one=True)["likes"]
    return {"liked": state, "likes": int(likes or 0)}


@app.post("/api/content/{cid}/useful")
def toggle_useful(cid: str, user: dict = Depends(current_user)):
    api_v2.guard_interact(user)
    uid = int(user["id"])
    row = db.query("SELECT id FROM useful_votes WHERE user_id = ? AND content_id = ?",
                   (uid, cid), one=True)
    if row:
        db.execute("DELETE FROM useful_votes WHERE id = ?", (row["id"],))
        on = False
    else:
        db.execute("INSERT INTO useful_votes(user_id, content_id, created_at) VALUES(?,?,?)",
                   (uid, cid, now_str()))
        on = True
    votes = db.query("SELECT COUNT(*) AS c FROM useful_votes WHERE content_id = ?", (cid,), one=True)
    return {"on": on, "count": useful_base(cid) + int(votes["c"] or 0)}


# ------------------------------------------------------------------ 评论
@app.get("/api/posts/{post_id}/comments")
def get_comments(post_id: int, uid: int = Depends(optional_uid)):
    rows = db.query(
        "SELECT c.* FROM comments c LEFT JOIN users u ON u.id = c.user_id"
        " WHERE c.post_id = ? AND (u.status IS NULL OR u.status <> 'banned' OR c.user_id = ?)"
        " ORDER BY c.id ASC", (post_id, uid))
    liked = {r["target_id"] for r in db.query(
        "SELECT target_id FROM likes WHERE user_id = ? AND target_type = 'comment'", (uid,))}
    out = []
    for r in rows:
        out.append({
            "id": str(r["id"]), "nickname": r["nickname"] or "匿名", "content": r["content"] or "",
            "time": r["time_label"] or "刚刚", "likes": int(r["likes"] or 0),
            "reply_to": r["reply_to"] or "", "parent_id": str(r.get("parent_id") or 0),
            "mine": bool(r["user_id"] == uid), "liked": str(r["id"]) in liked,
        })
    return out


@app.post("/api/posts/{post_id}/comments")
def add_comment(post_id: int, body: CommentIn, user: dict = Depends(current_user)):
    api_v2.guard_interact(user)
    text = body.content.strip()
    if not text:
        raise HTTPException(400, "评论不能为空")
    if len(text) > 100:
        raise HTTPException(400, "评论最多 100 字")
    post = db.query("SELECT user_id, title FROM posts WHERE id = ?", (post_id,), one=True)
    if not post:
        raise HTTPException(404, "帖子不存在")
    parent = 0
    if body.parent_id:
        p = db.query("SELECT id, parent_id, user_id FROM comments WHERE id = ? AND post_id = ?",
                     (body.parent_id, post_id), one=True)
        if p:
            parent = int(p["parent_id"] or 0) or int(p["id"])
    cid = db.execute(
        "INSERT INTO comments(post_id, user_id, nickname, content, likes, reply_to, time_label,"
        " created_at, parent_id) VALUES(?,?,?,?,0,?,?,?,?)",
        (post_id, user["id"], user["nickname"], text, body.reply_to, "刚刚", now_str(), parent))
    if post["user_id"] and post["user_id"] != user["id"]:
        api_v2.notify(post["user_id"],
                      f"{user['nickname']} 评论了你的内容《{post['title']}》：{text[:40]}",
                      "评论通知", f"#/activity/comments")
    row = db.query("SELECT * FROM comments WHERE id = ?", (cid,), one=True)
    return {
        "id": str(row["id"]), "nickname": row["nickname"], "content": row["content"],
        "time": "刚刚", "likes": 0, "reply_to": row["reply_to"] or "",
        "parent_id": str(row.get("parent_id") or 0), "mine": True, "liked": False,
    }


@app.delete("/api/comments/{cid}")
def delete_comment(cid: int, user: dict = Depends(current_user)):
    row = db.query("SELECT * FROM comments WHERE id = ?", (cid,), one=True)
    if not row:
        return {"ok": True}
    is_admin = (user.get("role") or "") == "admin"
    if row["user_id"] != int(user["id"]) and not is_admin:
        raise HTTPException(403, "只能删除自己的评论")
    db.execute("DELETE FROM comments WHERE id = ? OR parent_id = ?", (cid, cid))
    if is_admin:
        db.execute("INSERT INTO audit_records(target_type, target_id, admin_id, action, reason,"
                   " created_at) VALUES('comment', ?, ?, 'delete', '', ?)",
                   (str(cid), user["id"], now_str()))
    return {"ok": True}


# ------------------------------------------------------------------ 收藏
@app.get("/api/favorites")
def favorites(group_id: int = -1, uid: int = Depends(uid_of)):
    sql = ("SELECT f.content_id, f.title, f.category, f.tag, f.collect_time, f.group_id,"
           " g.name AS group_name FROM app_favorites f"
           " LEFT JOIN collect_groups g ON g.id = f.group_id WHERE f.user_id = ?")
    params = [uid]
    if group_id >= 0:
        sql += " AND f.group_id = ?"
        params.append(group_id)
    rows = db.query(sql + " ORDER BY f.id DESC", params)
    out = []
    for r in rows:
        route = ""
        cid = r["content_id"] or ""
        if cid.startswith("c"):
            item = db.query("SELECT * FROM content_items WHERE id = ?", (cid[1:],), one=True)
            if item:
                route = content_route(item["feature_id"], item)
        elif cid.startswith("p"):
            post = db.query("SELECT * FROM posts WHERE id = ?", (cid[1:],), one=True)
            if post:
                route = post_route(post, uid)
        out.append({"contentId": cid, "title": r["title"], "category": r["category"],
                    "tag": r["tag"], "collectTime": r["collect_time"],
                    "groupId": int(r["group_id"] or 0), "groupName": r["group_name"] or "",
                    "route": route})
    return out


@app.post("/api/favorites")
def add_favorite(body: FavoriteIn, user: dict = Depends(current_user)):
    api_v2.guard_interact(user)
    uid = int(user["id"])
    if db.query("SELECT id FROM app_favorites WHERE user_id = ? AND content_id = ?",
                (uid, body.content_id), one=True):
        return {"ok": True, "added": False}
    db.execute(
        "INSERT INTO app_favorites(user_id, content_id, title, category, tag, collect_time,"
        " created_at) VALUES(?,?,?,?,?,?,?)",
        (uid, body.content_id, body.title, body.category, body.tag, "刚刚", now_str()))
    return {"ok": True, "added": True}


@app.delete("/api/favorites/{content_id}")
def remove_favorite(content_id: str, uid: int = Depends(uid_of)):
    db.execute("DELETE FROM app_favorites WHERE user_id = ? AND content_id = ?", (uid, content_id))
    return {"ok": True}


# ------------------------------------------------------------------ 笔记
@app.get("/api/notes")
def notes(uid: int = Depends(uid_of)):
    return db.query(
        "SELECT id, title, category, content, time_label AS createTime FROM notes"
        " WHERE user_id = ? ORDER BY id DESC", (uid,))


@app.post("/api/notes")
def add_note(body: NoteIn, uid: int = Depends(uid_of)):
    title, content = body.title.strip(), body.content.strip()
    if not title or not content:
        raise HTTPException(400, "标题和内容不能为空")
    nid = db.execute(
        "INSERT INTO notes(user_id, title, category, content, time_label, created_at)"
        " VALUES(?,?,?,?,?,?)", (uid, title, body.category, content, "刚刚", now_str()))
    return db.query("SELECT id, title, category, content, time_label AS createTime FROM notes"
                    " WHERE id = ?", (nid,), one=True)


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int, uid: int = Depends(uid_of)):
    db.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, uid))
    return {"ok": True}


# ------------------------------------------------------------------ 消息
@app.get("/api/messages")
def messages(uid: int = Depends(uid_of)):
    rows = db.query("SELECT * FROM messages WHERE user_id = ? ORDER BY id", (uid,))
    out = {"like": [], "comment": [], "system": []}
    for r in rows:
        out.setdefault(r["type"], []).append({
            "id": r["id"], "avatar": r["avatar"] or "", "name": r["name"] or "",
            "text": r["text"] or "", "time": r["time_label"] or "", "unread": bool(r["unread"]),
        })
    return out


@app.post("/api/messages/read")
def read_message(payload: dict, uid: int = Depends(uid_of)):
    mid = payload.get("id")
    if mid is not None:
        db.execute("UPDATE messages SET unread = 0 WHERE id = ? AND user_id = ?", (mid, uid))
    return {"ok": True}


@app.post("/api/messages/read-all")
def read_all(uid: int = Depends(uid_of)):
    db.execute("UPDATE messages SET unread = 0 WHERE user_id = ?", (uid,))
    return {"ok": True}


# ------------------------------------------------------------------ 足迹
@app.get("/api/footprints")
def footprints(uid: int = Depends(uid_of)):
    return db.query(
        "SELECT date_label AS date, type, title, summary FROM footprints"
        " WHERE user_id = ? ORDER BY id DESC", (uid,))


# ------------------------------------------------------------------ 我的动态
@app.get("/api/activity/{tab}")
def activity(tab: str, uid: int = Depends(uid_of)):
    if tab == "posts":
        rows = db.query(
            "SELECT id, title, time_label, likes, comments, sort, created_at, pinned, status,"
            " reject_reason FROM posts WHERE user_id = ?"
            " ORDER BY created_at DESC, id DESC", (uid,))
        label = {"pending": "审核中", "approved": "已通过",
                 "rejected": "已驳回", "offline": "已下架"}
        return [{"title": r["title"], "time": r["time_label"], "likes": r["likes"],
                 "comments": r["comments"], "status": r["status"] or "approved",
                 "status_text": label.get(r["status"] or "approved", ""),
                 "reject_reason": r["reject_reason"] or "",
                 "route": post_route(r, uid)} for r in rows]
    if tab == "likes":
        rows = db.query(
            "SELECT p.* FROM post_likes l JOIN posts p ON p.id = l.post_id"
            " WHERE l.user_id = ? ORDER BY l.id DESC", (uid,))
        return [{"title": r["title"], "author": r["author"], "time": r["time_label"],
                 "route": post_route(r, uid)} for r in rows]
    rows = db.query(
        "SELECT c.content AS text, c.time_label AS time, p.title AS post, p.id AS pid"
        " FROM comments c JOIN posts p ON p.id = c.post_id WHERE c.user_id = ?"
        " ORDER BY c.id DESC", (uid,))
    out = []
    for r in rows:
        post = db.query("SELECT * FROM posts WHERE id = ?", (r["pid"],), one=True)
        out.append({"text": r["text"], "post": r["post"], "time": r["time"],
                    "route": post_route(post, uid) if post else "#/community"})
    return out


# ------------------------------------------------------------------ 体质
@app.get("/api/tizhi")
def get_tizhi(uid: int = Depends(uid_of)):
    row = db.query("SELECT type_name, created_at FROM tizhi WHERE user_id = ? ORDER BY id DESC",
                   (uid,), one=True)
    return {"type_name": row["type_name"] if row else "",
            "created_at": row["created_at"] if row else ""}


@app.post("/api/tizhi")
def save_tizhi(body: TizhiIn, uid: int = Depends(uid_of)):
    db.execute("INSERT INTO tizhi(user_id, type_name, created_at) VALUES(?,?,?)",
               (uid, body.type_name, now_str()))
    return {"ok": True}


# ------------------------------------------------------------------ 设置
@app.get("/api/settings")
def get_settings(uid: int = Depends(uid_of)):
    row = db.query("SELECT * FROM settings WHERE user_id = ?", (uid,), one=True)
    if not row:
        db.execute("INSERT INTO settings(user_id) VALUES(?)", (uid,))
        row = db.query("SELECT * FROM settings WHERE user_id = ?", (uid,), one=True)
    return row


@app.put("/api/settings")
def update_settings(body: SettingsIn, uid: int = Depends(uid_of)):
    fields = body.dict(exclude_none=True)
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        db.execute(f"UPDATE settings SET {sets} WHERE user_id = ?", (*fields.values(), uid))
    return db.query("SELECT * FROM settings WHERE user_id = ?", (uid,), one=True)


# ------------------------------------------------------------------ 反馈 / 举报
@app.post("/api/feedback")
def feedback(body: FeedbackIn, uid: int = Depends(uid_of)):
    text = body.content.strip()
    if len(text) < 5:
        raise HTTPException(400, "反馈内容至少 5 个字")
    db.execute("INSERT INTO feedback(user_id, content, contact, created_at) VALUES(?,?,?,?)",
               (uid, text, body.contact.strip(), now_str()))
    return {"ok": True}


@app.post("/api/reports")
def report(body: ReportIn, uid: int = Depends(uid_of)):
    db.execute("INSERT INTO reports(user_id, target_id, target_type, reason, created_at)"
               " VALUES(?,?,?,?,?)", (uid, body.target_id, body.target_type, body.reason, now_str()))
    return {"ok": True}


# ------------------------------------------------------------------ 小药童聊天记录
@app.get("/api/chat")
def get_chat(uid: int = Depends(uid_of)):
    return db.query("SELECT role, html FROM chat_messages WHERE user_id = ? ORDER BY id", (uid,))


@app.post("/api/chat")
def add_chat(body: ChatIn, uid: int = Depends(uid_of)):
    db.execute("INSERT INTO chat_messages(user_id, role, html, created_at) VALUES(?,?,?,?)",
               (uid, body.role, body.html, now_str()))
    return {"ok": True}


@app.delete("/api/chat")
def clear_chat(uid: int = Depends(uid_of)):
    db.execute("DELETE FROM chat_messages WHERE user_id = ?", (uid,))
    return {"ok": True}


@app.exception_handler(HTTPException)
def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
