"""Hàng đợi có trần cho luồng tiếng: đầy thì bỏ khúc CŨ NHẤT, luôn giữ tiếng mới nhất và dấu kết thúc.

Quy tắc tài nguyên của kho (docs/QUY-TAC-TAI-NGUYEN.md): hàng đợi KHÔNG BAO GIỜ không có trần. Tiếng PCM đẩy tới liên tục;
nếu kênh nói tới camera tắc mà bên đẩy vẫn đẩy thì hàng đợi không trần phình dần và làm Home Assistant đầy RAM."""

from __future__ import annotations

import asyncio
from typing import Any

#: Số khúc tối đa còn chờ gửi tới camera (mỗi khúc cỡ vài chục mili giây): đủ chịu giật mạng vài giây, không hơn.
NOI_QUEUE_TOI_DA_KHUC = 400


def day_bo_cu_nhat(hang: "asyncio.Queue[Any]", muc: Any) -> bool:
    """Đẩy ``muc`` vào ``hang``; đầy thì bỏ phần tử cũ nhất trước. Trả True nếu phải bỏ khúc cũ."""
    da_bo = False
    while hang.full():
        try:
            hang.get_nowait()
        except asyncio.QueueEmpty:
            break
        da_bo = True
    hang.put_nowait(muc)
    return da_bo
