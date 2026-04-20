#!/usr/bin/env python3
"""
Darwin Benchmark — measures LLM calls saved when a fleet of N agents
hits the same recurring tool failure.

Setup:
  - API is already broken (v2 schema)
  - Fleet = N agents, each starts from a fresh "naive" agent.py
  - First crash triggers diagnosis → rule goes on blackboard
  - Every subsequent crash should hit the blackboard (ZERO LLM call)

Output:
  Per-agent timing + a summary table. Proves the "diagnosed once, ever" claim.

Usage:
  python3 benchmark.py --fleet-size 10
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import time
from pathlib import Path

from darwin_harness import (
    AGENT_FILE,
    FIXES_DIR,
    blackboard_lookup,
    break_api,
    diagnose_and_fix,
    log_fix_pattern,
    restore_api,
    run_agent,
    _error_signature,
)

NAIVE_AGENT = (
    '#!/usr/bin/env python3\n'
    '"""SentimentTracker Agent — naive version (v1-only)."""\n\n'
    'import json\n'
    'import sys\n'
    'import yaml\n'
    'from pathlib import Path\n\n'
    'BASE_DIR = Path(__file__).parent\n\n\n'
    'def load_config():\n'
    '    with open(BASE_DIR / "config.yaml") as f:\n'
    '        return yaml.safe_load(f)\n\n\n'
    'def fetch_posts(api_version: str) -> list:\n'
    '    api_path = BASE_DIR / "api" / api_version / "data.json"\n'
    '    with open(api_path) as f:\n'
    '        data = json.load(f)\n'
    '    return data["posts"]\n\n\n'
    'def analyze_sentiment(text: str) -> str:\n'
    '    positive = {"love", "great", "awesome", "excellent", "amazing", "good", "best"}\n'
    '    negative = {"terrible", "awful", "bad", "worst", "hate", "horrible", "poor"}\n'
    '    words = set(text.lower().split())\n'
    '    if words & positive:\n'
    '        return "positive"\n'
    '    if words & negative:\n'
    '        return "negative"\n'
    '    return "neutral"\n\n\n'
    'def run():\n'
    '    config = load_config()\n'
    '    api_version = config["api_version"]\n'
    '    agent_name = config["agent_name"]\n'
    '    print(f"[{agent_name}] Polling API {api_version}...")\n'
    '    posts = fetch_posts(api_version)\n'
    '    results = []\n'
    '    for post in posts:\n'
    '        text = post["text"]\n'
    '        sentiment = analyze_sentiment(text)\n'
    '        results.append({"id": post["id"], "text": text, "sentiment": sentiment})\n'
    '    for r in results:\n'
    '        print(f"  #{r[\'id\']} [{r[\'sentiment\']:>8}] {r[\'text\']}")\n'
    '    print(f"[{agent_name}] Processed {len(results)} posts successfully.")\n'
    '    return results\n\n\n'
    'if __name__ == "__main__":\n'
    '    try:\n'
    '        run()\n'
    '    except Exception as e:\n'
    '        print(f"AGENT FAILURE: {type(e).__name__}: {e}", file=sys.stderr)\n'
    '        sys.exit(1)\n'
)


def reset_fleet() -> None:
    """Clear blackboard + force naive agent.py + broken v2 API."""
    if FIXES_DIR.exists():
        for p in FIXES_DIR.glob("fix-*.json"):
            p.unlink()
    AGENT_FILE.write_text(NAIVE_AGENT)
    break_api()


def reset_agent_only() -> None:
    """Reset agent.py to naive, keep blackboard + v2 API."""
    AGENT_FILE.write_text(NAIVE_AGENT)


def heal_one(agent_id: int) -> dict:
    """Run one agent through the crash-heal cycle. Return metrics."""
    t_start = time.perf_counter()

    ok, _, stderr = run_agent()
    if ok:
        return {"id": agent_id, "crashed": False, "blackboard_hit": False, "llm_called": False, "ms": 0, "healed": True}

    crash_time = time.perf_counter()

    prior = blackboard_lookup(stderr)
    if prior:
        AGENT_FILE.write_text(prior["fix_code"])
        llm_called = False
    else:
        fixed = diagnose_and_fix(AGENT_FILE.read_text(), stderr)
        llm_called = True
        if fixed:
            AGENT_FILE.write_text(fixed)
            log_fix_pattern(
                error_sig=_error_signature(stderr),
                root_cause="API v2 moved text to data.text",
                fix_applied=True,
                fix_code=fixed,
            )

    ok2, _, _ = run_agent()
    t_end = time.perf_counter()
    return {
        "id": agent_id,
        "crashed": True,
        "blackboard_hit": bool(prior),
        "llm_called": llm_called,
        "ms": int((t_end - t_start) * 1000),
        "crash_ms": int((crash_time - t_start) * 1000),
        "healed": ok2,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fleet-size", type=int, default=10)
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"  DARWIN BENCHMARK — fleet of {args.fleet_size} agents")
    print(f"{'=' * 60}\n")

    reset_fleet()
    results = []
    for i in range(1, args.fleet_size + 1):
        reset_agent_only()
        m = heal_one(i)
        results.append(m)
        tag = "LLM " if m["llm_called"] else "CACHE"
        status = "OK" if m["healed"] else "FAIL"
        print(f"  agent-{i:02d}  [{tag}]  {m['ms']:>5} ms  {status}")

    restore_api()

    llm_calls = sum(1 for r in results if r["llm_called"])
    cache_hits = sum(1 for r in results if r["blackboard_hit"])
    healed = sum(1 for r in results if r["healed"])
    times = [r["ms"] for r in results]

    print(f"\n{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Fleet size:      {args.fleet_size}")
    print(f"  Healed:          {healed}/{args.fleet_size}")
    print(f"  LLM calls:       {llm_calls}  (1 expected — first novel failure)")
    print(f"  Blackboard hits: {cache_hits}  ({cache_hits}/{args.fleet_size - 1} of remaining agents)")
    if llm_calls:
        llm_times = [r["ms"] for r in results if r["llm_called"]]
        cache_times = [r["ms"] for r in results if r["blackboard_hit"]]
        if cache_times:
            print(f"  LLM path avg:    {statistics.mean(llm_times):.0f} ms")
            print(f"  Cache path avg:  {statistics.mean(cache_times):.0f} ms")
            speedup = statistics.mean(llm_times) / max(1, statistics.mean(cache_times))
            print(f"  Speed-up:        {speedup:.1f}x")
    print(f"  Total wall-time: {sum(times)} ms")
    print()

    report = {
        "fleet_size": args.fleet_size,
        "healed": healed,
        "llm_calls": llm_calls,
        "blackboard_hits": cache_hits,
        "results": results,
    }
    Path("benchmark-report.json").write_text(json.dumps(report, indent=2))
    print(f"  Report → benchmark-report.json\n")


if __name__ == "__main__":
    main()
