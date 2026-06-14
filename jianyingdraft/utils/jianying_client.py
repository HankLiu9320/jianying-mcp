# -*- coding: utf-8 -*-
"""剪映 PC API 通用 HTTP 客户端。"""
from __future__ import annotations

import hashlib
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import urllib3
from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_BASE = "https://lv-pc-api-sinfonlineb.ulikecam.com"
DEFAULT_VOD_BASE = "https://vod.bytedanceapi.com/top/v1"
DEFAULT_SPACE_NAME = "lv-mac-recognition"
DEFAULT_APP_VERSION = "5.9.0"
DEFAULT_AID = "3704"
DEFAULT_APP_SDK_VERSION = "48.0.0"
DEFAULT_TDID = "420445199538212"
DEFAULT_INSTALL_ID = "420445199542308"
DEFAULT_USER_AGENT = (
    "GCronet/TTNetVersion:3024dcd7 2023-10-18 QuicVersion:4bf243e0 2023-04-17"
)

# 企业代理环境下可能需要关闭 SSL 校验
SSL_VERIFY = os.getenv("JIANYING_SSL_VERIFY", "false").lower() in ("1", "true", "yes")
if not SSL_VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _read_ttnet_device_id() -> Optional[str]:
    config_paths = [
        Path.home() / "Movies/JianyingPro/User Data/TTNet/tt_net_config.config",
        Path.home()
        / "Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/TTNet/tt_net_config.config",
    ]
    for path in config_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"device_id&#\*(\d+)", text)
        if match:
            return match.group(1)
    return None


def get_device_profile() -> Dict[str, str]:
    """剪映设备信息（来自 Charles 抓包，可通过环境变量覆盖）。"""
    tdid = (
        os.getenv("JIANYING_TDID", "").strip()
        or os.getenv("JIANYING_DEVICE_ID", "").strip()
        or _read_ttnet_device_id()
        or DEFAULT_TDID
    )
    return {
        "tdid": tdid,
        "device_id": tdid,
        "install_id": os.getenv("JIANYING_INSTALL_ID", "").strip() or DEFAULT_INSTALL_ID,
        "aid": os.getenv("JIANYING_AID", "").strip() or DEFAULT_AID,
        "appvr": os.getenv("JIANYING_APP_VERSION", "").strip() or DEFAULT_APP_VERSION,
        "app_sdk_version": os.getenv("JIANYING_APP_SDK_VERSION", "").strip() or DEFAULT_APP_SDK_VERSION,
        "pf": os.getenv("JIANYING_PF", "").strip() or "3",
        "lan": os.getenv("JIANYING_LAN", "").strip() or "zh-hans",
        "loc": os.getenv("JIANYING_LOC", "").strip() or "cn",
        "channel": os.getenv("JIANYING_CHANNEL", "jianyingpro_0"),
        "version_code": os.getenv("JIANYING_VERSION_CODE", "590000"),
        "user_agent": os.getenv("JIANYING_USER_AGENT", "").strip() or DEFAULT_USER_AGENT,
    }


def make_x_ss_stub(body_text: str) -> str:
    return hashlib.md5(body_text.encode("utf-8")).hexdigest()


def make_api_sign(path: str, appvr: str, device_time: str, tdid: str) -> str:
    """剪映 PC API sign 头（sign-ver=1）。"""
    sign_str = f"9e2c|{path[-7:]}|3|{appvr}|{device_time}|{tdid}|11ac"
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest()


def make_trace_id() -> str:
    seed = uuid.uuid4().hex[:32]
    return f"00-{seed}-{seed[:16]}-01"


def build_signed_api_headers(
    path: str,
    body_text: str,
    *,
    device_time: Optional[str] = None,
) -> Dict[str, str]:
    """无 Cookie 的设备签名请求头（upload_sign 等）。"""
    profile = get_device_profile()
    device_time = device_time or str(int(time.time()))
    return {
        "Content-Type": "application/json",
        "app-sdk-version": profile["app_sdk_version"],
        "appvr": profile["appvr"],
        "device-time": device_time,
        "lan": profile["lan"],
        "loc": profile["loc"],
        "pf": profile["pf"],
        "sign": make_api_sign(path, profile["appvr"], device_time, profile["tdid"]),
        "sign-ver": "1",
        "tdid": profile["tdid"],
        "x-ss-stub": make_x_ss_stub(body_text),
        "x-ss-dpt": profile["aid"],
        "x-tt-trace-id": make_trace_id(),
        "User-Agent": profile["user_agent"],
        "Accept-Encoding": "gzip, deflate",
    }


def get_jianying_cookie() -> str:
    cookie = os.getenv("JIANYING_COOKIE", "").strip()
    if cookie:
        return cookie
    cookie_file = os.getenv("JIANYING_COOKIE_FILE", "").strip()
    if cookie_file and Path(cookie_file).exists():
        return Path(cookie_file).read_text(encoding="utf-8").strip()
    return ""


def build_api_headers(
    *,
    device_id: Optional[str] = None,
    install_id: Optional[str] = None,
    cookie: Optional[str] = None,
) -> Dict[str, str]:
    profile = get_device_profile()
    device_id = device_id or profile["device_id"]
    install_id = install_id or profile["install_id"]
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"JianyingPro/{profile['appvr']} (Macintosh; Intel Mac OS X 10_15_7)",
        "appvr": profile["appvr"],
        "device-platform": "mac",
        "pf": profile["pf"],
        "device_id": device_id,
        "iid": install_id,
        "aid": profile["aid"],
        "channel": profile["channel"],
        "loc": profile["loc"],
        "lan": profile["lan"],
        "version_code": profile["version_code"],
    }
    cookie = cookie if cookie is not None else get_jianying_cookie()
    if cookie:
        headers["Cookie"] = cookie
    return headers


class JianyingApiClient:
    def __init__(
        self,
        api_base: str = DEFAULT_API_BASE,
        vod_base: str = DEFAULT_VOD_BASE,
        verify_ssl: bool = SSL_VERIFY,
    ):
        self.api_base = api_base.rstrip("/")
        self.vod_base = vod_base
        self.verify_ssl = verify_ssl
        self.session = requests.Session()

    def post_json(
        self,
        path: str,
        body: Dict[str, Any],
        *,
        headers: Optional[Dict[str, str]] = None,
        base: Optional[str] = None,
        timeout: float = 60,
    ) -> Dict[str, Any]:
        url = f"{(base or self.api_base).rstrip('/')}{path}"
        resp = self.session.post(
            url,
            json=body,
            headers=headers or build_api_headers(),
            timeout=timeout,
            verify=self.verify_ssl,
        )
        resp.raise_for_status()
        return resp.json()

    def post_json_text(
        self,
        path: str,
        body_text: str,
        *,
        headers: Dict[str, str],
        base: Optional[str] = None,
        timeout: float = 60,
    ) -> Dict[str, Any]:
        url = f"{(base or self.api_base).rstrip('/')}{path}"
        resp = self.session.post(
            url,
            data=body_text.encode("utf-8"),
            headers=headers,
            timeout=timeout,
            verify=self.verify_ssl,
        )
        resp.raise_for_status()
        return resp.json()

    def get_json(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 60,
    ) -> Dict[str, Any]:
        resp = self.session.get(
            url,
            params=params,
            headers=headers or {},
            timeout=timeout,
            verify=self.verify_ssl,
        )
        resp.raise_for_status()
        return resp.json()

    def post_raw(
        self,
        url: str,
        data: bytes,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 120,
    ) -> requests.Response:
        return self.session.post(
            url,
            data=data,
            headers=headers or {},
            timeout=timeout,
            verify=self.verify_ssl,
        )

    def post_json_vod(
        self,
        params: Dict[str, Any],
        body: Dict[str, Any],
        *,
        headers: Dict[str, str],
        timeout: float = 60,
    ) -> Dict[str, Any]:
        resp = self.session.post(
            self.vod_base,
            params=params,
            json=body,
            headers=headers,
            timeout=timeout,
            verify=self.verify_ssl,
        )
        resp.raise_for_status()
        return resp.json()
