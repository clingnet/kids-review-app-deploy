"""异步分析队列。

上传后入队一个"批任务":**并行**提取该批所有图片(加速),全部提取完后跑一次
全局分析 + 薄弱点 + 掌握度快照,version++。批与批之间串行(避免并发重分析)。
前端用 GET /api/analysis/status 轮询 {running,pending,version}。
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("jobs")

# 外层单线程:让多次上传的"批任务"串行,保证重分析不并发
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
# 批内提取并行度
_EXTRACT_WORKERS = 4

_lock = threading.Lock()
_state = {"running": False, "pending": 0, "version": 0, "updated_at": None}


def status() -> dict:
    with _lock:
        return dict(_state)


def enqueue(material_ids: list[int]) -> None:
    ids = list(material_ids)
    with _lock:
        _state["pending"] += len(ids)
        _state["running"] = True
    _executor.submit(_batch_job, ids)


def _batch_job(ids: list[int]) -> None:
    from . import analyze, dashboard, extract
    from .. import db

    with _lock:
        _state["running"] = True
    mats = {m["id"]: m for m in db.list_materials()}

    def _do(mid: int) -> None:
        try:
            if mid in mats:
                extract.extract_material(mid, mats[mid]["path"])
        except Exception:  # noqa: BLE001
            log.exception("异步提取失败 material=%s", mid)
        finally:
            with _lock:
                _state["pending"] = max(0, _state["pending"] - 1)

    # 并行提取本批
    with ThreadPoolExecutor(max_workers=_EXTRACT_WORKERS) as pool:
        list(pool.map(_do, ids))

    # 提取完跑一次重分析
    try:
        analyze.run_global_analysis()
        analyze.run_weak_points()
        db.snapshot_overall(dashboard.overall_mastery())
        with _lock:
            _state["version"] += 1
            _state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _state["running"] = _state["pending"] > 0
        log.info("异步重分析完成 version=%s", _state["version"])
    except Exception:  # noqa: BLE001
        log.exception("异步重分析失败")
        with _lock:
            _state["running"] = _state["pending"] > 0
