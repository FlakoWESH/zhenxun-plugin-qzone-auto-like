from zhenxun.configs.utils import PluginExtraData, RegisterConfig


def get_plugin_extra() -> PluginExtraData:
    """获取插件扩展元数据"""
    return PluginExtraData(
        author="FlakoWESH",
        version="1.2.0",
        menu_type="空间功能",
        plugin_type="NORMAL",
        introduction="自动点赞 QQ 空间好友说说，并可自动从 NapCat 刷新 Cookie。",
        precautions=[
            "自动点赞属于自动化操作，请遵守 QQ 空间使用规则。",
            "默认关闭，需在后台显式开启 enable_auto_like。",
        ],
        configs=[
            RegisterConfig(
                key="enable_auto_like",
                value=False,
                help="是否启用自动点赞功能（默认关闭）",
                type=bool,
            ),
            RegisterConfig(
                key="like_interval",
                value=600,
                help="点赞间隔时间（秒），两次点赞轮询之间的最小间隔",
                type=int,
            ),
            RegisterConfig(
                key="max_like_count",
                value=50,
                help="每轮最多抓取/点赞的说说数量",
                type=int,
            ),
            RegisterConfig(
                key="like_random_delay_min",
                value=2,
                help="单条点赞之间的最小随机延迟（秒）",
                type=int,
            ),
            RegisterConfig(
                key="like_random_delay_max",
                value=6,
                help="单条点赞之间的最大随机延迟（秒）",
                type=int,
            ),
            RegisterConfig(
                key="daily_like_limit",
                value=200,
                help="每日最多点赞条数（0 表示不限制）",
                type=int,
            ),
            # ===== Cookie 自动刷新配置 =====
            RegisterConfig(
                key="enable_auto_cookie",
                value=False,
                help="是否启用自动从 NapCat 获取 QQ 空间 Cookie（需 NapCat HTTP API 和 onebot-qzone 桥接服务）",
                type=bool,
            ),
            RegisterConfig(
                key="napcat_url",
                value="http://127.0.0.1:3000",
                help="NapCat HTTP API 地址",
                type=str,
            ),
            RegisterConfig(
                key="napcat_token",
                value="",
                help="NapCat access token（如 NapCat 设置了鉴权则填写）",
                type=str,
            ),
            RegisterConfig(
                key="bridge_url",
                value="http://127.0.0.1:5700",
                help="onebot-qzone 桥接服务 HTTP API 地址",
                type=str,
            ),
            RegisterConfig(
                key="bridge_token",
                value="",
                help="onebot-qzone access token（如桥接服务设置了鉴权则填写）",
                type=str,
            ),
            RegisterConfig(
                key="cookie_refresh_interval",
                value=7200,
                help="Cookie 自动刷新间隔（秒），默认 2 小时",
                type=int,
            ),
            RegisterConfig(
                key="cookie_request_timeout",
                value=10,
                help="HTTP 请求超时时间（秒）",
                type=int,
            ),
            RegisterConfig(
                key="cookie_verify_after_update",
                value=True,
                help="更新后是否调用 check_cookie API 验证新 Cookie 是否有效",
                type=bool,
            ),
        ],
    )
