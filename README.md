# Darwin — Claude Code that heals its own crashes

**Submission for** Cerebral Valley x Anthropic "Built with Opus 4.7" hackathon (Apr 21–27, 2026)
**Team** Solo — Miles (Germany)
**Status** Building.

---

## Live demos (runs on your machine today)

**1. Self-heal loop, narrated ~90s**
▶ https://asciinema.org/a/MOdDP1NrJGkFNrpU

5 scenes, zero human input:
1. Baseline — agent polls API v1, works fine
2. Real-world failure — upstream ships API v2, agent crashes `KeyError`
3. Darwin diagnoses — captures failure, checks blackboard (miss), generates patch via Opus 4.7
4. Self-verify → apply → broadcast fix + diff to fleet blackboard
5. **agent-02 hits the same failure → blackboard hits → instant heal, zero LLM call**

**2. Fleet benchmark — 20 agents, 1 LLM call**
▶ https://asciinema.org/a/QC5NO4kvnuQO2aaU

Measured this machine, [`benchmark-report.json`](./benchmark-report.json):

```
Fleet size:      20
Healed:          20/20
LLM calls:       1   ← one novel failure, diagnosed once
Blackboard hits: 19  ← every subsequent agent uses the cached rule
```

**That's the point.** 500 agents × 1 novel failure = 500 healings, 1 LLM call. The rest come from the fleet's own memory.

---

## Run it yourself

```bash
git clone https://github.com/Miles0sage/darwin-hackathon
cd darwin-hackathon
python3 darwin_harness.py              # 5-scene narrated demo
python3 benchmark.py --fleet-size 50   # your own numbers
```

Opus 4.7 API key optional — harness falls back to heuristic pattern-match so the loop still runs offline.

---

## Why Opus 4.7 specifically
- **Native file-memory across sessions** — rules persist across Claude Code sessions without an external DB
- **Self-verification** — agent checks its own fix before writing the rule
- **Literal instruction-following** — skill/fix files apply exactly, no drift
- **Adaptive thinking** — cheap scan on common failures, `xhigh` on novel ones

---

## Foundation (shipped before hackathon week)

- **fixcache v0.4.8** (at `/root/lore-lite`) — 614 tests passing, PostToolUse hook caching failure→fix pairs
- **Lore codex** — 134 markdown entries on agent reliability patterns
- **lean-ctx v3.1.2** — MCP + hooks live, 89–99% input token savings
- **16 MCPs, 21 agents, 94 skills** wired into Claude Code with 5-event hook coverage
- **AI Factory** — multi-LLM orchestrator for failure triage at $0.001/task

Hackathon week = N-agent fleet orchestration + visualization dashboard + final demo video. Single-agent loop + pattern reuse are already working (see demos above).

---

## Files
- [`darwin_harness.py`](./darwin_harness.py) — the 5-scene fail→heal→remember loop
- [`agent.py`](./agent.py) — the "victim" agent that crashes on API v2
- [`benchmark.py`](./benchmark.py) — N-agent fleet benchmark
- [`benchmark-report.json`](./benchmark-report.json) — latest run numbers
- [`api/v1`, `api/v2`](./api) — mock API with schema drift
- [`APPLICATION.md`](./APPLICATION.md) — hackathon submission copy
- [`BUILD-PLAN.md`](./BUILD-PLAN.md) — 6-day execution plan

---

## Honest caveats
- **API credits**: demo env has no Opus 4.7 credits, so Scene 3 falls back to a deterministic heuristic pattern-matcher. With credits, the same path calls real Opus 4.7 (`claude-opus-4-7`). Scene 5 (blackboard hit) uses zero LLM regardless — that's the point.
- **Fleet is 1 agent today**: Scene 5 simulates a second agent with the same code path. Day 2 of hackathon week wires real parallel Claude Code subagents.
- **Blackboard is a flat JSON dir** right now. Good enough for the MVP. Hackathon week adds semantic matching.

## Links
- Opus 4.7: https://www.anthropic.com/news/claude-opus-4-7
- Hackathon: https://cerebralvalley.ai/e/built-with-4-7-hackathon
