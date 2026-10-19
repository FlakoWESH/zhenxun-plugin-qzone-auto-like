# zhenxun-plugin-qzone-auto-like

真寻（ZhenXun）框架的 QQ 空间说说自动点赞插件，支持从 NapCat 自动获取 QQ 空间 Cookie 并推送到 [onebot-qzone](https://github.com/Gu-Heping/onebot-qzone) 桥接服务。

## ✨ 功能特性

- **自动点赞说说**：后台定时轮询好友空间时间线，对未点赞的说说自动点赞
- **防重复点赞**：使用真寻数据库 + `(qq_number, qzone_post_id)` 唯一约束记录已点赞说说，不会重复点赞
- **每日限额 + 随机延迟**：可配置每日点赞上限与单条随机间隔，降低风控风险
- **点赞结果校验**：仅在桥接服务确认点赞成功后落库，失败的说说会在下一轮重试
- **Cookie 自动刷新**：复用真寻已有的 OneBot 连接调用 NapCat `get_cookies`，自动推送最新 Cookie 到 onebot-qzone，无需手动粘贴、无需另开 HTTP 端口；按需刷新（Cookie 有效时跳过）
- **可配置参数**：点赞间隔、单轮上限、每日上限、随机延迟、Cookie 刷新间隔等均可在真寻管理后台配置
- **状态查询**：发送 `空间点赞状态` 查看运行状态和 Cookie 刷新状态

## 📦 安装

将 `qzone_auto_like` 文件夹复制到真寻框架的 `plugins/` 目录下，重启 Bot 即可。

```
zhenxun_bot/
└── plugins/
    └── qzone_auto_like/
        ├── __init__.py
        ├── bridge.py            # onebot-qzone 桥接服务 HTTP 客户端
        ├── config.py
        ├── cookie_refresher.py
        ├── like_service.py      # 自动点赞业务逻辑
        └── models.py
```

## ⚙️ 配置

在真寻管理后台的插件配置中设置（均有默认值）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| enable_auto_like | false | 是否启用自动点赞（默认关闭，需显式开启） |
| like_interval | 600 | 点赞轮询最小间隔（秒） |
| max_like_count | 50 | 每轮最多抓取/点赞的说说数量 |
| like_random_delay_min | 2 | 单条点赞之间的最小随机延迟（秒） |
| like_random_delay_max | 6 | 单条点赞之间的最大随机延迟（秒） |
| daily_like_limit | 200 | 每日最多点赞条数（0 表示不限） |
| enable_auto_cookie | false | 是否启用自动获取 QQ 空间 Cookie（优先复用 OneBot 连接） |
| napcat_url | http://127.0.0.1:3000 | NapCat HTTP API 地址（仅当 OneBot 连接不可用时回退） |
| napcat_token | 空 | NapCat access token |
| bridge_url | http://127.0.0.1:5700 | onebot-qzone 桥接服务地址 |
| bridge_token | 空 | onebot-qzone access token |
| cookie_refresh_interval | 7200 | Cookie 刷新间隔（秒，默认 2 小时） |
| cookie_request_timeout | 10 | HTTP 请求超时（秒） |
| cookie_verify_after_update | true | 更新后是否验证新 Cookie 有效性 |

## 🔄 Cookie 自动刷新

启用 `enable_auto_cookie` 后，插件会周期性：

1. 调用桥接服务 `check_cookie`（带网络探针）检测当前 Cookie 是否有效
2. Cookie 仍有效则跳过，不触发变更（防风控）；预检失败则 fail-open 直接刷新
3. 通过真寻已有的 OneBot 连接调用 NapCat `get_cookies` 获取 QQ 空间 Cookie（失败时回退到 `napcat_url` HTTP API），校验包含 `uin` / `p_uin` / `skey` / `p_skey`
4. 调用桥接服务 `update_cookie` 动态更新 Cookie，可选再次验证

**前提条件**：

- NapCat 版本 ≥ v4.18.0
- NapCat 已登录 QQ，并已连接到真寻
- onebot-qzone 桥接服务正在运行

## 🎉 使用

| 指令 | 说明 |
|------|------|
| 空间点赞状态 | 查看点赞状态 + Cookie 自动刷新状态（仅超级用户） |

## 🔧 工作原理

```
真寻插件 ──OneBot get_cookies──► NapCat(QQ登录)
   │
   │ POST /update_cookie
   ▼
onebot-qzone(桥接服务) ──QQ空间Web API(Cookie)──► QQ空间服务器
   ▲
   └── POST /get_friend_feeds, /send_like
```

点赞、拉时间线、Cookie 更新均通过 onebot-qzone 桥接服务的 OneBot v11 HTTP action 完成。

## ⚠️ 注意事项

1. 需要同时运行 NapCat（协议端）和 onebot-qzone（桥接服务）
2. `enable_auto_like` 默认关闭，请确认风险后再开启
3. Cookie 仅在本地各服务之间传递，不会上传到第三方
4. 自动点赞属于自动化操作，请遵守 QQ 空间使用规则

## 📄 License

MIT
