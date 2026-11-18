# 四序颐养

二十四节气养生 Web 应用，分前后端两个版本页面：电脑端与手机端，内容一致，仅布局适配不同。

## 目录

```
前端/           PC端.html（电脑版）、手机端.html（手机版）
后端/           FastAPI：app.py 入口 / api_v2.py 接口 / wechat.py 微信登录 / db.py(MySQL) / db_local.py(SQLite)
数据库/         local.db（SQLite，含全部内容与视频链接）、seed.json
启动四序颐养-本地版.bat    一键启动（自动建库 + 打开浏览器）
说明.md         启动方式、账号、换图与改链接说明
```

## 本地运行

需要 Python 3.10+，双击 `启动四序颐养-本地版.bat` 即可（首次会自动安装依赖）。

- 电脑访问 <http://127.0.0.1:8001/>（自动进 PC 版）
- 手机同一 Wi-Fi 访问 `http://电脑IP:8001/`（自动进手机版）
- `/pc` 强制电脑版，`/m` 强制手机版

演示账号：`admin / admin123`、`demo / demo1234`

## 数据

内容与视频链接存在 SQLite：

- `content_items` 125 条内容条目
- `content_sections` 482 段正文
- `content_links` 159 条外链（51 条视频 + 108 篇文章）

改链接直接改 `content_links` 表，`kind` 填 `video` 或 `article`，`item_id` 对应 `content_items.id`。

## 技术栈

FastAPI + SQLite/MySQL，前端为单文件 HTML（内置 CSS/JS，无构建步骤）。
