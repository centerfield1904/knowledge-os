# Knowledge Weekly — {{YYYY-Www}}
<!-- knos-weekly: {{YYYY-Www}} | {{Monday YYYY-MM-DD}} to {{Sunday YYYY-MM-DD}} | status: draft -->

<!-- knos-weekly-intro -->
{{Optional. A few lines on the week as a whole, only if something ties the picks together. Delete the whole block if nothing does.}}
<!-- /knos-weekly-intro -->

<!-- knos-weekly-pick: hn-{{HN item id}} -->
### {{Title — the digest title by default; I can rename it}}
🔗 {{article URL}}
→ HN: https://news.ycombinator.com/item?id={{HN item id}}
from: {{YYYY-MM-DD}} digest | source: {{hackernews|substack|economist}} | ↑{{points}} | by {{author}} | persona: {{persona_id}} | category: {{category}}

<!-- knos-weekly-take -->
{{My take, in my words. One paragraph per line, never hard-wrapped. One sentence is fine. I can link a specific HN comment inline: https://news.ycombinator.com/item?id={{comment id}}}}
<!-- /knos-weekly-take -->
<!-- /knos-weekly-pick -->

<!-- knos-weekly-pick: url-{{first 10 hex chars of sha1(normalized URL)}} -->
### {{Title — fetched from the page, editable}}
🔗 {{a URL that was not itself a digest item}}
via: {{parent digest title}} — {{parent HN or article URL}} ({{YYYY-MM-DD}} digest)

<!-- knos-weekly-take -->
{{My take.}}
<!-- /knos-weekly-take -->
<!-- /knos-weekly-pick -->

<!--
Format rules (delete nothing below this line; the parser ignores comments):

- Picks appear in the order I put them, not grouped by persona. Persona and category stay as metadata so the website can still filter.
- Pick ids: `hn-<id>` when the pick has an HN thread, else `url-<sha1 prefix>` of the normalized URL (lowercased host, no trailing slash, no utm_* params).
- A `via:` line replaces the `from:` line when the pick is a link I reached from a digest item rather than the item itself.
- Draft path: knos-weekly/drafts/YYYY-Www.md. Final path: knos-weekly/YYYY-Www.md. Same format for both; finalizing flips `status: draft` to `status: final` and validates.
- A pick with an empty take is a contender, not a pick. Finalize drops it with a warning on stderr.
- Research notes, thread summaries and LLM answers never go in this file. The repo is public.
- Markers are HTML comments, matching the existing `<!-- knos-persona: ... -->` and `<!-- knos-weekly-item: ... -->` idiom, so the file still reads cleanly as plain markdown on GitHub.
-->
