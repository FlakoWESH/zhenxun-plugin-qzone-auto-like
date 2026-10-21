"""自动评论业务逻辑。

评论名单内、未评论过的说说才会进入候选；个人模板优先于全局模板。
评论成功后落库，失败留待下一轮重试。
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime

from zhenxun.services.log import logger

from .bridge import QzoneBridgeClient
from .feed import FeedScanner, QzonePost
from .models import QzoneCommentRecord
from .policy import choose_template, render_template
from .preferences import get_personal_templates
from .selection import select_comment_candidates


def _start_of_today() -> datetime:
    now = datetime.now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class AutoCommentService:
    """自动评论服务。"""

    def __init__(self, bridge: QzoneBridgeClient, scanner: FeedScanner | None = None):
        self.bridge = bridge
        self.scanner = scanner or FeedScanner(bridge)

    async def run(
        self,
        posts: list[QzonePost],
        qq: str,
        allowed: set[str],
        global_template: str,
        max_per_round: int = 5,
        daily_limit: int = 50,
        delay_min: float = 5.0,
        delay_max: float = 15.0,
    ) -> dict:
        stats = {
            "fetched": len(posts),
            "commented": 0,
            "skipped": 0,
            "failed": 0,
            "limit_reached": False,
        }
        if not posts:
            return stats

        post_ids = [post.tid for post in posts]
        existing = set(
            await QzoneCommentRecord.filter(
                bot_qq=qq, post_id__in=post_ids
            ).values_list("post_id", flat=True)
        )
        pending = select_comment_candidates(
            posts,
            allowed=allowed,
            existing=existing,
            self_qq=qq,
            limit=max_per_round if max_per_round > 0 else None,
        )
        stats["skipped"] = len(posts) - len(pending)
        if not pending:
            return stats

        if daily_limit > 0:
            today_count = await QzoneCommentRecord.filter(
                bot_qq=qq, comment_time__gte=_start_of_today()
            ).count()
            remaining = daily_limit - today_count
            if remaining <= 0:
                stats["limit_reached"] = True
                logger.info(
                    f"[qzone_auto_like] 已达每日评论上限({daily_limit})，本轮跳过"
                )
                return stats
            pending = pending[:remaining]

        templates = await get_personal_templates(
            qq, [post.uin for post in pending if post.uin]
        )
        low, high = sorted((max(0.0, delay_min), max(0.0, delay_max)))

        for post in pending:
            template = choose_template(
                templates.get(post.uin), global_template
            )
            content = render_template(template, post.nickname)[:100]
            try:
                data = await self.bridge.send_comment(post.tid, content, post.uin)
            except Exception as e:  # noqa: BLE001 - 单条失败不应中断整轮
                stats["failed"] += 1
                logger.warning(
                    f"[qzone_auto_like] 评论失败 tid={post.tid}: {e}"
                )
                continue

            await QzoneCommentRecord.get_or_create(
                bot_qq=qq,
                post_id=post.tid,
                defaults={
                    "target_qq": post.uin,
                    "comment_id": str(data.get("comment_id") or "") or None,
                    "content": content,
                    "comment_time": datetime.now(),
                },
            )
            stats["commented"] += 1

            if high > 0:
                await asyncio.sleep(random.uniform(low, high))

        return stats
