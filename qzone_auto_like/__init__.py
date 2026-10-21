from datetime import datetime

import nonebot
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.plugin import PluginMetadata
from nonebot_plugin_apscheduler import scheduler

from zhenxun.configs.config import Config
from zhenxun.services.log import logger

from .bridge import QzoneBridgeClient
from .comment_service import AutoCommentService
from .commands import register_commands
from .config import get_plugin_extra
from .cookie_refresher import CookieRefresher
from .feed import FeedScanner
from .like_service import AutoLikeService
from .preferences import (
    get_comment_allowed,
    get_like_denied,
    get_runtime_config,
    touch_last_run,
)

__plugin_meta__ = PluginMetadata(
    name="QQ空间互动",
    description="自动点赞与评论QQ空间好友说说，支持勿扰名单、评论名单与个人内容。",
    usage="发送“查看空间配置”或“查看我的空间设置”查看当前设置。",
    extra=get_plugin_extra().to_dict(),
)

_CFG = "qzone_auto_like"

# 运行期服务（按配置惰性构建，配置变化时自动重建）
_bridge: QzoneBridgeClient | None = None
_cookie_refresher: CookieRefresher | None = None
_like_service: AutoLikeService | None = None
_comment_service: AutoCommentService | None = None
_scanner: FeedScanner | None = None
_bridge_conf: tuple | None = None


def _get(key: str, default):
    return Config.get_config(_CFG, key, default)


def _get_bot():
    try:
        return nonebot.get_bot()
    except Exception:  # noqa: BLE001
        return None


def _cookie_ready() -> bool:
    """自动 Cookie 开启时，是否已经成功刷新过一次。"""
    if not _get("enable_auto_cookie", False):
        return True
    if _cookie_refresher is None:
        return False
    return bool(_cookie_refresher.get_status().get("last_refresh_success"))


async def _ensure_services() -> None:
    """根据当前配置构建/重建服务实例（支持配置热更新、复用 session）。"""
    global _bridge, _cookie_refresher, _like_service, _comment_service
    global _scanner, _bridge_conf

    url = _get("bridge_url", "http://127.0.0.1:5700")
    token = _get("bridge_token", "")
    timeout = _get("cookie_request_timeout", 10)
    conf = (url, token, timeout)

    if _bridge is None or _bridge_conf != conf:
        if _bridge is not None:
            await _bridge.close()
        if _cookie_refresher is not None:
            await _cookie_refresher.close()
        _bridge = QzoneBridgeClient(url, token, timeout)
        _scanner = FeedScanner(_bridge)
        _like_service = AutoLikeService(_bridge, _scanner)
        _comment_service = AutoCommentService(_bridge, _scanner)
        _bridge_conf = conf

    if _get("enable_auto_cookie", False):
        if _cookie_refresher is None:
            _cookie_refresher = CookieRefresher(
                napcat_url=_get("napcat_url", "http://127.0.0.1:3000"),
                napcat_token=_get("napcat_token", ""),
                bridge_client=_bridge,
                refresh_interval=_get("cookie_refresh_interval", 7200),
                request_timeout=timeout,
                verify_after_update=_get("cookie_verify_after_update", True),
                bot_getter=_get_bot,
            )
            logger.info("[qzone_auto_like] Cookie 自动刷新已启用")
    elif _cookie_refresher is not None:
        await _cookie_refresher.close()
        _cookie_refresher = None


async def _interaction_tick() -> None:
    """共享扫描：一次拉取时间线，按开关分别执行点赞和评论。"""
    runtime = await get_runtime_config()
    if not runtime.like_enabled and not runtime.comment_enabled:
        return

    if _get("enable_auto_cookie", False):
        await _ensure_services()
        if not _cookie_ready() and _cookie_refresher is not None:
            await _cookie_refresher.maybe_refresh()
        if not _cookie_ready():
            return

    now = datetime.now()
    if runtime.last_run_at is not None:
        last_run = runtime.last_run_at
        if last_run.tzinfo is not None:
            now = datetime.now(last_run.tzinfo)
        elapsed = (now - last_run).total_seconds()
        if elapsed < max(30, runtime.monitor_interval):
            return

    try:
        bot = nonebot.get_bot()
    except Exception:  # noqa: BLE001
        logger.warning("[qzone_auto_like] 未找到可用的 Bot 实例，跳过本轮")
        return

    await _ensure_services()
    if _scanner is None or _like_service is None or _comment_service is None:
        return

    qq = str(bot.self_id)

    try:
        like_count = _get("max_like_count", 50) if runtime.like_enabled else 0
        comment_count = (
            _get("comment_max_per_round", 5) if runtime.comment_enabled else 0
        )
        comment_scan = comment_count * 3 if comment_count > 0 else 50
        scan_num = max(1, like_count, comment_scan)
        posts = await _scanner.scan(scan_num)
        await touch_last_run(now)

        if runtime.like_enabled:
            denied = await get_like_denied(qq)
            stats = await _like_service.run(
                posts,
                qq=qq,
                delay_min=_get("like_random_delay_min", 2),
                delay_max=_get("like_random_delay_max", 6),
                daily_limit=_get("daily_like_limit", 200),
                denied=denied,
            )
            logger.info(
                f"[qzone_auto_like] 点赞轮次完成 | 抓取={stats['fetched']} "
                f"点赞={stats['liked']} 跳过={stats['skipped']} "
                f"失败={stats['failed']} 达上限={stats['limit_reached']}"
            )

        if runtime.comment_enabled:
            allowed = await get_comment_allowed(qq)
            if not allowed:
                logger.info("[qzone_auto_like] 评论名单为空，跳过评论")
            else:
                stats = await _comment_service.run(
                    posts,
                    qq=qq,
                    allowed=allowed,
                    global_template=runtime.comment_template,
                    max_per_round=_get("comment_max_per_round", 5),
                    daily_limit=_get("comment_daily_limit", 50),
                    delay_min=_get("comment_delay_min", 5),
                    delay_max=_get("comment_delay_max", 15),
                )
                logger.info(
                    f"[qzone_auto_like] 评论轮次完成 | 抓取={stats['fetched']} "
                    f"评论={stats['commented']} 跳过={stats['skipped']} "
                    f"失败={stats['failed']} 达上限={stats['limit_reached']}"
                )
    except Exception as e:  # noqa: BLE001 - 主循环兜底，避免调度任务被移除
        logger.error(
            f"[qzone_auto_like] 自动互动出现错误: {type(e).__name__}: {e!r}",
            e=e,
        )


async def _cookie_tick() -> None:
    """调度器周期调用：到点才检查/刷新 Cookie。"""
    if not _get("enable_auto_cookie", False):
        return
    await _ensure_services()
    if _cookie_refresher is None:
        return
    try:
        await _cookie_refresher.maybe_refresh()
    except Exception as e:  # noqa: BLE001
        logger.error(f"[qzone_auto_like] Cookie 检查出现错误: {e}")


driver = get_driver()


@driver.on_startup
async def _startup():
    scheduler.add_job(
        _interaction_tick,
        "interval",
        seconds=30,
        id="qzone_interaction_tick",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        _cookie_tick,
        "interval",
        seconds=60,
        id="qzone_auto_cookie_tick",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("[qzone_auto_like] 后台调度任务已注册")


@driver.on_bot_connect
async def _on_bot_connect(_bot: Bot) -> None:
    """Bot 连接 NapCat 后立即刷新 Cookie，避免首轮互动因无 Cookie 失败。"""
    if not _get("enable_auto_cookie", False):
        return
    await _ensure_services()
    if _cookie_refresher is not None:
        await _cookie_refresher.maybe_refresh()


@driver.on_shutdown
async def _shutdown():
    if _cookie_refresher is not None:
        await _cookie_refresher.close()
    elif _bridge is not None:
        await _bridge.close()


register_commands()
