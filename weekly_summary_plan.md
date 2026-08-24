 # Plan: Launch Health + Personally Curated Weekly Summary

  ## Summary

  - Reprioritize NEXT.md so Add launch health summary command is the selected next reliability
    item.

  - Move Weekly summary mode into Immediate as Add personally curated weekly summary workflow.
  - Implement the health command first, then the weekly summary workflow.
  - Defaults: Mon–Sun weekly window, finalized/sent Monday, shared weekly edition rendered inside
    existing /knos-digest website as a Weekly view.

  ## Key Changes

  ### NEXT.md

  - Move Add launch health summary command to the top of Immediate and expand its acceptance
    criteria.

  - Add Immediate item: Add personally curated weekly summary workflow.
  - Remove or supersede the Short-term Weekly summary mode - Option for digest-of-digests item to
    avoid duplicate roadmap entries.

  - Add a decision-log entry dated 2026-06-23: manual weekly curation via editable draft; launch
    health selected as next operational item.

  ### Launch health command

  - Add CLI:

    venv/bin/python -m knowledge_os.launch_health \
      --db knowledge_os.db \
      --catalog personas/catalog.json \
      --users-dir configs/users \
      --users vb,mikey,kintu \
      --date YYYY-MM-DD \
      --format text|json

  - Report:
      - catalog counts by source / source_api
      - latest catalog refresh time
      - scored-item counts by topic
      - candidate counts before filters, after filters, after de-dupe, and selected count
      - per-user selected count and empty-digest risk
      - drop reasons: score threshold, source filter, send-day mismatch, missing timestamp, outside
        cadence window

  - Risk statuses:
      - ok: scheduled and selected count ≥ 2
      - low: scheduled and selected count = 1
      - empty: scheduled and selected count = 0
      - not_scheduled: no subscribed persona sends on that date
      - stale_catalog: latest fetch date is older than requested digest date

  - Refactor persona selection diagnostics so persona_digest.render keeps current behavior while
    launch_health can consume structured counts.

  ### Weekly curated summary

  - Add CLI:

    venv/bin/python -m knowledge_os.weekly_summary draft --week YYYY-Www
    venv/bin/python -m knowledge_os.weekly_summary finalize --week YYYY-Www
    venv/bin/python -m knowledge_os.weekly_summary whatsapp --week YYYY-Www

  - Draft output:
      - path: knos-weekly/drafts/YYYY-Www.md
      - generated from prior Mon–Sun daily files in knos-digest/
      - dedupes by URL / HN URL
      - uses checkboxes for your manual picks
      - supports optional Note: lines

  - Final output:
      - path: knos-weekly/YYYY-Www.md
      - includes only checked draft items
      - validates at least one selected item
      - preserves title, source, original date, URL/HN URL, category/persona, points, and optional
        human note

      - does not reuse daily digest checkboxes, so current read-tracking semantics remain unchanged

  ### Website and delivery

  - Update bvaibhav-info export to read both:
      - daily files from knos-digest/*.md
      - weekly files from knos-weekly/*.md

  - Extend /knos-digest with Daily / Weekly views.
  - Weekly share URL shape:

    /knos-digest?view=weekly&w=YYYY-Www

  - Add/update publish wrapper to commit knos-weekly/YYYY-Www.md, trigger the existing website
    workflow, and print/send a WhatsApp-ready shared weekly message.

  ## Test Plan

  - Python tests:
      - launch-health JSON output has expected catalog/scoring/user sections
      - empty/low/ok/not-scheduled/stale risk statuses
      - selection diagnostics match existing renderer selection behavior
      - weekly draft aggregates a Mon–Sun range correctly
      - weekly draft dedupes repeated daily items
      - finalize includes only checked items and rejects empty selections

  - Website checks:
      - npm run export-digest
      - npm run build
      - verify existing daily links still work
      - verify weekly link renders the finalized weekly edition

  ## Assumptions

  - Weekly summaries are manually curated by editing an intermediate draft.
  - Weekly summaries are shared editions, not per-user personalized editions.
  - No new SQLite schema is needed for v1.
  - No LLM-generated summary text is required; notes are human-written and optional.
  - Implementation should ignore the existing untracked .NEXT.md.swp file unless you explicitly
    decide to clean it up.
