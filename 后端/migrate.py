"""四序颐养 · 业务迁移脚本（幂等，可重复执行）

职责：
1. 建立分类 / 标签基础数据（后台可维护）
2. 初始化管理员与演示账号（用户名 + 密码）
3. 把历史社区帖子标记为已审核用户投稿，并补齐分类
"""
from datetime import datetime

import os as _os
if _os.getenv("DATABASE_URL", "").startswith("sqlite"):
    import db_local as db
else:
    import db
from security import hash_password

CATEGORIES = [
    ("diet", "饮食食疗", "bowl", "药食同源", 1),
    ("exercise", "运动功法", "run", "动以养形", 2),
    ("meridian", "经络穴位", "point", "通经活络", 3),
    ("emotion", "情志睡眠", "moon", "恬淡虚无", 4),
]

TAGS = {
    "crowd": ["上班族", "学生党", "中老年", "孕产妇", "儿童", "术后康复"],
    "solar": ["立春", "立夏", "立秋", "立冬", "春分", "夏至", "秋分", "冬至", "三伏", "三九"],
    "condition": ["健脾祛湿", "清心安神", "温阳散寒", "补气养血", "消食化积",
                  "润肺润燥", "疏肝理气", "固本培元", "缓解疲劳", "改善睡眠"],
}

POST_CAT_MAP = {
    "食疗分享": "diet", "功法打卡": "exercise", "穴位保健": "meridian",
    "情志睡眠": "emotion", "日常分享": "",
}

ADMIN = dict(username="admin", password="admin123", nickname="颐养管理员", tag="内容管理员")
DEMO = dict(username="demo", password="demo1234", nickname="养生修习者", tag="入门阶段")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def seed_categories():
    for cid, name, icon, descr, sort in CATEGORIES:
        if db.query("SELECT id FROM categories WHERE id = ?", (cid,), one=True):
            db.execute("UPDATE categories SET name=?, icon=?, descr=?, sort=? WHERE id=?",
                       (name, icon, descr, sort, cid))
        else:
            db.execute("INSERT INTO categories(id, name, icon, descr, sort, active, created_at)"
                       " VALUES(?,?,?,?,?,1,?)", (cid, name, icon, descr, sort, now_str()))


def seed_tags():
    sort = 0
    for dim, names in TAGS.items():
        for name in names:
            sort += 1
            row = db.query("SELECT id FROM tags WHERE name = ? AND dimension = ?",
                           (name, dim), one=True)
            if row:
                continue
            db.execute("INSERT INTO tags(name, dimension, sort, active, created_at)"
                       " VALUES(?,?,?,1,?)", (name, dim, sort, now_str()))


def upsert_account(username, password, nickname, tag, role):
    row = db.query("SELECT * FROM users WHERE username = ?", (username,), one=True)
    if row:
        if not row.get("password_hash"):
            db.execute("UPDATE users SET password_hash = ?, role = ? WHERE id = ?",
                       (hash_password(password), role, row["id"]))
        else:
            db.execute("UPDATE users SET role = ? WHERE id = ?", (role, row["id"]))
        return row["id"]
    uid = db.execute(
        "INSERT INTO users(nickname, avatar, tag, points, phone, username, password_hash,"
        " role, status, created_at) VALUES(?,?,?,?,?,?,?,?, 'normal', ?)",
        (nickname, nickname[:1], tag, 0, None, username, hash_password(password), role, now_str()))
    db.execute("INSERT IGNORE INTO settings(user_id) VALUES(?)", (uid,))
    return uid


def migrate_accounts():
    admin_id = upsert_account(ADMIN["username"], ADMIN["password"], ADMIN["nickname"],
                              ADMIN["tag"], "admin")
    demo = db.query("SELECT id FROM users WHERE phone = ?", ("13800000000",), one=True)
    if demo:
        db.execute("UPDATE users SET username = ?, password_hash = ?,"
                   " nickname = COALESCE(NULLIF(nickname,''), ?), role = 'user' WHERE id = ?",
                   (DEMO["username"], hash_password(DEMO["password"]), DEMO["nickname"], demo["id"]))
        demo_id = demo["id"]
    else:
        demo_id = upsert_account(DEMO["username"], DEMO["password"], DEMO["nickname"],
                                 DEMO["tag"], "user")
    return admin_id, demo_id


def migrate_posts(demo_id):
    rows = db.query("SELECT id, cat, user_id, status FROM posts")
    for r in rows:
        fields = {}
        if not r.get("status"):
            fields["status"] = "approved"
        if r.get("user_id") is None:
            fields["user_id"] = demo_id
        cid = POST_CAT_MAP.get(r.get("cat") or "", "")
        if cid:
            fields["category_id"] = cid
        if fields:
            sets = ", ".join(f"{k} = ?" for k in fields)
            db.execute(f"UPDATE posts SET {sets} WHERE id = ?", (*fields.values(), r["id"]))
    # 官方内容统一标记：已审核、非置顶
    db.execute("UPDATE posts SET pinned = 0 WHERE pinned IS NULL")
    db.execute("UPDATE users SET role = 'user' WHERE role IS NULL OR role = ''")
    db.execute("UPDATE users SET status = 'normal' WHERE status IS NULL OR status = ''")


def seed_welcome():
    admin = db.query("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1", one=True)
    if not admin:
        return
    exists = db.query("SELECT id FROM messages WHERE user_id = ? AND name = '系统通知' LIMIT 1",
                      (admin["id"],), one=True)
    if not exists:
        db.execute("INSERT INTO messages(user_id, type, avatar, name, text, time_label, unread,"
                   " link, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                   (admin["id"], "system", "系", "系统通知",
                    "管理后台已就绪：可在「我的 - 管理后台」审核投稿、置顶内容、处理举报。",
                    "刚刚", 1, "#/admin", now_str()))


def run():
    db.init_schema()
    seed_categories()
    seed_tags()
    admin_id, demo_id = migrate_accounts()
    migrate_posts(demo_id)
    seed_welcome()
    print(f"迁移完成：admin_id={admin_id}, demo_id={demo_id}, "
          f"分类 {db.query('SELECT COUNT(*) AS c FROM categories', one=True)['c']} 个，"
          f"标签 {db.query('SELECT COUNT(*) AS c FROM tags', one=True)['c']} 个")


if __name__ == "__main__":
    run()
