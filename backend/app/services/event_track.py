"""事件埋点服务：管理事件定义与埋点配置。"""
from __future__ import annotations

from typing import Any

from app.store import store


def list_events() -> list[dict[str, Any]]:
    """列出所有事件定义。"""
    return store.rows("event_track")


def get_event(event_id: str) -> dict[str, Any] | None:
    """获取单个事件定义。"""
    return store.find_by_field("event_track", "event_id", event_id)


def create_event(data: dict[str, Any]) -> dict[str, Any]:
    """创建事件定义。"""
    row = store.insert("event_track", data)
    return row


def update_event(event_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """更新事件定义。"""
    event = store.find_by_field("event_track", "event_id", event_id)
    if event is None:
        return None
    return store.update("event_track", event["id"], updates)


def delete_event(event_id: str) -> bool:
    """删除事件定义。"""
    event = store.find_by_field("event_track", "event_id", event_id)
    if event is None:
        return False
    return store.delete("event_track", event["id"])


def get_events_by_category(category: str) -> list[dict[str, Any]]:
    """按分类筛选事件。"""
    return store.find_all_by_field("event_track", "category", category)
