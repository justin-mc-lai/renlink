"""Fixed error codes and the shared failure envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ErrorSpec:
    http_status: int
    retryable: bool
    message: str


ERROR_SPECS: Dict[str, ErrorSpec] = {
    "INVALID_URL": ErrorSpec(400, False, "url 为空、不是 http(s) 链接或长度超过 2048"),
    "INVALID_REQUEST": ErrorSpec(400, False, "请求体不合法，或请求体包含 cookie 字段"),
    "UNSUPPORTED_PLATFORM": ErrorSpec(400, False, "只支持抖音与小红书链接"),
    "SHORTLINK_FAIL": ErrorSpec(422, True, "短链 3 次重定向后仍未到达规范页"),
    "COOKIE_EXPIRED": ErrorSpec(503, True, "运营方 cookie 失效，请运营刷新后重试"),
    "PARSE_FAILED": ErrorSpec(502, True, "页面结构变化，找不到媒体字段"),
    "TIMEOUT": ErrorSpec(504, True, "上游解析超过 12 秒"),
    "RATE_LIMITED": ErrorSpec(429, True, "单 IP 每分钟请求超过 20 次"),
}


class ApiError(Exception):
    """An error that maps to one fixed code in truth.md."""

    def __init__(self, code: str, message: Optional[str] = None) -> None:
        if code not in ERROR_SPECS:
            raise ValueError(f"unknown error code: {code}")
        self.code = code
        self.spec = ERROR_SPECS[code]
        self.message = message or self.spec.message
        super().__init__(self.message)

    @property
    def http_status(self) -> int:
        return self.spec.http_status

    @property
    def retryable(self) -> bool:
        return self.spec.retryable


def error_envelope(
    code: str,
    message: Optional[str] = None,
    elapsed_ms: int = 0,
    resolved_url: str = "",
) -> Dict[str, Any]:
    """Build the failure envelope shared by every 4xx/5xx response.

    resolved_url is always present (empty unless a shortlink was partially
    resolved) so TC-010 can assert it is the empty string.
    """
    spec = ERROR_SPECS[code]
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message or spec.message,
            "retryable": spec.retryable,
        },
        "items": [],
        "resolved_url": resolved_url,
        "elapsed_ms": int(elapsed_ms),
    }
