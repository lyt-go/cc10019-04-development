"""用户分群路由：执行分群计算并获取结果。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ActionPayload, ActionResult
from app.services.user_segment import compute_segment, get_segment_result
from app.store import store, query_filters

router = APIRouter(prefix="/api/user-segment", tags=["user_segment"])


@router.get("")
def index(request: Request, page: int = 1, size: int = 20) -> dict[str, Any]:
    rows = store.rows("user_segment")
    filters=query_filters(request)
    if filters:
        rows = [r for r in rows if all(str(r.get(k)) == str(v) for k, v in filters.items())]
    total = len(rows)
    start = (page - 1) * size
    return {"items": rows[start : start + size], "total": total, "page": page, "size": size}


@router.get("/{entry_id}")
def detail(entry_id: int) -> dict[str, Any]:
    row = store.find("user_segment", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.post("/{segment_id}/run")
def run(segment_id: str) -> ActionResult:
    try:
        result = compute_segment(segment_id)
        return ActionResult(ok=True, message="Computed", entry=result.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{segment_id}/result")
def result(segment_id: str) -> dict[str, Any]:
    res = get_segment_result(segment_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return res


@router.post("/{entry_id}/actions")
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    row = store.find("user_segment", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    action = payload.action
    row["status"] = action
    row["pending"] = False
    return ActionResult(ok=True, message=action, entry=row)
