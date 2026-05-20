# WhatsApp Delivery Plan

## Current Recommendation

Use manual WhatsApp delivery first. Do not build WhatsApp automation yet.

The immediate product question is whether Kintu and Mikey find the digest useful, not whether the delivery system is automated. A manually shared GitHub markdown URL is enough to test value.

## V1 Flow

Generate one digest per user:

```bash
bash scripts/run_user_digest.sh --user kintu --overwrite
bash scripts/run_user_digest.sh --user mikey --overwrite
```

Publish the rendered markdown and print the GitHub URL:

```bash
DATE="$(date +%F)"
bash scripts/publish_digest.sh --user kintu --date "$DATE"
bash scripts/publish_digest.sh --user mikey --date "$DATE"
```

Expected URL shape:

```text
https://github.com/centerfield1904/knowledge-os/blob/main/knos-digest/kintu/YYYY-MM-DD.md
```

## Suggested Messages

### Kintu

```text
Made you a small UX/design digest for today:
<github-url>

Can you tell me if even 1-2 links feel useful? If not, I’ll tune the sources.
```

### Mikey

```text
I made you a daily AI/LLM digest based on the article you asked about:
<github-url>

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

- **Kintu and Mikey**: twice-weekly, Tuesday and Friday.
  - Kintu: aggregating across 3–4 days solves the `ux_design` sparsity problem on HN
  - Mikey: lower social pressure than daily for a v1 external user; reads as "considered share" rather than "noise from VB"
  - Skips Monday (weekend carryover) and weekends
  - Tradeoff: loses topicality. Mitigated by keeping `freshness_days` short (7 for Mikey, 14 for Kintu)
- **VB**: stays daily — own reading habit, not a delivery question
- Cadence is enforced by *when the script is run*, not by the pipeline. `"cadence": "biweekly"` + `"send_days": ["tue", "fri"]` in `configs/users/{kintu,mikey}.json` documents intent.

### State of readiness

**Ready**
- Persona model + `configs/users/{kintu,mikey,vb}.json` exist
- Modular pipeline wired: ingestion → persona materializer → scoring → selection → render
- `publish_digest.sh` commits markdown and prints a stable GitHub URL
- Delivery decision frozen: manual WhatsApp share of a GitHub markdown URL
- Dry-run samples exist for Kintu, Mikey, and VB

**Gaps blocking a clean first send**
1. Modular renderer exposes internal metadata and has rough external-user formatting
2. Modular renderer is missing comment blurbs and author karma (parity gap, `NEXT.md`)
3. Kintu's source pool (`ux_design` on HN + current Substacks) returns <3 useful items
4. `send_whatsapp_digest_prompt.sh` helper not built yet

### Phase 1 — Dry run before sending anything

Goal: see what each user would actually receive before committing to a send.

1. Run `bash scripts/run_user_digest.sh --user kintu --overwrite` and `--user mikey --overwrite` against `knowledge_os.db`. Inspect the rendered markdown locally — do not publish.
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

1. Build `scripts/send_whatsapp_digest_prompt.sh --user <id> --date YYYY-MM-DD` — outputs path, GitHub URL, and suggested message body (see "Next Small Build" below).
2. Send Mikey first using the message above.
3. **Wait 24 hours before sending Kintu** — she is family, lower stakes to delay, and one real-world data point is worth more than a parallel send.
4. After Mikey's first reply (or 24h silence), send Kintu.

### Phase 4 — Observe manually for one week

- Optionally log only material observations in `pm/launch_log.md`: date, user, what changed for the next send.
- Do not build feedback infra during week 1. Goal is answering the strategy questions in `PM_NEXT.md`, not automating anything.
- After 5–7 sends each, decide:
  - Is markdown-on-mobile readable enough?
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

### Delivery surface: GitHub markdown vs. site page

The personal site at `bvaibhav.info` already renders my own digest at `/knos-digest` (source: `~/dev/projects/bvaibhav-info/src/app/knos-digest/page.tsx`, data from `public/data/knos-digest.json`). It's plausible to give Kintu and Mikey their own page (e.g., `/knos-digest/m-<slug>`) instead of a raw GitHub markdown URL.

**Pros of a site URL**
- Far better mobile reading — GitHub markdown on phones has UI chrome and login nags
- Feels like a product, not a leaked file
- Can render category grouping, read state, author meta cleanly
- One stable URL per user; can add light interactivity later (reactions, save)

**Cons**
- Requires per-user route + per-user JSON export, plus a site deploy on each digest run — couples digest cadence to site cadence
- Site is public; identifiable URLs (`/knos-digest/mikey`) leak names and reading interests. Mitigation: obfuscated slugs (`/knos-digest/m-7a3f`), but still indexable unless `noindex` is set
- More moving parts before we even know the content is valuable

**Decision for launch**: stay on the GitHub markdown URL for Phase 3. It is the cheapest way to test *whether the content is useful*. The site page is a Phase 5+ upgrade triggered by one specific signal: a user reports the markdown is hard to read on mobile, or asks for a "real" link. At that point:

1. Add a `/knos-digest/[slug]` dynamic route to the site
2. Have the digest pipeline export `public/data/knos-digest-<slug>.json` alongside the markdown
3. Set `noindex` on per-user pages; use unguessable slugs
4. Keep markdown as a fallback / archive

Tracked as a deferred item below.

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
