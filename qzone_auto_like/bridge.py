"""onebot-qzone 桥接服务 HTTP 客户端。

onebot-qzone（qzone-onebot-bridge）是一个 Node/TypeScript 服务，把 QQ 空间能力
以 OneBot v11 action 的形式暴露在 HTTP 接口上（POST /<action>）。

本模块用统一的 aiohttp.ClientSession 访问这些 action：
- check_cookie      ：带网络探针检测当前 Cookie 是否有效
- update_cookie     ：热更新 Cookie
- get_friend_feeds  ：拉取好友空间时间线（好友动态）
- get_emotion_list  ：拉取指定用户（默认自己）的说说列表
- send_like         ：给指定说说点赞
- send_comment      ：给指定说说发表评论
- get_login_info    ：查询桥接登录态

统一走后端配置 bridge_url / bridge_token，鉴权用 `Authorization: Bearer <token>`
（桥接服务同时兼容 `?access_token=`）。
"""
from __future__ import annotations

from typing import Any

import aiohttp


class BridgeError(RuntimeError):
    """桥接服务调用失败。"""


class QzoneBridgeClient:
    """onebot-qzone 桥接服务的轻量 HTTP 客户端。"""

    def __init__(self, base_url: str, token: str = "", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.token = token or ""
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def call(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """调用一个桥接 action，返回原始响应体（含 status/retcode/data/message）。"""
        session = await self._get_session()
        url = f"{self.base_url}/{action}"
        async with session.post(url, json=params or {}, headers=self._headers()) as resp:
            if resp.status == 401:
                raise BridgeError("桥接服务鉴权失败（401），请检查 bridge_token")
            if resp.status != 200:
                raise BridgeError(f"{action} 返回 HTTP {resp.status}")
            body = await resp.json(content_type=None)
        if not isinstance(body, dict):
            raise BridgeError(f"{action} 返回了非 JSON 对象")
        return body

    async def call_data(self, action: str, params: dict[str, Any] | None = None) -> Any:
        """调用 action，校验 retcode==0，返回 data 字段。"""
        body = await self.call(action, params)
        retcode = body.get("retcode", -1)
        if retcode != 0:
            raise BridgeError(
                f"{action} 失败: retcode={retcode}, message={body.get('message', '未知错误')}"
            )
        return body.get("data")

    async def check_cookie(self, probe: bool = True) -> dict[str, Any]:
        data = await self.call_data("check_cookie", {"probe": probe})
        return data or {}

    async def update_cookie(self, cookie: str) -> dict[str, Any]:
        data = await self.call_data("update_cookie", {"cookie": cookie})
        return data or {}

    async def get_login_info(self) -> dict[str, Any]:
        data = await self.call_data("get_login_info")
        return data or {}

    async def get_status(self) -> dict[str, Any]:
        # /status 是桥接服务的健康检查端点，返回结构与非 OneBot action 不同
        session = await self._get_session()
        url = f"{self.base_url}/status"
        async with session.get(url, headers=self._headers()) as resp:
            if resp.status != 200:
                raise BridgeError(f"status 返回 HTTP {resp.status}")
            return await resp.json(content_type=None)

    async def get_friend_feeds(self, num: int = 50, cursor: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {"num": max(1, num)}
        if cursor:
            params["cursor"] = cursor
        data = await self.call_data("get_friend_feeds", params)
        return data or {}

    async def get_emotion_list(self, uin: str = "", num: int = 50, pos: int = 0) -> dict[str, Any]:
        params: dict[str, Any] = {"num": max(1, num), "pos": pos}
        if uin:
            params["user_id"] = uin
        data = await self.call_data("get_emotion_list", params)
        return data or {}

    async def send_like(self, tid: str, user_id: str = "") -> None:
        params: dict[str, Any] = {"tid": str(tid)}
        if user_id:
            params["user_id"] = str(user_id)
        await self.call_data("send_like", params)

    async def send_comment(
        self, tid: str, content: str, user_id: str = ""
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"tid": str(tid), "content": content}
        if user_id:
            params["user_id"] = str(user_id)
        data = await self.call_data("send_comment", params)
        return data or {}
