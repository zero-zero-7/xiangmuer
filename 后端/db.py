"""MySQL 数据访问层（数据库：siyu）

连接串通过 DATABASE_URL 环境变量配置：
    mysql://root:你的密码@127.0.0.1:3306/siyu
    mysql://user:pass@xxx.psdb.cloud/dbname?ssl_mode=REQUIRED  (PlanetScale)
"""
import os
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs

import pymysql
from pymysql.cursors import DictCursor

BASE = Path(__file__).resolve().parent


def load_env():
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

DB_URL = os.getenv("DATABASE_URL", "mysql://root@127.0.0.1:3306/siyu")
# 兼容 mysql:// 和 mysql+pymysql://
_u = urlparse(DB_URL.replace("mysql+pymysql://", "mysql://"))
_q = parse_qs(_u.query)

DB_CONF = dict(
    host=_u.hostname or "127.0.0.1",
    port=_u.port or 3306,
    user=unquote(_u.username or "root"),
    password=unquote(_u.password or ""),
    database=(_u.path or "/siyu").lstrip("/"),
    charset="utf8mb4",
    cursorclass=DictCursor,
    autocommit=False,
)

# PlanetScale / 云数据库强制 SSL
_ssl_mode = (_q.get("ssl_mode") or [""])[0].upper()
_is_planetscale = "psdb.cloud" in (DB_CONF["host"] or "")
if _ssl_mode in ("REQUIRED", "VERIFY_IDENTITY", "VERIFY_CA") or _is_planetscale:
    DB_CONF["ssl"] = {"ssl": True}


def connect(with_db=True):
    kwargs = {k: v for k, v in DB_CONF.items() if k != "database"}
    if with_db:
        kwargs["database"] = DB_CONF["database"]
    return pymysql.connect(**kwargs)


def _sql(sql):
    return sql.replace("?", "%s")


def query(sql, params=(), one=False):
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_sql(sql), tuple(params))
            rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def execute(sql, params=()):
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_sql(sql), tuple(params))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users(
        id INT AUTO_INCREMENT PRIMARY KEY, nickname VARCHAR(64) NOT NULL,
        avatar VARCHAR(8) DEFAULT '颐', tag VARCHAR(32) DEFAULT '入门阶段',
        points INT DEFAULT 0, phone VARCHAR(32) UNIQUE,
        created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS sessions(
        token VARCHAR(64) PRIMARY KEY, user_id INT NOT NULL,
        created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS posts(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, author VARCHAR(64) DEFAULT '',
        title VARCHAR(160) NOT NULL, body TEXT, cat VARCHAR(32) DEFAULT '日常分享',
        img VARCHAR(64) DEFAULT '', img_data LONGTEXT, likes INT DEFAULT 0,
        comments INT DEFAULT 0, time_label VARCHAR(32) DEFAULT '刚刚',
        sort INT DEFAULT 0, created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS post_sections(
        id INT AUTO_INCREMENT PRIMARY KEY, post_id INT NOT NULL,
        title VARCHAR(128) DEFAULT '', body TEXT, sort INT DEFAULT 0
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS comments(
        id INT AUTO_INCREMENT PRIMARY KEY, post_id INT NOT NULL, user_id INT,
        nickname VARCHAR(64) DEFAULT '', content TEXT, likes INT DEFAULT 0,
        reply_to VARCHAR(64) DEFAULT '', time_label VARCHAR(32) DEFAULT '刚刚',
        created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS app_favorites(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,
        content_id VARCHAR(64) NOT NULL, title VARCHAR(160), category VARCHAR(32),
        tag VARCHAR(64), collect_time VARCHAR(32) DEFAULT '刚刚',
        created_at VARCHAR(32) DEFAULT '', UNIQUE KEY uk_user_content(user_id, content_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS notes(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, title VARCHAR(160),
        category VARCHAR(32), content TEXT, time_label VARCHAR(32) DEFAULT '刚刚',
        created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS messages(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, type VARCHAR(16) NOT NULL,
        avatar VARCHAR(8), name VARCHAR(64), text TEXT, time_label VARCHAR(32),
        unread INT DEFAULT 0, created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS footprints(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,
        date_label VARCHAR(32), type VARCHAR(16), title VARCHAR(160), summary TEXT,
        created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS tizhi(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,
        type_name VARCHAR(32), created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS settings(
        user_id INT PRIMARY KEY, comment_notify INT DEFAULT 1, like_notify INT DEFAULT 1,
        system_notify INT DEFAULT 1, searchable INT DEFAULT 1,
        visibility VARCHAR(16) DEFAULT '公开'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS feedback(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, content TEXT,
        contact VARCHAR(64), created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS reports(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, target_id VARCHAR(64),
        target_type VARCHAR(32), reason VARCHAR(64), created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS chat_messages(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, role VARCHAR(8),
        html TEXT, created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS post_likes(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, post_id INT NOT NULL,
        created_at VARCHAR(32) DEFAULT '', UNIQUE KEY uk_user_post(user_id, post_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS useful_votes(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,
        content_id VARCHAR(64) NOT NULL, created_at VARCHAR(32) DEFAULT '',
        UNIQUE KEY uk_user_content(user_id, content_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]

SCHEMA_EXT = [
    """CREATE TABLE IF NOT EXISTS categories(
        id VARCHAR(32) PRIMARY KEY, name VARCHAR(32) NOT NULL, icon VARCHAR(16) DEFAULT '',
        descr VARCHAR(64) DEFAULT '', sort INT DEFAULT 0, active INT DEFAULT 1,
        created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS tags(
        id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(32) NOT NULL,
        dimension VARCHAR(16) NOT NULL DEFAULT 'condition', sort INT DEFAULT 0,
        active INT DEFAULT 1, created_at VARCHAR(32) DEFAULT '',
        UNIQUE KEY uk_tag(name, dimension)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS collect_groups(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, name VARCHAR(32) NOT NULL,
        sort INT DEFAULT 0, created_at VARCHAR(32) DEFAULT '',
        UNIQUE KEY uk_user_group(user_id, name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS likes(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,
        target_type VARCHAR(16) NOT NULL, target_id VARCHAR(64) NOT NULL,
        created_at VARCHAR(32) DEFAULT '',
        UNIQUE KEY uk_like(user_id, target_type, target_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS ban_records(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, admin_id INT DEFAULT 0,
        reason VARCHAR(255) DEFAULT '', until VARCHAR(32) DEFAULT '',
        created_at VARCHAR(32) DEFAULT '', lifted_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS audit_records(
        id INT AUTO_INCREMENT PRIMARY KEY, target_type VARCHAR(16) NOT NULL,
        target_id VARCHAR(64) NOT NULL, admin_id INT DEFAULT 0, action VARCHAR(16) NOT NULL,
        reason VARCHAR(255) DEFAULT '', created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS cancel_records(
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, requested_at VARCHAR(32) DEFAULT '',
        effective_at VARCHAR(32) DEFAULT '', status VARCHAR(16) DEFAULT 'pending',
        created_at VARCHAR(32) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]

EXTRA_COLUMNS = {
    "users": [
        ("username", "VARCHAR(64) NULL"),
        ("password_hash", "VARCHAR(255) DEFAULT ''"),
        ("role", "VARCHAR(16) DEFAULT 'user'"),
        ("status", "VARCHAR(16) DEFAULT 'normal'"),
        ("ban_until", "VARCHAR(32) DEFAULT ''"),
        ("ban_reason", "VARCHAR(255) DEFAULT ''"),
        ("cancel_at", "VARCHAR(32) DEFAULT ''"),
        ("bio", "VARCHAR(255) DEFAULT ''"),
        ("wechat_openid", "VARCHAR(64) NULL"),
        ("wechat_unionid", "VARCHAR(64) NULL"),
    ],
    "posts": [
        ("status", "VARCHAR(16) DEFAULT 'approved'"),
        ("reject_reason", "VARCHAR(255) DEFAULT ''"),
        ("pinned", "INT DEFAULT 0"),
        ("pinned_at", "VARCHAR(32) DEFAULT ''"),
        ("views", "INT DEFAULT 0"),
        ("category_id", "VARCHAR(32) DEFAULT ''"),
        ("tags", "VARCHAR(255) DEFAULT ''"),
        ("audit_at", "VARCHAR(32) DEFAULT ''"),
    ],
    "comments": [
        ("parent_id", "INT DEFAULT 0"),
        ("target_type", "VARCHAR(16) DEFAULT 'post'"),
        ("status", "VARCHAR(16) DEFAULT 'normal'"),
    ],
    "app_favorites": [
        ("group_id", "INT DEFAULT 0"),
    ],
    "reports": [
        ("status", "VARCHAR(16) DEFAULT 'pending'"),
        ("handled_by", "INT DEFAULT 0"),
        ("result", "VARCHAR(255) DEFAULT ''"),
        ("handled_at", "VARCHAR(32) DEFAULT ''"),
    ],
    "messages": [
        ("link", "VARCHAR(128) DEFAULT ''"),
    ],
}

INDEXES = [
    ("users", "uk_users_username", "UNIQUE KEY uk_users_username(username)"),
    ("users", "uk_users_wechat_openid", "UNIQUE KEY uk_users_wechat_openid(wechat_openid)"),
    ("posts", "idx_posts_status", "KEY idx_posts_status(status)"),
    ("comments", "idx_comments_parent", "KEY idx_comments_parent(parent_id)"),
    ("reports", "idx_reports_status", "KEY idx_reports_status(status)"),
]


def _existing_columns(table):
    rows = query(
        "SELECT COLUMN_NAME AS c FROM information_schema.columns"
        " WHERE table_schema = ? AND table_name = ?", (DB_CONF["database"], table))
    return {r["c"] for r in rows}


def ensure_columns():
    for table, cols in EXTRA_COLUMNS.items():
        exist = _existing_columns(table)
        if not exist:
            continue
        for name, ddl in cols:
            if name in exist:
                continue
            try:
                execute(f"ALTER TABLE `{table}` ADD COLUMN `{name}` {ddl}")
            except Exception as e:
                print(f"[schema] 添加 {table}.{name} 失败: {e}")
    for table, idx_name, idx_ddl in INDEXES:
        try:
            execute(f"ALTER TABLE `{table}` ADD {idx_ddl}")
        except Exception:
            pass


def init_schema():
    conn = connect(with_db=False)
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONF['database']}` "
                        "DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        conn.commit()
    finally:
        conn.close()
    conn = connect()
    try:
        with conn.cursor() as cur:
            for ddl in SCHEMA + SCHEMA_EXT:
                cur.execute(ddl)
        conn.commit()
    finally:
        conn.close()
    ensure_columns()


def is_seeded():
    try:
        row = query("SELECT COUNT(*) AS c FROM features", one=True)
        return bool(row and row["c"] > 0)
    except Exception:
        return False
