"""QQ空间 Cookie 自动刷新模块（真寻版）。

通过 NapCat 的 get_cookies API 自动获取 QQ 空间 Cookie，
再调用 onebot-qzone 桥接服务的 update_cookie action 动态更新 Cookie。

工作流程（按需刷新）：
1. 调用桥接服务 check_cookie（带网络探针）检测当前 Cookie 是否有效
2. Cookie 仍有效 -> 跳过，不触发任何变更（防风控）
3. Cookie 失效，或预检本身失败（fail-open）-> 执行完整刷新流程
4. 更新后可选再次 check_cookie 验证

前提条件：
- NapCat 版本 >= v4.18.0（修复了 bkn 计算 bug）
- NapCat 已登录 QQ，且开启了 HTTP API
- onebot-qzone 桥接服务正在运行（v2.0.0+，支持 check_cookie / update_cookie）
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import aiohttp
from zhenxun.services.log import logger

if TYPE_CHECKING:
    from .bridge import QzoneBridgeClient


REQUIRED_COOKIE_FIELDS = ("uin", "p_uin", "skey", "p_skey")


class CookieRefresher:
    """QQ空间 Cookie 自动刷新器（按需刷新）。"""

    def __init__(
        self,
        napcat_url: str,
        napcat_token: str,
        bridge_client: "QzoneBridgeClient",
        refresh_interval: int = 7200,
        request_timeout: int = 10,
        verify_after_update: bool = True,
    ):
        self.napcat_url = napcat_url.rstrip("/")
        self.napcat_token = napcat_token or ""
        self.bridge = bridge_client
        self.refresh_interval = refresh_interval
        self.request_timeout = request_timeout
        self.verify_after_update = verify_after_update

        self._last_refresh_time: float | None = None
        self._last_refresh_success: bool | None = None
        self._last_error: str | None = None
        self._refresh_count: int = 0
        self._last_check_time: float | None = None
        self._last_cookie_valid: bool | None = None
        self._last_cookie_age_seconds: int | None = None
        self._last_check_message: str | None = None

        self._napcat_session: aiohttp.ClientSession | None = None

    async def _get_napcat_session(self) -> aiohttp.ClientSession:
        if self._napcat_session is None or self._napcat_session.closed:
            self._napcat_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.request_timeout)
            )
        return self._napcat_session

    async def close(self) -> None:
        if self._napcat_session is not None and not self._napcat_session.closed:
            await self._napcat_session.close()
        self._napcat_session = None
        await self.bridge.close()

    async def check_cookie_on_bridge(self) -> dict:
        """调用桥接服务 check_cookie，检测当前 Cookie 是否有效。"""
        logger.debug("[qzone_auto_like] 正在检测当前 Cookie 是否有效...")
        inner = await self.bridge.check_cookie(probe=True)
        result = {
            "valid": bool(inner.get("valid", False)),
            "expired": bool(inner.get("expired", True)),
            "message": inner.get("message", ""),
            "has_p_skey": bool(inner.get("has_p_skey", False)),
            "has_skey": bool(inner.get("has_skey", False)),
            "cookie_age_seconds": inner.get("cookie_age_seconds"),
        }
        self._last_check_time = time.time()
        self._last_cookie_valid = result["valid"]
        self._last_cookie_age_seconds = result.get("cookie_age_seconds")
        self._last_check_message = result["message"]
        return result

    async def fetch_cookie_from_napcat(self) -> str:
        """调用 NapCat 的 get_cookies API 获取 QQ 空间 Cookie。"""
        url = f"{self.napcat_url}/get_cookies"
        headers = {"Content-Type": "application/json"}
        if self.napcat_token:
            headers["Authorization"] = f"Bearer {self.napcat_token}"

        logger.info("[qzone_auto_like] 正在从 NapCat 获取 QQ 空间 Cookie: %s", url)

        session = await self._get_napcat_session()
        async with session.post(
            url, json={"domain": "user.qzone.qq.com"}, headers=headers
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"NapCat API 返回 HTTP {resp.status}")
            data = await resp.json(content_type=None)

        retcode = data.get("retcode", -1)
        status = data.get("status", "")
        if retcode != 0 or status != "ok":
            raise RuntimeError(
                f"NapCat API 返回错误: retcode={retcode}, status={status}, "
                f"message={data.get('message', '未知错误')}"
            )

        cookies_str = (data.get("data") or {}).get("cookies", "")
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
    def _check_required_fields(cookie_str: str) -> list[str]:
        found: dict[str, str] = {}
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                key, _, value = pair.partition("=")
                found[key.strip()] = value.strip()
        return [f for f in REQUIRED_COOKIE_FIELDS if not found.get(f)]

    async def refresh_once(self, force: bool = False) -> tuple[bool, str | None]:
        """执行一次 Cookie 检查与刷新（按需刷新）。"""
        try:
            if not force:
                try:
                    check_result = await self.check_cookie_on_bridge()
                except Exception as e:  # noqa: BLE001 - 预检失败不阻断刷新（fail-open）
                    logger.warning(
                        "[qzone_auto_like] Cookie 预检失败（%s），改为直接刷新", e
                    )
                else:
                    if check_result["valid"]:
                        age_min = ""
                        if check_result.get("cookie_age_seconds") is not None:
                            age_sec = check_result["cookie_age_seconds"]
                            age_min = f"，Cookie 年龄={round(age_sec / 60)} 分钟"
                        logger.info(
                            "[qzone_auto_like] 当前 Cookie 仍有效%s，无需刷新，跳过。",
                            age_min,
                        )
                        self._last_refresh_time = time.time()
                        self._last_refresh_success = True
                        self._last_error = None
                        return True, None
                    logger.info(
                        "[qzone_auto_like] 当前 Cookie 已失效：%s，开始刷新...",
                        check_result["message"],
                    )

            cookie_str = await self.fetch_cookie_from_napcat()
            logger.info("[qzone_auto_like] 成功获取 Cookie，长度=%d", len(cookie_str))

            inner = await self.bridge.update_cookie(cookie_str)
            logger.info(
                "[qzone_auto_like] Cookie 热更新成功！QQ号=%s, 昵称=%s, %s",
                inner.get("user_id", 0),
                inner.get("nickname", ""),
                inner.get("message", "Cookie 已更新"),
            )

            if self.verify_after_update:
                try:
                    verify_result = await self.check_cookie_on_bridge()
                    if verify_result["valid"]:
                        logger.info(
                            "[qzone_auto_like] Cookie 验证通过：has_p_skey=%s, has_skey=%s",
                            verify_result["has_p_skey"],
                            verify_result["has_skey"],
                        )
                    else:
                        logger.warning(
                            "[qzone_auto_like] Cookie 验证失败：%s，请检查 update_cookie 是否真正生效",
                            verify_result["message"],
                        )
                except Exception as e:  # noqa: BLE001
                    logger.warning("[qzone_auto_like] 更新后验证失败：%s", e)

            self._last_refresh_time = time.time()
            self._last_refresh_success = True
            self._last_error = None
            self._refresh_count += 1
            return True, None

        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            self._last_refresh_time = time.time()
            self._last_refresh_success = False
            self._last_error = error_msg
            logger.error("[qzone_auto_like] Cookie 刷新失败: %s", error_msg)
            return False, error_msg

    def is_refresh_due(self) -> bool:
        """距离上次检查是否已达到 refresh_interval。"""
        if self._last_check_time is None:
            return True
        return (time.time() - self._last_check_time) >= self.refresh_interval

    async def maybe_refresh(self) -> None:
        """供调度器周期调用：到点才执行一次检查/刷新。"""
        if self.is_refresh_due():
            await self.refresh_once(force=False)

    def get_status(self) -> dict:
        return {
            "last_refresh_time": self._last_refresh_time,
            "last_refresh_success": self._last_refresh_success,
            "last_error": self._last_error,
            "refresh_count": self._refresh_count,
            "refresh_interval": self.refresh_interval,
            "verify_after_update": self.verify_after_update,
            "last_check_time": self._last_check_time,
            "last_cookie_valid": self._last_cookie_valid,
            "last_cookie_age_seconds": self._last_cookie_age_seconds,
            "last_check_message": self._last_check_message,
        }
