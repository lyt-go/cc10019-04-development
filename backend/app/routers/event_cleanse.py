"""事件清洗路由：执行事件清洗并获取结果。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ActionPayload, ActionResult
from app.services.event_cleanse import cleanse_events, get_cleanse_result
from app.store import store, query_filters

router = APIRouter(prefix="/api/event-cleanse", tags=["event_cleanse"])


@router.get("")
def index(request: Request, page: int = 1, size: int = 20) -> dict[str, Any]:
    rows = store.rows("event_cleanse")
    filters=query_filters(request)
    if filters:
        rows = [r for r in rows if all(str(r.get(k)) == str(v) for k, v in filters.items())]
    total = len(rows)
    start = (page - 1) * size
    return {"items": rows[start : start + size], "total": total, "page": page, "size": size}


@router.get("/{entry_id}")
def detail(entry_id: int) -> dict[str, Any]:
    row = store.find("event_cleanse", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.post("/{rule_id}/run")
def run(rule_id: str) -> ActionResult:
    try:
        result = cleanse_events(rule_id)
        return ActionResult(ok=True, message="Cleansed", entry=result.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{rule_id}/result")
def result(rule_id: str) -> dict[str, Any]:
    res = get_cleanse_result(rule_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return res


@router.post("/{entry_id}/actions")
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    row = store.find("event_cleanse", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    action = payload.action
    row["status"] = action
    row["pending"] = False
    return ActionResult(ok=True, message=action, entry=row)
