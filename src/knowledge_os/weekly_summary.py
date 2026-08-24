#!/usr/bin/env python3
"""Create, finalize, and share manually curated weekly digest editions."""

import argparse
import re
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote

from .persona_digest import BASE_URL, CHECKBOX_RE, PERSONA_MARKER_RE, SOURCE_ICON_PREFIXES


WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")
WEEKLY_ITEM_MARKER_RE = re.compile(
    r"^<!--\s*knos-weekly-item:\s*([^|]+?)\s*\|\s*(.+?)\s*-->$"
)
FINAL_ITEM_MARKER = "<!-- knos-weekly-selected -->"


@dataclass(frozen=True)
class WeeklyItem:
    title: str
    original_date: str
    published_date: str
    source: str
    url: str
    hn_url: str
    category: str
    persona_id: str
    persona_name: str
    points: int = 0
    author: str = ""
    note: str = ""
    selected: bool = False


def week_bounds(week: str) -> tuple[date, date]:
    match = WEEK_RE.fullmatch(week)
    if not match:
        raise ValueError(f"Invalid ISO week {week!r}; expected YYYY-Www")
    try:
        monday = date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO week {week!r}") from exc
    return monday, monday + timedelta(days=6)


def _clean_title(raw_title: str) -> str:
    title = raw_title
    for prefix in SOURCE_ICON_PREFIXES:
        if title.startswith(prefix):
            title = title[len(prefix):]
            break
    return title


def parse_daily_digest(path: Path, original_date: Optional[str] = None) -> List[WeeklyItem]:
    """Parse current persona-marked daily markdown into weekly candidates."""
    lines = path.read_text().splitlines()
    digest_date = original_date or path.stem
    current_persona_id = ""
    current_persona_name = ""
    current_category = ""
    items: List[WeeklyItem] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        persona = PERSONA_MARKER_RE.match(line)
        if persona:
            current_persona_id = persona.group(1).strip()
            current_persona_name = persona.group(2).strip()
            current_category = ""
            i += 1
            continue
        category = re.match(r"^\*([^*]+)\*$", line)
        if category and current_persona_id:
            current_category = category.group(1).strip()
            i += 1
            continue
        checkbox = CHECKBOX_RE.match(line)
        if not checkbox or not current_persona_id or not current_category:
            i += 1
            continue

        title = _clean_title(checkbox.group(1).strip())
        published_date = ""
        source = ""
        points = 0
        author = ""
        url = ""
        hn_url = ""
        note = ""
        j = i + 1
        while j < len(lines):
            detail = lines[j].strip()
            if CHECKBOX_RE.match(detail) or PERSONA_MARKER_RE.match(detail) or re.match(r"^\*([^*]+)\*$", detail):
                break
            if detail.startswith("published:"):
                published = re.search(r"(?:^|\|\s*)published:\s*([^|]+)", detail)
                source_match = re.search(r"(?:^|\|\s*)source:\s*([^|]+)", detail)
                points_match = re.search(r"↑(\d+)", detail)
                author_match = re.search(r"(?:^|\|\s*)by\s+([^|]+)", detail)
                if published:
                    published_date = published.group(1).strip()
                if source_match:
                    source = source_match.group(1).strip()
                if points_match:
                    points = int(points_match.group(1))
                if author_match:
                    author = author_match.group(1).strip()
            elif detail.startswith("🔗"):
                url = detail.replace("🔗", "", 1).strip()
            elif detail.startswith("→ HN:"):
                hn_url = detail.replace("→ HN:", "", 1).strip()
            elif detail.startswith("Notes:"):
                note = detail.replace("Notes:", "", 1).strip()
            j += 1
        items.append(WeeklyItem(
            title=title,
            original_date=digest_date,
            published_date=published_date,
            source=source,
            url=url,
            hn_url=hn_url,
            category=current_category,
            persona_id=current_persona_id,
            persona_name=current_persona_name,
            points=points,
            author=author,
            note=note,
        ))
        i = j
    return items


def collect_weekly_items(week: str, daily_dir: str = "knos-digest") -> List[WeeklyItem]:
    monday, sunday = week_bounds(week)
    items: List[WeeklyItem] = []
    seen_urls = set()
    seen_hn_urls = set()
    current = monday
    while current <= sunday:
        path = Path(daily_dir) / f"{current.isoformat()}.md"
        if path.exists():
            for item in parse_daily_digest(path, current.isoformat()):
                normalized_url = item.url.strip().rstrip("/")
                normalized_hn = item.hn_url.strip().rstrip("/")
                if (normalized_url and normalized_url in seen_urls) or (
                    normalized_hn and normalized_hn in seen_hn_urls
                ):
                    continue
                if normalized_url:
                    seen_urls.add(normalized_url)
                if normalized_hn:
                    seen_hn_urls.add(normalized_hn)
                items.append(item)
        current += timedelta(days=1)
    return items


def render_draft(week: str, items: Iterable[WeeklyItem]) -> str:
    monday, sunday = week_bounds(week)
    rows = list(items)
    lines = [
        f"# Knowledge Weekly Draft — {week}",
        "",
        f"Window: {monday.isoformat()} to {sunday.isoformat()} (Mon–Sun)",
        f"Candidates: {len(rows)}",
        "",
        "Check the items to include. Add an optional human note after `Note:`.",
        "",
    ]
    for item in rows:
        lines.append(f"<!-- knos-weekly-item: {item.persona_id} | {item.persona_name} -->")
        lines.append(f"- [ ] {item.title}")
        metadata = [f"original date: {item.original_date}"]
        if item.published_date:
            metadata.append(f"published: {item.published_date}")
        metadata.append(f"source: {item.source or 'unknown'}")
        if item.points:
            metadata.append(f"↑{item.points}")
        if item.author:
            metadata.append(f"by {item.author}")
        lines.append(f"  {' | '.join(metadata)}")
        lines.append(f"  category: {item.category}")
        if item.url:
            lines.append(f"  🔗 {item.url}")
        if item.hn_url:
            lines.append(f"  → HN: {item.hn_url}")
        lines.append(f"  Note: {item.note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_draft(
    week: str,
    daily_dir: str = "knos-digest",
    drafts_dir: str = "knos-weekly/drafts",
    output: Optional[str] = None,
    overwrite: bool = False,
) -> Path:
    items = collect_weekly_items(week, daily_dir=daily_dir)
    path = Path(output) if output else Path(drafts_dir) / f"{week}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass --overwrite to replace it")
    path.write_text(render_draft(week, items))
    return path


def parse_draft(path: Path) -> List[WeeklyItem]:
    lines = path.read_text().splitlines()
    items: List[WeeklyItem] = []
    i = 0
    while i < len(lines):
        marker = WEEKLY_ITEM_MARKER_RE.match(lines[i].strip())
        if not marker:
            i += 1
            continue
        persona_id = marker.group(1).strip()
        persona_name = marker.group(2).strip()
        i += 1
        if i >= len(lines):
            break
        checkbox = re.match(r"^- \[([ Xx])\]\s+(.+)$", lines[i].strip())
        if not checkbox:
            raise ValueError(f"Malformed weekly draft item after line {i}: {path}")
        selected = checkbox.group(1).upper() == "X"
        title = checkbox.group(2).strip()
        original_date = ""
        published_date = ""
        source = ""
        points = 0
        author = ""
        category = ""
        url = ""
        hn_url = ""
        note = ""
        i += 1
        while i < len(lines) and not WEEKLY_ITEM_MARKER_RE.match(lines[i].strip()):
            detail = lines[i].strip()
            if detail.startswith("original date:"):
                original = re.search(r"(?:^|\|\s*)original date:\s*([^|]+)", detail)
                published = re.search(r"(?:^|\|\s*)published:\s*([^|]+)", detail)
                source_match = re.search(r"(?:^|\|\s*)source:\s*([^|]+)", detail)
                points_match = re.search(r"↑(\d+)", detail)
                author_match = re.search(r"(?:^|\|\s*)by\s+([^|]+)", detail)
                if original:
                    original_date = original.group(1).strip()
                if published:
                    published_date = published.group(1).strip()
                if source_match:
                    source = source_match.group(1).strip()
                if points_match:
                    points = int(points_match.group(1))
                if author_match:
                    author = author_match.group(1).strip()
            elif detail.startswith("category:"):
                category = detail.replace("category:", "", 1).strip()
            elif detail.startswith("🔗"):
                url = detail.replace("🔗", "", 1).strip()
            elif detail.startswith("→ HN:"):
                hn_url = detail.replace("→ HN:", "", 1).strip()
            elif detail.startswith("Note:"):
                note = detail.replace("Note:", "", 1).strip()
            i += 1
        items.append(WeeklyItem(
            title=title,
            original_date=original_date,
            published_date=published_date,
            source=source,
            url=url,
            hn_url=hn_url,
            category=category,
            persona_id=persona_id,
            persona_name=persona_name,
            points=points,
            author=author,
            note=note,
            selected=selected,
        ))
    return items


def render_final(week: str, items: Iterable[WeeklyItem]) -> str:
    monday, sunday = week_bounds(week)
    rows = list(items)
    grouped: Dict[tuple[str, str], Dict[str, List[WeeklyItem]]] = OrderedDict()
    for item in rows:
        persona_key = (item.persona_id, item.persona_name)
        grouped.setdefault(persona_key, OrderedDict()).setdefault(item.category, []).append(item)
    lines = [
        f"🦅 *Knowledge Weekly* - {week}",
        f"_{monday.isoformat()} to {sunday.isoformat()} · {len(rows)} curated item{'s' if len(rows) != 1 else ''}_",
        "",
    ]
    for (persona_id, persona_name), categories in grouped.items():
        lines.extend([f"<!-- knos-persona: {persona_id} | {persona_name} -->", f"## {persona_name}", ""])
        for category, category_items in categories.items():
            lines.extend([f"*{category}*", ""])
            for item in category_items:
                lines.append(FINAL_ITEM_MARKER)
                lines.append(f"### {item.title}")
                metadata = [f"original date: {item.original_date}"]
                if item.published_date:
                    metadata.append(f"published: {item.published_date}")
                metadata.append(f"source: {item.source or 'unknown'}")
                if item.points:
                    metadata.append(f"↑{item.points}")
                if item.author:
                    metadata.append(f"by {item.author}")
                lines.append(" | ".join(metadata))
                if item.url:
                    lines.append(f"🔗 {item.url}")
                if item.hn_url:
                    lines.append(f"→ HN: {item.hn_url}")
                if item.note:
                    lines.append(f"Note: {item.note}")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def finalize_summary(
    week: str,
    drafts_dir: str = "knos-weekly/drafts",
    output_dir: str = "knos-weekly",
    draft_path: Optional[str] = None,
    output: Optional[str] = None,
    overwrite: bool = False,
) -> Path:
    source = Path(draft_path) if draft_path else Path(drafts_dir) / f"{week}.md"
    selected = [replace(item, selected=True) for item in parse_draft(source) if item.selected]
    if not selected:
        raise ValueError(f"Weekly draft {source} has no checked items")
    path = Path(output) if output else Path(output_dir) / f"{week}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass --overwrite to replace it")
    path.write_text(render_final(week, selected))
    return path


def weekly_url(week: str, base_url: str = BASE_URL) -> str:
    week_bounds(week)
    return f"{base_url}?view=weekly&w={quote(week, safe='-')}"


def weekly_whatsapp_summary(
    week: str,
    summary_path: Optional[str] = None,
    base_url: str = BASE_URL,
    headline_limit: int = 3,
) -> Dict:
    path = Path(summary_path) if summary_path else Path("knos-weekly") / f"{week}.md"
    items = _parse_final(path)
    if not items:
        raise ValueError(f"Final weekly summary {path} has no items")
    headlines = [item.title for item in sorted(items, key=lambda item: item.points, reverse=True)[:headline_limit]]
    count = len(items)
    shown = len(headlines)
    opener = f"This week's reads — {count} curated"
    if count > shown:
        opener += f", top {shown}:"
    else:
        opener += ":"
    url = weekly_url(week, base_url)
    return {
        "summary_path": str(path),
        "website_url": url,
        "item_count": count,
        "headlines": headlines,
        "message": f"{opener}\n\n" + "\n".join(f"- {title}" for title in headlines) + f"\n\n{url}",
    }


def _parse_final(path: Path) -> List[WeeklyItem]:
    """Parse finalized files for delivery; the website has an equivalent parser."""
    lines = path.read_text().splitlines()
    items: List[WeeklyItem] = []
    persona_id = ""
    persona_name = ""
    category = ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        persona = PERSONA_MARKER_RE.match(line)
        if persona:
            persona_id, persona_name = persona.group(1).strip(), persona.group(2).strip()
        category_match = re.match(r"^\*([^*]+)\*$", line)
        if category_match and persona_id:
            category = category_match.group(1).strip()
        if line != FINAL_ITEM_MARKER:
            i += 1
            continue
        if i + 1 >= len(lines) or not lines[i + 1].strip().startswith("### "):
            raise ValueError(f"Malformed finalized weekly item in {path}")
        title = lines[i + 1].strip()[4:].strip()
        metadata = lines[i + 2].strip() if i + 2 < len(lines) else ""
        original = re.search(r"(?:^|\|\s*)original date:\s*([^|]+)", metadata)
        published = re.search(r"(?:^|\|\s*)published:\s*([^|]+)", metadata)
        source_match = re.search(r"(?:^|\|\s*)source:\s*([^|]+)", metadata)
        points_match = re.search(r"↑(\d+)", metadata)
        author_match = re.search(r"(?:^|\|\s*)by\s+([^|]+)", metadata)
        url = ""
        hn_url = ""
        note = ""
        j = i + 3
        while j < len(lines) and lines[j].strip() != FINAL_ITEM_MARKER and not PERSONA_MARKER_RE.match(lines[j].strip()):
            detail = lines[j].strip()
            if detail.startswith("🔗"):
                url = detail.replace("🔗", "", 1).strip()
            elif detail.startswith("→ HN:"):
                hn_url = detail.replace("→ HN:", "", 1).strip()
            elif detail.startswith("Note:"):
                note = detail.replace("Note:", "", 1).strip()
            elif detail.startswith("*") or detail.startswith("## "):
                break
            j += 1
        items.append(WeeklyItem(
            title=title,
            original_date=original.group(1).strip() if original else "",
            published_date=published.group(1).strip() if published else "",
            source=source_match.group(1).strip() if source_match else "",
            url=url,
            hn_url=hn_url,
            category=category,
            persona_id=persona_id,
            persona_name=persona_name,
            points=int(points_match.group(1)) if points_match else 0,
            author=author_match.group(1).strip() if author_match else "",
            note=note,
            selected=True,
        ))
        i = j
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Curate a shared Knowledge OS weekly summary.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    draft = subparsers.add_parser("draft", help="Aggregate a Mon–Sun draft for manual curation.")
    draft.add_argument("--week", required=True)
    draft.add_argument("--daily-dir", default="knos-digest")
    draft.add_argument("--drafts-dir", default="knos-weekly/drafts")
    draft.add_argument("--output")
    draft.add_argument("--overwrite", action="store_true")

    finalize = subparsers.add_parser("finalize", help="Write a checked-items-only weekly edition.")
    finalize.add_argument("--week", required=True)
    finalize.add_argument("--drafts-dir", default="knos-weekly/drafts")
    finalize.add_argument("--output-dir", default="knos-weekly")
    finalize.add_argument("--draft")
    finalize.add_argument("--output")
    finalize.add_argument("--overwrite", action="store_true")

    whatsapp = subparsers.add_parser("whatsapp", help="Print a WhatsApp-ready weekly share message.")
    whatsapp.add_argument("--week", required=True)
    whatsapp.add_argument("--summary")
    whatsapp.add_argument("--base-url", default=BASE_URL)

    args = parser.parse_args()
    if args.command == "draft":
        print(write_draft(args.week, args.daily_dir, args.drafts_dir, args.output, args.overwrite))
    elif args.command == "finalize":
        print(finalize_summary(
            args.week,
            args.drafts_dir,
            args.output_dir,
            args.draft,
            args.output,
            args.overwrite,
        ))
    else:
        summary = weekly_whatsapp_summary(args.week, args.summary, args.base_url)
        print(f"summary_path: {summary['summary_path']}")
        print(f"website_url: {summary['website_url']}")
        print("")
        print(summary["message"])


if __name__ == "__main__":
    main()
