"""
QQ空间 Cookie 自动刷新模块（真寻版）

通过 NapCat 的 get_cookies API 自动获取 QQ 空间 Cookie，
然后调用 onebot-qzone 桥接服务的 update_cookie API 动态更新 Cookie。
"""
import asyncio
import time
from typing import Optional, Tuple

import aiohttp
from nonebot.log import logger


REQUIRED_COOKIE_FIELDS = ("uin", "p_uin", "skey", "p_skey")


class CookieRefresher:
    """QQ空间 Cookie 自动刷新器"""

    def __init__(
        self,
        napcat_url: str,
        napcat_token: str,
        bridge_url: str,
        bridge_token: str,
        refresh_interval: int = 7200,
        request_timeout: int = 10,
    ):
        self.napcat_url = napcat_url.rstrip("/")
        self.napcat_token = napcat_token
        self.bridge_url = bridge_url.rstrip("/")
        self.bridge_token = bridge_token
        self.refresh_interval = refresh_interval
        self.request_timeout = request_timeout

        self._last_refresh_time: Optional[float] = None
        self._last_refresh_success: Optional[bool] = None
        self._last_error: Optional[str] = None
        self._refresh_count: int = 0

    async def fetch_cookie_from_napcat(self) -> str:
        """调用 NapCat 的 get_cookies API 获取 QQ 空间 Cookie"""
        url = f"{self.napcat_url}/get_cookies"
        headers = {"Content-Type": "application/json"}
        if self.napcat_token:
            headers["Authorization"] = f"Bearer {self.napcat_token}"

        payload = {"domain": "user.qzone.qq.com"}

        logger.info("[qzone_auto_like] 正在从 NapCat 获取 QQ 空间 Cookie: %s", url)

        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"NapCat API 返回 HTTP {resp.status}")

                data = await resp.json()
                retcode = data.get("retcode", -1)
                status = data.get("status", "")
                if retcode != 0 or status != "ok":
                    msg = data.get("message", "未知错误")
                    raise RuntimeError(
                        f"NapCat API 返回错误: retcode={retcode}, status={status}, message={msg}"
                    )

                inner = data.get("data") or {}
                cookies_str = inner.get("cookies", "")
                if not cookies_str:
                    raise RuntimeError("NapCat API 返回数据中缺少 cookies 字段")

                missing = self._check_required_fields(cookies_str)
                if missing:
                    raise RuntimeError(
                        f"Cookie 缺少必要字段: {', '.join(missing)}。"
                        f"请确认 NapCat 已正确登录 QQ 且版本 >= v4.18.0"
                    )

                return cookies_str

    @staticmethod
    def _check_required_fields(cookie_str: str) -> list:
        found = {}
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                key, _, value = pair.partition("=")
                found[key.strip()] = value.strip()
        return [f for f in REQUIRED_COOKIE_FIELDS if not found.get(f)]

    async def push_cookie_to_bridge(self, cookie_str: str) -> None:
        """调用 onebot-qzone 的 update_cookie API 更新 Cookie"""
        url = f"{self.bridge_url}/update_cookie"
        headers = {"Content-Type": "application/json"}
        if self.bridge_token:
            headers["Authorization"] = f"Bearer {self.bridge_token}"

        payload = {"cookie": cookie_str}

        logger.info("[qzone_auto_like] 正在更新 onebot-qzone Cookie: %s", url)

        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"onebot-qzone API 返回 HTTP {resp.status}")

                data = await resp.json()
                status = data.get("status", "")
                retcode = data.get("retcode", -1)
                if status != "ok" and retcode != 0:
                    msg = data.get("message", "未知错误")
                    raise RuntimeError(
                        f"onebot-qzone Cookie 更新失败: status={status}, retcode={retcode}, message={msg}"
                    )

                logger.info("[qzone_auto_like] onebot-qzone Cookie 更新成功")

    async def refresh_once(self) -> Tuple[bool, Optional[str]]:
        """执行一次完整的 Cookie 刷新"""
        try:
            cookie_str = await self.fetch_cookie_from_napcat()
            logger.info("[qzone_auto_like] 成功获取 Cookie，长度=%d", len(cookie_str))
            await self.push_cookie_to_bridge(cookie_str)

            self._last_refresh_time = time.time()
            self._last_refresh_success = True
            self._last_error = None
            self._refresh_count += 1
            return True, None
        except Exception as e:
            error_msg = str(e)
            self._last_refresh_time = time.time()
            self._last_refresh_success = False
            self._last_error = error_msg
            logger.error("[qzone_auto_like] Cookie 刷新失败: %s", error_msg)
            return False, error_msg

    async def refresh_loop(self):
        """Cookie 自动刷新后台循环"""
        logger.info(
            "[qzone_auto_like] Cookie 自动刷新任务已启动 (间隔=%d秒)",
            self.refresh_interval,
        )
        await asyncio.sleep(5)
        success, err = await self.refresh_once()
        if success:
            logger.info("[qzone_auto_like] 首次 Cookie 刷新成功")
        else:
            logger.warning("[qzone_auto_like] 首次 Cookie 刷新失败: %s", err)

        while True:
            await asyncio.sleep(self.refresh_interval)
            await self.refresh_once()

    def get_status(self) -> dict:
        return {
            "last_refresh_time": self._last_refresh_time,
            "last_refresh_success": self._last_refresh_success,
            "last_error": self._last_error,
            "refresh_count": self._refresh_count,
            "refresh_interval": self.refresh_interval,
        }
