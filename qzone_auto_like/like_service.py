"""自动点赞业务逻辑。

职责：接收共享时间线 -> 过滤勿扰/已赞 -> 限额 -> 逐条点赞 -> 记录。
点赞成功后再落库，避免把被风控/失败的说说标记为「已点赞」而永久跳过。
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime

from zhenxun.services.log import logger

from .bridge import QzoneBridgeClient
from .feed import FeedScanner, QzonePost
from .models import QzoneLikeRecord
from .selection import select_like_candidates


def _start_of_today() -> datetime:
    now = datetime.now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class AutoLikeService:
    """自动点赞服务。"""

    def __init__(self, bridge: QzoneBridgeClient, scanner: FeedScanner | None = None):
        self.bridge = bridge
        self.scanner = scanner or FeedScanner(bridge)

    async def run_once(
        self,
        qq: str,
        max_count: int = 50,
        delay_min: float = 2.0,
        delay_max: float = 6.0,
        daily_limit: int = 200,
        denied: set[str] | None = None,
    ) -> dict:
        posts = await self.scanner.scan(max_count)
        return await self.run(
            posts,
            qq=qq,
            delay_min=delay_min,
            delay_max=delay_max,
            daily_limit=daily_limit,
            denied=denied,
        )

    async def run(
        self,
        posts: list[QzonePost],
        qq: str,
        delay_min: float = 2.0,
        delay_max: float = 6.0,
        daily_limit: int = 200,
        denied: set[str] | None = None,
    ) -> dict:
        """对已抓取的时间线执行一轮点赞。"""
        stats = {
            "fetched": len(posts),
            "liked": 0,
            "skipped": 0,
            "failed": 0,
            "limit_reached": False,
        }
        if not posts:
            return stats

        like_ids = [post.tid for post in posts]
        existing = set(
            await QzoneLikeRecord.filter(
                qq_number=qq, qzone_post_id__in=like_ids
            ).values_list("qzone_post_id", flat=True)
        )
        pending = select_like_candidates(posts, denied=denied, existing=existing)
        stats["skipped"] = len(posts) - len(pending)
        if not pending:
            return stats

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

        low, high = sorted((max(0.0, delay_min), max(0.0, delay_max)))

        for post in pending:
            try:
                await self.bridge.send_like(post.tid, post.uin)
            except Exception as e:  # noqa: BLE001 - 单条失败不应中断整轮
                stats["failed"] += 1
                logger.warning(
                    f"[qzone_auto_like] 点赞失败 tid={post.tid}: {e}"
                )
                continue

            await QzoneLikeRecord.get_or_create(
                qq_number=qq,
                qzone_post_id=post.tid,
                defaults={"like_time": datetime.now()},
            )
            stats["liked"] += 1

            if high > 0:
                await asyncio.sleep(random.uniform(low, high))

        return stats
