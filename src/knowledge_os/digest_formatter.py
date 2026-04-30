#!/usr/bin/env python3
"""Digest text formatting and lightweight comment summarization."""
import re
from datetime import datetime
from typing import Dict, List


def extract_first_sentence(html_text: str) -> str:
    """Extract first meaningful sentence from an HN comment (HTML)."""
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#x27;", "'")
        .replace("&quot;", '"')
    )
    text = text.strip()
    if not text:
        return ""
    match = re.match(r"(.+?[.!?])\s", text)
    if match:
        return match.group(1).strip()
    return text[:120].strip()


def extract_keywords(sentences: List[str], stop_words: set) -> List[str]:
    """Extract key topic words from sentences."""
    word_counts = {}
    for sent in sentences:
        words = re.findall(r"[a-zA-Z]{4,}", sent.lower())
        for word in words:
            if word not in stop_words:
                word_counts[word] = word_counts.get(word, 0) + 1
    sorted_words = sorted(word_counts.items(), key=lambda item: item[1], reverse=True)
    return [word for word, _ in sorted_words[:5]]


def summarize_comments(comments: List[Dict], descendants: int = 0) -> str:
    """Return the first sentence of the top HN comment, or a fallback string."""
    if not comments:
        return f"{descendants} comments" if descendants else None

    text = comments[0].get("text", "")
    if text:
        sentence = extract_first_sentence(text)
        if sentence:
            return sentence

    return f"{descendants} comments" if descendants else None


def format_story_lines(story, notable_authors):
    """Return a list of lines for a single story entry."""
    lines = []
    title = story["title"]
    score = story["score"]
    author = story["by"]
    story_id = story.get("id")
    comment_summary = story.get("comment_summary")

    author_marker = ""
    if notable_authors:
        for notable in notable_authors:
            if notable["author_name"] == author:
                author_marker = " ⭐"
                break

    karma = story.get("author_karma")
    karma_str = f"karma: {karma:,}" if karma is not None else ""
    source_icon = "📰 " if story.get("source") == "substack" else ""
    lines.append(f"- [ ] {source_icon}{title}")
    meta_parts = [f"↑{score}"]
    if karma_str:
        meta_parts.append(karma_str)
    meta_parts.append(f"by {author}{author_marker}")
    lines.append(f"  {' | '.join(meta_parts)}")
    if comment_summary:
        lines.append(f"  💬 {comment_summary}")
    if story.get("source") == "substack":
        lines.append(f"  🔗 {story.get('url', '')}")
    elif story_id:
        lines.append(f"  🔗 https://news.ycombinator.com/item?id={story_id}")
    else:
        lines.append(f"  🔗 {story.get('url', '')}")
    lines.append("  Notes: ")
    return lines


def generate_digest_text(
    result: Dict,
    config: Dict = None,
    weekend_sections=None,
    engagement_enabled: bool = True,
    engagement_formatter=None,
) -> str:
    """Generate digest text from processed result."""
    stories = result["stories"]
    notable_authors = result["notable_authors"]
    engagement_opportunities = result.get("engagement_opportunities", [])

    if not stories:
        return "🦅 *HN Digest* - Quiet day on the frontier. Use the time to build.\n\n_No relevant stories today._"

    if weekend_sections is not None:
        top_matches, interesting_reads = weekend_sections
        wm = (config or {}).get("settings", {}).get("weekend_mode", {})
        title = wm.get("digest_title", "Weekend Reads")
        day_str = datetime.now().strftime("%a, %b %-d")

        lines = []
        lines.append(f"🌿 *{title}* — {day_str}")
        lines.append(f"_{len(top_matches)} top matches · {len(interesting_reads)} interesting reads_\n")

        lines.append("── Best Matches ──────────────────────")
        for story in top_matches:
            lines.extend(format_story_lines(story, notable_authors))
        lines.append("")

        lines.append("── Interesting Reads ─────────────────")
        for story in interesting_reads:
            lines.extend(format_story_lines(story, notable_authors))
        lines.append("")

        lines.append("_A quieter read for the weekend._")
        return "\n".join(lines)

    by_topic = {}
    for story in stories:
        topic = story["matched_topic"]
        if topic not in by_topic:
            by_topic[topic] = []
        by_topic[topic].append(story)

    lines = []
    lines.append("🦅 *HN Digest* - Afternoon Energy Boost")
    lines.append(f"_{len(stories)} stories worth your attention_\n")

    if notable_authors:
        lines.append("💡 *Signal:* Authors you're tracking posted today.\n")

    for topic, topic_stories in by_topic.items():
        lines.append(f"*{topic}*")
        for story in topic_stories[:5]:
            lines.extend(format_story_lines(story, notable_authors))
        lines.append("")

    if engagement_enabled and engagement_opportunities and engagement_formatter:
        engagement_section = engagement_formatter(engagement_opportunities)
        if engagement_section:
            lines.append(engagement_section)

    if notable_authors:
        lines.append("*Authors to Watch* ⭐")
        for author in notable_authors[:3]:
            topics = ", ".join(list(author["topics"].keys())[:3])
            lines.append(f"• {author['author_name']} ({author['story_count']} stories: {topics})")
        lines.append("")

    lines.append("")
    lines.append("_Keep building. The frontier moves forward._")
    lines.append("")
    lines.append("💬 *Feedback:* Reply with story numbers + action")
    lines.append("   Example: `1,3 👍  2 📌  4 skip`")

    return "\n".join(lines)
