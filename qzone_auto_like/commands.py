"""指令注册：管理员全局配置 + 普通用户个人偏好。"""
from __future__ import annotations

from datetime import datetime

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from zhenxun.services.log import logger

from .models import QzoneCommentRecord, QzoneLikeRecord
from .policy import (
    DEFAULT_COMMENT_TEMPLATE,
    format_qq_list,
    normalize_template,
    parse_interval,
    parse_target_qq,
)
from .preferences import (
    clear_comment_allowed,
    clear_like_denied,
    count_comment_allowed,
    count_like_denied,
    count_personal_templates,
    get_runtime_config,
    get_user_preference,
    list_comment_allowed,
    list_like_denied,
    set_user_preference,
    update_runtime_config,
)


def _sender(event: MessageEvent) -> str:
    return str(event.get_user_id())


def _bot_qq(bot: Bot) -> str:
    return str(bot.self_id)


async def _is_admin(bot: Bot, event: MessageEvent) -> bool:
    try:
        return bool(await SUPERUSER(bot, event))
    except Exception:  # noqa: BLE001
        return False


def _at_targets(event: MessageEvent) -> list[str]:
    targets: list[str] = []
    for segment in event.get_message():
        if segment.type != "at":
            continue
        qq = str(segment.data.get("qq", "")).strip()
        if qq.isdigit():
            targets.append(qq)
    return targets


def _start_of_today() -> datetime:
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


async def _cookie_line() -> str:
    from . import _cookie_refresher, _ensure_services

    await _ensure_services()
    if _cookie_refresher is None:
        return "Cookie 自动刷新：未启用"
    status = _cookie_refresher.get_status()
    if not status.get("last_refresh_time"):
        return "Cookie 自动刷新：尚未执行"
    when = datetime.fromtimestamp(status["last_refresh_time"]).strftime(
        "%Y-%m-%d %H:%M"
    )
    if status.get("last_refresh_success"):
        return f"Cookie 自动刷新：{when} 成功"
    return f"Cookie 自动刷新：{when} 失败（{status.get('last_error') or '未知'}）"


def register_commands() -> None:
    """注册全部指令；由插件入口调用一次。"""

    like_on = on_command("开启秒赞", priority=5, block=True)
    like_off = on_command("关闭秒赞", priority=5, block=True)
    comment_on = on_command("开启秒评", priority=5, block=True)
    comment_off = on_command("关闭秒评", priority=5, block=True)
    set_template = on_command("设置秒评内容", priority=5, block=True)

    @like_on.handle()
    async def _(bot: Bot, event: MessageEvent):
        sender = _sender(event)
        if await _is_admin(bot, event):
            await update_runtime_config(updated_by=sender, like_enabled=True)
            await like_on.finish("全局秒赞已开启。")
        await set_user_preference(
            _bot_qq(bot), sender, accept_like=True, updated_by=sender
        )
        await like_on.finish("已开启：全局允许时会赞你的说说。")

    @like_off.handle()
    async def _(bot: Bot, event: MessageEvent):
        sender = _sender(event)
        if await _is_admin(bot, event):
            await update_runtime_config(updated_by=sender, like_enabled=False)
            await like_off.finish("全局秒赞已关闭；个人勿扰设置会保留。")
        await set_user_preference(
            _bot_qq(bot), sender, accept_like=False, updated_by=sender
        )
        await like_off.finish("已加入点赞勿扰名单：不会再自动赞你的说说。")

    @comment_on.handle()
    async def _(bot: Bot, event: MessageEvent):
        sender = _sender(event)
        if await _is_admin(bot, event):
            await update_runtime_config(updated_by=sender, comment_enabled=True)
            count = await count_comment_allowed(_bot_qq(bot))
            if count:
                await comment_on.finish(
                    f"全局秒评已开启（评论名单 {count} 人）。"
                )
            await comment_on.finish("全局秒评已开启；评论名单为空，暂无用户会被评论。")
        await set_user_preference(
            _bot_qq(bot), sender, accept_comment=True, updated_by=sender
        )
        runtime = await get_runtime_config()
        if runtime.comment_enabled:
            await comment_on.finish("已加入评论名单，秒评将按监控间隔执行。")
        await comment_on.finish("已加入评论名单；全局秒评开启后生效。")

    @comment_off.handle()
    async def _(bot: Bot, event: MessageEvent):
        sender = _sender(event)
        if await _is_admin(bot, event):
            await update_runtime_config(updated_by=sender, comment_enabled=False)
            await comment_off.finish("全局秒评已关闭；评论名单保留。")
        await set_user_preference(
            _bot_qq(bot), sender, accept_comment=False, updated_by=sender
        )
        await comment_off.finish("已移出评论名单。")

    @set_template.handle()
    async def _(
        bot: Bot, event: MessageEvent, arg: Message = CommandArg()
    ):
        content = normalize_template(str(arg))
        if content is None:
            await set_template.finish(
                "内容需为 1-100 字且不能包含换行。"
                "用法：设置秒评内容 QεQ"
            )
        sender = _sender(event)
        if await _is_admin(bot, event):
            await update_runtime_config(
                updated_by=sender, comment_template=content
            )
            await set_template.finish(f"全局秒评内容已更新：{content}")
        await set_user_preference(
            _bot_qq(bot),
            sender,
            comment_template=content,
            updated_by=sender,
        )
        await set_template.finish(f"你的秒评内容已更新：{content}（仅用于你的说说）")

    interval_cmd = on_command("设置监控间隔", priority=5, block=True)

    @interval_cmd.handle()
    async def _(
        bot: Bot, event: MessageEvent, arg: Message = CommandArg()
    ):
        if not await _is_admin(bot, event):
            await interval_cmd.finish(
                "该指令仅管理员可用。普通用户可发送“关闭秒赞”或“开启秒评”设置自己。"
            )
        interval = parse_interval(str(arg))
        if interval is None:
            await interval_cmd.finish("间隔需为 30-3600 秒，例如：设置监控间隔120")
        await update_runtime_config(
            updated_by=_sender(event), monitor_interval=interval
        )
        await interval_cmd.finish(f"监控间隔已设为 {interval} 秒。")

    status_cmd = on_command(
        "查看空间配置", aliases={"空间点赞状态"}, priority=5, block=True
    )

    @status_cmd.handle()
    async def _(bot: Bot, event: MessageEvent):
        if not await _is_admin(bot, event):
            await status_cmd.finish(
                "该指令仅管理员可用。你可以发送“查看我的空间设置”。"
            )
        bot_qq = _bot_qq(bot)
        runtime = await get_runtime_config()
        denied_count = await count_like_denied(bot_qq)
        allowed_count = await count_comment_allowed(bot_qq)
        template_count = await count_personal_templates(bot_qq)
        today_start = _start_of_today()
        today_likes = await QzoneLikeRecord.filter(
            qq_number=bot_qq, like_time__gte=today_start
        ).count()
        today_comments = await QzoneCommentRecord.filter(
            bot_qq=bot_qq, comment_time__gte=today_start
        ).count()
        msg = (
            "QQ空间互动配置\n"
            f"秒赞：{'开启' if runtime.like_enabled else '关闭'}"
            f"（勿扰 {denied_count} 人）\n"
            f"秒评：{'开启' if runtime.comment_enabled else '关闭'}"
            f"（评论名单 {allowed_count} 人，自定义内容 {template_count} 人）\n"
            f"监控间隔：{runtime.monitor_interval} 秒\n"
            f"全局秒评内容：{runtime.comment_template or DEFAULT_COMMENT_TEMPLATE}\n"
            f"今日：赞 {today_likes} 条 / 评 {today_comments} 条\n"
            f"{await _cookie_line()}"
        )
        await status_cmd.finish(msg)

    user_status = on_command("查看我的空间设置", priority=5, block=True)

    @user_status.handle()
    async def _(bot: Bot, event: MessageEvent):
        sender = _sender(event)
        pref = await get_user_preference(_bot_qq(bot), sender)
        runtime = await get_runtime_config()
        accept_like = pref.accept_like if pref else True
        accept_comment = pref.accept_comment if pref else False
        personal = pref.comment_template if pref else None
        template = personal or runtime.comment_template or DEFAULT_COMMENT_TEMPLATE
        source = "个人" if personal else "全局默认"
        msg = (
            "你的空间设置\n"
            f"秒赞：{'接收' if accept_like else '已勿扰'}\n"
            f"秒评：{'已加入评论名单' if accept_comment else '未加入'}\n"
            f"秒评内容：{template}（{source}）"
        )
        await user_status.finish(msg)

    reset_template = on_command("恢复默认秒评内容", priority=5, block=True)

    @reset_template.handle()
    async def _(bot: Bot, event: MessageEvent):
        await set_user_preference(
            _bot_qq(bot),
            _sender(event),
            comment_template=None,
            updated_by=_sender(event),
        )
        await reset_template.finish("已恢复全局默认秒评内容。")

    def register_list_command(name: str, kind: str, action: str) -> None:
        matcher = on_command(name, priority=5, block=True)

        @matcher.handle()
        async def _(
            bot: Bot, event: MessageEvent, arg: Message = CommandArg()
        ):
            if not await _is_admin(bot, event):
                await matcher.finish(
                    "该指令仅管理员可用。普通用户可发送"
                    "“关闭秒赞”或“开启秒评”设置自己。"
                )
            bot_qq = _bot_qq(bot)
            if action == "view":
                values = (
                    await list_like_denied(bot_qq)
                    if kind == "like"
                    else await list_comment_allowed(bot_qq)
                )
                title = "点赞勿扰名单" if kind == "like" else "评论名单"
                await matcher.finish(
                    f"{title}（{len(values)} 人）：{format_qq_list(values)}"
                )
            if action == "clear":
                removed = (
                    await clear_like_denied(bot_qq)
                    if kind == "like"
                    else await clear_comment_allowed(bot_qq)
                )
                title = "点赞勿扰名单" if kind == "like" else "评论名单"
                await matcher.finish(f"已清空{title}，共 {removed} 人。")

            target = parse_target_qq(
                str(arg), _at_targets(event), self_qq=bot_qq
            )
            if target is None:
                await matcher.finish(
                    "请提供 5-12 位 QQ 号，或 @ 对应好友。"
                )
            if kind == "like":
                if action == "add":
                    await set_user_preference(
                        bot_qq,
                        target,
                        accept_like=False,
                        updated_by=_sender(event),
                    )
                    count = await count_like_denied(bot_qq)
                    await matcher.finish(
                        f"已将 {target} 加入点赞勿扰名单（当前 {count} 人）。"
                    )
                await set_user_preference(
                    bot_qq,
                    target,
                    accept_like=True,
                    updated_by=_sender(event),
                )
                count = await count_like_denied(bot_qq)
                await matcher.finish(
                    f"已将 {target} 移出点赞勿扰名单（当前 {count} 人）。"
                )
            if action == "add":
                await set_user_preference(
                    bot_qq,
                    target,
                    accept_comment=True,
                    updated_by=_sender(event),
                )
                count = await count_comment_allowed(bot_qq)
                await matcher.finish(
                    f"已将 {target} 加入评论名单（当前 {count} 人）。"
                )
            await set_user_preference(
                bot_qq,
                target,
                accept_comment=False,
                updated_by=_sender(event),
            )
            count = await count_comment_allowed(bot_qq)
            await matcher.finish(
                f"已将 {target} 移出评论名单（当前 {count} 人）。"
            )

    for name, kind, action in (
        ("加点赞勿扰", "like", "add"),
        ("删点赞勿扰", "like", "remove"),
        ("查看点赞勿扰", "like", "view"),
        ("清空点赞勿扰", "like", "clear"),
        ("加评论名单", "comment", "add"),
        ("删评论名单", "comment", "remove"),
        ("查看评论名单", "comment", "view"),
        ("清空评论名单", "comment", "clear"),
    ):
        register_list_command(name, kind, action)

    logger.info("[qzone_auto_like] 指令已注册")
