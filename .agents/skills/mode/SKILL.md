---
name: mode
description: Switch between PM mode and Engineering mode for this session
user-invocable: true
allowed-tools: Bash(cat ~/.Codex/current-mode), Bash(echo * > ~/.Codex/current-mode), Bash(echo * >> ~/.Codex/current-mode)
argument-hint: "[pm|engineering|engg]"
---

Read the current mode from ~/.Codex/current-mode.

If an argument is given ("pm", "engineering", or "engg"), write it to ~/.Codex/current-mode and confirm. Treat "engg" as an alias for "engineering".

If no argument, show the current mode and ask which to switch to.

After switching to PM mode: apply a product management lens this session — start with problem framing, user impact, and outcome definition before implementation. Reference pm/PRODUCT_STRATEGY.md and pm/PM_NOTEBOOK.md.

After switching to Engineering mode: standard engineering focus — clean code, tests, architecture.

Always confirm what mode is now active and what changes about how you'll approach work.
