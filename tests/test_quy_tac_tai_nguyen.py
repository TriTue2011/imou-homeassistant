"""Quy tắc tài nguyên (docs/QUY-TAC-TAI-NGUYEN.md): canh bằng AST để không tái phạm."""
import ast
import asyncio
from pathlib import Path

from custom_components.dahua_talk.hang_doi import NOI_QUEUE_TOI_DA_KHUC, day_bo_cu_nhat

GOC = Path(__file__).resolve().parents[1] / "custom_components" / "dahua_talk"
TEP = sorted(GOC.glob("*.py"))


def _ten(n):
    if isinstance(n, ast.Attribute):
        return f"{_ten(n.value)}.{n.attr}"
    return n.id if isinstance(n, ast.Name) else ""


def test_hang_doi_luon_co_tran():
    loi = []
    for p in TEP:
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and _ten(n.func) == "asyncio.Queue":
                if not n.args and not any(k.arg == "maxsize" for k in n.keywords):
                    loi.append(f"{p.name}:{n.lineno}")
    assert not loi, f"asyncio.Queue() không trần (dùng maxsize + hang_doi.day_bo_cu_nhat): {loi}"


def test_khong_chan_vong_lap_trong_ma_bat_dong_bo():
    """Không ``requests``/``urllib.request`` và không ``subprocess.run`` ở bất kỳ đâu; ``time.sleep`` chỉ trong hàm ĐỒNG BỘ
    (chạy ở luồng riêng của hik_talk/rtsp_talk/http_talk), không trong ``async def``."""
    loi = []
    for p in TEP:
        cay = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(cay):
            if isinstance(n, ast.Call) and _ten(n.func) in {"subprocess.run", "subprocess.call", "subprocess.check_output"}:
                loi.append(f"{p.name}:{n.lineno} {_ten(n.func)}")
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                ten = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
                if any(t.split(".")[0] == "requests" or t == "urllib.request" for t in ten):
                    loi.append(f"{p.name}:{n.lineno} import chặn")
            if isinstance(n, ast.AsyncFunctionDef):
                for m in ast.walk(n):
                    if isinstance(m, ast.Call) and _ten(m.func) == "time.sleep":
                        loi.append(f"{p.name}:{m.lineno} time.sleep trong async def {n.name}")
    assert not loi, f"gọi chặn: {loi}"


def test_day_bo_cu_nhat_giu_moi_nhat_va_dau_ket_thuc():
    q = asyncio.Queue(maxsize=3)
    bo = [day_bo_cu_nhat(q, i) for i in range(6)]
    assert bo == [False, False, False, True, True, True]
    assert [q.get_nowait() for _ in range(3)] == [3, 4, 5]
    for i in range(3):
        day_bo_cu_nhat(q, i)
    day_bo_cu_nhat(q, None)
    assert q.qsize() == 3 and [q.get_nowait() for _ in range(3)][-1] is None


def test_hang_noi_khong_phinh_khi_kenh_tac():
    q = asyncio.Queue(maxsize=NOI_QUEUE_TOI_DA_KHUC)
    for i in range(NOI_QUEUE_TOI_DA_KHUC * 5):
        day_bo_cu_nhat(q, (float(i), b"x" * 1920))
    assert q.qsize() == NOI_QUEUE_TOI_DA_KHUC
