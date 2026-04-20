# Darwin Hackathon Build Plan (Apr 21–27)

## North star
5 Claude Code agents on same bug-fix benchmark → 3 waves → visible curve.
Demo video < 3 min. Ship working code + repo.

## Swarm verdict baked in
- DROP: full fleet orchestration, Alibaba async pattern extraction (latency risk), emergent-learning claims
- KEEP: fixcache hook base, file-memory propagation, fleet visualization, pre-identified failure classes
- PIVOT framing: "self-healing tool crashes" not "emergent fleet learning"

## Existing foundation (reuse, don't rewrite)
| Asset | Status | Used for |
|-------|--------|----------|
| `darwin-mvp/darwin_harness.py` | scaffold exists | fail→fix→verify loop |
| `darwin-mvp/agent.py` | scaffold exists | runnable sample agent |
| `fixcache v0.4.8` | 583 tests pass | PostToolUse failure capture |
| `lean-ctx` MCP | live | compressed failure context |
| Lore codex | knowledge base | rule template source |
| 94 skills framework | wired | rule deployment target |

## Day-by-day (solo, 6 days)

### Day 1 (Apr 21) — loop closure
- Wire fixcache PostToolUse → rule extractor → skill file writer
- 5 pre-identified failure classes hard-coded: rate-limit, missing-file, bad-diff, permission-denied, hung-process
- Single-agent happy path: agent fails, rule written, second run of same agent uses rule
- Smoke test: `python darwin_harness.py --scenario rate-limit` shows full cycle

### Day 2 (Apr 22) — fleet mechanics
- Spawn 5 Claude Code subagents in parallel (Agent tool with isolation=worktree)
- Shared skills dir = fleet memory
- Rule write by any agent visible to next subagent spawn
- Metric: repeat-failure count drops on Wave 2 vs Wave 1

### Day 3 (Apr 23) — benchmark + metrics
- Freeze the bug-fix benchmark (5 bugs, reproducible)
- Logger: wave, agent-id, failure-class, recovered?, time-to-fix, rule-hit?
- SQLite + live tail for demo overlay
- 3 waves wired end-to-end

### Day 4 (Apr 24) — visualization
- Terminal dashboard (rich/textual) OR simple web page
- 5 agent panes + rolling metrics + rule-propagation feed
- Test recording workflow (OBS / asciinema + screen cap)

### Day 5 (Apr 25) — polish + novel failure demo
- Novel-failure injection script (unknown class)
- Show agent-1 catching it, rule propagated, agents 2-5 skip
- README with run-yourself instructions (judges may test)

### Day 6 (Apr 26) — record + submit
- 3 takes of demo video
- GitHub repo public with tag `opus-4-7`
- Submit via Cerebral Valley form
- Tweet build-in-public thread, tag @claudeai @bcherny @catwu_

### Buffer (Apr 27) — bug fixes only

## Daily discipline
- Morning: 10-min plan review. Drop anything not on critical path.
- Evening: commit + short tweet. Build-in-public = distribution.
- No scope creep. Every feature answered by "does this show on the 3-min video?"

## Kill-switches
If Day 3 morning: no measurable curve → pivot to single-agent self-healing demo (drop fleet, keep rule propagation across sessions).
If Day 5: visualization eats day → use plain terminal logs + overlay in video editor.

## Capital angle (parallel, not critical path)
- Daily tweet thread w/ #BuiltWithOpus tag
- Demo video also posted on HN, r/LocalLLaMA
- Email Boris + Cat Wu Day 3 with mid-week progress gif
- Finalist selection Apr 28 — if selected, SF presentation = investor intro chain
- If not finalist, the demo still exists, the tweets still shipped, the repo is public

## Open questions
- Late app accepted? Find out within 24 hrs of submit; build regardless.
- Can `Agent(isolation=worktree)` spawn real Claude Code subagents with separate hooks? Validate Day 1 AM.
- Demo video host: YouTube (judges prefer) or Loom (faster)?
