"""漏斗分析路由：执行漏斗计算并获取结果。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ActionPayload, ActionResult
from app.services.funnel_analyze import analyze_funnel, get_funnel_result, compare_funnels
from app.store import store

router = APIRouter(prefix="/api/funnel-analyze", tags=["funnel_analyze"])


@router.get("")
def index(page: int = 1, size: int = 20) -> dict[str, Any]:
    rows = store.rows("funnel_analyze")
    total = len(rows)
    start = (page - 1) * size
    return {"items": rows[start : start + size], "total": total, "page": page, "size": size}




@router.get("/export")
def export_entries() -> dict[str, Any]:
    rows = store.rows("funnel_analyze")
    return {"items": rows, "total": len(rows)}
@router.get("/{entry_id}")
def detail(entry_id: int) -> dict[str, Any]:
    row = store.find("funnel_analyze", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.post("/{funnel_id}/run")
def run(funnel_id: str) -> ActionResult:
    try:
        result = analyze_funnel(funnel_id)
        return ActionResult(ok=True, message="Analyzed", entry=result.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{funnel_id}/result")
def result(funnel_id: str) -> dict[str, Any]:
    res = get_funnel_result(funnel_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return res


@router.get("/compare/{funnel_id_a}/{funnel_id_b}")
def compare(funnel_id_a: str, funnel_id_b: str) -> dict[str, Any]:
    try:
        return compare_funnels(funnel_id_a, funnel_id_b)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{entry_id}/actions")
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    row = store.find("funnel_analyze", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    action = payload.action
    row["status"] = action
    row["pending"] = False
    return ActionResult(ok=True, message=action, entry=row)
