# -*- coding: utf-8 -*-
"""剪映识别业务 VOD/TOS 上传（ApplyUploadInner → TOS → CommitUploadInner）。"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import binascii
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

from jianyingdraft.utils.jianying_client import (
    DEFAULT_SPACE_NAME,
    DEFAULT_VOD_BASE,
    JianyingApiClient,
    build_signed_api_headers,
)


class VodUploadError(Exception):
    pass


def _sign_v4_get(
    *,
    host: str,
    path: str,
    query: Dict[str, str],
    access_key_id: str,
    secret_access_key: str,
    session_token: str,
    region: str = "cn-north-1",
    service: str = "vod",
) -> Dict[str, str]:
    """AWS SigV4 签名（Volcengine/字节 VOD Inner GET）。"""
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    canonical_query = urlencode(sorted(query.items()), quote_via=quote)
    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-security-token:{session_token}\n"
    )
    signed_headers = "host;x-amz-date;x-amz-security-token"
    payload_hash = hashlib.sha256(b"").hexdigest()
    canonical_request = "\n".join(
        ["GET", path, canonical_query, canonical_headers, signed_headers, payload_hash]
    )

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    k_date = _sign(("AWS4" + secret_access_key).encode(), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "X-Amz-Date": amz_date,
        "X-Amz-Security-Token": session_token,
        "Host": host,
    }


def _sign_v4_post_json(
    *,
    host: str,
    path: str,
    query: Dict[str, str],
    body: str,
    access_key_id: str,
    secret_access_key: str,
    session_token: str,
    region: str = "cn-north-1",
    service: str = "vod",
) -> Dict[str, str]:
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    canonical_query = urlencode(sorted(query.items()), quote_via=quote)
    canonical_headers = (
        f"content-type:application/json\n"
        f"host:{host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-security-token:{session_token}\n"
    )
    signed_headers = "content-type;host;x-amz-date;x-amz-security-token"
    payload_hash = hashlib.sha256(body.encode()).hexdigest()
    canonical_request = "\n".join(
        ["POST", path, canonical_query, canonical_headers, signed_headers, payload_hash]
    )
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    k_date = _sign(("AWS4" + secret_access_key).encode(), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": "application/json",
        "X-Amz-Date": amz_date,
        "X-Amz-Security-Token": session_token,
        "Host": host,
    }


def fetch_upload_credentials(
    client: JianyingApiClient,
    *,
    space_name: str = DEFAULT_SPACE_NAME,
) -> Dict[str, str]:
    """调用 /lv/v1/upload_sign 获取 VOD 临时凭证（设备签名，无需 Cookie）。"""
    path = "/lv/v1/upload_sign"
    body_text = json.dumps({"biz": "pc-recognition"}, separators=(",", ":"))
    headers = build_signed_api_headers(path, body_text)
    resp = client.post_json_text(path, body_text, headers=headers)
    if str(resp.get("ret")) != "0":
        raise VodUploadError(
            f"upload_sign 失败: ret={resp.get('ret')} errmsg={resp.get('errmsg')}。"
            "请确认设备信息（tdid/appvr）与剪映客户端一致。"
        )
    data = resp.get("data") or {}
    access_key_id = data.get("access_key_id") or data.get("accessKey") or data.get("access_key")
    secret_key = (
        data.get("secret_access_key")
        or data.get("secretKey")
        or data.get("secret_key")
    )
    session_token = data.get("session_token") or data.get("sessionToken")
    namespace = data.get("space_name") or data.get("nameSpace") or space_name
    if not all([access_key_id, secret_key, session_token]):
        raise VodUploadError(f"upload_sign 响应缺少凭证字段: {data}")
    return {
        "access_key_id": access_key_id,
        "secret_access_key": secret_key,
        "session_token": session_token,
        "space_name": namespace,
    }


def _load_static_credentials() -> Optional[Dict[str, str]]:
    """允许通过环境变量直接注入 upload_sign 凭证（便于调试）。"""
    ak = os.getenv("JIANYING_VOD_ACCESS_KEY_ID", "").strip()
    sk = os.getenv("JIANYING_VOD_SECRET_ACCESS_KEY", "").strip()
    token = os.getenv("JIANYING_VOD_SESSION_TOKEN", "").strip()
    if ak and sk and token:
        return {
            "access_key_id": ak,
            "secret_access_key": sk,
            "session_token": token,
            "space_name": os.getenv("JIANYING_VOD_SPACE_NAME", DEFAULT_SPACE_NAME),
        }
    return None


def apply_upload_inner(
    client: JianyingApiClient,
    creds: Dict[str, str],
    *,
    space_name: str = DEFAULT_SPACE_NAME,
    device_platform: str = "win",
) -> Dict[str, Any]:
    query = {
        "Action": "ApplyUploadInner",
        "SpaceName": space_name,
        "UseQuic": "false",
        "Version": "2020-11-19",
        "device_platform": device_platform,
    }
    host = "vod.bytedanceapi.com"
    sign_headers = _sign_v4_get(
        host=host,
        path="/top/v1",
        query=query,
        access_key_id=creds["access_key_id"],
        secret_access_key=creds["secret_access_key"],
        session_token=creds["session_token"],
    )
    resp = client.get_json(f"https://{host}/top/v1", params=query, headers=sign_headers)
    meta = resp.get("ResponseMetadata") or {}
    if meta.get("Error"):
        raise VodUploadError(f"ApplyUploadInner 失败: {meta['Error']}")
    return resp["Result"]


def upload_file_to_tos(
    client: JianyingApiClient,
    apply_result: Dict[str, Any],
    file_path: str,
) -> str:
    inner = apply_result.get("InnerUploadAddress") or {}
    nodes = inner.get("UploadNodes") or []
    if not nodes:
        raise VodUploadError("ApplyUploadInner 未返回 UploadNodes")
    node = nodes[0]
    store_infos = node.get("StoreInfos") or []
    if not store_infos:
        raise VodUploadError("ApplyUploadInner 未返回 StoreInfos")
    store = store_infos[0]
    store_uri = store["StoreUri"]
    auth = store["Auth"]
    upload_id = store["UploadID"]
    upload_host = node.get("UploadHost") or inner.get("UploadHost") or "tos-d-x-lf.douyin.com"

    with open(file_path, "rb") as f:
        payload = f.read()
    part_crc32 = f"{binascii.crc32(payload) & 0xFFFFFFFF:08x}"

    transfer_url = (
        f"https://{upload_host}/upload/v1/{store_uri}"
        f"?uploadid={upload_id}&part_number=0&phase=transfer"
    )
    transfer_headers = {
        "Authorization": auth,
        "Content-Type": "application/octet-stream",
        "X-Upload-Content-CRC32": part_crc32,
    }
    transfer_resp = client.post_raw(transfer_url, payload, headers=transfer_headers)
    if transfer_resp.status_code >= 400:
        raise VodUploadError(f"TOS transfer 失败: {transfer_resp.status_code} {transfer_resp.text[:300]}")
    try:
        transfer_data = transfer_resp.json()
        if transfer_data.get("code") != 2000:
            raise VodUploadError(f"TOS transfer 失败: {transfer_data}")
    except VodUploadError:
        raise
    except Exception:
        pass

    finish_url = (
        f"https://{upload_host}/upload/v1/{store_uri}"
        f"?uploadmode=part&phase=finish&uploadid={upload_id}"
    )
    finish_resp = client.post_raw(
        finish_url,
        f"0:{part_crc32}".encode(),
        headers={"Authorization": auth},
    )
    if finish_resp.status_code >= 400:
        raise VodUploadError(f"TOS finish 失败: {finish_resp.status_code} {finish_resp.text[:300]}")
    try:
        finish_data = finish_resp.json()
        if finish_data.get("code") != 2000:
            raise VodUploadError(f"TOS finish 失败: {finish_data}")
    except VodUploadError:
        raise
    except Exception:
        pass

    return store_uri


def commit_upload_inner(
    client: JianyingApiClient,
    creds: Dict[str, str],
    *,
    session_key: str,
    store_uri: str,
    space_name: str = DEFAULT_SPACE_NAME,
    device_platform: str = "win",
) -> Dict[str, Any]:
    query = {
        "Action": "CommitUploadInner",
        "SpaceName": space_name,
        "Version": "2020-11-19",
        "device_platform": device_platform,
    }
    body_obj = {
        "Functions": [{"Input": {"SnapshotTime": 0.0}, "Name": "Snapshot"}],
        "SessionKey": session_key,
        "SuccessOids": [store_uri],
    }
    import json

    body = json.dumps(body_obj, separators=(",", ":"))
    host = "vod.bytedanceapi.com"
    sign_headers = _sign_v4_post_json(
        host=host,
        path="/top/v1",
        query=query,
        body=body,
        access_key_id=creds["access_key_id"],
        secret_access_key=creds["secret_access_key"],
        session_token=creds["session_token"],
    )
    resp = client.session.post(
        DEFAULT_VOD_BASE,
        params=query,
        data=body,
        headers=sign_headers,
        timeout=60,
        verify=client.verify_ssl,
    )
    resp.raise_for_status()
    data = resp.json()
    meta = data.get("ResponseMetadata") or {}
    if meta.get("Error"):
        raise VodUploadError(f"CommitUploadInner 失败: {meta['Error']}")
    return data.get("Result") or {}


def upload_audio_for_recognition(
    client: JianyingApiClient,
    file_path: str,
    *,
    space_name: str = DEFAULT_SPACE_NAME,
) -> str:
    """上传本地音频到 VOD，返回 TOS StoreUri。"""
    creds = _load_static_credentials() or fetch_upload_credentials(client, space_name=space_name)
    apply_result = apply_upload_inner(client, creds, space_name=space_name)
    inner = apply_result.get("InnerUploadAddress") or {}
    nodes = inner.get("UploadNodes") or []
    if not nodes:
        raise VodUploadError("ApplyUploadInner 未返回 UploadNodes")
    session_key = nodes[0].get("SessionKey")
    if not session_key:
        raise VodUploadError("ApplyUploadInner 未返回 SessionKey")
    store_uri = upload_file_to_tos(client, apply_result, file_path)
    commit_upload_inner(
        client,
        creds,
        session_key=session_key,
        store_uri=store_uri,
        space_name=space_name,
    )
    return store_uri
