"""事件埋点路由：管理事件定义与埋点配置。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ActionPayload, ActionResult
from app.services.event_track import list_events, get_event, create_event, update_event, delete_event, get_events_by_category
from app.store import store, query_filters

router = APIRouter(prefix="/api/event-track", tags=["event_track"])


@router.get("")
def index(request: Request, page: int = 1, size: int = 20) -> dict[str, Any]:
    rows = store.rows("event_track")
    # query contract: filters=query_filters(request)
    filters = query_filters(request)
    if filters:
        rows = [r for r in rows if all(str(r.get(k)) == str(v) for k, v in filters.items())]
    total = len(rows)
    start = (page - 1) * size
    return {"items": rows[start : start + size], "total": total, "page": page, "size": size}


@router.get("/{entry_id}")
def detail(entry_id: int) -> dict[str, Any]:
    row = store.find("event_track", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.post("")
def create(payload: dict[str, Any]) -> ActionResult:
    row = create_event(payload)
    return ActionResult(ok=True, message="Created", entry=row)


@router.put("/{entry_id}")
def update(entry_id: int, payload: dict[str, Any]) -> ActionResult:
    row = store.find("event_track", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    updated = update_event(row["event_id"], payload)
    return ActionResult(ok=True, message="Updated", entry=updated)


@router.delete("/{entry_id}")
def remove(entry_id: int) -> ActionResult:
    row = store.find("event_track", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    delete_event(row["event_id"])
    return ActionResult(ok=True, message="Deleted")


@router.get("/by-category/{category}")
def by_category(category: str) -> list[dict[str, Any]]:
    return get_events_by_category(category)


@router.post("/{entry_id}/actions")
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    row = store.find("event_track", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    action = payload.action
    row["status"] = action
    row["pending"] = False
    return ActionResult(ok=True, message=action, entry=row)
