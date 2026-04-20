# Darwin — Claude Code that heals its own crashes

**Submission for** Cerebral Valley x Anthropic "Built with Opus 4.7" hackathon (Apr 21–27, 2026)
**Team** Solo — Miles (Germany)
**Status** Building.

## Live demo (60s, runs today)
▶ **https://asciinema.org/a/ZIN3d4vrZLgWvPCx**

Watch: agent runs → API breaks → agent crashes → Darwin diagnoses + patches → agent resurrected → fix logged for fleet. Zero human input.

---

## The pitch
Every Claude Code session silently hemorrhages context on the same recurring tool failures — rate limits, missing files, bad diffs, hung processes, permission errors. Darwin puts a PostToolUse hook on every agent in a fleet: when a tool call fails, it captures the full failure context, extracts the minimal repair rule, and writes it to Claude's 4.7 file-memory. **The next agent across the fleet has the skill before it makes the same mistake.**

## The demo
5 Claude Code agents on the same bug-fix benchmark, 3 waves:
- **Wave 1** — baseline. 60% of agents hit the same 5 failure classes.
- **Wave 2** — after Darwin. Repeat failures drop 80%.
- **Wave 3** — fleet sync. Zero repeat failures, and live novel-failure propagation.

## Why Opus 4.7
- Native file-memory across sessions — rules persist without external DB
- Self-verification — agent checks its own fix before writing the rule
- Literal instruction-following — skill files apply exactly, no drift
- Adaptive thinking — cheap scan on common failures, `xhigh` on novel

## Foundation (shipped before hackathon week)
- `fixcache v0.4.8` — 583 passing tests, PostToolUse hook caching failure→fix pairs
- Lore codex — agent reliability knowledge base
- `lean-ctx` MCP — 89–99% input token savings
- 16 MCPs, 21 agents, 94 skills wired with 5-event hook coverage
- AI Factory — multi-LLM failure triage at $0.001/task

## Files in this repo
- [`darwin-application.pdf`](./darwin-application.pdf) — submission copy (PDF)
- [`APPLICATION.md`](./APPLICATION.md) — submission copy (markdown)
- [`BUILD-PLAN.md`](./BUILD-PLAN.md) — 6-day day-by-day execution plan

## Links
- Anthropic Opus 4.7: https://www.anthropic.com/news/claude-opus-4-7
- Hackathon: https://cerebralvalley.ai/e/built-with-4-7-hackathon

## Status updates
Will update this README with daily progress during build week.
