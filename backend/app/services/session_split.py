"""会话切割引擎：按超时阈值和跨天/跨渠道策略切割用户会话。"""
from __future__ import annotations

from typing import Any
from collections import defaultdict

from app.store import store
from app.schemas import SessionResult


def _generate_raw_events() -> list[dict[str, Any]]:
    """生成原始事件流用于会话切割。"""
    events = []
    base_time = 1700000000
    for user_idx in range(1, 51):  # 50个用户
        user_id = f"U{user_idx:05d}"
        device_id = f"D{user_idx % 10 + 1:03d}"
        # 每个用户生成3-8个事件
        num_events = 3 + (user_idx % 6)
        for ev_idx in range(num_events):
            # 模拟会话间隔：有时短（会话内），有时长（新会话）
            if ev_idx > 0 and user_idx % 7 == 0:
                # 长间隔，触发新会话
                offset = ev_idx * 3600 + 7200
            else:
                offset = ev_idx * 300  # 5分钟间隔，同一会话
            events.append({
                "user_id": user_id,
                "device_id": device_id,
                "event_id": ["EV-001", "EV-002", "EV-003"][ev_idx % 3],
                "timestamp": base_time + user_idx * 10000 + offset,
                "channel": ["app", "web"][ev_idx % 2],
                "page_url": f"/page{ev_idx % 5 + 1}",
            })
    return sorted(events, key=lambda x: x["timestamp"])


def split_sessions(strategy_id: str) -> SessionResult:
    """执行会话切割。"""
    strategy = store.find_by_field("session_split", "strategy_id", strategy_id)
    if strategy is None:
        raise ValueError(f"Strategy not found: {strategy_id}")

    timeout_sec = strategy["timeout_sec"]
    cross_day_policy = strategy["cross_day_policy"]
    cross_channel_policy = strategy["cross_channel_policy"]
    session_key = strategy["session_key"]

    events = _generate_raw_events()

    # 按会话键分组
    keyed_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in events:
        key = e.get(session_key, e["user_id"])
        keyed_events[key].append(e)

    sessions: list[dict[str, Any]] = []
    total_events = len(events)

    for key, evts in keyed_events.items():
        evts.sort(key=lambda x: x["timestamp"])
        current_session: list[dict[str, Any]] = []
        session_start = evts[0]["timestamp"] if evts else 0

        for i, evt in enumerate(evts):
            if not current_session:
                current_session = [evt]
                session_start = evt["timestamp"]
                continue

            prev = current_session[-1]
            time_diff = evt["timestamp"] - prev["timestamp"]

            # 超时检查
            should_split = time_diff > timeout_sec

            # 跨天检查
            if not should_split and cross_day_policy == "split":
                prev_day = prev["timestamp"] // 86400
                curr_day = evt["timestamp"] // 86400
                if prev_day != curr_day:
                    should_split = True

            # 跨渠道检查
            if not should_split and cross_channel_policy == "split":
                if prev.get("channel") != evt.get("channel"):
                    should_split = True

            if should_split:
                # 保存当前会话
                sessions.append({
                    "session_key": key,
                    "events": [dict(e) for e in current_session],
                    "event_count": len(current_session),
                    "start_time": session_start,
                    "end_time": prev["timestamp"],
                    "duration": prev["timestamp"] - session_start,
                })
                current_session = [evt]
                session_start = evt["timestamp"]
            else:
                current_session.append(evt)

        # 保存最后一个会话
        if current_session:
            sessions.append({
                "session_key": key,
                "events": [dict(e) for e in current_session],
                "event_count": len(current_session),
                "start_time": session_start,
                "end_time": current_session[-1]["timestamp"],
                "duration": current_session[-1]["timestamp"] - session_start,
            })

    # 计算统计
    avg_duration = sum(s["duration"] for s in sessions) / len(sessions) if sessions else 0

    result = SessionResult(
        strategy_id=strategy_id,
        total_events=total_events,
        session_count=len(sessions),
        avg_session_duration=round(avg_duration, 2),
        sessions=sessions[:20],  # 只返回前20个会话
    )

    # 存储产物
    store.set_artifact("session_split", strategy_id, result.model_dump())

    # 更新状态
    store.update("session_split", strategy["id"], {
        "status": "已完成",
        "pending": False,
    })

    return result


def get_session_result(strategy_id: str) -> dict[str, Any] | None:
    """获取会话切割结果。"""
    artifact = store.get_artifact("session_split", strategy_id)
    if artifact:
        return artifact
    try:
        result = split_sessions(strategy_id)
        return result.model_dump()
    except ValueError:
        return None


def resegment_with_strategy(strategy_id: str, new_timeout: int | None = None) -> SessionResult:
    """使用新参数重新切割会话。"""
    strategy = store.find_by_field("session_split", "strategy_id", strategy_id)
    if strategy is None:
        raise ValueError(f"Strategy not found: {strategy_id}")

    if new_timeout is not None:
        store.update("session_split", strategy["id"], {"timeout_sec": new_timeout})
        store.invalidate_compute_cache(f"session_split:{strategy_id}")

    return split_sessions(strategy_id)
