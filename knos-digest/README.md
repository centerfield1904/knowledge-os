# knos-digest

Generated daily digest markdown output.

Digest files are local runtime artifacts and are ignored by git. Keep only this README in the repository.

## Format

**Filename:** `YYYY-MM-DD.md`  
**Content:** Full digest as delivered to WhatsApp

## Structure

Each file contains:
- **Matched Stories** - Topic-organized HN stories
- **Engagement Opportunities** - 5 actionable opportunities
- **Notable Authors** - Authors being tracked

## Usage

**View digest:**
```bash
cat 2026-02-20.md
```

**Search across digests:**
```bash
grep -r "AI agent" .
```

**Count digests with engagement section:**
```bash
grep -l "🎯" *.md | wc -l
```

**Sync read items after marking [x] checkboxes:**
```bash
venv/bin/python -m knowledge_os.sync_reading_log knos-digest/YYYY-MM-DD.md
```

**Browse all stories/authors/config in the dashboard:**
```bash
venv/bin/python -m streamlit run src/knowledge_os/dashboard.py
```

## Archive Stats

```bash
# Total digests
ls -1 *.md | wc -l

# Digests with Substack items
grep -l "📰" *.md | wc -l
```

---

_Auto-generated daily at 2 PM by knowledge-os pipeline_
