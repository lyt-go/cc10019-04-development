"""属性字典服务：管理用户属性字段的元数据定义。"""
from __future__ import annotations

from typing import Any

from app.store import store


def list_attrs() -> list[dict[str, Any]]:
    """列出所有属性定义。"""
    return store.rows("attr_dict")


def get_attr(attr_id: str) -> dict[str, Any] | None:
    """获取单个属性定义。"""
    return store.find_by_field("attr_dict", "attr_id", attr_id)


def create_attr(data: dict[str, Any]) -> dict[str, Any]:
    """创建属性定义。"""
    row = store.insert("attr_dict", data)
    return row


def update_attr(attr_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """更新属性定义。"""
    attr = store.find_by_field("attr_dict", "attr_id", attr_id)
    if attr is None:
        return None
    return store.update("attr_dict", attr["id"], updates)


def delete_attr(attr_id: str) -> bool:
    """删除属性定义。"""
    attr = store.find_by_field("attr_dict", "attr_id", attr_id)
    if attr is None:
        return False
    return store.delete("attr_dict", attr["id"])


def get_attrs_by_source(source: str) -> list[dict[str, Any]]:
    """按数据来源筛选属性。"""
    return store.find_all_by_field("attr_dict", "source", source)
