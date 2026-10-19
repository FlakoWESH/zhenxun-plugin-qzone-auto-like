import time
from datetime import datetime

import nonebot
from nonebot import get_driver, on_command
from nonebot.adapters.onebot.v11 import Bot
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot_plugin_apscheduler import scheduler

from zhenxun.configs.config import Config
from zhenxun.services.log import logger
from zhenxun.utils.message import MessageUtils

from .bridge import QzoneBridgeClient
from .config import get_plugin_extra
from .cookie_refresher import CookieRefresher
from .like_service import AutoLikeService

__plugin_meta__ = PluginMetadata(
    name="QQ空间说说自动点赞",
    description="自动点赞QQ空间说说，支持Cookie自动刷新",
    usage="空间点赞状态 - 查询自动点赞功能状态",
    extra=get_plugin_extra().to_dict(),
)

_CFG = "qzone_auto_like"

# 运行期服务（按配置惰性构建，配置变化时自动重建）
_bridge: QzoneBridgeClient | None = None
_cookie_refresher: CookieRefresher | None = None
_like_service: AutoLikeService | None = None
_bridge_conf: tuple | None = None

# 上一轮点赞时间戳
_last_like_run: float = 0.0


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
    global _bridge, _cookie_refresher, _like_service, _bridge_conf

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
        _like_service = AutoLikeService(_bridge)
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


async def _auto_like_tick() -> None:
    """调度器周期调用：达到 like_interval 才执行一轮点赞。"""
    global _last_like_run

    if not _get("enable_auto_like", False):
        return

    if _get("enable_auto_cookie", False):
        await _ensure_services()
        if not _cookie_ready() and _cookie_refresher is not None:
            await _cookie_refresher.maybe_refresh()
        if not _cookie_ready():
            return

    interval = max(0, _get("like_interval", 600))
    now = time.time()
    if now - _last_like_run < interval:
        return

    try:
        bot = nonebot.get_bot()
    except Exception:
        logger.warning("[qzone_auto_like] 未找到可用的 Bot 实例，跳过本轮")
        return

    _last_like_run = now
    qq = str(bot.self_id)

    await _ensure_services()
    if _like_service is None:
        return

    max_count = _get("max_like_count", 50)
    delay_min = _get("like_random_delay_min", 2)
    delay_max = _get("like_random_delay_max", 6)
    daily_limit = _get("daily_like_limit", 200)

    try:
        stats = await _like_service.run_once(
            qq=qq,
            max_count=max_count,
            delay_min=delay_min,
            delay_max=delay_max,
            daily_limit=daily_limit,
        )
        logger.info(
            f"[qzone_auto_like] 点赞轮次完成 | 抓取={stats['fetched']} "
            f"点赞={stats['liked']} 跳过={stats['skipped']} "
            f"失败={stats['failed']} 达上限={stats['limit_reached']}"
        )
    except Exception as e:  # noqa: BLE001 - 主循环兜底，避免调度任务被移除
        logger.error(f"[qzone_auto_like] 自动点赞出现错误: {e}")


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


status_cmd = on_command("空间点赞状态", permission=SUPERUSER, priority=5, block=True)


@status_cmd.handle()
async def _():
    """查询自动点赞状态"""
    await _ensure_services()

    like_enabled = _get("enable_auto_like", False)
    cookie_enabled = _get("enable_auto_cookie", False)

    msg = (
        "QQ空间自动点赞状态\n"
        f"自动点赞：{'已启用' if like_enabled else '已禁用'}\n"
        f"点赞间隔：{_get('like_interval', 600)} 秒\n"
        f"单轮上限：{_get('max_like_count', 50)} 条\n"
        f"每日上限：{_get('daily_like_limit', 200) or '不限'}\n"
    )

    try:
        from .models import QzoneLikeRecord

        today_count = await QzoneLikeRecord.filter(
            qq_number=str(nonebot.get_bot().self_id),
            like_time__gte=datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
        ).count()
        msg += f"今日已点赞：{today_count} 条\n"
    except Exception:  # noqa: BLE001
        pass

    if cookie_enabled and _cookie_refresher is not None:
        s = _cookie_refresher.get_status()
        msg += "\n─── Cookie 自动刷新 ───\n"
        msg += f"刷新间隔：{s['refresh_interval']} 秒\n"
        if s["last_refresh_time"]:
            last_time = datetime.fromtimestamp(s["last_refresh_time"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if s["last_refresh_success"]:
                msg += f"上次刷新：{last_time} 成功\n"
            else:
                msg += f"上次刷新：{last_time} 失败\n错误：{s['last_error'] or '未知'}\n"
        else:
            msg += "上次刷新：尚未执行\n"
        msg += f"累计刷新：{s['refresh_count']} 次"
    else:
        msg += "\nCookie 自动刷新：未启用"

    await MessageUtils.build_message(msg).finish()


driver = get_driver()


@driver.on_startup
async def _startup():
    scheduler.add_job(
        _auto_like_tick,
        "interval",
        seconds=30,
        id="qzone_auto_like_tick",
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
    """Bot 连接 NapCat 后立即刷新 Cookie，避免首轮点赞因无 Cookie 失败。"""
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
