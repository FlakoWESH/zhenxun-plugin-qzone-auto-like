# QQ空间互动（zhenxun-plugin-qzone-auto-like）

真寻（ZhenXun）框架的 QQ 空间互动插件：自动点赞、自动评论好友说说，支持点赞勿扰名单、评论名单与个人评论内容。Cookie 可复用真寻已有的 OneBot 连接从 NapCat 自动获取。

## ✨ 功能特性

- **自动点赞**：默认面向所有好友；用户可把自己加入点赞勿扰名单
- **自动评论**：默认关闭；只有评论名单内的用户会被评论
- **个人评论内容**：每个用户可以设置自己的秒评内容，未设置时使用全局模板
- **管理员与普通用户分权**：同一句“关闭秒赞”，管理员关闭全局，普通用户只设置自己
- **共享扫描**：每轮只拉取一次好友时间线，点赞与评论共用，减少空间请求
- **防重复**：点赞、评论分别落库，失败不标记，下一轮自动重试
- **限额与随机延迟**：点赞/评论独立的每轮与每日上限，降低风控风险
- **Cookie 自动刷新**：复用 OneBot 连接调用 NapCat `get_cookies`，按需刷新

## 📦 安装

将 `qzone_auto_like` 文件夹复制到真寻框架的 `plugins/` 目录下，重启 Bot 即可。真寻不支持符号链接插件目录，请复制实体文件。

```
zhenxun_bot/
└── plugins/
    └── qzone_auto_like/
        ├── __init__.py
        ├── bridge.py            # onebot-qzone HTTP 客户端
        ├── commands.py          # 管理员/普通用户指令
        ├── comment_service.py   # 自动评论
        ├── config.py
        ├── cookie_refresher.py
        ├── feed.py              # 时间线抓取与规范化
        ├── like_service.py      # 自动点赞
        ├── models.py            # 运行态配置、用户偏好、互动记录
        ├── policy.py            # 参数解析/名单判定/模板渲染
        ├── preferences.py       # 配置与名单仓储
        └── selection.py         # 候选筛选
```

## ⚙️ 配置

在真寻管理后台的插件配置中设置。`enable_auto_like` 与 `like_interval` 只用于首次初始化运行态配置，之后通过指令修改，重启后保留。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| enable_auto_like | false | 首次初始化时的全局秒赞开关 |
| like_interval | 120 | 首次初始化时的监控间隔（秒） |
| max_like_count | 50 | 每轮最多抓取/点赞的说说数量 |
| like_random_delay_min | 2 | 单条点赞最小随机延迟（秒） |
| like_random_delay_max | 6 | 单条点赞最大随机延迟（秒） |
| daily_like_limit | 200 | 每日最多点赞条数（0 表示不限） |
| comment_max_per_round | 5 | 每轮最多评论条数（0 表示不限） |
| comment_daily_limit | 50 | 每日最多评论条数（0 表示不限） |
| comment_delay_min | 5 | 单条评论最小随机延迟（秒） |
| comment_delay_max | 15 | 单条评论最大随机延迟（秒） |
| enable_auto_cookie | false | 是否自动获取 QQ 空间 Cookie |
| napcat_url | http://127.0.0.1:3000 | NapCat HTTP API（OneBot 不可用时回退） |
| napcat_token | 空 | NapCat access token |
| bridge_url | http://127.0.0.1:5700 | onebot-qzone 桥接服务地址 |
| bridge_token | 空 | onebot-qzone access token |
| cookie_refresh_interval | 7200 | Cookie 刷新间隔（秒） |
| cookie_request_timeout | 10 | HTTP 请求超时（秒） |
| cookie_verify_after_update | true | 更新后是否验证新 Cookie |

## 🎛 指令

指令权限按发送者身份自动分流：管理员操作全局，普通用户只操作自己。群聊和私聊都可以触发。

### 管理员

| 指令 | 说明 |
|------|------|
| 开启秒赞 / 关闭秒赞 | 全局秒赞总开关 |
| 开启秒评 / 关闭秒评 | 全局秒评总开关 |
| 设置秒评内容 `<文本>` | 设置全局秒评内容（默认 `QεQ`） |
| 设置监控间隔 `<秒>` | 设置轮询间隔，范围 30-3600 |
| 查看空间配置 | 查看全局开关、名单人数、今日统计、Cookie 状态 |
| 加点赞勿扰 `<QQ>` / 删点赞勿扰 `<QQ>` | 添加/移除点赞勿扰用户 |
| 查看点赞勿扰 / 清空点赞勿扰 | 查询/清空点赞勿扰名单 |
| 加评论名单 `<QQ>` / 删评论名单 `<QQ>` | 添加/移除评论名单用户 |
| 查看评论名单 / 清空评论名单 | 查询/清空评论名单 |

`空间点赞状态` 仍可作为 `查看空间配置` 的别名。

### 普通用户

| 指令 | 说明 |
|------|------|
| 开启秒赞 / 关闭秒赞 | 恢复接收 / 加入点赞勿扰名单 |
| 开启秒评 / 关闭秒评 | 加入 / 移出评论名单 |
| 设置秒评内容 `<文本>` | 设置自己的秒评内容 |
| 查看我的空间设置 | 查看自己的开关与模板 |
| 恢复默认秒评内容 | 删除个人模板，改用全局模板 |

示例：

```text
947142539: 关闭秒赞
Bot: 已加入点赞勿扰名单：不会再自动赞你的说说。

947142539: 开启秒评
Bot: 已加入评论名单；全局秒评开启后生效。

947142539: 设置秒评内容 QεQ
Bot: 你的秒评内容已更新：QεQ（仅用于你的说说）
```

## 🔄 生效规则

```text
秒赞：全局 like_enabled AND 个人 accept_like
秒评：全局 comment_enabled AND 个人 accept_comment
模板：个人 comment_template 优先，其次全局模板，最后 QεQ
```

- 点赞默认接收；`accept_like=false` 表示在点赞勿扰名单。
- 评论默认不接收；`accept_comment=true` 表示在评论名单。
- 全局秒评开启但评论名单为空时，不会评论任何人。
- 普通用户只能修改自己；管理员可以修改任意 QQ。
- 清空名单只修改标记，不会删除个人模板。

## 🔄 Cookie 自动刷新

启用 `enable_auto_cookie` 后，插件会周期性：

1. 调用桥接服务 `check_cookie` 检测 Cookie 是否有效
2. 仍有效则跳过；预检失败则 fail-open 直接刷新
3. 通过 OneBot 连接调用 NapCat `get_cookies`（失败时回退 `napcat_url` HTTP API）
4. 调用桥接服务 `update_cookie` 热更新，可选再次验证

前提条件：NapCat ≥ v4.18.0 且已登录、onebot-qzone 正在运行。

## 🔧 工作原理

```
真寻插件
  ├─ OneBot get_cookies ──► NapCat
  └─ 每轮 get_friend_feeds（一次）
        ├─ 点赞：过滤勿扰/已赞 ──► send_like
        └─ 评论：过滤名单/已评 ──► send_comment
                                   │
                          onebot-qzone ──► QQ空间 Web API
```

点赞、评论、时间线、Cookie 更新均通过 onebot-qzone 的 OneBot v11 HTTP action 完成。

## ⚠️ 注意事项

1. 需要同时运行 NapCat 和 onebot-qzone
2. 全局秒赞默认关闭；开启后默认面向所有好友，可通过勿扰名单排除
3. 秒评默认关闭；开启全局后仍需把用户加入评论名单
4. 评论比点赞更容易触发风控，建议保留较小的每轮/每日上限
5. Cookie 仅在本地服务之间传递，不会上传到第三方

## 📄 License

MIT
