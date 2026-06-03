# Product Strategy

## Why / Who / What

**Why:** The amount of information has exploded past the point of being useful. Opening any news site feels overwhelming. I've found myself switching off entirely rather than tuning — which means missing things I'd actually care about. The problem isn't content quantity; it's attention cost.

**Who:** Initially me — an AI engineer who wants to stay connected to the frontier without the overwhelm. Now also Mikey (user #2), organically acquired — a PM interested in product strategy and LLM applications. He asked where I found an article I shared. That's the acquisition story: content as the referral.

**What:** A daily digest that curates information by personal interest profile, gets quieter over time (not louder), and shows what's worth engaging with — not everything that's happening.

---

## Problem Statement

I spend time deciding what to read, then forget most of it. After a while I stop reading entirely because the cost of starting is too high. A trusted filter would let me stay connected without the cognitive tax of triage.

---

## Target User

**User 1 — VB (me)**
- AI/ML background, 10+ years in data and mapping, now independent
- Located in Indore — intellectually isolated by geography; staying connected to the frontier matters more than it would in SF
- Strong topic opinions (AI/ML, data science, applied math, philosophy), occasional personal interests (parenting)
- Values depth over breadth; wants to finish reading a digest, not skim 30 items
- Habit: reads in the afternoon; doesn't want to start the day with news

**User 2 — Kintu (VB's wife)**
- UX / design background
- Persona: `ux_design`

**User 3 — Mikey (first organic external user)**
- AI researcher / LLM engineer background
- Came in through a shared article — he asked where it came from
- Doesn't want to configure anything; wants the value to arrive
- Personas: `ai_researcher` + `llm_researcher`

---

## Vision

A daily briefing that feels like a trusted peer filtered the internet for you. Not a feed, not a reader — something closer to a colleague saying "you'd probably care about this one." The right content earns attention; it doesn't demand it.

Done means: I open it daily, I finish it most days, and I occasionally think "I'm glad I saw this before everyone else."

---

## Goals

1. Every digest contains ≥2 stories the user reads fully (link clicks or read log sync)
2. Digest takes < 3 minutes to process on a normal day — not a reading burden
3. Adding a new user (after persona system) takes < 5 minutes of setup

---

## Non-Goals

- Not a social feed — no follower graph, no "trending with your network"
- Not real-time — the daily cadence is intentional; urgency is noise
- Not a news replacement — this surfaces ideas, not breaking events
- Not a recommendation engine — interest profile is explicit, not inferred from behavior (yet)
- Not a product for everyone — the persona system is for people with clear intellectual identities

---

## Key Metrics

| Metric | Current | Target | How to measure |
|--------|---------|--------|----------------|
| Stories clicked / digest | unknown | ≥2 | read log sync |
| Digests opened / week | ~7 (generated, not tracked) | 5+ | delivery confirmation |
| Time to first story click | unknown | < 30s | not yet measurable |

---

## Persona Model (v1 — May 2026)

### Problem it solves

Onboarding a new user currently requires enumerating topics + keywords manually — high friction, inconsistent quality. The persona layer introduces a shared vocabulary for interest profiles that makes onboarding near-zero for typical archetypes.

### Concept

A **persona** is a canonical, system-owned bundle of topics + keywords representing a recognizable intellectual archetype. Users are assigned one or more personas. The pipeline resolves personas → topics at runtime, merges them with any personal additions, and runs matching on the union.

### Taxonomy (v1)

| ID | Name | Core areas |
|----|------|-----------|
| `software_eng` | Software Engineer | programming languages, systems design, open source, tooling |
| `data_eng` | Data Engineer | pipelines, ETL, streaming, orchestration, warehouse |
| `data_scientist` | Data Scientist | statistical modeling, ML engineering, experimentation, analytics |
| `ai_researcher` | AI / ML Researcher | research papers, training, architectures, benchmarks, interpretability |
| `llm_researcher` | LLM Researcher | LLMs, prompting, RAG, agents, evals, fine-tuning, inference |
| `pm` | Product Manager | product strategy, user research, roadmapping, metrics, GTM |
| `ux_design` | UX / Design | interaction design, usability, design systems, accessibility |
| `applied_math` | Applied Mathematician | optimization, stochastic systems, probability, causal inference |
| `swe_infra` | Infrastructure / Platform | DevOps, cloud, distributed systems, reliability, observability |
| `startup_founder` | Founding Engineer | startups, fundraising, PMF, hiring, growth |
| `philosopher` | Philosophy / Thinking | epistemology, decision theory, rationality, mental models |

### User model

```json
{
  "user": {
    "identifier": "...",
    "timezone": "...",
    "personas": ["data_scientist", "llm_researcher", "philosopher"],
    "personal_topics": [
      { "name": "Parenting/Education", "keywords": ["parenting", "child development", ...] }
    ]
  },
  "delivery": { "type": "github", "path": "knos-digest/vb" }
}
```

`personal_topics` handles interests that don't fit any persona (e.g., Parenting — too personal to be a canonical archetype).

### Digest structure

Multi-persona digests are **unified**: topics from all personas are merged and deduplicated. The digest groups by topic, not by persona. No "as a PM..." sections.

### Onboarding delta

Before: ask for topic list + keywords (10-minute exchange).
After: assign 1-3 persona IDs in a config file (< 5 minutes).

### What's deferred

- User-defined keyword additions on top of a persona
- Persona weights (prioritize one persona over another)
- Self-serve selection UI
- Inferred personas from engagement patterns
- Persona discovery / quiz onboarding

---

## Decision Log

**2026-02-11** — Initial architecture: semantic matching, SQLite, WhatsApp delivery
**2026-02-13** — v2 migration: improved storage, better topic handling
**2026-04-30** — Fixed empty digest bug: `get_undelivered_item_ids` replaces `is_new` as display gate
**2026-05-13** — Persona model: canonical topic packages replace per-user topic elicitation; triggered by first organic user (Mikey)
**2026-05-30** — Decided to validate via real users instead of narrowing scope: send the current digest to Mikey and Kintu and ask for feedback rather than pre-deciding whether the product is "AI-only" or "all intellectual identities." UX fix shipped alongside: WhatsApp links now pin `?date=` to the digest's date so an old message reopens that day's items, not the latest export (a digest you skim three days later should still show what it described).
**2026-05-30 (message + page polish)** — Reworked the delivery surface before sending: (1) message copy dropped the "small digest: N items across <internal topic labels>" framing for a count-aware "Made you a digest — a few worth a look" (no taxonomy leak); (2) teasers now rank by HN points so the message leads with the strongest item, not file order; (3) casual empty-state ("Quiet one today — nothing worth sending your way. Back tomorrow.") replacing the preachy "protect your attention" version; (4) site subtitle corrected from "learns what matters over time" (untrue — no behavioral learning) to "remembers what it has already shown you — quieter over time, not louder" (true; the suppression behavior is the real differentiator). Per-user reality at decision time: Mikey avg 5.0 items/day (0 empty days), VB 2.9 (AI persona only — data_scientist/applied_math/parenting still produce 0), Kintu 0.2 (17/21 empty) — so design-source breadth is the next unblock for Kintu.
