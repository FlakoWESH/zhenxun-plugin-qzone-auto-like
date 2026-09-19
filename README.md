# zhenxun-plugin-qzone-auto-like

真寻（ZhenXun）框架的 QQ 空间说说自动点赞插件，支持从 NapCat 自动获取 QQ 空间 Cookie 并推送到 [onebot-qzone](https://github.com/Gu-Heping/onebot-qzone) 桥接服务。

## ✨ 功能特性

- **自动点赞说说**：后台定时轮询好友空间时间线，对未点赞的说说自动点赞
- **Cookie 自动刷新**：通过 NapCat `get_cookies` API 自动获取最新 Cookie，推送到 onebot-qzone，无需手动粘贴
- **防重复点赞**：使用真寻数据库记录已点赞说说 ID，不会重复点赞
- **可配置参数**：点赞间隔、单次上限、Cookie 刷新间隔等均可在真寻管理后台配置
- **状态查询**：发送 `空间点赞状态` 查看运行状态和 Cookie 刷新状态

## 📦 安装

将 `qzone_auto_like` 文件夹复制到真寻框架的 `plugins/` 目录下，重启 Bot 即可。

```
zhenxun_bot/
└── plugins/
    └── qzone_auto_like/
        ├── __init__.py
        ├── config.py
        ├── models.py
        └── cookie_refresher.py
```

## ⚙️ 配置

在真寻管理后台的插件配置中设置以下参数（均有默认值）：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| enable_auto_like | true | 是否启用自动点赞 |
| like_interval | 600 | 点赞轮询间隔（秒） |
| max_like_count | 50 | 每次最多点赞说说数量 |
| enable_auto_cookie | false | 是否启用自动从 NapCat 获取 Cookie |
| napcat_url | http://127.0.0.1:3000 | NapCat HTTP API 地址 |
| napcat_token | 空 | NapCat access token |
| bridge_url | http://127.0.0.1:5700 | onebot-qzone 桥接服务地址 |
| bridge_token | 空 | onebot-qzone access token |
| cookie_refresh_interval | 7200 | Cookie 刷新间隔（秒，默认2小时） |

## 🔄 Cookie 自动刷新

启用 `enable_auto_cookie` 后，插件会自动：

1. 调用 NapCat `POST /get_cookies` 获取 QQ 空间 Cookie
2. 验证 Cookie 包含 `uin` / `p_uin` / `skey` / `p_skey`
3. 调用 onebot-qzone `POST /update_cookie` 动态更新 Cookie

**前提条件**：
- NapCat 版本 ≥ v4.18.0
- NapCat 已开启 HTTP API 并登录 QQ
- onebot-qzone 桥接服务正在运行

## 🎉 使用

| 指令 | 说明 |
|---|---|
| 空间点赞状态 | 查看点赞状态 + Cookie 自动刷新状态 |

## 🔧 工作原理

```
┌──────────────┐  NapCat HTTP API  ┌──────────┐
│              │ ◄────────────────► │  NapCat  │
│  真寻插件     │  POST /get_cookies │ (QQ登录)  │
│ (qzone_auto) │                    └──────────┘
│              │  POST /update_cookie ┌──────────────────┐  QQ空间Web API  ┌──────────┐
│              │ ◄──────────────────► │  onebot-qzone    │ ◄─────────────► │  QQ空间   │
└──────────────┘   (动态更新Cookie)   │  (桥接服务)      │   Cookie 认证    │  服务器   │
                                        └──────────────────┘                  └──────────┘
```

## ⚠️ 注意事项

1. 需要同时运行 NapCat（协议端）和 onebot-qzone（桥接服务）
2. Cookie 仅在本地各服务之间传递，不会上传到第三方
3. 建议点赞轮询间隔不低于 5 分钟，避免触发 QQ 风控
4. 自动点赞属于自动化操作，请遵守 QQ 空间使用规则

## 📄 License

MIT
