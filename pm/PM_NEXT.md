# PM_NEXT.md — Product Strategy Backlog

---

## Immediate

- [ ] **Build persona model + multi-user config** (engg) — `personas/` dir, `configs/users/` dir, pipeline resolves personas → topics at runtime. Highest priority — blocks Kintu and Mikey.

- [ ] **Delivery for Kintu and Mikey** — They can't browse GitHub. Current plan: shared markdown URL sent over WhatsApp. No email infra needed for now. Validate this is enough before building something more.

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

- [x] **Fill in Target User** — Done (2026-05-13): VB, Kintu, Mikey profiles in PRODUCT_STRATEGY.md
- [x] **Define Vision** — Done (2026-05-13): "A trusted peer filtered the internet for you"
- [x] **Define Goals** — Done (2026-05-13): 3 measurable outcomes in PRODUCT_STRATEGY.md
- [x] **Non-goals** — Done (2026-05-13): 5 explicit non-goals documented
- [x] **Taste Profiles / onboarding design** — Done (2026-05-13): Persona model designed and frozen; 11 canonical personas; users map to 1+ personas; `personal_topics` for anything outside taxonomy
- [x] **Pipeline runs broken** — Fixed (2026-05-13): venv recreated, numpy bumped to >=2.0 for Python 3.13 compat
