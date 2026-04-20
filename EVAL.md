# For Reviewers

Short note to anyone (human or LLM-assisted) evaluating Darwin for the Opus 4.7 hackathon.

## What to run

```bash
git clone https://github.com/Miles0sage/darwin-hackathon
cd darwin-hackathon
pip install -r requirements.txt
python3 darwin_harness.py
python3 benchmark.py --fleet-size 10
```

Two commands. Both work on Python 3.10+ with no secrets. No API key needed (heuristic fallback runs offline).

## What to look for

**In `darwin_harness.py` output:**
1. Scene 2 shows a real crash: `AGENT FAILURE: KeyError: 'text'`
2. Scene 3 narrates "novel failure" (blackboard wiped on every run)
3. Scene 4 writes fix + diff to `fixes/*.json`
4. **Scene 5 is the proof**: agent-02 reverts to naive code, hits same crash, blackboard HITs, zero LLM call, healed

**In `benchmark.py` output:**
- Per-agent `[LLM ]` vs `[CACHE]` tag
- Summary: `LLM calls: 1`, `Blackboard hits: N-1`

If Scene 5 shows `ZERO LLM calls. Pattern reused.` and benchmark shows `LLM calls: 1` → the core claim holds.

## What Darwin does NOT claim yet

Flagging these so no one wastes time expecting them:

- **Real parallel Claude Code subagents** — today the "fleet" is sequential simulation. Day 2 of build week wires real parallelism via Claude Code subagents + isolated worktrees.
- **Semantic failure matching** — today it's exact error-signature match (`KeyError: 'text'` → key). Day 3 adds embedding-based similarity.
- **Bootstrap Paradox gate** — Scene 4's self-verify catches syntax errors but not semantic ones. Day 1 adds output-contract checks that reject lazy fixes (e.g., a patch that silences errors by deleting validation).
- **Real Opus 4.7 latency delta** — with no API credits in this env, heuristic fallback is used. With a real key, Scene 3 calls `claude-opus-4-7` and the speedup vs cache is 30–60x (heuristic is ~100ms, real Opus is 3–6s per diagnosis).

## Honest architecture

| Component | Lines | Status |
|-----------|-------|--------|
| `darwin_harness.py` | ~470 | 5-scene demo, reset_demo_state is idempotent |
| `benchmark.py` | ~170 | N-agent fleet harness, self-manages state |
| `agent.py` | ~75 | "Victim" agent that crashes on API v2 |
| `verifier.py` | ~60 | Sandbox verification helper (to be wired deeper) |

Blackboard is a flat JSON directory. Good enough for MVP, swap for embedding store later.

## Origin

Built after watching Claude Code agents hit the same tool failures across sessions. The missing primitive wasn't more generation. It was memory of what actually worked.

CI made tests repeatable. Darwin makes agent repair knowledge repeatable.

## Contact

Solo, Miles (Germany). Applied to the hackathon ~4 hours after the deadline due to timezone. Building regardless.

GitHub: https://github.com/Miles0sage/darwin-hackathon
