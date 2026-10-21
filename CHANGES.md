# 更新记录

## 1.3.0 - 2026-10-22

### 新增

- 插件更名为「QQ空间互动」，菜单类型改为「一些工具」
- 自动评论：评论名单内的好友说说会按监控间隔自动评论，默认关闭
- 用户偏好表：`accept_like` 默认接收、`accept_comment` 默认不接收
- 点赞勿扰名单与评论名单，管理员可管理任意 QQ，普通用户只能管理自己
- 每个用户可设置自己的秒评内容；全局默认内容为 `QεQ`
- 管理员指令：全局开关、监控间隔、全局内容、名单增删查清
- 普通用户指令：个人开关、个人内容、查看设置、恢复默认内容
- 共享扫描：点赞与评论共用一次 `get_friend_feeds`
- 评论记录表与评论去重、每日限额、随机延迟

### 变更

- `enable_auto_like` / `like_interval` 只用于首次初始化运行态配置
- 监控间隔默认 120 秒，允许 30-3600 秒
- 点赞与评论分别使用独立的每轮/每日上限
- 旧指令「空间点赞状态」保留为「查看空间配置」的别名
- 新增配置 `comment_max_per_round` / `comment_daily_limit` /
  `comment_delay_min` / `comment_delay_max`

### 验证

- `ruff check`：通过
- `pytest`：11 项纯逻辑测试通过
- 真寻运行时：插件加载成功，17 条指令注册成功，4 张表创建成功
- 点赞轮次：抓取 6 条，点赞 1 条，跳过 5 条
- 评论轮次：评论名单为空时正确跳过，不产生评论
- 偏好 CRUD：临时 SQLite 库验证运行态配置、个人偏好与名单增删查清

---

# qzone_auto_like 优化改动总结

- 日期：2026-10-14
- 目标：按代码评审清单优化 `qzone_auto_like` 插件（真寻 QQ 空间自动点赞）
- 版本：`1.1.0` -> `1.2.0`

## 背景

评审发现该插件存在功能性与架构性问题，其中最关键的两点：

1. README 承诺的「防重复点赞」在代码中**未实现**——每轮都会对时间线上所有说说重新点赞并写入记录。
2. 点赞主逻辑 `from onebot_qzone import QzoneSession` 依赖一个**不存在的 Python 包**；`onebot-qzone` 实际是 Node/TypeScript 的 OneBot 桥接服务，点赞/拉时间线/Cookie 更新都应通过其 HTTP action 完成。因此原点赞链路实际不工作。

## 文件改动

| 文件 | 类型 | 说明 |
|------|------|------|
| `qzone_auto_like/bridge.py` | 新增 | onebot-qzone 桥接服务 HTTP 客户端（统一 session、Bearer 鉴权），封装 `check_cookie`/`update_cookie`/`get_friend_feeds`/`send_like` 等 action |
| `qzone_auto_like/like_service.py` | 新增 | 自动点赞业务：去重 + 每日限额 + 随机延迟 + 结果校验 + 逐条容错 |
| `qzone_auto_like/models.py` | 修改 | 增加 `(qq_number, qzone_post_id)` 唯一约束与 `(qq_number, like_time)` 索引 |
| `qzone_auto_like/config.py` | 修改 | `enable_auto_like` 默认改 `False`；新增随机延迟/每日上限配置；补全作者；加 introduction/precautions |
| `qzone_auto_like/cookie_refresher.py` | 修改 | 复用 `QzoneBridgeClient` 与单个 aiohttp session；预检失败 fail-open；去掉重复校验 |
| `qzone_auto_like/__init__.py` | 修改 | 改用 apscheduler 调度；每轮热读配置；服务按配置变化重建；状态命令加 SUPERUSER 权限 |
| `README.md` | 修改 | 更新架构说明、配置表与默认值、注意事项 |
| `.gitignore` | 新增 | 忽略 `__pycache__/`、`*.pyc`、`.venv/` |

## 评审项 -> 落地对照

| 编号 | 问题 | 处理 |
|------|------|------|
| 1 | 防重复点赞未实现 | `like_service.py` 先查已点赞 tid 集合再跳过 |
| 2 | 记录表缺唯一约束 | `models.py` 加 `unique_together`（实测重复插入抛 `IntegrityError`） |
| 3 | 点赞结果未校验即落库 | 经 `call_data` 校验 `retcode==0` 后才 `get_or_create` |
| 4 | 架构自相矛盾 | 新增 `bridge.py`，删除死导入，点赞改走桥接 HTTP action |
| 5 | Cookie 预检失败阻断刷新 | `refresh_once` 预检异常时 fail-open 继续刷新 |
| 6 | 固定 1 秒、无上限 | 随机延迟 + `daily_like_limit` |
| 7 | 出错中断整轮 | 单条点赞 try/except 后继续 |
| 8 | 每轮重复登录 | 复用单个 aiohttp session |
| 9 | 裸 asyncio 循环 | 改 apscheduler `add_job(replace_existing=True)` 的 tick 模式 |
| 10 | 配置固化需重启 | 每 tick 热读配置，`_ensure_services()` 按变化重建 |
| 11 | `enable_auto_like` 默认 True | 默认改 `False` |
| 12 | 状态命令无权限 | 加 `permission=SUPERUSER`（行为变更） |
| 13 | 作者占位 | `author="FlakoWESH"` |
| 14 | 日志器不统一 | 统一用 `zhenxun.services.log.logger` |
| 15 | 类型注解不规范 | 改为 `list[str]`、`X | None` |
| 16 | 重复校验 | 必填字段仅在 `fetch_cookie_from_napcat` 校验一次 |
| 17 | 每次新建 session | 复用 `ClientSession` |
| 18 | README 提醒 | 更新说明并标注默认关闭与风险 |

## 行为变更

- `enable_auto_like` 默认关闭，需在后台显式开启。
- 状态命令 `空间点赞状态` 现仅超级用户可查询。
- 点赞链路从「本地不存在的 Python 库」改为「onebot-qzone 桥接服务 HTTP action」，需桥接服务运行且 `bridge_url`/`bridge_token` 正确。

## 验证

- `python -m py_compile`：通过。
- `ruff check`：通过。
- `bridge.py` / `config.py` 直接加载：通过。
- Tortoise 唯一约束 + 索引 DDL、`get_or_create`、`values_list(flat)`、`count`：实测正常。
- apscheduler `add_job` 支持 `id`/`replace_existing`：实测支持。
- 完整运行时加载未做（未将插件安装进 `zhenxun_bot/plugins/`，以避免未经请求改变运行态）。
