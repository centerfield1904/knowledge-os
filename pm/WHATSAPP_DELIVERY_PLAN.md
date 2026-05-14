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
bash scripts/publish_digest.sh --user kintu --date 2026-05-14
bash scripts/publish_digest.sh --user mikey --date 2026-05-14
```

Expected URL shape:

```text
https://github.com/centerfield1904/knowledge-os/blob/main/knos-digest/kintu/2026-05-14.md
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

## Feedback Capture

Ask for lightweight replies:

```text
1 good
2 not relevant
3 too basic
```

For now, manually map the reply to feedback events:

```bash
./venv/bin/python -m knowledge_os.feedback_events \
  --db knowledge_os.db \
  --user mikey \
  --item-id <item_id> \
  --action saved
```

This is intentionally rough. The goal is to learn whether the content is valuable before designing a full feedback loop.

## Open Questions

- Is a GitHub markdown link readable enough on mobile?
- Do Kintu and Mikey open the link when sent over WhatsApp?
- Do they reply with enough signal to tune future digests?
- Is the digest too technical, too broad, or too sparse for Kintu?
- Is Mikey’s `ai_researcher + llm_researcher` persona assignment accurate?
- Should feedback be explicit replies, link tracking, reactions, or read receipts?
- At what user count does manual delivery become too expensive?

## Deferred

- WhatsApp Business API
- Automated sending
- Link tracking
- Reply parsing
- External-user dashboard
- Email delivery

## Next Small Build

Add a helper script that prints the delivery prompt without sending it:

```bash
scripts/send_whatsapp_digest_prompt.sh --user mikey --date 2026-05-14
```

It should output:

- digest path
- GitHub URL
- suggested WhatsApp message

This keeps delivery manual while reducing copy/paste mistakes.
