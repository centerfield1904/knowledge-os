from pathlib import Path

import pytest

from knowledge_os.weekly_summary import (
    _parse_final,
    collect_weekly_items,
    finalize_summary,
    weekly_whatsapp_summary,
    write_draft,
)


def _daily(title, url, hn_url="", persona="ai", persona_name="AI", category="Research", points=10):
    hn_line = f"\n  → HN: {hn_url}" if hn_url else ""
    return f"""🦅 *Knowledge Digest*

<!-- knos-persona: {persona} | {persona_name} -->
## {persona_name}

*{category}*
- [ ] {title}
  published: 2026-06-15 | source: hackernews | ↑{points} | by alice
  🔗 {url}{hn_line}
"""


def test_draft_aggregates_monday_through_sunday_and_dedupes_urls(tmp_path):
    daily_dir = tmp_path / "knos-digest"
    daily_dir.mkdir()
    (daily_dir / "2026-06-15.md").write_text(
        _daily("Monday story", "https://example.com/shared", "https://news.ycombinator.com/item?id=1")
    )
    (daily_dir / "2026-06-17.md").write_text(
        _daily("Repeated story", "https://example.com/shared", "https://news.ycombinator.com/item?id=1")
    )
    (daily_dir / "2026-06-21.md").write_text(
        _daily("Sunday story", "https://example.com/sunday", points=20)
    )
    (daily_dir / "2026-06-22.md").write_text(
        _daily("Next week", "https://example.com/next")
    )

    items = collect_weekly_items("2026-W25", str(daily_dir))
    assert [item.title for item in items] == ["Monday story", "Sunday story"]
    assert [item.original_date for item in items] == ["2026-06-15", "2026-06-21"]

    path = write_draft(
        "2026-W25",
        daily_dir=str(daily_dir),
        drafts_dir=str(tmp_path / "knos-weekly" / "drafts"),
    )
    text = path.read_text()
    assert text.count("- [ ]") == 2
    assert "Note:" in text


def test_finalize_includes_only_checked_items_and_preserves_fields(tmp_path):
    drafts = tmp_path / "knos-weekly" / "drafts"
    drafts.mkdir(parents=True)
    draft = drafts / "2026-W25.md"
    draft.write_text("""# Draft

<!-- knos-weekly-item: ai | AI -->
- [x] Selected story
  original date: 2026-06-15 | published: 2026-06-14 | source: hackernews | ↑42 | by alice
  category: Research
  🔗 https://example.com/selected
  → HN: https://news.ycombinator.com/item?id=42
  Note: The useful bit is the evaluation method.

<!-- knos-weekly-item: ux | Design -->
- [ ] Skipped story
  original date: 2026-06-16 | source: substack
  category: Design
  🔗 https://example.com/skipped
  Note:
""")

    output = finalize_summary(
        "2026-W25",
        drafts_dir=str(drafts),
        output_dir=str(tmp_path / "knos-weekly"),
    )
    text = output.read_text()
    assert "Selected story" in text
    assert "Skipped story" not in text
    assert "- [x]" not in text.lower()
    assert "- [ ]" not in text
    assert "original date: 2026-06-15" in text
    assert "https://news.ycombinator.com/item?id=42" in text
    assert "The useful bit is the evaluation method." in text

    parsed = _parse_final(output)
    assert len(parsed) == 1
    assert parsed[0].points == 42
    assert parsed[0].category == "Research"

    summary = weekly_whatsapp_summary("2026-W25", str(output))
    assert summary["website_url"].endswith("?view=weekly&w=2026-W25")
    assert "Selected story" in summary["message"]


def test_finalize_rejects_empty_selection(tmp_path):
    draft = tmp_path / "draft.md"
    draft.write_text("""<!-- knos-weekly-item: ai | AI -->
- [ ] Not selected
  original date: 2026-06-15 | source: hackernews
  category: Research
  🔗 https://example.com/no
  Note:
""")

    with pytest.raises(ValueError, match="no checked items"):
        finalize_summary(
            "2026-W25",
            draft_path=str(draft),
            output=str(tmp_path / "final.md"),
        )
