"""标签定义服务：管理标签规则的定义与元数据。"""
from __future__ import annotations

from typing import Any

from app.store import store


def list_tags() -> list[dict[str, Any]]:
    """列出所有标签定义。"""
    return store.rows("tag_define")


def get_tag(tag_id: str) -> dict[str, Any] | None:
    """获取单个标签定义。"""
    return store.find_by_field("tag_define", "tag_id", tag_id)


def create_tag(data: dict[str, Any]) -> dict[str, Any]:
    """创建标签定义。"""
    row = store.insert("tag_define", data)
    return row


def update_tag(tag_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """更新标签定义。"""
    tag = store.find_by_field("tag_define", "tag_id", tag_id)
    if tag is None:
        return None
    return store.update("tag_define", tag["id"], updates)


def delete_tag(tag_id: str) -> bool:
    """删除标签定义。"""
    tag = store.find_by_field("tag_define", "tag_id", tag_id)
    if tag is None:
        return False
    return store.delete("tag_define", tag["id"])


def get_tags_by_level(level: str) -> list[dict[str, Any]]:
    """按层级筛选标签。"""
    return store.find_all_by_field("tag_define", "tag_level", level)


def validate_tag_logic(tag_id: str) -> dict[str, Any]:
    """校验标签计算逻辑是否引用了有效的属性。"""
    tag = get_tag(tag_id)
    if tag is None:
        return {"valid": False, "error": "Tag not found"}

    source_attrs = tag.get("source_attrs", [])
    missing = []
    for attr_id in source_attrs:
        attr = store.find_by_field("attr_dict", "attr_id", attr_id)
        if attr is None:
            missing.append(attr_id)

    return {
        "tag_id": tag_id,
        "valid": len(missing) == 0,
        "missing_attrs": missing,
        "source_attrs": source_attrs,
    }
