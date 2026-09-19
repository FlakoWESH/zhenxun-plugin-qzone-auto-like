import asyncio
from datetime import datetime

import nonebot
from nonebot import on_command, get_driver
from nonebot.plugin import PluginMetadata

from zhenxun.configs.config import Config
from zhenxun.services.log import logger
from zhenxun.utils.message import MessageUtils

from .config import get_plugin_extra
from .cookie_refresher import CookieRefresher
from .models import QzoneLikeRecord

__plugin_meta__ = PluginMetadata(
    name="QQ空间说说自动点赞",
    description="自动点赞QQ空间说说，支持Cookie自动刷新",
    usage="空间点赞状态 - 查询自动点赞功能状态",
    extra=get_plugin_extra().to_dict(),
)

# 标记后台任务是否已启动
_task_started = False

# Cookie 自动刷新器
_cookie_refresher: CookieRefresher | None = None


def _init_cookie_refresher():
    """根据配置初始化 Cookie 自动刷新器"""
    global _cookie_refresher
    if not Config.get_config("qzone_auto_like", "enable_auto_cookie", False):
        return

    _cookie_refresher = CookieRefresher(
        napcat_url=Config.get_config("qzone_auto_like", "napcat_url", "http://127.0.0.1:3000"),
        napcat_token=Config.get_config("qzone_auto_like", "napcat_token", ""),
        bridge_url=Config.get_config("qzone_auto_like", "bridge_url", "http://127.0.0.1:5700"),
        bridge_token=Config.get_config("qzone_auto_like", "bridge_token", ""),
        refresh_interval=Config.get_config("qzone_auto_like", "cookie_refresh_interval", 7200),
        request_timeout=Config.get_config("qzone_auto_like", "cookie_request_timeout", 10),
        verify_after_update=Config.get_config("qzone_auto_like", "cookie_verify_after_update", True),
    )
    logger.info("[qzone_auto_like] Cookie 自动刷新已启用")


async def _auto_like_loop():
    """自动点赞后台循环任务"""
    logger.info("[qzone_auto_like] 自动点赞任务已启动")
    while True:
        try:
            if not Config.get_config("qzone_auto_like", "enable_auto_like", True):
                await asyncio.sleep(60)
                continue

            interval = Config.get_config("qzone_auto_like", "like_interval", 600)
            max_count = Config.get_config("qzone_auto_like", "max_like_count", 50)

            # 获取当前bot实例
            try:
                bot = nonebot.get_bot()
            except Exception:
                logger.warning("[qzone_auto_like] 未找到可用的Bot实例，等待重连...")
                await asyncio.sleep(30)
                continue

            qq = bot.self_id
            logger.info(
                "[qzone_auto_like] 开始一轮空间说说点赞 | QQ: %s | 最大数量: %d",
                qq,
                max_count,
            )

            # 尝试导入onebot_qzone并执行点赞
            try:
                from onebot_qzone import QzoneSession

                qzone = QzoneSession(qq)
                await qzone.login()
                posts = await qzone.get_user_timeline(count=max_count)
                for post in posts:
                    await qzone.like(post["postid"])
                    await QzoneLikeRecord.create(
                        qq_number=qq,
                        qzone_post_id=post["postid"],
                        like_time=datetime.now(),
                    )
                    await asyncio.sleep(1)
                logger.info("[qzone_auto_like] 完成一轮QQ空间说说点赞")
            except ImportError:
                logger.error(
                    "[qzone_auto_like] 未安装onebot-qzone库，请执行 pip install onebot-qzone"
                )
                await asyncio.sleep(interval)
                continue
            except Exception as e:
                logger.error("[qzone_auto_like] 点赞过程出现错误: %s", str(e))

            await asyncio.sleep(interval)
        except Exception as e:
            logger.error("[qzone_auto_like] 主循环异常: %s", str(e))
            await asyncio.sleep(60)


status_cmd = on_command("空间点赞状态", priority=5, block=True)


@status_cmd.handle()
async def _():
    """查询自动点赞状态"""
    enabled = Config.get_config("qzone_auto_like", "enable_auto_like", True)
    status = "已启用" if enabled else "已禁用"

    msg = f"QQ空间自动点赞状态\n功能开关：{status}\n"

    if _cookie_refresher is not None:
        s = _cookie_refresher.get_status()
        msg += f"\n─── Cookie 自动刷新 ───\n"
        msg += f"刷新间隔：{s['refresh_interval']} 秒\n"
        if s["last_refresh_time"]:
            last_time = datetime.fromtimestamp(s["last_refresh_time"]).strftime("%Y-%m-%d %H:%M:%S")
            if s["last_refresh_success"]:
                msg += f"上次刷新：{last_time} ✅ 成功\n"
            else:
                msg += f"上次刷新：{last_time} ❌ 失败\n错误：{s['last_error'] or '未知'}\n"
        else:
            msg += "上次刷新：尚未执行\n"
        msg += f"累计刷新：{s['refresh_count']} 次"
    else:
        msg += "\nCookie 自动刷新：未启用"

    await MessageUtils.build_message(msg).finish()


# 插件加载时初始化
_init_cookie_refresher()

driver = get_driver()


@driver.on_startup
async def _startup():
    global _task_started
    if not _task_started:
        _task_started = True
        asyncio.create_task(_auto_like_loop())
        if _cookie_refresher is not None:
            asyncio.create_task(_cookie_refresher.refresh_loop())
            logger.info("[qzone_auto_like] Cookie 自动刷新后台任务已启动")
