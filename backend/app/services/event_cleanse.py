"""事件清洗引擎：校验事件数据，执行去重和异常处理。"""
from __future__ import annotations

from typing import Any
from collections import defaultdict

from app.store import store
from app.schemas import CleanseResult


def _generate_raw_event_data(event_id: str, count: int) -> list[dict[str, Any]]:
    """生成原始事件数据用于清洗。"""
    events = []
    base_time = 1700000000
    for i in range(1, count + 1):
        user_id = f"U{i:05d}"
        # 模拟部分异常数据
        is_bot = i % 20 == 0
        is_dup = i % 15 == 0
        is_invalid = i % 25 == 0

        events.append({
            "user_id": user_id,
            "event_id": event_id,
            "timestamp": base_time + i * 60,
            "page_url": "" if is_invalid else f"/page{i % 10}",
            "item_id": -1 if is_invalid else i,
            "amount": -10.0 if is_invalid else float(i * 5.5),
            "is_bot": is_bot,
            "is_dup": is_dup,
        })
        if is_dup:
            # 插入重复数据
            events.append({
                "user_id": user_id,
                "event_id": event_id,
                "timestamp": base_time + i * 60,
                "page_url": f"/page{i % 10}",
                "item_id": i,
                "amount": float(i * 5.5),
                "is_bot": False,
                "is_dup": True,
            })
    return events


def cleanse_events(rule_id: str) -> CleanseResult:
    """执行事件清洗。"""
    rule = store.find_by_field("event_cleanse", "rule_id", rule_id)
    if rule is None:
        raise ValueError(f"Cleanse rule not found: {rule_id}")

    event_id = rule["event_id"]
    check_fields = rule.get("check_fields", [])
    valid_range = rule.get("valid_range", {})
    anomaly_action = rule["anomaly_action"]
    bot_detect = rule.get("bot_detect", False)
    dedup_window = rule.get("dedup_window", 0)

    # 获取原始事件数据
    events = _generate_raw_event_data(event_id, 500)

    total_records = len(events)
    valid_records = 0
    invalid_records = 0
    deduped_records = 0

    # 去重窗口
    seen: set[tuple[str, ...]] = set()
    cleansed: list[dict[str, Any]] = []

    for evt in events:
        # 刷量检测
        if bot_detect and evt.get("is_bot"):
            invalid_records += 1
            if anomaly_action == "discard":
                continue
            elif anomaly_action == "quarantine":
                evt["quarantined"] = True
            else:  # flag
                evt["flagged"] = True

        # 字段校验
        is_invalid = False
        for field in check_fields:
            val = evt.get(field)
            if val is None or val == "":
                is_invalid = True
                break
            # 范围校验
            if field in valid_range:
                range_cfg = valid_range[field]
                if "min" in range_cfg:
                    try:
                        if float(val) < float(range_cfg["min"]):
                            is_invalid = True
                            break
                    except (ValueError, TypeError):
                        pass
                if "max" in range_cfg:
                    try:
                        if float(val) > float(range_cfg["max"]):
                            is_invalid = True
                            break
                    except (ValueError, TypeError):
                        pass

        if is_invalid:
            invalid_records += 1
            if anomaly_action == "discard":
                continue
            elif anomaly_action == "quarantine":
                evt["quarantined"] = True
            else:
                evt["flagged"] = True

        # 去重
        if dedup_window > 0:
            dup_key = tuple(str(evt.get(f, "")) for f in ["user_id", "event_id", "timestamp"])
            if dup_key in seen:
                deduped_records += 1
                continue
            seen.add(dup_key)

        cleansed.append(evt)
        valid_records += 1

    result = CleanseResult(
        rule_id=rule_id,
        event_id=event_id,
        total_records=total_records,
        valid_records=valid_records,
        invalid_records=invalid_records,
        deduped_records=deduped_records,
        output_table=f"cleansed_{event_id}",
        snapshot_path=f"/data/cleansed/{rule_id}.parquet",
    )

    # 存储产物
    store.set_artifact("event_cleanse", rule_id, result.model_dump())

    # 更新状态
    store.update("event_cleanse", rule["id"], {
        "status": "已生效",
        "pending": False,
    })

    return result


def get_cleanse_result(rule_id: str) -> dict[str, Any] | None:
    """获取清洗结果。"""
    artifact = store.get_artifact("event_cleanse", rule_id)
    if artifact:
        return artifact
    try:
        result = cleanse_events(rule_id)
        return result.model_dump()
    except ValueError:
        return None
