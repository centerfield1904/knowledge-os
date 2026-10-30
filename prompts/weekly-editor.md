# Build brief: knos weekly editor + link deep-dive

To use: open your LLM coding agent at the knowledge-os repo root and say `Read prompts/weekly-editor.md and follow it.` The edition format lives next to this file in `prompts/weekly-edition-template.md`.

Written 2026-10-30. Facts marked "verified" were checked against the repo on that date; re-check anything that matters before relying on it.

---

## What I want

I want to publish a weekly knos edition: a handful of links I picked from the week's daily digests, each with a short comment from me. Eventually this edition replaces what the website shows today (the daily persona list).

There are two jobs, and I may do the first one every day:

1. **Go deeper on a link.** From any digest item, pull more context without opening ten browser tabs: what the article actually says, what the HN thread thinks, a summary of all comments or just a subset, prior HN discussions of the same URL, and free-form questions to an LLM grounded in that material.
2. **Write the weekly edition easily.** Pick from the week's digests, write my take under each pick, reorder, preview, publish. Fixing grammar should be one keystroke away.

The wording is mine. The LLM is a research assistant and a proofreader, never a ghostwriter. There is no "suggest a take" or "rewrite this" button, and the grammar fix never changes what I said or how I said it.

## Who it's for

- **Me, writing.** I read in the afternoon, mostly on the daily digest page. Writing happens in free time, on weekends and evenings, never in deep-work blocks. So the tool has to be cheap to open and cheap to resume halfway through.
- **Readers.** Mikey (AI/LLM), Kintu (UX/design), and whoever gets the link next. They get the weekly link on WhatsApp and read it on bvaibhav.info. For them, my take is the point. The link list alone is what the daily digest already does.

## What success looks like

- Clicking a digest item and reading a thread summary takes under 30 seconds, and repeat views are instant because they're cached.
- A 3–5 pick edition takes as long as the writing takes. I never hand-copy a URL, a points count or an HN id.
- The grammar fix shows a diff I can review at a glance, and it never changes meaning, word choice or tone.
- Every claim in a thread summary links to the comment it came from, so I can check it in one click.
- I use it two weeks in a row without going back to the browser plus a scratch file. That's the real test.

Acceptance run, using my actual W43 contenders (I'd been collecting these by hand in a NEXT.md list):

| My note | Link | Where it came from |
|---|---|---|
| On decision models, jev et al | https://docs.liquid.ai/lfm/models/decision-models | Not itself a digest item. I reached it from "Introducing LFM3: Every Modality for Specialized Intelligence" (2026-10-27 digest, HN 50262229). Exercises the `via:` pick. |
| Compare AI writing with food that tastes the same, and write a post on this | https://www.bolkunov.com/p/on-ai-writing | "On AI writing", 2026-10-20 digest, HN 50171771, ↑96. This one is also a State Overflow post seed, not only a weekly take. |
| On building a robotics company | https://news.ycombinator.com/item?id=50155616 | Digest title "A robot I didn't expect to build" (spectrum.ieee.org), 2026-10-19 digest, ↑72. My note is about the thread more than the article. |

Done means I can build that edition with the tool, deep-dive the robotics thread, ask one follow-up question, and grammar-fix a take, all without opening a browser tab or copying anything by hand.

---

## What already exists (verified 2026-10-30)

- `src/knowledge_os/weekly_summary.py` has `draft`, `finalize` and `whatsapp` subcommands. `draft --week YYYY-Www` aggregates the Mon–Sun daily files in `knos-digest/`, dedupes by URL and HN URL (this matters: LFM3 shows up in both the 10-27 and 10-29 digests), and writes a checkbox file with a one-line `Note:` per item to `knos-weekly/drafts/`. `finalize` keeps checked items, groups them by persona/category and writes `knos-weekly/YYYY-Www.md`. Tests are in `tests/test_weekly_summary.py`. It's fine for curation and wrong for writing: one-line notes, persona grouping, no per-week intro.
- `scripts/publish_weekly_summary.sh` finalizes, commits, pushes, triggers the website workflow and prints or sends the WhatsApp message. It runs `git push origin HEAD`, but at least one checkout names its only remote `upstream`, so check which remote this machine uses.
- `weekly_url()` already defines the share URL as `https://www.bvaibhav.info/knos-digest?view=weekly&w=YYYY-Www`.
- Only one draft has ever been made (`knos-weekly/drafts/2026-W27.md`), and no edition has been finalized. Nothing depends on the current final format, so replacing it is cheap.
- **Website (`~/dev/projects/bvaibhav-info`)**: `scripts/export-digest.ts` reads only `knos-digest/*.md` (`DIGEST_PATH` env override) into `public/data/knos-digest.json`. `src/app/knos-digest/page.tsx` reads `d`/`date` and has no weekly view. The publish is a GitHub Action, `update-digest.yml`. Look at how the Action checks out knowledge-os before adding a second input directory.
- **HN data**: there is no comment fetching left in the Python package (the old `engagement.py` is gone). `item_content` is empty. `knowledge_os.db` is gitignored and may be stale or missing on this machine, so the deep-dive must work from digest files plus live APIs, and use the DB only as an optional speed-up.
- **No LLM integration exists anywhere in the repo.** This is the first.
- **Downstream reader**: the `/next-x` skill (in `~/.claude/skills/next-x/SKILL.md`) reads `knos-weekly/YYYY-Www.md` and the drafts as its main pool of "what he actually read". Update it to understand the new format in the same change.
- **The knowledge-os repo is public.** Anything committed under `knos-weekly/`, drafts included, is public.

---

## About me: my work and how I write

This section is here so the tool fits what I actually publish. It only contains what is already public on bvaibhav.info, because this repo is public. Keep it that way: no personal or family details here, in edition files, or in anything else that gets committed. The sources at the end of this section are the current versions; if they disagree with this, they win.

### My work

- Trained in operations research at Columbia (optimization, stochastic systems).
- Founding engineer at Mapsense, from before the company formally existed through its acquisition by Apple in 2015.
- About ten years at Apple Maps: ML systems, large-scale data infrastructure, geospatial systems, aerial imagery, production pipelines across 20+ countries. In my last year I designed the architecture for an internal agentic platform, which is where I learned that agents expose the debt a system already carries.
- I left Apple in 2026 and moved to Indore. I now work independently on one question: how probabilistic AI becomes dependable in real systems, especially when it has to run local, offline and small. The site splits it into two questions. **Dependability** covers determinism, reproducibility, verification, calibration and knowing when not to answer. **Intelligence under constraint** covers small and local models, edge inference, privacy, latency, cost and offline operation.
- Testbeds: the Acropolis Edge Lab, a student research cohort in Indore working on offline Hinglish voice Q&A and people counting on laptops and Android phones; physical and geospatial systems; agentic systems and operations automation.
- I also do advisory work with teams putting AI into real operations. Client work is never a source for a published take, and clients are never named. If a take only makes sense with client context, it stays out of the edition.
- State Overflow is my Substack, applying statistics to everyday decisions. I'm working through McElreath's *Statistical Rethinking*, so base rates, shrinkage and measurement error show up in how I read things.

### Where the weekly edition fits

- The site is canonical. X carries condensed reading observations, and LinkedIn carries occasional essays. The weekly edition is my reading observations in full, on the site, and `/next-x` picks its X candidates from it.
- The takes that carry the most weight add something the source doesn't say: a test I ran, a number I measured, a bet specific enough to be wrong, or a connection from my own work (a decade of production maps, the Acropolis students, Indian languages and users). Plenty of takes will be a single line on why I read something, and that's fine too.

### How I write

What my published writing does, drawn from my Bangalore note (`notes/small-ai-real-systems.md` on the site) and my State Overflow voice rules:

- First person, conversational, reflective. I open with a specific moment rather than a general observation. In the Bangalore note, a stranger at a co-working cafe tells me he can fine-tune a model to be deterministic, and I ask him one question back.
- I label my position plainly. "My take:" appears verbatim in my notes.
- One concrete number does more than a paragraph: "the same base model with retrieval, untrained, beat the fine-tuned version closed-book (60.35 against 56)".
- I push back on big claims with a question.
- A short sentence after a long one. Dry humor, never performed. A sentence over a bullet list when a sentence will do.
- Data informs but doesn't dominate. When I'm uncertain, I say it plainly instead of stacking qualifiers.

What I avoid, and what the tool must never introduce:

- Moralizing or prescribing ("you should"), productivity or hustle framing, startup-speak, motivational tone.
- "X, not Y" constructions where Y is a straw man. Say what the thing is.
- Future-tense announcements. Evidence outranks intention: mostly past tense, some present, rarely future.
- Words, bets or results in my name. The LLM can say what a bet would be about. The bet and any result are mine to write.

My English is Indian English and fairly informal, and the grammar fix has to respect that. These fixture sentences are verbatim from my published note:

| Sentence | Expected |
|---|---|
| "Its more about knowing the confidence (the degree of rightness)." | `Its` → `It's`. Nothing else. |
| "The problem still lies in educating them of it's side effects." | `it's` → `its`. Leave "educating them of" alone. |
| "And even though he didn't, I will anyday have this conversation rather than sit alone in a cafe." | `anyday` → `any day`. The sentence still starts with "And". |
| "At a small gathering focussed on Small AI, I saw that question come up again and again." | Unchanged. "focussed" is a valid spelling and "Small AI" is my capitalization. |
| "Why don't Anthropics and OpenAIs of the world do that every night?" | Unchanged. The construction is deliberate. |
| "Most of my other conversations were around agents - in Bangalore, everyone is building agents." | Unchanged. I use a spaced hyphen as a dash; don't convert it to an em dash. |

### What this means for the tool

- **Grammar fix:** calibrate on the fixtures above. When in doubt, leave the sentence alone.
- **Deep-dive presets:** start with questions I'd actually ask, and keep them in an editable config file rather than in code. Examples:
  - How strong is the evidence: sample size, baseline, and whether the benchmark measures the claim?
  - Would this hold up in production: determinism, reproducibility, failure modes?
  - What changes on a small, offline or on-device model?
  - Who in the thread has actually built or run this?
  - Has HN discussed this before, and what has changed since?
- **Deep-dive answers:** plain and specific. Numbers over adjectives, sources cited, uncertainty stated once and plainly. No hype words.
- **Editor microcopy:** plain labels. No streaks, nudges or praise. Empty states say what's there ("No picks yet").
- **Website (phase 3):** follow the copy rules in `bvaibhav-info/CLAUDE.md`: no unfinished signals, no sentences explaining why the page is arranged the way it is, and reader-facing labels from `READER_LABELS` instead of raw persona names.

### Sources

- `~/.claude/CLAUDE.md`, the Voice & Tone section
- `~/dev/projects/bvaibhav-info/src/app/about/page.tsx` and `src/content/research.ts`
- `~/dev/projects/bvaibhav-info/CLAUDE.md`, the copy rules and the `/knos-digest` route notes
- `~/dev/projects/bvaibhav-info/notes/*.md`, my published notes
- `~/dev/projects/stateoverflow/CLAUDE.md`, section 1 (author's voice)
- `~/.claude/skills/next-x/SKILL.md`, the weekly bar and channel rules

---

## Job 1: deep-dive on a link

Input: a digest item (HN id or URL), or any URL I paste.

Material to gather, cached to disk so a second look is free:

- **The article.** Fetch and extract readable text (look at `trafilatura` or `readability-lxml`; handle PDFs since arXiv links are common). If it's paywalled or the extraction fails, say so plainly and don't guess at its contents.
- **The HN thread.** `https://hn.algolia.com/api/v1/items/<id>` returns the whole nested tree in one request. Firebase (`https://hacker-news.firebaseio.com/v0/item/<id>.json`) gives `kids` in HN's ranked order. Verify whether Algolia's `children` keep that order; if they don't, use Firebase order for anything that says "top".
- **Prior discussions of the same URL.** Algolia search restricted to the `url` attribute. Show the dates and comment counts, and offer to summarize what changed since then.
- **Author context**, only if the LLM backend has web search. Cite URLs.

Comment subsets I want to be able to ask about:

- all comments
- top-level comments only
- the top N by HN rank
- one subtree (I paste or click a comment id)
- comments by a given user
- comments matching a keyword
- LLM-classified slices: people claiming firsthand experience, the strongest disagreements with the article, and "what are people actually arguing about"

Rules for anything the LLM says about a thread:

- Every claim cites the comment id(s) it came from, rendered as `https://news.ycombinator.com/item?id=<comment id>` links.
- Quotes are verbatim and checked by string match against the fetched comment text. A quote that fails the check is dropped and flagged, not shown.
- Long threads get chunked or map-reduced rather than truncated. If something is cut, the answer says what was left out.

Free-form Q&A: I can ask any question about the link, grounded in the article plus the thread (or a chosen subset). Answers keep the same citation rules. Q&A history is kept per pick in the local cache.

One action I want on every deep-dive result: **"add to this week"**, which drops the item into the current week's draft as a contender, optionally with a first-line take I type right there. This is what makes daily use work: I dive during the afternoon read, add the item with a half-sentence, and polish it on the weekend.

Where research lives: a local, gitignored cache keyed by pick id (for example under `~/Library/Application Support/knowledge-os/research/`, next to the existing `cron/` state directory). Never in the edition file. If I want to sync research across my machines later, that's a separate decision.

## Job 2: writing the weekly edition

- Open the week. The editor lists every item from that week's daily digests (reuse the existing aggregation and dedupe in `weekly_summary.py`), with title, source, points, date, persona, and links to the article and the HN thread.
- Pick an item. It becomes a pick with an empty take in the draft. A pick with an empty take is a contender; finalize drops it.
- Add a URL that isn't a digest item and attach it to the digest item I found it through (the `via:` pick in the template).
- Write the take. Plain prose, one paragraph per line, no hard wraps. Optional week intro.
- Reorder picks. Order is mine, not grouped by persona.
- Deep-dive opens beside the take, for the pick I'm on. Inserting a comment permalink into the take is one action.
- Preview the edition roughly as the website will render it, and preview the WhatsApp message.
- Publish through the existing path: finalize, then commit and push, then trigger the website, then the WhatsApp message. Rework `weekly_summary.py` and `scripts/publish_weekly_summary.sh` rather than building a parallel path.
- The draft markdown file is the source of truth. The editor autosaves to it, and I can also edit it by hand in any editor or through an LLM agent without breaking anything.
- A pick can carry a "post idea" flag (the AI-writing one above is a post seed). `/next-x` should be able to read that flag.

The edition format is in `prompts/weekly-edition-template.md`. Treat it as a proposal: change it if the editor or the website needs something different, but keep the properties it's built around. The file reads cleanly as plain markdown, markers are HTML comments in the repo's existing style, the draft and final share one format, and research never lands in the file.

## Grammar fix

This is the part most likely to go wrong, so the rules are strict:

- Fix spelling, grammar, punctuation, agreement, and missing or wrong articles. Nothing else.
- Don't change word choice unless a word is an outright error. Don't restructure sentences, merge or split them, add or remove hedges, adjectives or claims, or change the tone.
- Keep my spelling variant consistent with what I already used.
- Keep line structure: one paragraph per line in, one paragraph per line out.
- Scope is the current selection or the current take, never the whole edition at once.
- Show it as a diff. I accept each change or all of them, and nothing is ever applied silently. Return "no changes" when there's nothing to fix.
- Guardrail: if the proposed fix changes more than a small share of words (start around 15% at the word level and tune it), show a warning that it looks like a rewrite instead of offering it as a fix.
- Test it with a fixture of my own sentences, some with errors and some deliberately informal but correct, starting with the table in "How I write" above. The informal-but-correct ones must come back unchanged.

---

## Explore the options before writing code

I don't know what shape this should be. Lay out the realistic options, compare them, and recommend one. Include at least these:

1. **VS Code extension.** A webview side panel for the deep-dive, commands and code actions on the draft markdown (grammar fix as a diff, insert pick, open thread summary). Note how it gets installed locally without the Marketplace.
2. **Local web app.** Python (FastAPI or Flask with htmx or plain JS), started with one command, opened at localhost. Three panes: week's items, draft, research. It matches the repo's stack, and it could later become a private mode of the website.
3. **Obsidian plugin.** I already write daily and weekly notes in Obsidian (`~/obsidian-vault`). Consider whether the draft lives in the vault or the plugin points at the repo.
4. **LLM-agent-native.** Agent skills or slash commands (for example `/knos-dive <hn id>`, `/knos-week`, `/knos-proof`) plus the markdown file open in any editor. This is the least to build and needs no separate API key, because the agent is the LLM. It's also the weakest as an "editor".
5. **Terminal UI** (Textual).
6. **Anything else worth naming**: a Raycast extension, a native macOS app, a private page hosted inside an LLM chat app. Say in a line why each one isn't the pick, if it isn't.

For each option, give:

- **Seconds from seeing a link to reading a thread summary.** This decides whether I'd use it daily.
- **Whether writing feels like writing** or like filling in a form.
- **Daily friction**: does something need to be running, and can I use it from the machine I read on?
- **Build effort and upkeep.**
- **What survives if I switch later.**
- **How the LLM is plugged in.**

Architecture constraint, whichever UI wins: put the core in Python modules with CLI subcommands that emit JSON (something like `knowledge_os.deep_dive` and a reworked `knowledge_os.weekly_summary`). That covers HN and article fetching, caching, LLM calls, and parsing and writing the edition format. The UI stays a thin shell over that. Then the UI choice is reversible, an LLM agent can call the same commands, and the tests stay in pytest.

Hybrids are fine. For example, an LLM-agent-native first version over the Python core, with a real editor UI later, is a legitimate recommendation if it gets me writing sooner.

### Plugging in the LLM

- Compare two backends: an LLM API with a key, or shelling out to a headless LLM agent CLI that runs on my existing subscription. Say which you recommend for each job, since deep-dive and grammar fix may want different answers.
- Default to the latest, most capable models. At my volume (a few dozen calls a week), cost isn't a constraint, so pick for quality. Check the provider's current documentation for model ids and API details before wiring anything.
- Keys never go in the repo. `config.json` is gitignored, but prefer an env var or a file under `~/.config/knowledge-os/` (where `cron.env` already lives).
- Put the backend behind one small interface so it can be swapped.

## The website, eventually

The weekly edition replaces what the website shows, but not in the first build. Sequence it:

- **Phase 1**: the Python core plus CLI, the new edition format, and tests.
- **Phase 2**: the editor UI I approve.
- **Phase 3**, in `bvaibhav-info`: export reads `knos-weekly/YYYY-Www.md` (finals only, never drafts), and `/knos-digest?view=weekly&w=YYYY-Www` renders an edition with the takes as the main content. Then propose, without doing it yet, how the weekly view becomes the default and where the daily list goes.
- Old WhatsApp daily links (`&date=YYYY-MM-DD`) must keep working through all of this.

---

## Questions to ask me before building

1. **Week label.** The existing code labels an edition by the Mon–Sun week its items came from: `draft --week 2026-W43` reads 10-19 to 10-25. In my hand-kept list I called the same picks "W44 contenders (from the W43 digests)", which names the week I publish in. Which label do I want?
2. **LLM backend.** API key, a headless LLM agent CLI, or a split by job. Give me your recommendation with the question.
3. **Drafts in git.** The repo is public. Do drafts get committed (my half-written takes become public) or stay local until finalize?
4. **Publish cadence.** The existing plan says finalize and send on Monday. Still true?

Ask these together in one round, with your recommendation for each, then wait.

## How to work

- PM first: before code, write a short plan covering the problem, success criteria, the options comparison with a recommendation, the phases, and what's out of scope. Wait for my approval. If the `/build` skill is available, use it.
- Follow the repo conventions in `CLAUDE.md`: `uv pip install <pkg> --python venv/bin/python`, never bare pip; `venv/bin/python` only; errors and warnings to stderr; pytest with `tmp_path`; mock all network and LLM calls in tests; don't import `sentence_transformers` in unit tests.
- Keep docs current in the same commit: README (usage for the new commands and the editor), `knos-digest/README.md` if the export changes, `CLAUDE.md` for the new format and conventions, `NEXT.md` (move the weekly-summary item to Completed when done, add a decision-log entry for the UI choice), and the `/next-x` skill.
- Never hard-wrap prose in markdown files. One paragraph per line.
- Commit per phase. Ask before pushing.
