# Prioritization

> The most important PM skill is deciding what *not* to build. Every item you add is a cost — to focus, to complexity, to maintenance.

---

## RICE Framework

**RICE Score = (Reach × Impact × Confidence) / Effort**

| Factor | Question | Scale |
|--------|----------|-------|
| **Reach** | Users affected per week | # users |
| **Impact** | How much does it move the needle per user | 3=massive, 2=high, 1=medium, 0.5=low |
| **Confidence** | How sure are the Reach and Impact estimates | 1.0=high, 0.8=medium, 0.5=low |
| **Effort** | Person-weeks | weeks |

---

## Active Backlog

| Item | Reach | Impact | Conf | Effort | RICE | Status |
|------|-------|--------|------|--------|------|--------|
| Persona model + multi-user config | 3 | 3 | 0.8 | 1 | **7.2** | next |
| Delivery for Kintu + Mikey (markdown URL via WhatsApp) | 2 | 3 | 0.8 | 0.5 | **9.6** | next |
| Feedback loop for external users | 3 | 2 | 0.5 | 1.5 | **2.0** | backlog |
| Substack feeds tuned for ux_design (Kintu) | 1 | 2 | 0.8 | 0.5 | **3.2** | backlog |
| Redesign digest format for mobile (non-technical users) | 2 | 1 | 0.5 | 1 | **1.0** | backlog |
| Local LLM for summarization | 3 | 1 | 0.5 | 2 | **0.75** | parked |
| Dashboard for external users | 2 | 1 | 0.5 | 2 | **0.5** | parked |

**Delivery for Kintu + Mikey scores highest** — even though it's simple work, the impact is a 3 because without it users 2 and 3 get nothing. Build it as part of the persona rollout.

---

## Decision Log

| Date | Decision | Why |
|------|----------|-----|
| 2026-05-13 | Persona model over per-user topic elicitation | Onboarding Mikey exposed that asking for keyword lists is a bad first interaction. Personas make it a role assignment instead. |
| 2026-05-13 | WhatsApp website link over email delivery | Email infra (SMTP, app passwords) was avoidable; the useful delivery surface is a persona-filtered `bvaibhav.info/knos-digest` link sent over WhatsApp. |
| 2026-05-13 | Separate DB per user | Engagement tracking, delivered items, and topic scores shouldn't intermingle across users. Cheap to keep separate; expensive to untangle later. |
| 2026-05-13 | No dashboard for external users (yet) | Kintu and Mikey don't need a dashboard. They need a daily link. Build the dashboard when the number of users makes the link unscalable. |
