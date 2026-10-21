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
        indexes = (("qq_number", "like_time"),)


class QzoneCommentRecord(Model):
    """记录 QQ 空间说说评论记录（用于防重复评论）。"""

    bot_qq = fields.CharField(max_length=20, description="执行评论的Bot QQ")
    post_id = fields.CharField(max_length=64, description="说说ID")
    target_qq = fields.CharField(max_length=20, description="说说作者QQ")
    comment_id = fields.CharField(
        max_length=64, null=True, description="QQ空间返回的评论ID"
    )
    content = fields.CharField(max_length=100, description="评论内容")
    comment_time = fields.DatetimeField(description="评论时间")

    class Meta:
        table = "qzone_comment_record"
        table_description = "QQ空间说说评论记录表"
        unique_together = (("bot_qq", "post_id"),)
        indexes = (("bot_qq", "comment_time"),)


class QzoneRuntimeConfig(Model):
    """插件的运行态配置（单例，id 固定为 1）。"""

    id = fields.IntField(pk=True, default=1, description="固定为1")
    like_enabled = fields.BooleanField(default=False, description="全局秒赞开关")
    comment_enabled = fields.BooleanField(default=False, description="全局秒评开关")
    monitor_interval = fields.IntField(default=120, description="监控间隔（秒）")
    comment_template = fields.CharField(
        max_length=100, default="QεQ", description="全局秒评内容"
    )
    last_run_at = fields.DatetimeField(null=True, description="上一轮执行时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
    updated_by = fields.CharField(max_length=20, default="", description="最后修改人")

    class Meta:
        table = "qzone_runtime_config"
        table_description = "QQ空间互动运行态配置表"


class QzoneUserPreference(Model):
    """普通用户的接收偏好。

    accept_like 默认 True：默认接收点赞，False 表示在点赞勿扰名单。
    accept_comment 默认 False：默认不接收评论，True 表示在评论名单。
    """

    bot_qq = fields.CharField(max_length=20, description="Bot QQ")
    user_qq = fields.CharField(max_length=20, description="用户QQ")
    accept_like = fields.BooleanField(default=True, description="是否接收秒赞")
    accept_comment = fields.BooleanField(default=False, description="是否接收秒评")
    comment_template = fields.CharField(
        max_length=100, null=True, description="个人秒评内容，空则用全局"
    )
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
    updated_by = fields.CharField(max_length=20, default="", description="最后修改人")

    class Meta:
        table = "qzone_user_preference"
        table_description = "QQ空间互动用户偏好表"
        unique_together = (("bot_qq", "user_qq"),)
        indexes = (
            ("bot_qq", "accept_like"),
            ("bot_qq", "accept_comment"),
        )
