from zhenxun.configs.utils import RegisterConfig, PluginExtraData


def get_plugin_extra() -> PluginExtraData:
    """获取插件扩展元数据"""
    return PluginExtraData(
        author="Your Name",
        version="1.1.0",
        menu_type="空间功能",
        plugin_type="NORMAL",
        configs=[
            RegisterConfig(
                key="enable_auto_like",
                value=True,
                help="是否启用自动点赞功能",
                type=bool
            ),
            RegisterConfig(
                key="like_interval",
                value=600,
                help="点赞间隔时间（秒）",
                type=int
            ),
            RegisterConfig(
                key="max_like_count",
                value=50,
                help="每次最多点赞说说数量",
                type=int
            ),
            # ===== Cookie 自动刷新配置 =====
            RegisterConfig(
                key="enable_auto_cookie",
                value=False,
                help="是否启用自动从 NapCat 获取 QQ 空间 Cookie（需 NapCat HTTP API 和 onebot-qzone 桥接服务）",
                type=bool
            ),
            RegisterConfig(
                key="napcat_url",
                value="http://127.0.0.1:3000",
                help="NapCat HTTP API 地址",
                type=str
            ),
            RegisterConfig(
                key="napcat_token",
                value="",
                help="NapCat access token（如 NapCat 设置了鉴权则填写）",
                type=str
            ),
            RegisterConfig(
                key="bridge_url",
                value="http://127.0.0.1:5700",
                help="onebot-qzone 桥接服务 HTTP API 地址",
                type=str
            ),
            RegisterConfig(
                key="bridge_token",
                value="",
                help="onebot-qzone access token（如桥接服务设置了鉴权则填写）",
                type=str
            ),
            RegisterConfig(
                key="cookie_refresh_interval",
                value=7200,
                help="Cookie 自动刷新间隔（秒），默认 2 小时",
                type=int
            ),
        ]
    )
