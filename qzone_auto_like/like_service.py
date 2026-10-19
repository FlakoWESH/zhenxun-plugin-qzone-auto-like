"""自动点赞业务逻辑。

职责：拉取好友空间时间线 -> 过滤 -> 去重 -> 限额 -> 逐条点赞 -> 记录。
所有点赞均通过 onebot-qzone 桥接服务的 HTTP action 完成，点赞成功后再落库，
避免把被风控/失败的说说标记为「已点赞」而永久跳过。
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime

from zhenxun.services.log import logger

from .bridge import QzoneBridgeClient
from .models import QzoneLikeRecord


def _extract_tid(post: dict) -> str:
    return str(post.get("tid") or post.get("cellid") or "").strip()


def _extract_uin(post: dict) -> str:
    for key in ("user_id", "uin", "hostuin", "host_uin"):
        value = post.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _start_of_today() -> datetime:
    now = datetime.now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class AutoLikeService:
    """自动点赞服务。"""

    def __init__(self, bridge: QzoneBridgeClient):
        self.bridge = bridge

    async def run_once(
        self,
        qq: str,
        max_count: int = 50,
        delay_min: float = 2.0,
        delay_max: float = 6.0,
        daily_limit: int = 200,
    ) -> dict:
        """执行一轮点赞。

        返回统计 dict：fetched / liked / skipped / failed / limit_reached。
        """
        stats = {
            "fetched": 0,
            "liked": 0,
            "skipped": 0,
            "failed": 0,
            "limit_reached": False,
        }

        data = await self.bridge.get_friend_feeds(num=max_count)
        posts = data.get("msglist") if isinstance(data, dict) else None
        if not isinstance(posts, list):
            logger.warning("[qzone_auto_like] 时间线返回结构异常，跳过本轮")
            return stats

        # 规整候选（去空 tid）
        candidates: list[tuple[str, str]] = []
        for post in posts:
            if not isinstance(post, dict):
                continue
            tid = _extract_tid(post)
            if tid:
                candidates.append((tid, _extract_uin(post)))
        stats["fetched"] = len(candidates)

        if not candidates:
            return stats

        # 去重：一次查询已点赞的 tid 集合
        like_ids = [tid for tid, _ in candidates]
        existing = set(
            await QzoneLikeRecord.filter(
                qq_number=qq, qzone_post_id__in=like_ids
            ).values_list("qzone_post_id", flat=True)
        )
        pending = [(tid, uin) for tid, uin in candidates if tid not in existing]
        stats["skipped"] = len(candidates) - len(pending)

        if not pending:
            return stats

        # 每日限额
        if daily_limit > 0:
            today_count = await QzoneLikeRecord.filter(
                qq_number=qq, like_time__gte=_start_of_today()
            ).count()
            remaining = daily_limit - today_count
            if remaining <= 0:
                stats["limit_reached"] = True
                logger.info(
                    f"[qzone_auto_like] 已达每日点赞上限({daily_limit})，本轮跳过"
                )
                return stats
            pending = pending[:remaining]

        # 随机延迟区间保护
        low, high = sorted((max(0.0, delay_min), max(0.0, delay_max)))

        for tid, uin in pending:
            try:
                await self.bridge.send_like(tid, uin)
            except Exception as e:  # noqa: BLE001 - 单条失败不应中断整轮
                stats["failed"] += 1
                logger.warning(
                    f"[qzone_auto_like] 点赞失败 tid={tid}: {e}"
                )
                continue

            # 点赞成功后才落库；唯一约束兜底并发/重复
            await QzoneLikeRecord.get_or_create(
                qq_number=qq,
                qzone_post_id=tid,
                defaults={"like_time": datetime.now()},
            )
            stats["liked"] += 1

            if high > 0:
                await asyncio.sleep(random.uniform(low, high))

        return stats
