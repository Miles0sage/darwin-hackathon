# Darwin

**AI coding agents should not make the same mistake twice.**

Darwin is a failure memory layer for coding agents. It captures errors, fingerprints them, retrieves proven fix recipes, applies them, verifies the result, and records the outcome. The fleet gets smarter with every crash.

## Why

AI agents repeatedly hit the same dependency, import, test, and environment failures. Today those fixes disappear into chat logs and terminal output. Darwin turns them into reusable repair memory that grows stronger with every run.

## Demo

90 seconds, narrated. 5 scenes, zero human input.

▶ https://asciinema.org/a/MOdDP1NrJGkFNrpU

1. Baseline — agent polls API v1, works fine
2. Real-world failure — upstream ships v2, agent crashes with `KeyError`
3. Darwin fingerprints the failure, checks blackboard, diagnoses via Opus 4.7
4. Self-verify → apply patch → broadcast fix + diff to the fleet blackboard
5. **Second agent hits the same failure → blackboard serves the stored fix → zero LLM call**

## Benchmark

20 agents, same recurring failure class.

▶ https://asciinema.org/a/QC5NO4kvnuQO2aaU

```
Fleet size:      20
Healed:          20/20
LLM calls:       1   (one novel failure, diagnosed once)
Blackboard hits: 19  (every subsequent agent uses the cached rule)
```

Raw numbers in [`benchmark-report.json`](./benchmark-report.json).

## Quickstart

```bash
git clone https://github.com/Miles0sage/darwin-hackathon
cd darwin-hackathon
pip install anthropic pyyaml
python3 darwin_harness.py              # 5-scene narrated demo
python3 benchmark.py --fleet-size 10   # your own numbers
```

Requires Python 3.10+. Opus 4.7 API key optional — harness falls back to a deterministic heuristic pattern-matcher so the loop still runs offline.

## How it works

Four pieces, nothing more:

| Component | What it does |
|-----------|--------------|
| **Fingerprint** | Extract a stable signature from agent stderr (`KeyError: 'text'` → key) |
| **Recipe store** | JSON files under `fixes/`. Each entry: error signature, root cause, fix code, confidence, timestamp |
| **Lookup** | Given a crash, match against recipe store by signature. Hit → reuse. Miss → call LLM |
| **Outcome** | After applying a fix, run verification. Update confidence. Log whether it stuck |

That's it. No empire.

## What's next

- Failure taxonomy beyond single-signature match (semantic similarity via embeddings)
- Verification gate that rejects lazy fixes (catches the Bootstrap Paradox: "Opus removes a validation check to silence an error" → reject)
- Webhook-triggered heal (Sentry/Datadog-style POST → Darwin → fleet hot-reload)
- Real parallel Claude Code subagents sharing one blackboard via 4.7's file-memory

## Known limitations

- Today, Darwin matches by exact error signature. Semantic matching comes next.
- Verification gate is basic (re-run the agent). Needs teeth to stop bad fixes from propagating.
- Fleet is simulated: Scene 5 reverts one agent to a prior state and reruns. Real parallel fleet is Day 2 of hackathon week.
- Heuristic fallback only knows one failure class (`KeyError: 'text'`). Opus 4.7 path handles anything.

## Origin

Built after watching AI coding agents repeatedly hit fixable failures. The missing layer wasn't more generation. It was memory of what actually worked.

Logs record what happened. RAG retrieves documents. Stack Overflow stores human answers. **Darwin stores verified repair recipes ranked by outcome.**

CI made tests repeatable. Darwin makes agent repair knowledge repeatable.

## Files
- [`darwin_harness.py`](./darwin_harness.py) — the 5-scene fail→heal→remember loop
- [`agent.py`](./agent.py) — the "victim" agent that crashes on API v2
- [`benchmark.py`](./benchmark.py) — N-agent fleet benchmark
- [`verifier.py`](./verifier.py) — sandbox verification helper
- [`api/v1`, `api/v2`](./api) — mock API with schema drift

## Submission

Built for Cerebral Valley × Anthropic "Built with Opus 4.7" hackathon (Apr 21–27, 2026). Solo, Germany.
