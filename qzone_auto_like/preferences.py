"""运行态配置、用户偏好与名单查询。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from zhenxun.configs.config import Config

from .models import QzoneRuntimeConfig, QzoneUserPreference
from .policy import DEFAULT_COMMENT_TEMPLATE, DEFAULT_MONITOR_INTERVAL

_CFG = "qzone_auto_like"
_UNSET = object()

_RUNTIME_FIELDS = {
    "like_enabled",
    "comment_enabled",
    "monitor_interval",
    "comment_template",
    "last_run_at",
}


def _initial_interval() -> int:
    value = Config.get_config(_CFG, "like_interval", DEFAULT_MONITOR_INTERVAL)
    try:
        interval = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MONITOR_INTERVAL
    return min(3600, max(30, interval))


async def get_runtime_config() -> QzoneRuntimeConfig:
    """读取单例配置；首次访问时从 zhenxun 配置初始化。"""
    defaults = {
        "like_enabled": bool(Config.get_config(_CFG, "enable_auto_like", False)),
        "comment_enabled": False,
        "monitor_interval": _initial_interval(),
        "comment_template": DEFAULT_COMMENT_TEMPLATE,
    }
    obj, _ = await QzoneRuntimeConfig.get_or_create(id=1, defaults=defaults)
    return obj


async def update_runtime_config(updated_by: str = "", **fields: Any) -> QzoneRuntimeConfig:
    """更新运行态配置，只接受白名单字段。"""
    updates = {key: value for key, value in fields.items() if key in _RUNTIME_FIELDS}
    if "monitor_interval" in updates:
        updates["monitor_interval"] = min(
            3600, max(30, int(updates["monitor_interval"]))
        )
    if "comment_template" in updates:
        updates["comment_template"] = str(updates["comment_template"])[:100]
    if updates:
        updates["updated_by"] = updated_by[:20]
    await get_runtime_config()
    if updates:
        await QzoneRuntimeConfig.filter(id=1).update(**updates)
    return await get_runtime_config()


async def touch_last_run(when: datetime | None = None) -> None:
    await QzoneRuntimeConfig.filter(id=1).update(last_run_at=when or datetime.now())


async def get_user_preference(
    bot_qq: str, user_qq: str
) -> QzoneUserPreference | None:
    return await QzoneUserPreference.get_or_none(bot_qq=bot_qq, user_qq=user_qq)


async def set_user_preference(
    bot_qq: str,
    user_qq: str,
    *,
    accept_like: bool | None = None,
    accept_comment: bool | None = None,
    comment_template: str | None | object = _UNSET,
    updated_by: str = "",
) -> QzoneUserPreference:
    """按需更新个人偏好；未提供的字段保持不变。"""
    pref, _ = await QzoneUserPreference.get_or_create(
        bot_qq=bot_qq,
        user_qq=user_qq,
        defaults={
            "accept_like": True,
            "accept_comment": False,
            "comment_template": None,
        },
    )
    updates: dict[str, Any] = {}
    if accept_like is not None:
        updates["accept_like"] = accept_like
    if accept_comment is not None:
        updates["accept_comment"] = accept_comment
    if comment_template is not _UNSET:
        updates["comment_template"] = comment_template
    if updates:
        updates["updated_by"] = updated_by[:20]
        await QzoneUserPreference.filter(id=pref.id).update(**updates)
        await pref.refresh_from_db()
    return pref


async def get_like_denied(bot_qq: str) -> set[str]:
    """点赞勿扰名单：accept_like=False 的用户。"""
    rows = await QzoneUserPreference.filter(
        bot_qq=bot_qq, accept_like=False
    ).values_list("user_qq", flat=True)
    return set(rows)


async def get_comment_allowed(bot_qq: str) -> set[str]:
    """评论名单：accept_comment=True 的用户。"""
    rows = await QzoneUserPreference.filter(
        bot_qq=bot_qq, accept_comment=True
    ).values_list("user_qq", flat=True)
    return set(rows)


async def list_like_denied(bot_qq: str) -> list[str]:
    rows = await QzoneUserPreference.filter(
        bot_qq=bot_qq, accept_like=False
    ).order_by("user_qq").values_list("user_qq", flat=True)
    return list(rows)


async def list_comment_allowed(bot_qq: str) -> list[str]:
    rows = await QzoneUserPreference.filter(
        bot_qq=bot_qq, accept_comment=True
    ).order_by("user_qq").values_list("user_qq", flat=True)
    return list(rows)


async def get_personal_templates(bot_qq: str, user_ids: list[str]) -> dict[str, str]:
    """批量取个人模板，避免逐条查询。"""
    if not user_ids:
        return {}
    rows = await QzoneUserPreference.filter(
        bot_qq=bot_qq,
        user_qq__in=user_ids,
        comment_template__isnull=False,
    ).values_list("user_qq", "comment_template")
    return {str(qq): str(tpl) for qq, tpl in rows if tpl}


async def clear_like_denied(bot_qq: str) -> int:
    return await QzoneUserPreference.filter(
        bot_qq=bot_qq, accept_like=False
    ).update(accept_like=True)


async def clear_comment_allowed(bot_qq: str) -> int:
    return await QzoneUserPreference.filter(
        bot_qq=bot_qq, accept_comment=True
    ).update(accept_comment=False)


async def count_like_denied(bot_qq: str) -> int:
    return await QzoneUserPreference.filter(bot_qq=bot_qq, accept_like=False).count()


async def count_comment_allowed(bot_qq: str) -> int:
    return await QzoneUserPreference.filter(
        bot_qq=bot_qq, accept_comment=True
    ).count()


async def count_personal_templates(bot_qq: str) -> int:
    return await QzoneUserPreference.filter(
        bot_qq=bot_qq, comment_template__isnull=False
    ).count()
