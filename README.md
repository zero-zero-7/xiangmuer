<div align="center">

# 四序颐养

**把中医养生翻译成年轻人能用的日常行动指南**

面向年轻人的中医药养生科普 + 养生交流社区 · 电脑端 / 手机端双版本

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-local.db-003B57?logo=sqlite&logoColor=white)
![Frontend](https://img.shields.io/badge/前端-单文件HTML%20无构建-B86B5C)

</div>

---

## 一、这是什么

当代年轻人亚健康问题普遍（久坐、熬夜、饮食不规律），但对中医药养生有三大障碍：

| 障碍 | 具体表现 |
|---|---|
| 信息碎片化 | 小红书、抖音上的内容零散不成体系，良莠不齐 |
| 门槛过高 | 术语晦涩，看不懂也不知道怎么落到日常 |
| 难以坚持 | 养生是长期的事，没有同伴容易放弃 |

「四序颐养」不做医疗问诊、不做处方推荐，只做两件事：

- **可落地的养生知识科普**：吃得对、动得对、按得对、睡得好
- **真实经验分享社区**：打卡、交流、互相鼓励

## 二、功能一览

| 模块 | 能力 |
|---|---|
| 首页 | 水墨 Banner、四大功能入口、今日推荐、悬浮小药童 |
| 饮食食疗 | 药食同源药膳、节气食谱，每条含做法、功效、宜忌 |
| 运动功法 | 八段锦、五禽戏、六字诀等标准健身气功 |
| 经络穴位 | 日常保健穴的定位、手法、适用症状 |
| 情志睡眠 | 呼吸法、静坐、助眠音频与作息建议 |
| 详情页 | 分段正文 + 演示视频 + 科普文章外链（权威来源） |
| 颐养社区 | 发帖（图文）、点赞、评论与回复、分类筛选、审核状态 |
| 小药童 | 悬浮 AI 养生助手，按板块推荐内容并可跳转 |
| 搜索 | 热词、全文检索、空态与结果分页 |
| 个人中心 | 收藏分组、我的笔记、修习足迹、消息通知、设置 |
| 体质测试 | 九种体质问答，生成结果并可分享 |
| 内容治理 | 举报、审核（通过 / 驳回 / 下架 / 置顶）、用户封禁 |
| 管理后台 | 内容审核、用户管理、举报处理、分类与标签维护 |

## 三、设计规范

新中式国风 × 现代极简，青釉白配色：

| 用途 | 色值 | 说明 |
|---|---|---|
| 主色 | `#3A6B6B` | 青釉色，导航栏、主按钮、标题 |
| 背景 | `#F2F5F2` | 月白 / 浅青灰 |
| 强调 | `#A8C4B8` | 标签、卡片高亮、次要按钮 |
| 正文灰青 | `#6B8A8A` | 次级文字、辅助说明 |
| 点缀砖红 | `#B86B5C` | 重点标记、印章、通知红点 |
| 深青墨 | `#2A4A4A` | 标题文字、底部导航深色区 |

标题用衬线体体现国风质感，正文用无衬线体保证可读性；卡片圆角 12px、柔和阴影，云纹与印章做点缀。

## 四、目录结构

```
四序颐养/
├── 前端/
│   ├── PC端.html          电脑版（白顶栏 + 横向导航，固定桌面布局）
│   └── 手机端.html        手机版（全屏 + 底部 Tab，适配刘海安全区）
├── 后端/
│   ├── app.py             服务入口、页面路由、主要业务接口
│   ├── api_v2.py          账号 / 微信登录 / 收藏分组 / 管理后台接口
│   ├── wechat.py          微信开放平台 OAuth（未配置则返回 503）
│   ├── db.py              MySQL 连接层
│   ├── db_local.py        SQLite 连接层（本地版默认）
│   ├── migrate.py         增量迁移（补列、补分类标签）
│   ├── seed.py            演示数据导入
│   └── requirements.txt
├── 数据库/
│   ├── local.db           SQLite，25 张表，含全部内容与视频链接
│   └── seed.json          演示用户 / 帖子种子
├── 启动四序颐养-本地版.bat  一键启动（自动装依赖 + 打开浏览器）
├── 说明.md                 启动、账号、换图与改链接说明
└── README.md
```

## 五、快速开始

需要 **Python 3.10+**，无需 Node、无需 Docker、无需 MySQL。

**方式一：双击启动（推荐）**

双击 `启动四序颐养-本地版.bat`，首次会自动安装依赖，完成后自动打开浏览器。

**方式二：命令行**

```bash
cd 后端
pip install -r requirements.txt
set DATABASE_URL=sqlite:///./local.db     # Windows；macOS/Linux 用 export
python -m uvicorn app:app --host 0.0.0.0 --port 8001
```

打开 <http://127.0.0.1:8001/>。

演示账号：`admin / admin123`、`demo / demo1234`

## 六、双端适配

后端按 UA 自动分发，也可以显式指定：

| 入口 | 说明 |
|---|---|
| `/` | 自动识别：电脑 → PC 版，手机 → 手机版 |
| `/pc` | 强制电脑版 |
| `/m` | 强制手机版 |

两个页面**内容、功能、文案完全一致**，只差布局：PC 版固定桌面布局（白顶栏、横向导航、无底部栏），手机版固定移动布局（全屏卡片、底部 Tab、`env(safe-area-inset-*)` 安全区）。

手机与电脑连同一 Wi-Fi 时，手机访问 `http://电脑IP:8001/` 即进入手机版。

## 七、数据和内容

内容全部在 SQLite 里，不再写死在前端：

| 表 | 行数 | 说明 |
|---|---|---|
| `content_items` | 125 | 四大板块的内容条目 |
| `content_sections` | 482 | 条目正文分段 |
| `content_links` | 159 | 外链：**51 条视频** + 108 篇科普文章 |

- 详情页的「📹 演示视频 / 📖 科普文章」由 `content_links` 驱动，`kind` 填 `video` 或 `article`
- 新增链接：`item_id` 对应 `content_items.id`，`sort` 控制顺序，重启后端生效
- 社区帖子、评论、收藏、笔记、足迹、消息等用户数据同样落在同一库里
- 前端内置一份内容仅作「后端未启动」时的兜底

## 八、接口概览

| 分组 | 主要接口 |
|---|---|
| 健康检查 | `GET /api/health` |
| 内容 | `GET /api/features`、`GET /api/features/{fid}/items-full`、`GET /api/search` |
| 账号 | `POST /api/auth/login`、`POST /api/auth/send-code`、`GET /api/me` |
| 微信 | `GET /api/auth/wechat/status`、`POST /api/auth/wechat/authorize`、`GET /api/auth/wechat/callback` |
| 社区 | `GET/POST /api/posts`、`POST /api/posts/{id}/like`、`GET/POST /api/posts/{id}/comments` |
| 个人 | `/api/favorites`、`/api/notes`、`/api/footprints`、`/api/messages`、`/api/tizhi`、`/api/settings` |
| 治理 | `POST /api/reports`、`/api/admin/contents/{id}/audit`、`/api/admin/users/{uid}/ban` |

接口文档启动后可在 <http://127.0.0.1:8001/docs> 查看（FastAPI 自动生成）。

## 九、技术架构

```
浏览器（PC端.html / 手机端.html，单文件，CSS/JS/图片内嵌）
        │  fetch + X-Auth-Token
        ▼
FastAPI (uvicorn :8001)
├── 页面路由     /  /pc  /m          → FileResponse 对应 HTML
├── 业务接口     api_v2.py + app.py
├── 登录鉴权     sessions 表 + Bearer Token
└── 数据层       db_local.py（SQLite）｜db.py（MySQL）
                        │
                        ▼
                  数据库/local.db
```

- `DATABASE_URL` 以 `sqlite` 开头走 SQLite，否则走 MySQL
- 单文件前端：改样式、加页面都在这两个 HTML 里，改完刷新即生效

## 十、内容来源与免责声明

内容参考《黄帝内经·素问》四季养生理论、《本草纲目》药食同源记载、国家中医药管理局「中医养生保健素养」科普内容、国家推广的健身气功标准功法，以及中国中医科学院公开的穴位保健资料。

> 所有内容均为**日常保健级别，不构成医疗建议**。如有疾病请及时就医。

## 十一、Roadmap

- [x] 四大养生板块内容体系（125 条 / 482 段正文）
- [x] 社区发帖、点赞、评论回复与审核
- [x] 收藏分组、笔记、足迹、消息、体质测试
- [x] 管理后台（审核、封禁、举报、分类标签）
- [x] 电脑端 / 手机端双版本 + UA 自动分发
- [x] 内容外链体系（51 条视频 + 108 篇文章）
- [ ] 微信扫码登录正式接入（当前为骨架，配置后可用）
- [ ] 二十四节气专题与节气自动推荐
- [ ] 关注系统与话题聚合
- [ ] 移动端打包（小程序 / App）
