# PM_NEXT.md — Product Strategy Backlog

---

## Immediate

- [ ] **Wire modular digest runner** (engg) — Orchestrate the separated commands: Scala ingestion, Python topic scoring, Python subscription loading, Scala selection/ranking, Python rendering, feedback sync. The runner must not let digest generation trigger scrape or scoring implicitly.

- [ ] **Make rendering read digest membership** (engg) — Markdown generation should consume `digest_items` or Scala selection JSON. Ranking should not be duplicated in Python.

- [ ] **Populate separate content** (engg) — Store comments, extracted bodies, summaries, and source annotations in `item_content`; topic scoring config decides whether each content type participates.

- [x] **Global topic catalog from personas** (engg/product) — COMPLETE (2026-05-14: `personas/catalog.json`, `configs/users/{vb,kintu,mikey}.json`, and `knowledge_os.personas` materialize global topics + user subscriptions)

- [ ] **Delivery for Kintu and Mikey** — They can't browse GitHub. Current plan: shared markdown URL sent over WhatsApp. No email infra needed for now. Validate this is enough before building something more after the modular runner can produce per-user digests.

- [ ] **Validate Kintu's digest** — After first digest ships (`ux_design`), confirm topics resonate. UX/design content on HN is sparse — may need to add Substack feeds that cover design.

- [ ] **Validate Mikey's persona assignment** — After first digest ships (`ai_researcher + llm_researcher`), ask if topics feel right. Tune persona keyword sets if needed.

- [ ] **Fill Key Metrics baseline** — After a week of multi-user runs, record story click rates and digest quality signals in PRODUCT_STRATEGY.md.

---

## Strategy Questions to Resolve

- [ ] **Feedback loop for external users** — How do Kintu and Mikey signal what's good or bad? They're not on the read log workflow. WhatsApp reply? Link tracking? Needs a lightweight mechanism before the list grows.

- [ ] **Delivery format for non-technical users** — Kintu and Mikey won't sync a reading log. If markdown-over-WhatsApp is the format, is it readable enough on mobile? Consider whether a plain-text or simplified format serves them better than VB's current checklist-style digest.

- [ ] **Clarify implicit feedback signals** — "Gets better over time" is vague. What counts as signal — link clicks, ignoring digests entirely, explicit replies? Decide before building the feedback loop.

- [ ] **Resolve the weekly unfiltered view tension** — Is the weekly summary FOMO catch-up or awareness? Different purposes, different designs.

- [ ] **Persona weight question** — Should users eventually be able to weight personas (e.g., 70% data scientist, 30% PM)? Not blocking v1.

---

## Resolved

- [x] **Architecture split** — Done (2026-05-13): four independent modules defined: catalog/ingestion, topic scoring, subscriptions/digests, feedback/engagement
- [x] **Language ownership decision** — Done (2026-05-13): Scala for ingestion and selection/ranking; Python for ML scoring, customizability, rendering, and feedback parsing
- [x] **Historical topic scores** — Done (2026-05-13): target schema keeps scores by `scoring_config_id`
- [x] **Separate content model** — Done (2026-05-13): target schema includes `item_content` for comments/body/summaries outside canonical `items`
- [x] **Fill in Target User** — Done (2026-05-13): VB, Kintu, Mikey profiles in PRODUCT_STRATEGY.md
- [x] **Define Vision** — Done (2026-05-13): "A trusted peer filtered the internet for you"
- [x] **Define Goals** — Done (2026-05-13): 3 measurable outcomes in PRODUCT_STRATEGY.md
- [x] **Non-goals** — Done (2026-05-13): 5 explicit non-goals documented
- [x] **Taste Profiles / onboarding design** — Done (2026-05-13): Persona model designed and frozen; 11 canonical personas; users map to 1+ personas; `personal_topics` for anything outside taxonomy
- [x] **Pipeline runs broken** — Fixed (2026-05-13): venv recreated, numpy bumped to >=2.0 for Python 3.13 compat
