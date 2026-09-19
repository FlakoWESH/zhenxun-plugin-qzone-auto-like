from tortoise import fields

from zhenxun.services.db_context import Model


class QzoneLikeRecord(Model):
    """记录QQ空间说说点赞记录"""

    qq_number = fields.CharField(max_length=20, description="点赞的QQ号")
    qzone_post_id = fields.CharField(max_length=50, description="说说ID")
    like_time = fields.DatetimeField(description="点赞时间")

    class Meta:
        table = "qzone_like_record"
        table_description = "QQ空间说说点赞记录表"
