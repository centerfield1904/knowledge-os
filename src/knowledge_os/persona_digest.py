#!/usr/bin/env python3
"""Render and summarize the canonical persona-based digest."""
import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote

from .personas import _load, persona_selection, validate_catalog


BASE_URL = "https://www.bvaibhav.info/knos-digest"
PERSONA_MARKER_RE = re.compile(r"^<!--\s*knos-persona:\s*([^|]+?)\s*\|\s*(.+?)\s*-->$")
CHECKBOX_RE = re.compile(r"^- \[[ Xx]\]\s+(.+)$")
WEEKDAYS = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARN": 30,
    "ERROR": 40,
}


def _configured_log_level() -> int:
    raw_level = os.environ.get("KNOS_PERSONA_DIGEST_LOG_LEVEL", "INFO").strip().upper()
    return LOG_LEVELS.get(raw_level, LOG_LEVELS["INFO"])


def _log(message: str, level: str = "INFO") -> None:
    normalized = level.strip().upper()
    if LOG_LEVELS.get(normalized, LOG_LEVELS["INFO"]) < _configured_log_level():
        return
    print(
        f"[{datetime.now().isoformat(timespec='seconds')}] [persona_digest] [{normalized}] {message}",
        file=sys.stderr,
    )


@dataclass(frozen=True)
class PersonaTopic:
    persona_id: str
    persona_name: str
    topic_name: str
    selection: Dict


@dataclass(frozen=True)
class Candidate:
    persona_id: str
    persona_name: str
    topic_name: str
    topic_score: float
    item_id: int
    title: str
    url: str
    source: str
    external_id: str
    author_name: str
    item_score: int
    published_at: str
    fetched_at: str


def _catalog_topics(catalog: Dict) -> Dict[str, PersonaTopic]:
    validate_catalog(catalog)
    topics: Dict[str, PersonaTopic] = {}
    for persona_id, persona in catalog.get("personas", {}).items():
        for topic in persona.get("topics", []):
            topics[topic["name"].strip().lower()] = PersonaTopic(
                persona_id=persona_id,
                persona_name=persona.get("name", persona_id),
                topic_name=topic["name"],
                selection=persona_selection(persona),
            )
    return topics


def _parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _published_date(value: str) -> str:
    parsed = _parse_dt(value)
    return parsed.date().isoformat() if parsed else "unknown"


def _matches_send_day(selection: Dict, today: date) -> bool:
    send_days = selection.get("send_days") or []
    if not send_days:
        return True

    today_weekday = today.weekday()
    for raw_day in send_days:
        day_key = str(raw_day).strip().lower()
        if day_key not in WEEKDAYS:
            raise ValueError(f"Unsupported send day: {raw_day}")
        if WEEKDAYS[day_key] == today_weekday:
            return True
    return False


def _cadence_window(selection: Dict, today: date) -> Optional[tuple[date, date]]:
    if not _matches_send_day(selection, today):
        return None

    cadence = str(selection.get("cadence", "daily")).strip().lower()
    if cadence == "daily":
        return today, today
    if cadence == "weekly":
        return today - timedelta(days=6), today
    raise ValueError(f"Unsupported persona cadence: {cadence}")


def _passes_selection(candidate: Candidate, selection: Dict, today: date) -> bool:
    return not _selection_drop_reasons(candidate, selection, today)


def _selection_drop_reasons(candidate: Candidate, selection: Dict, today: date) -> List[str]:
    reasons = []
    min_topic_score = float(selection.get("min_topic_score", 0.35))
    if candidate.topic_score < min_topic_score:
        reasons.append("below_min_topic_score")
        return reasons
    sources = selection.get("sources") or []
    if sources and candidate.source not in sources:
        reasons.append("source_not_allowed")
        return reasons
    window = _cadence_window(selection, today)
    if window is None:
        reasons.append("send_day_mismatch")
        return reasons
    cadence_dt, missing_reason = _cadence_dt(candidate)
    if not cadence_dt:
        reasons.append(missing_reason)
        return reasons
    start_date, end_date = window
    if not start_date <= cadence_dt.date() <= end_date:
        reasons.append("outside_cadence_window")
    return reasons


def _cadence_dt(candidate: Candidate) -> tuple[Optional[datetime], str]:
    if candidate.source == "hackernews":
        return _parse_dt(candidate.fetched_at), "missing_fetched_at"
    return _parse_dt(candidate.published_at), "missing_published_at"


def _cadence_field(candidate: Candidate) -> str:
    return "fetched_at" if candidate.source == "hackernews" else "published_at"


def _candidate_sort_key(candidate: Candidate) -> tuple:
    published = _parse_dt(candidate.published_at) or datetime.min
    return (-candidate.topic_score, -candidate.item_score, -published.toordinal(), candidate.title)


def select_persona_items(db_path: str, catalog_path: str, today: Optional[date] = None) -> List[Candidate]:
    """Select one canonical persona assignment per item from precomputed topic scores."""
    today = today or date.today()
    catalog = _load(catalog_path)
    topics = _catalog_topics(catalog)
    _log(
        f"Selecting persona digest items for date={today.isoformat()} "
        f"db={db_path} catalog={catalog_path} catalog_topics={len(topics)}"
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                i.item_id,
                i.title,
                i.url,
                i.source,
                COALESCE(i.external_id, '') AS external_id,
                COALESCE(i.author_name, '') AS author_name,
                COALESCE(i.score, 0) AS item_score,
                i.published_at AS published_at,
                i.fetched_at AS fetched_at,
                t.name AS topic_name,
                MAX(s.score) AS topic_score
            FROM item_topic_scores s
            JOIN topics t ON t.topic_id = s.topic_id
            JOIN items i ON i.item_id = s.item_id
            WHERE t.active = 1
            GROUP BY i.item_id, t.topic_id
            """
        ).fetchall()
    finally:
        conn.close()

    candidates: List[Candidate] = []
    drop_reason_counts: Counter[str] = Counter()
    passed_by_persona: Counter[str] = Counter()
    unknown_topic_rows = 0
    for row in rows:
        topic = topics.get(row["topic_name"].strip().lower())
        if topic is None:
            unknown_topic_rows += 1
            _log(
                f"Ignoring scored row for non-catalog topic={row['topic_name']!r} "
                f"item_id={row['item_id']} title={row['title']!r}",
                "DEBUG",
            )
            continue
        candidate = Candidate(
            persona_id=topic.persona_id,
            persona_name=topic.persona_name,
            topic_name=topic.topic_name,
            topic_score=float(row["topic_score"]),
            item_id=int(row["item_id"]),
            title=row["title"],
            url=row["url"],
            source=row["source"],
            external_id=row["external_id"],
            author_name=row["author_name"],
            item_score=int(row["item_score"]),
            published_at=row["published_at"] or "",
            fetched_at=row["fetched_at"] or "",
        )
        drop_reasons = _selection_drop_reasons(candidate, topic.selection, today)
        if drop_reasons:
            drop_reason_counts.update(drop_reasons)
            _log(
                "Dropped candidate "
                f"item_id={candidate.item_id} persona={candidate.persona_id} topic={candidate.topic_name!r} "
                f"topic_score={candidate.topic_score:.3f} source={candidate.source!r} "
                f"cadence_field={_cadence_field(candidate)} published_at={candidate.published_at!r} "
                f"fetched_at={candidate.fetched_at!r} reasons={','.join(drop_reasons)} "
                f"title={candidate.title!r}",
                "DEBUG",
            )
        else:
            candidates.append(candidate)
            passed_by_persona[candidate.persona_id] += 1
            _log(
                "Accepted candidate "
                f"item_id={candidate.item_id} persona={candidate.persona_id} topic={candidate.topic_name!r} "
                f"topic_score={candidate.topic_score:.3f} source={candidate.source!r} "
                f"cadence_field={_cadence_field(candidate)} published_at={candidate.published_at!r} "
                f"fetched_at={candidate.fetched_at!r} title={candidate.title!r}",
                "DEBUG",
            )

    best_by_item: Dict[int, Candidate] = {}
    for candidate in sorted(candidates, key=lambda c: (-c.topic_score, c.persona_id, c.topic_name, c.title)):
        best_by_item.setdefault(candidate.item_id, candidate)

    by_persona: Dict[str, List[Candidate]] = OrderedDict()
    for persona_id in catalog.get("personas", {}):
        by_persona[persona_id] = []
    for candidate in sorted(best_by_item.values(), key=_candidate_sort_key):
        by_persona.setdefault(candidate.persona_id, []).append(candidate)

    selected: List[Candidate] = []
    for persona_id, persona in catalog.get("personas", {}).items():
        max_items = int(persona_selection(persona).get("max_items", 8))
        selected.extend(sorted(by_persona.get(persona_id, []), key=_candidate_sort_key)[:max_items])
    selected_by_persona = Counter(candidate.persona_id for candidate in selected)
    _log(
        "Persona selection summary: "
        f"scored_rows={len(rows)} unknown_topic_rows={unknown_topic_rows} "
        f"passed_candidates={len(candidates)} unique_items={len(best_by_item)} selected_items={len(selected)}"
    )
    if passed_by_persona:
        _log(
            "Passed candidates by persona: "
            + ", ".join(f"{persona}={count}" for persona, count in sorted(passed_by_persona.items()))
        )
    if selected_by_persona:
        _log(
            "Selected items by persona: "
            + ", ".join(f"{persona}={count}" for persona, count in sorted(selected_by_persona.items()))
        )
    else:
        _log("Selected items by persona: none")
    if drop_reason_counts:
        _log(
            "Candidate drop reasons: "
            + ", ".join(f"{reason}={count}" for reason, count in sorted(drop_reason_counts.items()))
        )
    return selected


def render_persona_digest_text(candidates: Iterable[Candidate], digest_date: str, catalog_path: str) -> str:
    catalog = _load(catalog_path)
    candidates = list(candidates)
    by_persona: Dict[str, List[Candidate]] = OrderedDict((pid, []) for pid in catalog.get("personas", {}))
    for candidate in candidates:
        by_persona.setdefault(candidate.persona_id, []).append(candidate)

    visible_personas = [pid for pid, rows in by_persona.items() if rows]
    lines = [
        f"🦅 *Knowledge Digest* - {digest_date}",
        f"_{len(candidates)} selected item{'s' if len(candidates) != 1 else ''} across {len(visible_personas)} persona{'s' if len(visible_personas) != 1 else ''}_",
        "",
    ]

    for persona_id, rows in by_persona.items():
        if not rows:
            continue
        persona = catalog["personas"][persona_id]
        persona_name = persona.get("name", persona_id)
        lines.append(f"<!-- knos-persona: {persona_id} | {persona_name} -->")
        lines.append(f"## {persona_name}")
        lines.append("")

        by_topic: Dict[str, List[Candidate]] = OrderedDict()
        for row in sorted(rows, key=_candidate_sort_key):
            by_topic.setdefault(row.topic_name, []).append(row)
        for topic_name, topic_rows in by_topic.items():
            lines.append(f"*{topic_name}*")
            for row in topic_rows:
                source_icon = "📰 " if row.source == "substack" else ""
                lines.append(f"- [ ] {source_icon}{row.title}")
                meta = [f"published: {_published_date(row.published_at)}", f"source: {row.source}"]
                if row.item_score:
                    meta.append(f"↑{row.item_score}")
                if row.author_name:
                    meta.append(f"by {row.author_name}")
                lines.append(f"  {' | '.join(meta)}")
                lines.append(f"  🔗 {row.url}")
                if row.source == "hackernews" and row.external_id:
                    lines.append(f"  → HN: https://news.ycombinator.com/item?id={row.external_id}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_persona_digest_file(
    db_path: str,
    catalog_path: str,
    output: Optional[str] = None,
    overwrite: bool = False,
    digest_date: Optional[str] = None,
) -> Path:
    digest_date = digest_date or date.today().isoformat()
    candidates = select_persona_items(db_path, catalog_path, today=date.fromisoformat(digest_date))
    text = render_persona_digest_text(candidates, digest_date, catalog_path)
    path = Path(output) if output else Path("knos-digest") / f"{digest_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass --overwrite to replace it")
    path.write_text(text)
    _log(f"Wrote persona digest markdown to {path}")
    return path


def parse_persona_markdown(path: str) -> List[Dict]:
    current_persona_id = ""
    current_persona_name = ""
    current_topic = ""
    current_story: Optional[Dict] = None
    stories: List[Dict] = []
    for raw_line in Path(path).read_text().splitlines():
        line = raw_line.strip()
        marker = PERSONA_MARKER_RE.match(line)
        if marker:
            current_persona_id = marker.group(1).strip()
            current_persona_name = marker.group(2).strip()
            current_topic = ""
            continue
        topic = re.match(r"^\*([^*]+)\*$", line)
        if topic and current_persona_id:
            current_topic = topic.group(1)
            continue
        checkbox = CHECKBOX_RE.match(line)
        if checkbox and current_persona_id:
            title = checkbox.group(1).replace("📰 ", "", 1)
            current_story = {
                "persona_id": current_persona_id,
                "persona_name": current_persona_name,
                "topic": current_topic,
                "title": title,
                "points": 0,
            }
            stories.append(current_story)
            continue
        # The metadata line after a story carries HN points like "↑343".
        if current_story is not None:
            points_match = re.search(r"↑(\d+)", line)
            if points_match:
                current_story["points"] = int(points_match.group(1))
    return stories


def persona_url(
    persona_ids: Iterable[str],
    base_url: str = BASE_URL,
    digest_date: Optional[str] = None,
) -> str:
    encoded = ",".join(quote(pid, safe="") for pid in persona_ids)
    params = []
    if encoded:
        params.append(f"personas={encoded}")
    if digest_date:
        params.append(f"date={quote(digest_date, safe='')}")
    return f"{base_url}?{'&'.join(params)}" if params else base_url


def whatsapp_summary(
    user_config_path: str,
    digest_path: str,
    base_url: Optional[str] = None,
    headline_limit: int = 3,
) -> Dict:
    user_config = _load(user_config_path)
    user = user_config["user"]
    personas = user.get("personas", [])
    selected = [story for story in parse_persona_markdown(digest_path) if story["persona_id"] in personas]
    topics = []
    for story in selected:
        if story["topic"] and story["topic"] not in topics:
            topics.append(story["topic"])
    # Lead the teaser with the strongest items (by HN points), not file order.
    # Titles are already emoji-stripped in parse_persona_markdown.
    ranked = sorted(selected, key=lambda story: story.get("points", 0), reverse=True)
    headlines = [story["title"] for story in ranked[:headline_limit]]
    effective_base_url = base_url or user_config.get("delivery", {}).get("base_url") or BASE_URL
    # Link to the specific digest the message describes so re-opening an old message
    # shows that day's items, not the latest export. Only pin when the filename stem is
    # a real YYYY-MM-DD (the canonical artifact name); otherwise fall back to "latest".
    stem = Path(digest_path).stem
    digest_date = stem if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stem) else None
    url = persona_url(personas, effective_base_url, digest_date=digest_date)
    summary = {
        "digest_path": digest_path,
        "website_url": url,
        "user": user["identifier"],
        "item_count": len(selected),
        "topics": topics,
        "headlines": headlines,
    }
    if not selected:
        summary["message"] = (
            "Quiet one today — nothing worth sending your way. Back tomorrow."
        )
        return summary

    count = len(selected)
    shown = len(headlines)
    if count == 1:
        opener = "Today's read — 1 picked:"
    elif count > shown:
        opener = f"Today's reads — {count} picked, top {shown}:"
    else:
        opener = f"Today's reads — {count} picked:"
    headline_text = "\n".join(f"- {headline}" for headline in headlines)
    summary["message"] = f"{opener}\n\n{headline_text}\n\n{url}"
    return summary


def _render_command(args: argparse.Namespace) -> None:
    path = render_persona_digest_file(
        db_path=args.db,
        catalog_path=args.catalog,
        output=args.output,
        overwrite=args.overwrite,
        digest_date=args.date,
    )
    print(path)


def _whatsapp_command(args: argparse.Namespace) -> None:
    summary = whatsapp_summary(
        user_config_path=args.user_config,
        digest_path=args.digest,
        base_url=args.base_url,
    )
    print(f"digest_path: {summary['digest_path']}")
    print(f"website_url: {summary['website_url']}")
    print("")
    print(summary["message"])
    if summary["item_count"] == 0:
        raise SystemExit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render and summarize persona-based digests.")
    sub = parser.add_subparsers(dest="command", required=True)

    render = sub.add_parser("render")
    render.add_argument("--db", default="knowledge_os.db")
    render.add_argument("--catalog", default="personas/catalog.json")
    render.add_argument("--output")
    render.add_argument("--overwrite", action="store_true")
    render.add_argument("--date")
    render.set_defaults(func=_render_command)

    whatsapp = sub.add_parser("whatsapp")
    whatsapp.add_argument("--user-config", required=True)
    whatsapp.add_argument("--digest", required=True)
    whatsapp.add_argument("--base-url")
    whatsapp.set_defaults(func=_whatsapp_command)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
