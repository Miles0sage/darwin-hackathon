#!/usr/bin/env python3
"""
Darwin Harness — The core engine for the Darwin MVP demo.

Orchestrates the fail→diagnose→fix→verify→learn loop:
1. Run agent → capture crash (stderr + source code)
2. Simulate breaking API change
3. Send failure context to LLM for diagnosis + code diff
4. Apply the patch
5. Re-run agent → verify fix
6. Log the fix pattern to the blackboard (fixes/ directory)

Usage:
    python3 darwin_harness.py              # Full demo flow
    python3 darwin_harness.py --break-only # Just break the API
    python3 darwin_harness.py --fix-only   # Just run diagnosis + fix
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

BASE_DIR = Path(__file__).parent
FIXES_DIR = BASE_DIR / "fixes"
AGENT_FILE = BASE_DIR / "agent.py"
CONFIG_FILE = BASE_DIR / "config.yaml"
MAX_FIX_ATTEMPTS = 3


# ─── Terminal colors ───────────────────────────────────────────────
class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def banner(msg: str, color: str = C.CYAN) -> None:
    width = 60
    print(f"\n{color}{C.BOLD}{'═' * width}")
    print(f"  {msg}")
    print(f"{'═' * width}{C.RESET}\n")


def step(msg: str) -> None:
    print(f"{C.YELLOW}▸{C.RESET} {msg}")


def success(msg: str) -> None:
    print(f"{C.GREEN}✓{C.RESET} {msg}")


def fail(msg: str) -> None:
    print(f"{C.RED}✗{C.RESET} {msg}")


def reasoning(msg: str) -> None:
    print(f"  {C.DIM}{C.CYAN}{msg}{C.RESET}")


# ─── Agent runner ──────────────────────────────────────────────────
def run_agent() -> tuple[bool, str, str]:
    """Run agent.py, return (success, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(AGENT_FILE)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(BASE_DIR),
    )
    return result.returncode == 0, result.stdout, result.stderr


# ─── API breaker ───────────────────────────────────────────────────
def break_api() -> None:
    """Simulate breaking API change: switch config from v1 to v2."""
    with open(CONFIG_FILE) as f:
        content = f.read()
    content = content.replace("api_version: v1", "api_version: v2")
    with open(CONFIG_FILE, "w") as f:
        f.write(content)


def restore_api() -> None:
    """Restore API to v1."""
    with open(CONFIG_FILE) as f:
        content = f.read()
    content = content.replace("api_version: v2", "api_version: v1")
    with open(CONFIG_FILE, "w") as f:
        f.write(content)


# ─── Demo state reset (idempotent re-runs) ────────────────────────
NAIVE_AGENT_TEMPLATE = '''#!/usr/bin/env python3
"""
SentimentTracker Agent — The "victim" agent for Darwin MVP demo.

Polls a local mock API (JSON files), extracts post text, runs basic
sentiment analysis, and prints results. Designed to break when the
API schema changes from v1 to v2.
"""

import json
import sys
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent


def load_config():
    with open(BASE_DIR / "config.yaml") as f:
        return yaml.safe_load(f)


def fetch_posts(api_version: str) -> list:
    """Fetch posts from the mock API (local JSON files)."""
    api_path = BASE_DIR / "api" / api_version / "data.json"
    with open(api_path) as f:
        data = json.load(f)
    return data["posts"]


def analyze_sentiment(text: str) -> str:
    """Dead-simple keyword sentiment. Real version would use an LLM."""
    positive = {"love", "great", "awesome", "excellent", "amazing", "good", "best"}
    negative = {"terrible", "awful", "bad", "worst", "hate", "horrible", "poor"}
    words = set(text.lower().split())
    if words & positive:
        return "positive"
    if words & negative:
        return "negative"
    return "neutral"


def run():
    config = load_config()
    api_version = config["api_version"]
    agent_name = config["agent_name"]

    print(f"[{agent_name}] Polling API {api_version}...")

    posts = fetch_posts(api_version)

    results = []
    for post in posts:
        text = post["text"]
        sentiment = analyze_sentiment(text)
        results.append({
            "id": post["id"],
            "text": text,
            "sentiment": sentiment,
        })

    for r in results:
        print(f"  #{r['id']} [{r['sentiment']:>8}] {r['text']}")

    print(f"[{agent_name}] Processed {len(results)} posts successfully.")
    return results


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"AGENT FAILURE: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
'''

NAIVE_CONFIG_TEMPLATE = "api_version: v1\nagent_name: sentiment-tracker-01\npoll_interval: 2\n"


def reset_demo_state() -> None:
    """Restore agent.py + config.yaml + blackboard so demo is idempotent.

    Wiping fixes/ at start is deliberate: the demo narrates "novel failure"
    in Scene 3, so the blackboard must start empty every run.
    """
    AGENT_FILE.write_text(NAIVE_AGENT_TEMPLATE)
    CONFIG_FILE.write_text(NAIVE_CONFIG_TEMPLATE)
    if FIXES_DIR.exists():
        for p in FIXES_DIR.glob("fix-*.json"):
            p.unlink()


# ─── LLM Diagnosis ────────────────────────────────────────────────
def diagnose_and_fix(source_code: str, stderr: str) -> str | None:
    """Send failure context to Claude for diagnosis + fix diff."""
    if not HAS_ANTHROPIC:
        step("anthropic SDK not installed — using fallback heuristic fix")
        return _heuristic_fix(source_code, stderr)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        step("No ANTHROPIC_API_KEY — using fallback heuristic fix")
        return _heuristic_fix(source_code, stderr)

    client = anthropic.Anthropic()

    prompt = f"""You are Darwin, an autonomous agent debugging engine.

An agent crashed in production. Diagnose the root cause and provide the EXACT fix.

SOURCE CODE (agent.py):
```python
{source_code}
```

ERROR LOG (stderr):
```
{stderr}
```

CONTEXT: The API schema changed. The v2 data format nests text inside a "data" object:
v1: {{"id": 1, "text": "..."}}
v2: {{"id": 1, "data": {{"text": "...", "lang": "en"}}}}

Instructions:
1. First explain your diagnosis in 2-3 lines
2. Then provide the COMPLETE fixed version of agent.py

Output format:
DIAGNOSIS: <your diagnosis>
FIXED_CODE:
```python
<complete fixed agent.py>
```"""

    reasoning("Sending failure context to Claude for diagnosis...")

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.content[0].text

    # Show diagnosis
    diag_match = re.search(r"DIAGNOSIS:\s*(.+?)(?=FIXED_CODE|```)", response_text, re.DOTALL)
    if diag_match:
        diagnosis = diag_match.group(1).strip()
        for line in diagnosis.split("\n"):
            reasoning(f"  {line.strip()}")

    # Extract code
    code_match = re.search(r"```python\n(.+?)```", response_text, re.DOTALL)
    if code_match:
        return code_match.group(1)

    return None


def _heuristic_fix(source_code: str, stderr: str) -> str | None:
    """Fallback: pattern-match the error and apply known fix."""
    if "KeyError" in stderr and "'text'" in stderr:
        reasoning("Observation: KeyError: 'text' — API schema changed")
        reasoning("Hypothesis: text field moved to post['data']['text'] in v2")
        reasoning("Action: Patching agent to handle nested data structure")

        # Match the line regardless of trailing comments
        fixed = re.sub(
            r'text = post\["text"\].*',
            'text = post.get("data", {}).get("text") or post.get("text", "")',
            source_code,
        )
        if fixed != source_code:
            return fixed
    return None


# ─── Blackboard (fix pattern log) ─────────────────────────────────
def _error_signature(stderr: str) -> str:
    """Extract a stable signature from agent stderr for blackboard matching."""
    match = re.search(r"([A-Za-z_]+Error: [^\n]+)", stderr)
    if match:
        return match.group(1).strip()
    lines = stderr.strip().splitlines()
    return lines[-1] if lines else "unknown_failure"


def blackboard_lookup(stderr: str) -> dict | None:
    """Return a prior fix pattern matching the current failure, or None."""
    if not FIXES_DIR.exists():
        return None
    sig = _error_signature(stderr)
    for path in sorted(FIXES_DIR.glob("fix-*.json")):
        try:
            entry = json.loads(path.read_text())
        except Exception:
            continue
        if entry.get("error_signature") == sig and entry.get("fix_applied") and entry.get("fix_code"):
            return entry
    return None


def log_fix_pattern(error_sig: str, root_cause: str, fix_applied: bool, fix_code: str | None = None) -> None:
    """Append fix pattern to the blackboard (fixes/ directory)."""
    FIXES_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pattern = {
        "error_signature": error_sig,
        "root_cause": root_cause,
        "fix_applied": fix_applied,
        "fix_code": fix_code,
        "timestamp": ts,
        "originating_agent": "sentiment-tracker-01",
        "confidence": 0.95 if fix_applied else 0.0,
    }
    fix_file = FIXES_DIR / f"fix-{ts}.json"
    with open(fix_file, "w") as f:
        json.dump(pattern, f, indent=2)
    success(f"Fix pattern logged to {fix_file.name}")


# ─── Main demo flow ───────────────────────────────────────────────
def run_demo() -> bool:
    # Idempotent re-runs: reset any mutations from prior demo runs
    reset_demo_state()

    banner("DARWIN ENGINE — live demo", C.MAGENTA)
    print(f"  {C.BOLD}Problem:{C.RESET} Claude Code agents keep hitting the same tool failures.")
    print(f"  {C.BOLD}Claim:{C.RESET}   They shouldn't have to. First agent learns, whole fleet benefits.")
    print(f"  {C.DIM}Watch: fail → diagnose → patch → verify → remember{C.RESET}\n")
    time.sleep(3)

    # ── Scene 1: Baseline ──
    banner("1/5  Baseline — agent working normally", C.GREEN)
    reasoning("A sentiment-tracker polls API v1 and processes posts.")
    time.sleep(1.5)
    step("Running agent...")
    time.sleep(0.8)
    ok, stdout, stderr = run_agent()
    if ok:
        print(stdout)
        success("Agent running perfectly.")
    else:
        fail(f"Agent already broken! stderr: {stderr}")
        return False

    time.sleep(2.5)

    # ── Scene 2: The Crash ──
    banner("2/5  Real-world failure — API schema breaks", C.RED)
    reasoning("Upstream team ships API v2. Field `text` moves to `data.text`.")
    reasoning("Agent has no idea. This is what silently kills prod agents every day.")
    time.sleep(2.5)
    step("Deploying v2...")
    break_api()
    time.sleep(1.2)
    step("Re-running agent against v2...")
    time.sleep(0.8)

    ok, stdout, stderr = run_agent()
    if ok:
        fail("Agent didn't crash?! Demo broken.")
        restore_api()
        return False

    print(f"\n{C.RED}{C.BOLD}  ╔══════════════════════════════════════╗")
    print(f"  ║   ⚠   AGENT CRASHED — PROD IS DOWN   ⚠  ║")
    print(f"  ╚══════════════════════════════════════╝{C.RESET}\n")
    print(f"  {C.RED}{stderr.strip()}{C.RESET}\n")
    time.sleep(2.5)

    # ── Scene 3: Darwin Diagnoses ──
    banner("3/5  Darwin auto-diagnoses + patches", C.CYAN)
    reasoning("No human needed. PostToolUse hook captures the failure context.")
    time.sleep(1.5)
    step("Capturing failure context (stderr + source)...")
    time.sleep(1)
    source_code = AGENT_FILE.read_text()
    error_sig = _error_signature(stderr)

    step("Checking fleet blackboard for a matching fix pattern...")
    time.sleep(1.2)
    prior = blackboard_lookup(stderr)
    if prior:
        reasoning(f"HIT — prior pattern matches '{error_sig}'. Skipping LLM.")
        fixed_code = prior["fix_code"]
    else:
        existing = list(FIXES_DIR.glob("fix-*.json")) if FIXES_DIR.exists() else []
        reasoning(f"{len(existing)} prior patterns on blackboard — no match. Novel failure.")
        time.sleep(1.5)
        step("Diagnosing + generating patch via Opus 4.7...")
        time.sleep(0.8)
        fixed_code = diagnose_and_fix(source_code, stderr)

    if not fixed_code:
        fail("Darwin could not generate a fix.")
        restore_api()
        return False

    time.sleep(1)
    success("Patch generated.")
    time.sleep(2)

    # ── Scene 4: Apply & Verify ──
    banner("4/5  Self-verify, apply, broadcast to fleet", C.GREEN)
    reasoning("4.7 self-verifies before writing the rule. No blind patches.")
    time.sleep(1.5)

    # Backup original
    backup = source_code
    step("Applying patch to agent.py...")
    time.sleep(0.8)
    AGENT_FILE.write_text(fixed_code)
    success("Patch applied.")
    time.sleep(1)

    step("Running verification in sandbox...")
    time.sleep(1)
    ok, stdout, stderr2 = run_agent()

    if not ok:
        fail(f"Fix didn't work! stderr: {stderr2}")
        step("Reverting to original code...")
        AGENT_FILE.write_text(backup)
        restore_api()
        log_fix_pattern(
            error_sig=error_sig,
            root_cause="Unknown — fix attempt failed",
            fix_applied=False,
        )
        return False

    print(f"\n{stdout}")
    time.sleep(1.2)
    print(f"{C.GREEN}{C.BOLD}  ╔══════════════════════════════════════╗")
    print(f"  ║     ✓   AGENT RESURRECTED   ✓         ║")
    print(f"  ╚══════════════════════════════════════╝{C.RESET}\n")
    success("Agent is back online. Processing v2 data correctly.")
    time.sleep(2)

    # Log to blackboard WITH the fix code so future agents can reuse it
    step("Broadcasting fix pattern + diff to fleet blackboard...")
    time.sleep(1)
    log_fix_pattern(
        error_sig=error_sig,
        root_cause="API v2 moved text to data.text",
        fix_applied=True,
        fix_code=fixed_code,
    )
    time.sleep(2)

    # ── Scene 5: Second agent benefits — the WHOLE point ──
    banner("5/5  Second agent, same failure — fleet benefit", C.MAGENTA)
    reasoning("Now the REAL test: does the rule actually save the next agent?")
    time.sleep(2)
    step("Spawning agent-02. Reverting its code to naive v1-only logic.")
    time.sleep(1)
    AGENT_FILE.write_text(backup)  # simulate fresh agent, no memory of the patch
    time.sleep(0.8)
    step("agent-02 runs against (still-broken) v2 API...")
    time.sleep(1)
    ok2, stdout2, stderr2 = run_agent()
    if ok2:
        fail("agent-02 didn't crash — test setup failed.")
        restore_api()
        return False
    reasoning(f"Crashed with: {_error_signature(stderr2)}")
    time.sleep(1.5)
    step("Darwin intercepts. Blackboard lookup...")
    time.sleep(1.5)
    prior = blackboard_lookup(stderr2)
    if not prior:
        fail("No match — blackboard failed to recall.")
        restore_api()
        return False
    success(f"HIT on prior pattern. Confidence {prior['confidence']}. ZERO LLM calls.")
    time.sleep(1.5)
    step("Applying stored fix to agent-02...")
    time.sleep(1)
    AGENT_FILE.write_text(prior["fix_code"])
    time.sleep(0.8)
    step("Re-running agent-02...")
    time.sleep(1)
    ok3, stdout3, _ = run_agent()
    if not ok3:
        fail("Stored fix didn't apply cleanly.")
        return False
    print(f"\n{stdout3}")
    time.sleep(1.5)
    print(f"{C.GREEN}{C.BOLD}  agent-02 healed in ZERO LLM calls. Pattern reused.{C.RESET}\n")
    time.sleep(2)

    banner("DONE", C.MAGENTA)
    print(f"  {C.BOLD}agent-01{C.RESET} hit a novel crash → Opus 4.7 diagnosed → wrote rule.")
    print(f"  {C.BOLD}agent-02{C.RESET} hit the same crash → blackboard served the rule instantly.")
    print(f"  {C.DIM}Scale that to 500 agents. Each novel failure is diagnosed once, ever.{C.RESET}\n")
    time.sleep(3)
    return True


def main() -> None:
    args = sys.argv[1:]

    if "--break-only" in args:
        break_api()
        print("API switched to v2. Agent will crash on next run.")
    elif "--fix-only" in args:
        source_code = AGENT_FILE.read_text()
        _, _, stderr = run_agent()
        if stderr:
            fixed = diagnose_and_fix(source_code, stderr)
            if fixed:
                AGENT_FILE.write_text(fixed)
                success("Fix applied.")
        else:
            print("Agent not broken — nothing to fix.")
    elif "--restore" in args:
        restore_api()
        print("API restored to v1.")
    else:
        ok = run_demo()
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
