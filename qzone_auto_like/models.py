from tortoise import fields

from zhenxun.services.db_context import Model


class QzoneLikeRecord(Model):
    """记录 QQ 空间说说点赞记录（用于防重复点赞）。"""

    qq_number = fields.CharField(max_length=20, description="点赞的QQ号")
    qzone_post_id = fields.CharField(max_length=64, description="说说ID")
    like_time = fields.DatetimeField(description="点赞时间")

    class Meta:
        table = "qzone_like_record"
        table_description = "QQ空间说说点赞记录表"
        unique_together = (("qq_number", "qzone_post_id"),)
        # 常用查询：按 (qq_number, like_time) 统计当日点赞数
        indexes = (("qq_number", "like_time"),)
