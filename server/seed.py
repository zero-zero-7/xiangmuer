"""导入演示用户、社区帖子与个人数据（幂等，可重复运行）。"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import db

BASE = Path(__file__).resolve().parent
SEED = BASE / "data" / "seed.json"


def now(offset_minutes=0):
    return (datetime.now() - timedelta(minutes=offset_minutes)).strftime("%Y-%m-%d %H:%M:%S")


def ensure_user(data):
    row = db.query("SELECT * FROM users WHERE phone = ?", ("13800000000",), one=True)
    if row:
        return row["id"]
    uid = db.execute(
        "INSERT INTO users(nickname, avatar, tag, points, phone, created_at) VALUES(?,?,?,?,?,?)",
        (data["profile"]["name"], "颐", data["profile"]["tag"],
         data["profile"]["stats"][0]["num"], "13800000000", now()))
    db.execute("INSERT IGNORE INTO settings(user_id) VALUES(?)", (uid,))
    return uid


def seed_posts(data, uid):
    if db.query("SELECT id FROM posts LIMIT 1", one=True):
        return
    samples = data["commentSamples"]
    for i, it in enumerate(data["features"]):
        if it["id"] != "fun":
            continue
        for idx, post in enumerate(it["items"]):
            pid = db.execute(
                "INSERT INTO posts(user_id, author, title, body, cat, img, likes, comments,"
                " time_label, sort, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (None, post.get("author", ""), post["name"],
                 (post.get("sections") or [{}])[0].get("body", ""), post.get("cat", "日常分享"),
                 post.get("img", ""), int(post.get("likes", 0)), 0, post.get("time", "刚刚"),
                 idx, now(60 * (idx + 1))))
            for s_i, sec in enumerate(post.get("sections", [])):
                db.execute("INSERT INTO post_sections(post_id, title, body, sort) VALUES(?,?,?,?)",
                           (pid, sec.get("title", ""), sec.get("body", ""), s_i))
            for c_i, c in enumerate(samples):
                db.execute(
                    "INSERT INTO comments(post_id, user_id, nickname, content, likes, reply_to,"
                    " time_label, created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (pid, None, c["nickname"], c["content"], int(c.get("likes", 0)), "",
                     c.get("time", "刚刚"), now(30 * (c_i + 1))))

    # 我发布的两条帖子，让「我的动态-我发布的」有真实数据
    demo = [
        ("我的秋日养生茶桌，一壶枸杞菊花", "日常分享",
         [("正文", "周末给自己搭了一个小茶桌，煮一壶枸杞菊花茶，晒着太阳慢慢喝，整个人都松下来了。"),
          ("小贴士", "枸杞5g+菊花3朵，80度水泡5分钟，下午喝最舒服。")]),
        ("八段锦打卡第21天，肩颈松快多了", "功法打卡",
         [("正文", "坚持每天早起打一遍八段锦，第三周开始明显感觉肩颈不僵了，分享给同样久坐的朋友。"),
          ("小贴士", "重点在“慢”和“呼吸”，动作幅度不用追求标准。")]),
    ]
    for i, (title, cat, secs) in enumerate(demo):
        pid = db.execute(
            "INSERT INTO posts(user_id, author, title, body, cat, img, likes, comments,"
            " time_label, sort, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (uid, data["profile"]["name"], title, secs[0][1], cat, "", 0, 0,
             "2天前", 100 + i, now(200 + i)))
        for s_i, (t, b) in enumerate(secs):
            db.execute("INSERT INTO post_sections(post_id, title, body, sort) VALUES(?,?,?,?)",
                       (pid, t, b, s_i))
    return


def seed_activity(data, uid):
    posts = db.query("SELECT id, title FROM posts ORDER BY id")
    by_name = {p["title"]: p["id"] for p in posts}
    for i, name in enumerate([
        "山药薏米粥连喝一周，湿气真的轻了",
        "按揉足三里缓解胃胀，亲测有效",
        "睡前的十分钟静坐，把心收回来",
    ]):
        pid = by_name.get(name)
        if pid and not db.query("SELECT id FROM post_likes WHERE user_id=? AND post_id=?",
                                (uid, pid), one=True):
            db.execute("INSERT INTO post_likes(user_id, post_id, created_at) VALUES(?,?,?)",
                       (uid, pid, now(120 + i)))
    for i, (name, text) in enumerate([
        ("山药薏米粥连喝一周，湿气真的轻了", "跟着做了一周，确实有效！"),
        ("八段锦打卡第21天，肩颈松快多了", "一起加油，坚持就是胜利～"),
        ("睡前的十分钟静坐，把心收回来", "今晚就试试这个方法。"),
    ]):
        pid = by_name.get(name)
        if pid:
            exists = db.query(
                "SELECT id FROM comments WHERE post_id=? AND user_id=? AND content=?",
                (pid, uid, text), one=True)
            if not exists:
                db.execute(
                    "INSERT INTO comments(post_id, user_id, nickname, content, likes, reply_to,"
                    " time_label, created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (pid, uid, data["profile"]["name"], text, 0, "", "昨天", now(600 + i)))


def seed_personal(data, uid):
    if not db.query("SELECT id FROM app_favorites WHERE user_id = ? LIMIT 1", (uid,), one=True):
        picks = [
            ("山药薏米粥", "饮食食疗"),
            ("两手托天理三焦", "运动功法"),
            ("神门", "经络穴位"),
            ("固定生物钟", "情志睡眠"),
            ("菊花决明子茶", "饮食食疗"),
            ("足三里", "经络穴位"),
        ]
        for i, (name, cat) in enumerate(picks):
            item = db.query(
                "SELECT ci.id, ci.tag FROM content_items ci WHERE ci.name = ? LIMIT 1",
                (name,), one=True)
            if not item:
                continue
            db.execute(
                "INSERT INTO app_favorites(user_id, content_id, title, category, tag, collect_time,"
                " created_at) VALUES(?,?,?,?,?,?,?)",
                (uid, f"c{item['id']}", name, cat, item["tag"] or "", ["3天前", "1周前", "2周前"][i % 3], now()))

    if not db.query("SELECT id FROM footprints WHERE user_id = ? LIMIT 1", (uid,), one=True):
        for i, fp in enumerate(data["footprints"]):
            db.execute(
                "INSERT INTO footprints(user_id, date_label, type, title, summary, created_at)"
                " VALUES(?,?,?,?,?,?)",
                (uid, fp["date"], fp["type"], fp["title"], fp["summary"], now(i * 60)))
    if not db.query("SELECT id FROM notes WHERE user_id = ? LIMIT 1", (uid,), one=True):
        for i, note in enumerate(data["notes"]):
            db.execute(
                "INSERT INTO notes(user_id, title, category, content, time_label, created_at)"
                " VALUES(?,?,?,?,?,?)",
                (uid, note["title"], note["category"], note["content"], note["createTime"], now(i * 60)))
    if not db.query("SELECT id FROM messages WHERE user_id = ? LIMIT 1", (uid,), one=True):
        for mtype, rows in data["messages"].items():
            for m in rows:
                db.execute(
                    "INSERT INTO messages(user_id, type, avatar, name, text, time_label, unread,"
                    " created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (uid, mtype, m.get("avatar", ""), m.get("name", ""), m.get("text", ""),
                     m.get("time", ""), 1 if m.get("unread") else 0, now()))
    if not db.query("SELECT id FROM chat_messages WHERE user_id = ? LIMIT 1", (uid,), one=True):
        db.execute("INSERT INTO chat_messages(user_id, role, html, created_at) VALUES(?,?,?,?)",
                   (uid, "ai", "你好呀！我是小药童～可以问我养生问题、找食谱、要推荐哦 🌿", now()))


def seed():
    data = json.loads(SEED.read_text(encoding="utf-8"))
    uid = ensure_user(data)
    seed_posts(data, uid)
    seed_activity(data, uid)
    seed_personal(data, uid)
    print(f"种子数据就绪：用户 id={uid}，帖子 "
          f"{db.query('SELECT COUNT(*) AS c FROM posts', one=True)['c']} 条")


if __name__ == "__main__":
    db.init_schema()
    seed()
