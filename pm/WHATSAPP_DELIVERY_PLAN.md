# WhatsApp Delivery Plan

## Current Status

WhatsApp delivery is automated through the website link flow. The morning job generates the canonical digest, pushes `knos-digest/YYYY-MM-DD.md`, triggers the `bvaibhav-info` GitHub Action, and verifies public website readiness before external links are sent.

## V1 Flow

Run and verify the daily ingest/publish path:

```bash
bash scripts/run_daily_ingest_and_verify_publish.sh
```

Check daily website readiness:

```bash
bash scripts/check_daily_digest_ready.sh
bash scripts/check_daily_digest_ready.sh --alert-vb
```

Expected URL shape:

```text
https://www.bvaibhav.info/knos-digest?p=<persona-codes>&d=YYYY-MM-DD
```

## Suggested Messages

### Kintu

```text
Made you a small UX/design digest for today:
<website-url>

Can you tell me if even 1-2 links feel useful? If not, I’ll tune the sources.
```

### Mikey

```text
I made you a daily AI/LLM digest based on the article you asked about:
<website-url>

Quick check: are these the kind of links you’d actually want to receive?
```

## Reply Handling

Skip the feedback feature for this launch.

Ask one plain-language question in WhatsApp and read the reply manually. Do not ask users to label every item, do not log per-item feedback, and do not build feedback storage, parsing, reactions, or click tracking for this phase.

Useful reply prompts:

```text
Did any of these links feel worth opening?
```

```text
Was this too broad, too technical, or roughly right?
```

The only record for now is a short human note in `pm/launch_log.md` when something materially changes the next send.

---

## Launch Plan (Mikey + Kintu)

### Cadence

- **Kintu**: Friday weekly, matching `ux_design.send_days`.
  - Kintu: aggregating across 3–4 days solves the `ux_design` sparsity problem on HN
- **Mikey**: daily at 2 PM Pacific.
- **Manas**: daily at 2 PM Singapore time.
- **VB**: stays daily — own reading habit, not a delivery question
- Cadence is enforced by persona `selection.cadence` and cron timing. User configs in `configs/users/*.json` select persona bundles; delivery wrappers send from the shared website-facing artifact.

### State of readiness

**Ready**
- Persona model + `configs/users/{kintu,manas,mikey,vb}.json` exist
- Modular pipeline wired: ingestion → persona materializer → scoring → selection → render
- `scripts/run_catalog_ingest.sh` commits markdown and triggers the website publish workflow
- `scripts/check_daily_digest_ready.sh` verifies the public website JSON and can alert VB
- Delivery decision frozen: WhatsApp share of the persona-filtered website URL
- Dry-run samples exist for Kintu, Mikey, Manas, and VB

**Gaps blocking a clean first send**
1. Kintu's source pool can still be sparse on non-Friday runs
2. External-user reply handling is still manual
3. Link click/open tracking is intentionally not built yet

### Phase 1 — Dry run before sending anything

Goal: see what each user would actually receive before committing to a send.

1. Run `bash scripts/run_daily_ingest_and_verify_publish.sh`. Inspect `knos-digest/YYYY-MM-DD.md` and the website URL locally before sending new-user links.
2. **Hard gate for Kintu:** if her digest has fewer than 3 items, do not launch her until 4–6 design Substack feeds are added (a16z design, Nielsen Norman, Julie Zhuo, etc.). Add to shared sources if broadly useful, otherwise scope to her config.
3. Read Mikey's digest as if you were him. If it reads as generic HN noise rather than AI-researcher signal, raise `min_topic_score` from 0.35 → 0.40 in his config.

#### Phase 1 results (2026-05-15)

Samples generated under `knos-digest/{kintu,mikey,vb}/2026-05-{14,15}.md`.

- **Kintu — fails hard gate.** 1 item on 5-14 (score 0.327, borderline), 0 items on 5-15. Confirms HN `ux_design` is too sparse. **Blocked on Substack design feed additions.** Twice-weekly cadence will help but doesn't solve it alone.
- **Mikey — borderline pass.** 6 items on 5-14 (decent quality: Needle distillation, software architecture); 2 items on 5-15 with one HN-rant ("AI is making me dumb") slipping through. Twice-weekly cadence improves the per-send average. Threshold raise 0.35 → 0.40 deferred — re-evaluate after first two real sends.
- **VB — volatile.** 4 items then 0. Likely a `freshness_days` / `suppress_delivered` interaction, not a threshold issue. Investigate separately.

#### Format gaps to fix before any external send

Visible in the samples — fine for VB, confusing for Mikey/Kintu:

1. `_digest_id: 6_` line — engineering metadata; hide for non-VB users
2. `topic: 0.413` — exposes internal scoring; remove or replace with a human label
3. `_No selected items for this run._` — bad cold-start experience; **skip-send on zero-item days** rather than render an empty digest
4. Empty trailing `Notes:` field on every item — feels templated; drop unless populated
5. Missing karma and 💬 top-comment blurb — parity gap already tracked in `NEXT.md`

### Phase 2 — Close the smallest renderer gaps

Only what is needed to make the digest feel polished to a stranger:

- Hide `digest_id` for non-VB users
- Remove raw `topic: 0.413` scoring from item metadata
- Drop empty `Notes:` lines
- Skip rendering/publishing empty external-user digests
- Include author karma and 💬 top-comment blurb in the modular renderer
- Skip the engagement section — it is a VB-only feature and would confuse external users

### Phase 3 — Send

Prerequisite: Phase 2 renderer fixes are done, Mikey has at least 3 selected items, and Kintu has at least 3 selected items after source additions.

1. Use `scripts/send_whatsapp_digest_prompt.sh --user <id> --date YYYY-MM-DD` or the daily delivery wrappers to produce/send the website URL.
2. Send Mikey first using the message above.
3. **Wait 24 hours before sending Kintu** — she is family, lower stakes to delay, and one real-world data point is worth more than a parallel send.
4. After Mikey's first reply (or 24h silence), send Kintu.

### Phase 4 — Observe manually for one week

- Optionally log only material observations in `pm/launch_log.md`: date, user, what changed for the next send.
- Do not build feedback infra during week 1. Goal is answering the strategy questions in `PM_NEXT.md`, not automating anything.
- After 5–7 sends each, decide:
  - Is the website page readable enough on mobile?
  - Is Mikey's persona assignment correct?
  - Does Kintu have enough source coverage?
  - Is there a repeated enough reply pattern to justify a real feedback feature later?

### Requirement Code Changes

Implement the smallest code changes needed to make the manual launch reliable.

1. **Renderer polish**
   - Add a `--audience internal|external` option to `knowledge_os.render_digest`, defaulting to `external` when the user is not `vb`.
   - For `external`, hide `digest_id`, hide raw topic scores, drop empty `Notes:`, and keep item metadata readable: score, author, source, and date.
   - Return a non-zero exit or a clear `NO_ITEMS` status when an external digest has zero selected items, so publish/send scripts can skip it.

2. **Content enrichment parity**
   - Populate modular digest rows with author karma and top-comment blurb when available.
   - Prefer existing stored `item_content` records for comments/summaries; only fetch live HN details during enrichment if the data is missing.
   - Keep enrichment separate from selection/ranking so Scala remains responsible only for choosing items.

3. **Kintu source coverage**
   - Add 4–6 design/product feeds to `config/sources.example.json` or a per-user source config if the source is too specific.
   - Re-run Kintu dry runs and keep her blocked until twice-weekly output consistently reaches at least 3 items.

4. **WhatsApp prompt helper**
   - Add `scripts/send_whatsapp_digest_prompt.sh --user <id> --date YYYY-MM-DD`.
   - Validate that `knos-digest/<user>/<date>.md` exists and has selected items.
   - Print the digest path, GitHub URL, and user-specific WhatsApp message.
   - Do not send anything automatically.

5. **Launch log template**
   - Add `pm/launch_log.md` with a small table for date, user, sent link, observation, and next change.
   - Keep it human-written; do not wire it to the feedback tables.

#### Implementation status (2026-05-15)

- Renderer polish is implemented for external users: no `digest_id`, no raw topic score, no empty `Notes:`, and every item includes `published: YYYY-MM-DD`.
- Empty external digests fail with `NO_ITEMS` instead of producing a sendable empty artifact.
- Daily catalog refresh is separated from digest sending via `scripts/run_catalog_ingest.sh`; Tuesday/Friday digest runs can use `--skip-ingest` after the daily catalog job has populated new items.
- `scripts/send_whatsapp_digest_prompt.sh` prints the digest path, GitHub URL, and user-specific WhatsApp message without sending anything.
- Kintu source coverage now includes UX Collective, Nielsen Norman Group, The Looking Glass, Proof of Concept, Some Designers, Digital Psychology AI, and Soren Iverson feeds.
- Mikey is tuned to `min_topic_score: 0.42` and `freshness_days: 10`; this excludes the observed `0.413` low-signal AI rant while keeping stronger AI-agent/LLM items.

### Delivery surface: site page

The personal site at `bvaibhav.info` renders the shared digest at `/knos-digest` from `public/data/knos-digest.json`. WhatsApp messages use persona-filtered links with compact persona codes and date pins.

**Pros of a site URL**
- Far better mobile reading — GitHub markdown on phones has UI chrome and login nags
- Feels like a product, not a leaked file
- Can render category grouping, read state, author meta cleanly
- One stable URL per user; can add light interactivity later (reactions, save)

**Cons**
- Requires per-user route + per-user JSON export, plus a site deploy on each digest run — couples digest cadence to site cadence
- Site is public; identifiable URLs (`/knos-digest/mikey`) leak names and reading interests. Mitigation: obfuscated slugs (`/knos-digest/m-7a3f`), but still indexable unless `noindex` is set
- More moving parts before we even know the content is valuable

**Decision for launch**: use the existing site page rather than GitHub markdown. Keep markdown as the source artifact and fallback archive.

### Explicit non-goals for this launch

- WhatsApp Business API / automation
- Link click tracking
- External-user dashboard
- Reply parsing
- Feedback capture/storage/parsing
- Email fallback

These remain deferred until real reply data exists.

---

## Open Questions

- Is a GitHub markdown link readable enough on mobile?
- Do Kintu and Mikey open the link when sent over WhatsApp?
- Do they reply with enough signal to tune future digests?
- Is the digest too technical, too broad, or too sparse for Kintu?
- Is Mikey’s `ai_researcher + llm_researcher` persona assignment accurate?
- Is there enough repeated signal to justify building feedback later?
- At what user count does manual delivery become too expensive?

## Deferred

- WhatsApp Business API
- Automated sending
- Link tracking
- Reply parsing
- Feedback capture/storage/parsing
- External-user dashboard
- Email delivery
- **Per-user page on bvaibhav.info** — `/knos-digest/<slug>` with obfuscated slug + `noindex`; export per-user JSON from the digest pipeline. Trigger: a user complains about mobile readability or asks for a "real" link.

## Next Small Build

Add a helper script that prints the delivery prompt without sending it:

```bash
scripts/send_whatsapp_digest_prompt.sh --user mikey --date "$(date +%F)"
```

It should output:

- digest path
- GitHub URL
- suggested WhatsApp message

This keeps delivery manual while reducing copy/paste mistakes.
