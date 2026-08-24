#!/usr/bin/env python3
"""Report catalog, scoring, selection, and per-user launch health."""

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional
from zoneinfo import ZoneInfo

from .persona_digest import (
    WEEKDAYS,
    _matches_send_day,
    _parse_dt,
    select_persona_items_with_diagnostics,
)
from .personas import _load, persona_selection, validate_catalog


DROP_REASON_NAMES = {
    "below_min_topic_score": "score_threshold",
    "source_not_allowed": "source_filter",
    "send_day_mismatch": "send_day_mismatch",
    "missing_fetched_at": "missing_timestamp",
    "missing_published_at": "missing_timestamp",
    "outside_cadence_window": "outside_cadence_window",
}
RISK_ORDER = {
    "ok": 0,
    "not_scheduled": 1,
    "low": 2,
    "empty": 3,
    "stale_catalog": 4,
}
DEFAULT_STATE_DIR = Path.home() / "Library" / "Application Support" / "knowledge-os" / "cron"
DEFAULT_INGEST_LOG = Path.home() / "Library" / "Logs" / "knowledge-os-ingest.log"
DEFAULT_DELIVERY_LOG = Path.home() / "Library" / "Logs" / "knowledge-os-delivery.log"


def _catalog_stats(conn: sqlite3.Connection, requested_date: date) -> Dict:
    rows = conn.execute(
        """
        SELECT source, COALESCE(NULLIF(source_api, ''), 'unknown') AS source_api,
               COUNT(*) AS item_count
        FROM items
        GROUP BY source, COALESCE(NULLIF(source_api, ''), 'unknown')
        ORDER BY source, source_api
        """
    ).fetchall()
    by_source: Counter[str] = Counter()
    by_source_api: Counter[str] = Counter()
    source_api_rows = []
    for row in rows:
        count = int(row["item_count"])
        by_source[row["source"]] += count
        by_source_api[row["source_api"]] += count
        source_api_rows.append({
            "source": row["source"],
            "source_api": row["source_api"],
            "count": count,
        })

    latest_value = conn.execute("SELECT MAX(fetched_at) FROM items").fetchone()[0]
    latest = _parse_dt(latest_value or "")
    stale = latest is None or latest.date() < requested_date
    return {
        "total_items": sum(by_source.values()),
        "counts_by_source": dict(sorted(by_source.items())),
        "counts_by_source_api": dict(sorted(by_source_api.items())),
        "counts_by_source_and_api": source_api_rows,
        "latest_refresh_time": latest_value,
        "stale": stale,
        "status": "stale_catalog" if stale else "ok",
    }


def _scoring_stats(conn: sqlite3.Connection) -> Dict:
    rows = conn.execute(
        """
        SELECT t.name AS topic, COUNT(DISTINCT s.item_id) AS item_count
        FROM topics t
        LEFT JOIN item_topic_scores s ON s.topic_id = t.topic_id
        WHERE t.active = 1
        GROUP BY t.topic_id, t.name
        ORDER BY t.name
        """
    ).fetchall()
    counts = {row["topic"]: int(row["item_count"]) for row in rows}
    return {
        "total_scored_items": int(conn.execute(
            "SELECT COUNT(DISTINCT item_id) FROM item_topic_scores"
        ).fetchone()[0]),
        "counts_by_topic": counts,
    }


def _normalized_drop_reasons(raw_reasons: Dict[str, int]) -> Dict[str, int]:
    normalized: Counter[str] = Counter()
    for reason, count in raw_reasons.items():
        normalized[DROP_REASON_NAMES.get(reason, reason)] += count
    for reason in (
        "score_threshold",
        "source_filter",
        "send_day_mismatch",
        "missing_timestamp",
        "outside_cadence_window",
    ):
        normalized.setdefault(reason, 0)
    return dict(sorted(normalized.items()))


def _user_configs(users_dir: str, requested_users: Iterable[str]) -> Dict[str, Dict]:
    configs = {}
    for user_id in requested_users:
        path = Path(users_dir) / f"{user_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"User config not found: {path}")
        config = _load(str(path))
        configured_id = config.get("user", {}).get("identifier")
        if configured_id != user_id:
            raise ValueError(f"Expected user {user_id!r} in {path}, found {configured_id!r}")
        configs[user_id] = config
    return configs


def _parse_timestamp(value: Optional[str], default_timezone: Optional[ZoneInfo] = None) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    normalized = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", normalized)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None and default_timezone is not None:
        parsed = parsed.replace(tzinfo=default_timezone)
    return parsed


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _schedule_datetime(requested_date: date, schedule: Dict) -> Optional[datetime]:
    if not schedule:
        return None
    cadence = str(schedule.get("cadence", "daily")).lower()
    if cadence == "weekly":
        configured_days = schedule.get("days") or []
        weekdays = []
        for raw_day in configured_days:
            day_key = str(raw_day).strip().lower()
            if day_key not in WEEKDAYS:
                raise ValueError(f"Unsupported delivery day: {raw_day}")
            weekdays.append(WEEKDAYS[day_key])
        if weekdays and requested_date.weekday() not in weekdays:
            return None
    elif cadence != "daily":
        raise ValueError(f"Unsupported delivery cadence: {cadence}")
    schedule_time = time.fromisoformat(str(schedule.get("time", "")))
    schedule_zone = ZoneInfo(schedule["timezone"])
    return datetime.combine(requested_date, schedule_time, tzinfo=schedule_zone)


def _read_env_marker(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _ingest_start_from_log(path: Optional[str], requested_date: date, host_zone: ZoneInfo) -> Optional[datetime]:
    if not path or not Path(path).is_file():
        return None
    pattern = re.compile(
        rf"^\[{re.escape(requested_date.isoformat())} (\d{{2}}:\d{{2}}:\d{{2}})\] Initializing schema$"
    )
    found = None
    for line in Path(path).read_text(errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            found = datetime.combine(requested_date, time.fromisoformat(match.group(1)), tzinfo=host_zone)
    return found


def _scheduled_ingest(requested_date: date, host_zone: ZoneInfo) -> datetime:
    return datetime.combine(requested_date, time(9, 0), tzinfo=host_zone)


def _ingest_operations(
    requested_date: date,
    state_dir: Optional[str],
    ingest_log: Optional[str],
    host_zone: ZoneInfo,
    now: datetime,
) -> Dict:
    scheduled_at = _scheduled_ingest(requested_date, host_zone)
    marker_path = Path(state_dir) / f"ingest-{requested_date.isoformat()}.env" if state_dir else None
    marker = _read_env_marker(marker_path) if marker_path else {}
    started = _parse_timestamp(marker.get("started_at"), host_zone)
    source = "marker" if marker else "none"
    if started is None:
        started = _ingest_start_from_log(ingest_log, requested_date, host_zone)
        if started:
            source = "log" if not marker else "marker+log"
    completed = _parse_timestamp(marker.get("completed_at"), host_zone)
    status = marker.get("status") or ("succeeded" if completed else "missing")
    if status == "missing" and now < scheduled_at:
        status = "pending"

    trigger = marker.get("trigger")
    trigger_evidence = marker.get("trigger_evidence")
    if not trigger and started:
        offset_seconds = abs((started - scheduled_at).total_seconds())
        if offset_seconds <= 90:
            trigger = "automatic_inferred"
            trigger_evidence = "legacy log start matched the 09:00 cron schedule"
        else:
            trigger = "unknown"
            trigger_evidence = "legacy run predates provenance markers"
    elif not trigger:
        trigger = "unknown"
        trigger_evidence = "no run evidence"

    duration_seconds = None
    if started and completed:
        duration_seconds = max(0, int((completed - started).total_seconds()))
    return {
        "status": status,
        "scheduled_at": _iso(scheduled_at),
        "started_at": _iso(started),
        "completed_at": _iso(completed),
        "duration_seconds": duration_seconds,
        "trigger": trigger,
        "trigger_evidence": trigger_evidence,
        "evidence_source": source,
        "marker_path": str(marker_path) if marker_path else None,
        "website_workflow_status": marker.get("website_workflow_status"),
        "git_commit": marker.get("git_commit"),
    }


def _delivery_from_log(
    path: Optional[str],
    user_id: str,
    requested_date: date,
    host_zone: ZoneInfo,
) -> Optional[Dict]:
    if not path or not Path(path).is_file():
        return None
    lines = Path(path).read_text(errors="replace").splitlines()
    last_started: Optional[datetime] = None
    last_sender: Dict = {}
    matches = []
    timestamp_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\] Sending WhatsApp messages$")
    for index, line in enumerate(lines):
        timestamp_match = timestamp_pattern.match(line)
        if timestamp_match:
            last_started = datetime.combine(
                date.fromisoformat(timestamp_match.group(1)),
                time.fromisoformat(timestamp_match.group(2)),
                tzinfo=host_zone,
            )
            last_sender = {}
            continue
        if line.startswith("{") and '"ok":true' in line:
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                last_sender = parsed
            continue
        if line != f"user: {user_id}":
            continue
        fields = {}
        for detail in lines[index + 1:index + 9]:
            if ": " in detail:
                key, value = detail.split(": ", 1)
                fields[key] = value
        if fields.get("digest_path", "").endswith(f"/{requested_date.isoformat()}.md"):
            matches.append((last_started, dict(last_sender), fields))
    if not matches:
        return None
    started, sender, fields = matches[-1]
    receipt_status = sender.get("receiptStatus", "unknown")
    confirmed = receipt_status in {"delivery_ack", "read", "played"}
    sent_at = _parse_timestamp(sender.get("sentAt")) or started
    return {
        "status": "delivered" if confirmed else "sent_unconfirmed",
        "started_at": _iso(started),
        "sent_at": _iso(sent_at),
        "receipt_at": sender.get("receiptAt"),
        "receipt_status": receipt_status,
        "message_id": sender.get("messageId"),
        "trigger": "automatic_inferred",
        "trigger_evidence": "legacy delivery log matched a configured schedule",
        "item_count": int(fields.get("item_count", "0")),
        "evidence_source": "log",
        "timestamp_precision": "exact" if sender.get("sentAt") else "attempt_start_estimate",
    }


def _delivery_operation(
    user_id: str,
    config: Dict,
    requested_date: date,
    state_dir: Optional[str],
    delivery_log: Optional[str],
    host_zone: ZoneInfo,
    now: datetime,
) -> Dict:
    schedule = config.get("delivery", {}).get("schedule", {})
    scheduled_at = _schedule_datetime(requested_date, schedule) if schedule else None
    marker_path = Path(state_dir) / f"delivery-{requested_date.isoformat()}-{user_id}.json" if state_dir else None
    marker = {}
    if marker_path and marker_path.is_file():
        try:
            marker = json.loads(marker_path.read_text())
        except (json.JSONDecodeError, OSError):
            marker = {"status": "invalid_marker"}
        if not isinstance(marker, dict):
            marker = {"status": "invalid_marker"}

    if marker:
        evidence = dict(marker)
        evidence["evidence_source"] = "marker"
        evidence["marker_path"] = str(marker_path)
        has_evidence = True
    else:
        evidence = _delivery_from_log(delivery_log, user_id, requested_date, host_zone) or {}
        has_evidence = bool(evidence)
        evidence["marker_path"] = str(marker_path) if marker_path else None

    if has_evidence and evidence.get("evidence_source") == "log" and scheduled_at:
        logged_start = _parse_timestamp(evidence.get("started_at"), host_zone)
        if not logged_start or abs((logged_start - scheduled_at.astimezone(host_zone)).total_seconds()) > 90:
            evidence["trigger"] = "unknown"
            evidence["trigger_evidence"] = "legacy log has no explicit provenance marker"

    if not schedule:
        status = evidence.get("status", "schedule_not_configured")
    elif scheduled_at is None:
        status = evidence.get("status", "not_scheduled")
    elif has_evidence:
        status = evidence.get("status", "unknown")
    elif now < scheduled_at.astimezone(now.tzinfo or timezone.utc):
        status = "pending"
    else:
        status = "missing"
    evidence["status"] = status
    evidence["scheduled_at"] = _iso(scheduled_at)
    evidence["scheduled_at_host"] = _iso(scheduled_at.astimezone(host_zone)) if scheduled_at else None
    evidence["schedule"] = schedule or None
    return evidence


def _operations_status(ingest: Dict, users: Dict[str, Dict]) -> str:
    issue_statuses = {"failed", "missing", "invalid_marker"}
    delivery_statuses = [user.get("delivery", {}).get("status") for user in users.values()]
    if ingest.get("status") in issue_statuses or any(status in issue_statuses for status in delivery_statuses):
        return "issues"
    if ingest.get("status") == "pending" or any(status in {"pending", "sending"} for status in delivery_statuses):
        return "pending"
    if any(status in {"sent_unconfirmed", "unknown", "schedule_not_configured"} for status in delivery_statuses):
        return "warnings"
    return "ok"


def _user_health(
    catalog: Dict,
    configs: Dict[str, Dict],
    selected_by_persona: Counter[str],
    requested_date: date,
    catalog_stale: bool,
) -> Dict[str, Dict]:
    result = {}
    personas = catalog.get("personas", {})
    for user_id, config in configs.items():
        subscribed = config.get("user", {}).get("personas", [])
        unknown = [persona_id for persona_id in subscribed if persona_id not in personas]
        if unknown:
            raise ValueError(f"User {user_id!r} has unknown personas: {', '.join(unknown)}")
        scheduled = [
            persona_id
            for persona_id in subscribed
            if _matches_send_day(persona_selection(personas[persona_id]), requested_date)
        ]
        selected_count = sum(selected_by_persona[persona_id] for persona_id in subscribed)
        if not scheduled:
            status = "not_scheduled"
        elif catalog_stale:
            status = "stale_catalog"
        elif selected_count == 0:
            status = "empty"
        elif selected_count == 1:
            status = "low"
        else:
            status = "ok"
        result[user_id] = {
            "subscribed_personas": subscribed,
            "scheduled_personas": scheduled,
            "selected_count": selected_count,
            "empty_digest_risk": bool(scheduled and selected_count == 0),
            "status": status,
        }
    return result


def build_launch_health(
    db_path: str,
    catalog_path: str,
    users_dir: str,
    users: Iterable[str],
    requested_date: date,
    state_dir: Optional[str] = None,
    ingest_log: Optional[str] = None,
    delivery_log: Optional[str] = None,
    operations_timezone: str = "Asia/Kolkata",
    now: Optional[datetime] = None,
) -> Dict:
    """Build a JSON-serializable launch health report."""
    catalog = _load(catalog_path)
    validate_catalog(catalog)
    configs = _user_configs(users_dir, users)
    selection_result = select_persona_items_with_diagnostics(
        db_path, catalog_path, today=requested_date
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        catalog_stats = _catalog_stats(conn, requested_date)
        scoring_stats = _scoring_stats(conn)
    finally:
        conn.close()

    diagnostics = selection_result.diagnostics
    selected_by_persona = Counter(candidate.persona_id for candidate in selection_result.selected)
    user_stats = _user_health(
        catalog,
        configs,
        selected_by_persona,
        requested_date,
        catalog_stats["stale"],
    )
    host_zone = ZoneInfo(operations_timezone)
    effective_now = now or datetime.now(timezone.utc)
    ingest_operations = _ingest_operations(
        requested_date, state_dir, ingest_log, host_zone, effective_now
    )
    for user_id, config in configs.items():
        user_stats[user_id]["delivery"] = _delivery_operation(
            user_id,
            config,
            requested_date,
            state_dir,
            delivery_log,
            host_zone,
            effective_now,
        )
    statuses = [entry["status"] for entry in user_stats.values()]
    overall_status = (
        "stale_catalog"
        if catalog_stats["stale"]
        else max(statuses, key=lambda status: RISK_ORDER[status]) if statuses else "ok"
    )
    return {
        "request": {
            "date": requested_date.isoformat(),
            "db": db_path,
            "catalog": catalog_path,
            "users_dir": users_dir,
            "users": list(configs),
        },
        "status": overall_status,
        "operational_status": _operations_status(ingest_operations, user_stats),
        "operations": {
            "timezone": operations_timezone,
            "state_dir": state_dir,
            "ingest": ingest_operations,
        },
        "catalog": catalog_stats,
        "scoring": scoring_stats,
        "selection": {
            "scored_rows": diagnostics.scored_rows,
            "unknown_topic_rows": diagnostics.unknown_topic_rows,
            "candidates_before_filters": diagnostics.candidates_before_filters,
            "candidates_after_filters": diagnostics.candidates_after_filters,
            "candidates_after_dedupe": diagnostics.candidates_after_dedupe,
            "selected_count": diagnostics.selected_count,
            "drop_reasons": _normalized_drop_reasons(diagnostics.drop_reasons),
            "selected_by_persona": diagnostics.selected_by_persona,
        },
        "users": user_stats,
    }


def render_text(report: Dict) -> str:
    catalog = report["catalog"]
    scoring = report["scoring"]
    selection = report["selection"]
    ingest = report["operations"]["ingest"]
    lines = [
        f"Launch health: {report['status']} ({report['request']['date']})",
        f"Operational status: {report['operational_status']}",
        (
            "Ingest: "
            f"{ingest['status']}; scheduled={ingest['scheduled_at'] or 'unknown'}; "
            f"started={ingest['started_at'] or 'unknown'}; completed={ingest['completed_at'] or 'unknown'}; "
            f"duration={ingest['duration_seconds'] if ingest['duration_seconds'] is not None else 'unknown'}s; "
            f"trigger={ingest['trigger']} ({ingest['trigger_evidence']}); "
            f"website_workflow={ingest['website_workflow_status'] or 'unknown'}"
        ),
        f"Catalog: {catalog['total_items']} items; latest refresh: {catalog['latest_refresh_time'] or 'none'}; status: {catalog['status']}",
        "Sources: " + (", ".join(f"{key}={value}" for key, value in catalog["counts_by_source"].items()) or "none"),
        "Source APIs: " + (", ".join(f"{key}={value}" for key, value in catalog["counts_by_source_api"].items()) or "none"),
        "Scored by topic: " + (", ".join(f"{key}={value}" for key, value in scoring["counts_by_topic"].items()) or "none"),
        (
            "Selection: "
            f"before={selection['candidates_before_filters']} "
            f"after_filters={selection['candidates_after_filters']} "
            f"after_dedupe={selection['candidates_after_dedupe']} "
            f"selected={selection['selected_count']}"
        ),
        "Drop reasons: " + ", ".join(f"{key}={value}" for key, value in selection["drop_reasons"].items()),
        "Users:",
    ]
    for user_id, user in report["users"].items():
        scheduled = ",".join(user["scheduled_personas"]) or "none"
        delivery = user["delivery"]
        received = delivery.get("receipt_at") or ("unconfirmed" if delivery.get("sent_at") else "none")
        lines.append(
            f"  {user_id}: content={user['status']}; selected={user['selected_count']}; personas={scheduled}"
        )
        lines.append(
            "    delivery: "
            f"{delivery['status']}; scheduled={delivery.get('scheduled_at') or 'none'}; "
            f"sent={delivery.get('sent_at') or 'none'}; received={received}; "
            f"receipt={delivery.get('receipt_status') or 'none'}; "
            f"trigger={delivery.get('trigger') or 'unknown'}; evidence={delivery.get('evidence_source') or 'none'}"
            + (f" ({delivery['timestamp_precision']})" if delivery.get("timestamp_precision") else "")
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Report Knowledge OS launch health.")
    parser.add_argument("--db", default="knowledge_os.db")
    parser.add_argument("--catalog", default="personas/catalog.json")
    parser.add_argument("--users-dir", default="configs/users")
    parser.add_argument("--users", default="vb,mikey,kintu")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--ingest-log", default=str(DEFAULT_INGEST_LOG))
    parser.add_argument("--delivery-log", default=str(DEFAULT_DELIVERY_LOG))
    parser.add_argument("--operations-timezone", default="Asia/Kolkata")
    args = parser.parse_args()

    users = [user.strip() for user in args.users.split(",") if user.strip()]
    report = build_launch_health(
        db_path=args.db,
        catalog_path=args.catalog,
        users_dir=args.users_dir,
        users=users,
        requested_date=date.fromisoformat(args.date),
        state_dir=args.state_dir,
        ingest_log=args.ingest_log,
        delivery_log=args.delivery_log,
        operations_timezone=args.operations_timezone,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report), end="")


if __name__ == "__main__":
    main()
