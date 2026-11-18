"""SQLite 兼容层 —— 用于本地单机版（零依赖，Python 自带 sqlite3）

这个模块是 db.py 的 SQLite 替代品。
当 DATABASE_URL=sqlite:///./local.db 时自动走这里。
API 和 db.py 完全一样：connect / query / execute / init_schema / is_seeded
"""
import os
import sqlite3
import threading
from pathlib import Path

BASE = Path(__file__).resolve().parent          # 后端/
ROOT = BASE.parent                              # 项目根目录
# 数据库文件统一放在 数据库/local.db；可用 SQLITE_PATH 覆盖
LOCAL_DB = Path(os.getenv("SQLITE_PATH") or (ROOT / "数据库" / "local.db"))

_lock = threading.Lock()


def connect(with_db=True):
    """连接 SQLite（with_db 参数兼容 db.py，SQLite 总是连同一个文件）"""
    conn = sqlite3.connect(str(LOCAL_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _convert_sql(sql):
    """把 MySQL DDL/DML 转 SQLite 兼容"""
    # INSERT IGNORE INTO → INSERT OR IGNORE INTO
    sql = sql.replace("INSERT IGNORE INTO", "INSERT OR IGNORE INTO")
    # ON DUPLICATE KEY UPDATE → OR REPLACE INTO (简单替换，部分场景语义不同)
    # 这个比较复杂，简单处理即可
    if "ON DUPLICATE KEY UPDATE" in sql:
        sql = sql.split("ON DUPLICATE KEY UPDATE")[0].replace("INSERT INTO", "INSERT OR REPLACE INTO")
    # ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    sql = sql.replace("ENGINE=InnoDB", "")
    sql = sql.replace("DEFAULT CHARSET=utf8mb4", "")
    sql = sql.replace("CHARSET=utf8mb4", "")
    sql = sql.replace("COLLATE=utf8mb4_0900_ai_ci", "")
    # AUTO_INCREMENT → 删掉
    sql = sql.replace("AUTO_INCREMENT", "")
    # 反引号 → 双引号
    sql = sql.replace("`", '"')
    # LONGTEXT → TEXT
    sql = sql.replace("LONGTEXT", "TEXT")
    # TINYINT / SMALLINT → INTEGER
    sql = sql.replace("TINYINT", "INTEGER")
    sql = sql.replace("SMALLINT", "INTEGER")
    # DATETIME → TEXT
    sql = sql.replace("DATETIME", "TEXT")
    return sql


def query(sql, params=(), one=False):
    sql = _convert_sql(sql)
    with _lock:
        conn = connect()
        try:
            cur = conn.execute(sql, tuple(params))
            rows = [dict(r) for r in cur.fetchall()]
            return (rows[0] if rows else None) if one else rows
        finally:
            conn.close()


def execute(sql, params=()):
    sql = _convert_sql(sql)
    with _lock:
        conn = connect()
        try:
            cur = conn.execute(sql, tuple(params))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


# ── 注意：下面的 SCHEMA 和 db.py 里 MySQL 版略有不同（去掉 MySQL 特有语法） ──

SCHEMA_SQLITE = [
    """CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT NOT NULL, avatar TEXT DEFAULT '颐',
        tag TEXT DEFAULT '入门阶段', points INTEGER DEFAULT 0,
        phone TEXT UNIQUE, created_at TEXT DEFAULT '',
        username TEXT, password_hash TEXT DEFAULT '',
        role TEXT DEFAULT 'user', status TEXT DEFAULT 'normal',
        bio TEXT DEFAULT '',
        wechat_openid TEXT, wechat_unionid TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sessions(
        token TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
        created_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, author TEXT DEFAULT '',
        title TEXT NOT NULL, body TEXT, cat TEXT DEFAULT '日常分享',
        img TEXT DEFAULT '', img_data TEXT, likes INTEGER DEFAULT 0,
        comments INTEGER DEFAULT 0, time_label TEXT DEFAULT '刚刚',
        sort INTEGER DEFAULT 0, created_at TEXT DEFAULT '',
        status TEXT DEFAULT 'approved', pinned INTEGER DEFAULT 0,
        views INTEGER DEFAULT 0, category_id TEXT DEFAULT '',
        tags TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS post_sections(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL, title TEXT DEFAULT '',
        body TEXT, sort INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS comments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL, user_id INTEGER,
        nickname TEXT DEFAULT '', content TEXT, likes INTEGER DEFAULT 0,
        reply_to TEXT DEFAULT '', time_label TEXT DEFAULT '刚刚',
        created_at TEXT DEFAULT '', parent_id INTEGER DEFAULT 0,
        status TEXT DEFAULT 'normal'
    )""",
    """CREATE TABLE IF NOT EXISTS app_favorites(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, content_id TEXT NOT NULL,
        title TEXT, category TEXT, tag TEXT, group_id INTEGER DEFAULT 0,
        collect_time TEXT DEFAULT '刚刚', created_at TEXT DEFAULT '',
        UNIQUE(user_id, content_id)
    )""",
    """CREATE TABLE IF NOT EXISTS notes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, title TEXT, category TEXT,
        content TEXT, time_label TEXT DEFAULT '刚刚', created_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, type TEXT NOT NULL,
        avatar TEXT, name TEXT, text TEXT, time_label TEXT,
        unread INTEGER DEFAULT 0, link TEXT DEFAULT '',
        created_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS footprints(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, date_label TEXT, type TEXT,
        title TEXT, summary TEXT, created_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS tizhi(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, type_name TEXT, created_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS settings(
        user_id INTEGER PRIMARY KEY,
        comment_notify INTEGER DEFAULT 1, like_notify INTEGER DEFAULT 1,
        system_notify INTEGER DEFAULT 1, searchable INTEGER DEFAULT 1,
        visibility TEXT DEFAULT '公开'
    )""",
    """CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, content TEXT, contact TEXT, created_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, target_id TEXT, target_type TEXT,
        reason TEXT, status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS chat_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, role TEXT, html TEXT, created_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS post_likes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, post_id INTEGER NOT NULL,
        created_at TEXT DEFAULT '', UNIQUE(user_id, post_id)
    )""",
    """CREATE TABLE IF NOT EXISTS useful_votes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, content_id TEXT NOT NULL,
        created_at TEXT DEFAULT '', UNIQUE(user_id, content_id)
    )""",
    # 额外表
    """CREATE TABLE IF NOT EXISTS categories(
        id TEXT PRIMARY KEY, name TEXT NOT NULL, icon TEXT DEFAULT '',
        descr TEXT DEFAULT '', sort INTEGER DEFAULT 0, active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS tags(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, dimension TEXT NOT NULL DEFAULT 'condition',
        sort INTEGER DEFAULT 0, active INTEGER DEFAULT 1, created_at TEXT DEFAULT '',
        UNIQUE(name, dimension)
    )""",
    """CREATE TABLE IF NOT EXISTS collect_groups(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, name TEXT NOT NULL, sort INTEGER DEFAULT 0,
        created_at TEXT DEFAULT '', UNIQUE(user_id, name)
    )""",
    """CREATE TABLE IF NOT EXISTS likes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, target_type TEXT NOT NULL,
        target_id TEXT NOT NULL, created_at TEXT DEFAULT '',
        UNIQUE(user_id, target_type, target_id)
    )""",
    # 业务内容表
    """CREATE TABLE IF NOT EXISTS features(
        id TEXT PRIMARY KEY, name TEXT NOT NULL, descr TEXT DEFAULT '',
        icon TEXT DEFAULT '', sort INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS content_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feature_id TEXT NOT NULL, name TEXT NOT NULL,
        tag TEXT DEFAULT '', summary TEXT DEFAULT '', sort INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS content_sections(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL, title TEXT DEFAULT '',
        body TEXT, sort INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS content_links(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER, feature_id TEXT DEFAULT '',
        title TEXT DEFAULT '', source TEXT DEFAULT '', url TEXT NOT NULL,
        kind TEXT DEFAULT 'article', note TEXT DEFAULT '', sort INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS audit_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_type TEXT NOT NULL, target_id TEXT NOT NULL,
        admin_id INTEGER DEFAULT 0, action TEXT NOT NULL,
        reason TEXT DEFAULT '', created_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS ban_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, admin_id INTEGER DEFAULT 0,
        reason TEXT DEFAULT '', until TEXT DEFAULT '', created_at TEXT DEFAULT '',
        lifted_at TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS cancel_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, requested_at TEXT DEFAULT '', effective_at TEXT DEFAULT '',
        status TEXT DEFAULT 'pending', created_at TEXT DEFAULT ''
    )""",
]


def ensure_columns():
    """给已存在的 local.db 补齐后加的列（幂等）"""
    extra = {
        "users": [("wechat_openid", "TEXT"), ("wechat_unionid", "TEXT"),
                  ("ban_reason", "TEXT DEFAULT ''"), ("ban_until", "TEXT DEFAULT ''"),
                  ("cancel_at", "TEXT DEFAULT ''")],
        "posts": [("audit_at", "TEXT DEFAULT ''"), ("pinned_at", "TEXT DEFAULT ''"),
                  ("reject_reason", "TEXT DEFAULT ''")],
        "comments": [("target_type", "TEXT DEFAULT 'post'")],
        "reports": [("handled_at", "TEXT DEFAULT ''"), ("handled_by", "INTEGER DEFAULT 0"),
                    ("result", "TEXT DEFAULT ''")],
    }
    with _lock:
        conn = connect()
        try:
            for table, cols in extra.items():
                exist = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
                for name, ddl in cols:
                    if name not in exist:
                        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS uk_users_wechat_openid'
                         ' ON users(wechat_openid)')
            conn.commit()
        finally:
            conn.close()


def init_schema():
    """创建所有表"""
    # 确保文件存在
    LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
    if not LOCAL_DB.exists():
        LOCAL_DB.touch()

    with _lock:
        conn = connect()
        try:
            for ddl in SCHEMA_SQLITE:
                conn.execute(ddl)
            conn.commit()
        finally:
            conn.close()
    ensure_columns()


def is_seeded():
    """检查是否已有种子数据"""
    try:
        row = query("SELECT COUNT(*) AS c FROM features", one=True)
        return bool(row and row["c"] > 0)
    except Exception:
        return False
