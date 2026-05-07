"""自定义 JSON 响应，修复 MySQL DATETIME 无时区问题

MySQL 的 DATETIME 列不保存时区信息。Pydantic 的 model_dump(mode="json")
输出无 'Z' 后缀的 ISO 字符串（如 2026-05-07T02:00:00），
前端 new Date() 将其解析为本地时间（UTC+8），与 Date.now()（UTC 毫秒）
比较时产生 8 小时偏差。

本模块提供 UtcJsonResponse，在 JSON 序列化后自动为无时区 datetime 字符串追加 'Z'。
"""

import json
import re
from typing import Any

from starlette.responses import JSONResponse

# 匹配 ISO 8601 无时区的日期时间字符串（如 2026-05-07T02:00:00 或带微秒）
_NAIVE_DT_RE = re.compile(r'"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)"')


def _add_utc_suffix(match: re.Match) -> str:
    """为匹配的 datetime 字符串追加 Z"""
    return f'"{match.group(1)}Z"'


class UtcJsonResponse(JSONResponse):
    """自动为无时区 datetime 追加 'Z' 的 JSON 响应

    在 JSON 序列化完成后，通过正则替换为所有无时区 datetime 字符串追加 UTC 标记。
    已有时区信息的字符串（含 +、-、Z）不会被修改。
    """

    def render(self, content: Any) -> bytes:
        raw = super().render(content)
        # 只处理包含 T 的字符串（datetime 特征），避免误匹配纯数字
        if b"T" in raw:
            text = raw.decode("utf-8")
            text = _NAIVE_DT_RE.sub(_add_utc_suffix, text)
            return text.encode("utf-8")
        return raw
