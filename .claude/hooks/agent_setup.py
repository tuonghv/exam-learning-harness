#!/usr/bin/env python3
"""
agent_setup.py - Role-based Claude Code workflow with a zero-token context supervisor.

Two ways to run the same roles (.claude/agents/*.md):

  1. Pipeline mode (recommended for batch work, scripts, req kits):
     Python is the orchestrator. Each role runs as its own `claude -p` session with a fresh
     context, reads the kit + previous handoffs from work/<id>/, writes its handoff, exits.
     No LLM orchestrator tokens, deterministic resume, usage-limit aware, stoppable.

  2. Interactive mode: open `claude` in the repo. The CLAUDE.md block makes the main session an
     orchestrator that delegates to the same roles as subagents.

Commands
  plan       [--window N]                         print budgets
  init       --repo R [--window N] [--enforce roles] [--profile DIR] [--update-tool]
                                                  write agents, CLAUDE.md block, hook, config;
                                                  copies this script to .claude/hooks/ (the hook runs it)
  task       --repo R --id ID --goal TEXT [--kit FILE] [--roles a,b,c] [--scope TEXT]
  pipeline   --repo R --id ID [--on-limit exit|wait] [--claude-args "..."]
                                                  run/resume one task, role by role
  start-all  (--batch FILE.jsonl | --repo R ...)  run every unfinished task sequentially
  stop       [--repo R --id ID] [--now] [--grace S]
                                                  graceful stop (default) or kill now; no args = all
  status     [--repo R ...]                       running processes and task states
  lessons    --repo R [--repo R ...]              what to fix in kits/prompts/budgets
  doctor     --repo R                             verify role detection and hook input
  hook       --config PATH                        called by Claude Code (PreToolUse)

Exit codes (pipeline / start-all), for your own manifest:
  0 done | 2 partial (resumable) | 3 blocked | 75 usage limit (retry after reset) | 130 stopped
The last stdout line of `pipeline` is a JSON summary.

UNVERIFIED (check with a small run + `doctor`): the exact usage-limit message format of
`claude -p`, hook environment inheritance (CTXGUARD_ROLE), and stream-json usage field names.
"""
from __future__ import annotations
import argparse, collections, contextlib, fnmatch, json, os, queue, re, shlex, shutil, signal, subprocess, sys, threading, time
from pathlib import Path

TOOL_NAME = "agent_setup.py"

# =========================================================================== budgets
ABS_SOFT_CAP, ABS_HARD_CAP = 130_000, 180_000
ORCH_SOFT = 40_000
SESSION_SOFT, SESSION_HARD = 0.50, 0.70
HOME = Path(os.environ.get("AGENT_SETUP_HOME", Path.home() / ".agent_setup"))
GLOBAL_STOP = HOME / "STOP_ALL"
RUNNING = HOME / "running"

ROLES = {
    "designer": dict(
        tools="Read, Grep, Glob, Write, Skill", read=400, out=60, files=40, handoff="design.md",
        desc="Designs one step of a task: reads the relevant code and writes a design to "
             "work/<id>/handoff/design.md. Never edits source code.",
        rules=["Do not edit source files.",
               "Prefer interfaces, data flow and path:line references over prose.",
               "Keep design.md under 150 lines."],
        spec="goal, affected files (path:line), proposed change per file, risks, test points"),
    "coder": dict(
        tools="Read, Grep, Glob, Edit, Write, Bash, Skill", read=300, out=80, files=30, handoff="code.md",
        desc="Implements one step of a task within the given scope and writes "
             "work/<id>/handoff/code.md.",
        rules=["Change only files inside the scope given in plan.md or design.md.",
               "Follow the existing code style. No drive-by refactoring.",
               "If handoff/test.md reports failures, fix those first.",
               "Run a build or compile check with truncated output before reporting DONE."],
        spec="changed files (path:line ranges), why, what to test, known risks"),
    "tester": dict(
        tools="Read, Grep, Glob, Edit, Write, Bash, Skill", read=250, out=60, files=25, handoff="test.md",
        desc="Writes and runs tests for one step and writes work/<id>/handoff/test.md. "
             "Edits test files only.",
        rules=["Edit test files only. Never fix production code; report failures instead.",
               "Always truncate test output: `<cmd> 2>&1 | tail -n {out}`.",
               "Report each failure as test name + first relevant error line, not full logs.",
               "Reply STATUS: FAILED when tests fail because of production code."],
        spec="commands run, pass/fail counts, failing tests with one-line cause, coverage gaps"),
    "verifier": dict(
        tools="Read, Grep, Glob, Write, Skill", read=200, out=40, files=15, handoff="verify.md",
        desc="Independently verifies a task against plan.md goals and writes "
             "work/<id>/handoff/verify.md. Read-only except for its own outputs.",
        rules=["Never edit any file except your handoff file and findings.jsonl.",
               "Every conclusion needs evidence as path:line.",
               "Verify against the goals in plan.md, not against other roles' claims.",
               "Mark each claim VERIFIED, REFUTED or UNVERIFIED."],
        spec="per goal: verdict + evidence (path:line); open issues"),
}
KEEP_KEYS = ("protect", "orch_delegate", "deny_globs", "enforce", "warn", "msg_budget")  # project-tuned: init keeps them
DEFAULT_PIPELINE = ["designer", "coder", "tester", "verifier"]
DEFAULT_LOOP = ("tester", "coder")        # tester FAILED -> back to coder
MAX_LOOPS, MAX_ATTEMPTS = 3, 3
SESSION_LIMITS = dict(read=300, out=80, files=30)
STATE_EVERY, STATE_MAX_CHARS = 10, 1500
WRITE_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit", "Bash"}
DENY_GLOBS = ["**/node_modules/**", "**/vendor/**", "**/dist/**", "**/build/**", "**/.git/**",
              "**/*.min.js", "**/*.min.css", "**/*.map", "**/*.lock", "**/package-lock.json",
              "**/go.sum", "**/*.pb.go"]
LIMIT_RE = re.compile(r"usage limit|limit reached|rate[ _-]?limit|\b429\b|overloaded|\b529\b|"
                      r"credit balance", re.I)

LESSONS = {
    "big_read":   ("Read a whole large file",
                   "Put outlines/function signatures in the kit or handoff; Grep first."),
    "reread":     ("Re-read the same file section",
                   "Handoffs lack a one-line summary per file read."),
    "noisy_bash": ("Command output not truncated",
                   "Give ready-made truncated commands (test/grep/git log) in the kit or agent file."),
    "grep_nolim": ("Grep content without head_limit",
                   "files_with_matches first, content with head_limit second."),
    "deny_zone":  ("Read vendor/build/minified/lockfile",
                   "Put the needed library interface in the kit."),
    "max_files":  ("Exceeded the per-role file quota",
                   "Step scope too wide: narrow --scope or split the task."),
    "state_big":  ("state.md too long", "Bullets only; details go in handoffs."),
    "orch_work":  ("Interactive orchestrator did hands-on work",
                   "Tighten CLAUDE.md delegation; or use pipeline mode."),
    "over_soft":  ("Context passed the soft budget",
                   "Smaller kit, narrower scope, or split the task."),
    "orch_big":   ("Interactive orchestrator context passed ~40k",
                   "Subagent replies too long, or it reads files itself."),
    "protected":  ("A role touched a path or command the project reserves (refused)",
                   "State the reserved paths/commands in the agent file; hand those steps to the main session."),
}
MARK_START, MARK_END = "<!-- agent-setup:start -->", "<!-- agent-setup:end -->"
MARK_CUSTOM = "<!-- agent-setup:custom -->"   # inside the block: init leaves the block alone
PROJ_START, PROJ_END = "<!-- agent-setup:project:start -->", "<!-- agent-setup:project:end -->"


def session_budget(window):
    return dict(window=window, soft=min(int(window * SESSION_SOFT), ABS_SOFT_CAP),
                hard=min(int(window * SESSION_HARD), ABS_HARD_CAP), orch_soft=ORCH_SOFT)


# =========================================================================== templates
CLAUDE_BLOCK = """{start}
## Workflow: orchestrator + role subagents (interactive mode)

When working interactively in this repository, the main session is the **orchestrator**.
It coordinates; it does not do the work. Roles live in `.claude/agents/`: {roles}.
(Batch work uses `agent_setup.py pipeline`, where a script plays the orchestrator.)

### Orchestrator rules
- Do not read source code, grep, or run builds/tests yourself. Delegate every read, edit and run to a subagent.
- Delegate by path, never by pasting content:
  `Task work/<id>, step <n> of plan.md. Inputs: <kit/handoff files>. Scope: <dirs>. Output: work/<id>/handoff/<file>.md`
- One goal per delegation, with an explicit scope.
- Before delegating, mark the step IN_PROGRESS in state.md. After the reply, mark it DONE/PARTIAL/BLOCKED.
- Read only the subagent's reply (max 8 lines). Open a handoff file only when a decision depends on it.
- Keep `work/<id>/state.md` under {state_max} characters.
- coder <-> tester: at most 3 rounds per step, then `STATUS: BLOCKED` with the reason, and stop.
- Evidence comes from `verifier`, never from reading code yourself.
- Subagents never call other subagents.
- All steps verified: write `STATUS: DONE` in state.md and stop.

### Resuming
Read only `work/<id>/plan.md` and `work/<id>/state.md`. A step marked IN_PROGRESS was interrupted:
re-delegate it with "resume from your partial handoff". Never re-run DONE steps.

### Stop requests
If a tool call is refused with "stop requested", update state.md, reply with STATUS: PARTIAL, and end.

### Context budget
Orchestrator under ~{orch_k}k tokens. Session soft limit ~{soft_k}k: finish the step, update state.md, stop.
{end}
"""

# hard stop per role; must equal the numbers in skill coordinator section 2 (guard_table_test.sh)
MAX_TURNS = {"designer": 40, "coder": 60, "tester": 50, "verifier": 30}

AGENT_TMPL = """---
name: {name}
description: {desc}
tools: {tools}
maxTurns: {turns}
---
You are the **{name}** in a multi-role workflow. Do only the step you were given.

## Inputs
The request names a task directory (`work/<id>/`), your step and input files (kit.md, plan.md,
earlier handoffs). Read only those. Do not re-explore what earlier roles already documented.

## Context budget
- Read at most {read} lines per call (use offset/limit). Grep for locations before reading.
- Cap command output at {out} lines (`| head -n {out}`; for tests `2>&1 | tail -n {out}`).
- Open at most {files} files in this step. Never re-read a file you already read.
- Never read vendor/, node_modules/, build/, dist/, minified files, lockfiles or generated code.
- If the step cannot be done within this budget, stop and report PARTIAL with what remains.
- Turn budget: the brief's `Turns: N` (hard cap: `maxTurns` in this file). At about half of N, update
  the handoff's `PROGRESS:` line; if less than half the step is done, `SendMessage` main with where you
  are and what blocks you. Before N runs out, save the handoff and reply PARTIAL. Never spend turns
  retrying the same failing call: after 2 identical failures, stop and report them.

## Role rules
{rules}

## Output (mandatory)
1. Create `work/<id>/handoff/{handoff}` early with a first line `PROGRESS: IN_PROGRESS`, and update it
   as you go, so an interrupted run can resume. Set the first line to `PROGRESS: COMPLETE` when done.
   Content: {spec}.
   The main session commits your edits. List the changed files under FILES and stop; never reply
   about commits or the uncommitted-edits guard note.
2. Append each security issue or bug to `work/<id>/findings.jsonl` as soon as you find it
   (one JSON object per line: id, severity, title, location, evidence, role).
3. If a tool call is refused with "stop requested": save progress to the handoff, reply PARTIAL, end.
4. Reply with AT MOST 8 lines, exactly:
   STATUS: DONE | PARTIAL | BLOCKED | FAILED
   OUTPUT: work/<id>/handoff/{handoff}
   NEXT: <what the next role should do>
   NOTE: <1-3 lines, most important only>
   Never include code, diffs, logs or file contents in the reply.
"""

PLAN_TMPL = """# Task {id}

Goal: {goal}
Scope: {scope}
Kit: {kit}
Pipeline: {roles}

## Acceptance criteria
- ...
"""

STATE_TMPL = """STATUS: IN_PROGRESS
Current step: 1
Done:
Next:
Blockers:
"""

ROLE_PROMPT = """Task directory: work/{id}/
Your step: {role} (step {n} of {total}: {pipeline}).
Goal: {goal}
Scope: {scope}
Inputs: {inputs}
Output: work/{id}/handoff/{handoff}
{extra}"""


# =========================================================================== plan / init / task
def cmd_plan(a):
    b = session_budget(a.window)
    print(f"Window {a.window//1000}k: soft {b['soft']//1000}k, hard {b['hard']//1000}k "
          f"(hard = ask the role to wrap up, well before compact)\n")
    print(f"{'role':9} {'read/call':>9} {'output':>7} {'files':>6}  tools")
    for n, r in ROLES.items():
        print(f"{n:9} {r['read']:>9} {r['out']:>7} {r['files']:>6}  {r['tools']}")


def write_claude_md(repo, block, force=False):
    p = repo / "CLAUDE.md"
    text = p.read_text() if p.exists() else ""
    if MARK_START in text and MARK_END in text:
        pre, rest = text.split(MARK_START, 1)
        if not force and MARK_CUSTOM in rest.split(MARK_END, 1)[0]:
            return False  # the project adapted the block to its own workflow: keep it
        text = pre + block.strip() + rest.split(MARK_END, 1)[1]
    else:
        text = (text.rstrip() + "\n\n" if text.strip() else "") + block.strip() + "\n"
    p.write_text(text)
    return True


def load_profile(d):
    """A project profile adapts the roles to a project's own workflow (init --profile DIR):
      profile.json     {"config": {...merged into agent_setup.json: protect, orch_delegate, ...},
                        "roles": {"<role>": "extra role-specific lines"}}
      project-rules.md shared rules added to every agent file (marked section, re-applied by init)
      claude-block.md  the CLAUDE.md block (written as a custom block, which a plain init keeps)
    Every file is optional."""
    d = Path(d).resolve()
    if not d.is_dir():
        sys.exit(f"profile {d}: not a directory")
    read = lambda n: (d / n).read_text().strip() if (d / n).exists() else ""
    prof = json.loads(read("profile.json") or "{}")
    return dict(config=prof.get("config") or {}, roles=prof.get("roles") or {},
                rules=read("project-rules.md"), block=read("claude-block.md"), path=str(d))


def apply_project_section(p: Path, body: str):
    """Put `body` in the agent file's marked project section (before '## Output'), replacing an
    earlier one; the rest of the file (user edits) is kept."""
    text = p.read_text()
    if PROJ_START in text and PROJ_END in text:
        pre, rest = text.split(PROJ_START, 1)
        text = pre.rstrip("\n") + "\n\n" + rest.split(PROJ_END, 1)[1].lstrip("\n")
    sec = f"{PROJ_START}\n{body.strip()}\n{PROJ_END}\n\n" if body.strip() else ""
    anchor = "## Output (mandatory)"
    text = text.replace(anchor, sec + anchor, 1) if anchor in text else text.rstrip("\n") + "\n\n" + sec
    p.write_text(text)


def install_tool(dest, update=False):
    """Copy this script into the repo so the hook runs the repo's own copy (committed, cloned
    and fixed together with the project). A copy edited in the repo is kept unless `update`."""
    src = Path(__file__).resolve()
    if dest.exists() and dest.resolve() == src:
        return ""  # init run from the repo copy itself
    code = src.read_bytes()
    if dest.exists() and dest.read_bytes() != code and not update:
        return f"{dest.name} in repo differs from {src}, kept (--update-tool to replace)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(code)
    dest.chmod(0o755)
    return ""


def cmd_init(a):
    repo = Path(a.repo).resolve()
    cdir = repo / ".claude"
    (cdir / "agents").mkdir(parents=True, exist_ok=True)
    b = session_budget(a.window)
    enforce = [r.strip() for r in (a.enforce or "").split(",") if r.strip()]
    for name, r in ROLES.items():
        p = cdir / "agents" / f"{name}.md"
        if p.exists() and not a.overwrite_agents:
            continue  # keep user customizations
        rules = "\n".join(f"- {x.format(out=r['out'])}" for x in r["rules"])
        p.write_text(AGENT_TMPL.format(name=name, desc=r["desc"], tools=r["tools"], turns=MAX_TURNS.get(name, 40), read=r["read"],
                                       out=r["out"], files=r["files"], rules=rules,
                                       handoff=r["handoff"], spec=r["spec"]))
    prof = load_profile(a.profile) if a.profile else None
    if prof:
        for name in ROLES:
            body = "\n\n".join(x for x in (prof["rules"], prof["roles"].get(name, "").strip()) if x)
            apply_project_section(cdir / "agents" / f"{name}.md", body)
    if prof and prof["block"]:
        block = prof["block"]
        if MARK_CUSTOM not in block:
            block = MARK_CUSTOM + "\n" + block
        write_claude_md(repo, f"{MARK_START}\n{block}\n{MARK_END}", force=True)
    kept_md = prof is not None and bool(prof["block"]) or not write_claude_md(repo, CLAUDE_BLOCK.format(
        start=MARK_START, end=MARK_END, roles=", ".join(f"`{r}`" for r in ROLES),
        state_max=STATE_MAX_CHARS, orch_k=ORCH_SOFT // 1000, soft_k=b["soft"] // 1000))
    cfg = dict(b, enforce=enforce, state_every=STATE_EVERY,
               state_max_chars=STATE_MAX_CHARS, deny_globs=DENY_GLOBS,
               roles={n: dict(read=r["read"], out=r["out"], files=r["files"]) for n, r in ROLES.items()},
               session=SESSION_LIMITS,
               # repo-relative so the repo can be moved/cloned; resolved by resolve_cfg()
               violations_log=".claude/agent_setup_violations.jsonl",
               runs_log=".claude/agent_setup_runs.jsonl",
               hookkeys=".claude/agent_setup_hookkeys.json",
               calls_log=".claude/agent_setup_calls.jsonl",
               warn=["orch_work", "orch_big", "msg_budget", "dirty_stop", "partial_stop"],
               msg_budget=3)
    cp = cdir / "agent_setup.json"
    try:  # keep project keys init does not generate (protect, orch_delegate, ...)
        old = json.loads(cp.read_text()) if cp.exists() else {}
    except ValueError:
        old = {}
    for k, v in old.items():
        if k not in cfg or k in KEEP_KEYS:
            cfg[k] = v
    if prof:
        cfg.update(prof["config"])  # the profile is the source for the keys it sets
    cp.write_text(json.dumps(cfg, indent=2))

    sp = cdir / "settings.json"
    settings = json.loads(sp.read_text()) if sp.exists() else {}
    tool_note = install_tool(cdir / "hooks" / TOOL_NAME, a.update_tool)
    hook_cmd = (f'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/{TOOL_NAME}" hook '
                f'--config "$CLAUDE_PROJECT_DIR/.claude/agent_setup.json"')
    pre = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    pre[:] = [h for h in pre if "agent_setup.py" not in json.dumps(h)]
    pre.append({"matcher": "*", "hooks": [{"type": "command", "command": hook_cmd}]})
    sp.write_text(json.dumps(settings, indent=2))

    excl = repo / ".git" / "info" / "exclude"
    if excl.parent.is_dir():
        lines = excl.read_text().splitlines() if excl.exists() else []
        for pat in ("work/", ".claude/agent_setup_*"):
            if pat not in lines:
                lines.append(pat)
        excl.write_text("\n".join(lines) + "\n")
    print(f"[init] {repo}: soft {b['soft']//1000}k, hard {b['hard']//1000}k, "
          f"enforced: {', '.join(enforce) or 'none (advise only)'}"
          + ("; profile " + prof["path"] if prof else "")
          + ("; CLAUDE.md block kept (custom)" if kept_md and not prof else "")
          + ("; " + tool_note if tool_note else ""))


def cmd_task(a):
    repo = Path(a.repo).resolve()
    d = repo / "work" / a.id
    (d / "handoff").mkdir(parents=True, exist_ok=True)
    kit = "-"
    if a.kit:
        src = Path(a.kit).resolve()
        (d / "kit.md").write_text(src.read_text())
        kit = "work/%s/kit.md (from %s)" % (a.id, src)
    roles = a.roles or ",".join(DEFAULT_PIPELINE)
    for name, content in (("plan.md", PLAN_TMPL.format(id=a.id, goal=a.goal, scope=a.scope, kit=kit,
                                                       roles=roles)),
                          ("state.md", STATE_TMPL), ("findings.jsonl", "")):
        if not (d / name).exists():
            (d / name).write_text(content)
    meta = dict(id=a.id, goal=a.goal, scope=a.scope, roles=roles.split(","))
    (d / "task.json").write_text(json.dumps(meta, indent=2))
    print(f"[task] {d}")


# =========================================================================== helpers
def ctx_from_usage(u):
    if not isinstance(u, dict):
        return 0
    return sum(int(u.get(k) or 0) for k in
               ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))


def ctx_from_transcript(path):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 400_000))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except (OSError, TypeError):
        return 0
    for line in reversed(lines):
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        n = ctx_from_usage((obj.get("message") or {}).get("usage")) if isinstance(obj, dict) else 0
        if n:
            return n
    return 0


def resolve_cfg(cfg, repo):
    """Derive repo from the config location and anchor relative paths to it (absolute ones from
    older inits are kept as-is)."""
    cfg["repo"] = str(repo)
    defaults = {"violations_log": ".claude/agent_setup_violations.jsonl",
                "runs_log": ".claude/agent_setup_runs.jsonl",
                "hookkeys": ".claude/agent_setup_hookkeys.json",
                "calls_log": ".claude/agent_setup_calls.jsonl"}  # calls_log: TASK-064, may predate a config
    for k, default in defaults.items():
        cfg[k] = str(repo / cfg.get(k, default))
    return cfg


def load_cfg(repo):
    repo = Path(repo).resolve()
    p = repo / ".claude" / "agent_setup.json"
    if not p.exists():
        sys.exit(f"{p} missing: run `init` first")
    return resolve_cfg(json.loads(p.read_text()), repo)


def load_jsonl(path, pred=lambda _: True):
    out = []
    try:
        for line in open(path):
            try:
                v = json.loads(line)
            except ValueError:
                continue
            if pred(v):
                out.append(v)
    except OSError:
        pass
    return out


def append_jsonl(path, obj):
    try:
        with open(path, "a") as f:
            f.write(json.dumps(obj) + "\n")
    except OSError:
        pass


def stop_flags(repo: Path, tid: str | None):
    flags = [GLOBAL_STOP, repo / "work" / "STOP_ALL"]
    if tid:
        flags += [repo / "work" / tid / "STOP", repo / "work" / tid / ".wrapup"]
    return [f for f in flags if f.exists()]


# ------------------------------------------------------------------ REQ-0060 96.7 per-task binding
_STATE = Path(".claude") / "state"
_TASK_ID = re.compile(r"TASK-[0-9]+$")
_EXCLUDED = (".claude/state/", "docs/req/", "docs/design/", "docs/report/", "work/")
_BIND_TTL = 3600


def _jload(p, default):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return default


def _jsave(p, obj):
    try:
        tmp = Path(str(p) + f".{os.getpid()}.{os.urandom(3).hex()}.tmp")
        with open(tmp, "w") as f:
            f.write(json.dumps(obj))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except OSError:
        pass


def multi_mode(repo):
    """True when per-task files exist (`task.TASK-N.json`): the 96.7 rules apply only then."""
    try:
        return any(re.fullmatch(r"task\.TASK-[0-9]+\.json", f) for f in os.listdir(Path(repo) / _STATE))
    except OSError:
        return False


def _task_file(repo, tid):
    if isinstance(tid, str) and _TASK_ID.match(tid):
        return Path(repo) / _STATE / f"task.{tid}.json"
    return None


# ------------------------------------------------------------------ REQ-0061 97.x task lead
_BIND_FLAGS = {"fence": False, "pending": False}
_LEAD_CHILDREN = ("designer", "coder", "tester", "verifier", "inspector")


def _vlog(repo, row):
    row = dict({"ts": int(time.time())}, **row)
    append_jsonl(Path(repo) / ".claude" / "agent_setup_violations.jsonl", row)


def _proc_start(pid):
    """Field 22 of /proc/<pid>/stat (start time in ticks), None without /proc."""
    try:
        t = Path(f"/proc/{pid}/stat").read_text()
        return t[t.rindex(")") + 2:].split()[19]
    except (OSError, ValueError, IndexError):
        return None


def _lock_break_reason(lock):
    """Why a held lock may be broken, "gone" when it vanished, else None (97.12)."""
    o = _jload(lock / "owner.json", None)
    if not isinstance(o, dict):
        try:
            age = time.time() - lock.stat().st_mtime
        except OSError:
            return "gone"
        return "no_owner" if age > 5 else None
    pid = o.get("pid")
    if isinstance(pid, int) and pid > 0:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return "pid_gone"
        except OSError:
            pass  # PermissionError: alive
        else:
            st = o.get("start")
            if st and _proc_start(pid) not in (None, st):
                return "pid_reused"
    try:
        if time.time() - float(o.get("ts", 0)) >= 30:
            return "stale"
    except (TypeError, ValueError):
        return "stale"
    return None


@contextlib.contextmanager
def _bind_lock(repo, task=None, role=None):
    """mkdir lock around the binds/launch read-modify-write (97.12). Waits <= 2 s, breaks a dead or stale
    holder (rename aside, then rmtree, logged `lock_break`); fails open with a `bind_lock` row."""
    lock = Path(repo) / ".git" / "agent-setup-binds.lock"
    held, deadline, why = False, time.time() + 2.0, ""
    while True:
        try:
            os.mkdir(lock)
            held = True
            break
        except FileExistsError:
            r = _lock_break_reason(lock)
            if r:
                aside = str(lock) + f".broken.{os.getpid()}.{os.urandom(3).hex()}"
                try:
                    os.rename(lock, aside)
                    shutil.rmtree(aside, ignore_errors=True)
                    if r != "gone":
                        _vlog(repo, {"kind": "lock_break", "role": role, "task": task, "detail": r})
                except OSError:
                    pass
                continue
            if time.time() >= deadline:
                why = "timeout"
                break
            time.sleep(0.02)
        except OSError as e:
            why = type(e).__name__
            break
    if held:
        _jsave(lock / "owner.json", {"pid": os.getpid(), "start": _proc_start(os.getpid()),
                                     "task": task, "role": role, "ts": time.time()})
    else:
        _vlog(repo, {"kind": "bind_lock", "role": role, "task": task, "detail": why})
    try:
        yield
    finally:
        if held:
            o = _jload(lock / "owner.json", {})
            if not isinstance(o, dict) or o.get("pid") in (None, os.getpid()):
                shutil.rmtree(lock, ignore_errors=True)


def _task_lead_gen(repo, t):
    tf = _task_file(repo, t)
    g = _jload(tf, {}).get("lead_gen") if tf else None
    return g if isinstance(g, int) and not isinstance(g, bool) else 0


def _fence_check(repo, role, key, binds, t):
    """97.4: a lead whose claimed gen is older than the task's lead_gen has been replaced."""
    if role != "lead":
        return
    stored = binds.get("gen:" + key)
    if isinstance(stored, int) and stored < _task_lead_gen(repo, t):
        _BIND_FLAGS["fence"] = True


def bound_task(cfg, repo, ev, role, sid):
    """Task of this call (96.7): (1) env CTXGUARD_TASK, (2) sticky bind for sid/agent, (3) launch queue
    (a launching Agent/Task call named the task; the child's first call claims the single match, or with
    several the one whose T its call text names - 97.3), (4) the first write under work/TASK-x/ (only when
    the queue was not ambiguous), (5) the single active task / view (task_from). Binds 2-4 are for roles
    only. A lead's claim stores its gen (97.4). binds/launch updates run under the 97.12 lock."""
    _BIND_FLAGS["fence"] = _BIND_FLAGS["pending"] = False
    env = os.environ.get("CTXGUARD_TASK")
    if env:
        return env
    if role != "session" and multi_mode(repo):
        bp = Path(repo) / ".claude" / "agent_setup_binds.json"
        key = f"{sid}/{ev.get('agent_id') or role}"
        binds = _jload(bp, {})
        binds = binds if isinstance(binds, dict) else {}
        if isinstance(binds.get(key), str):
            _fence_check(repo, role, key, binds, binds[key])
            return binds[key]
        t, pending = None, False
        with _bind_lock(repo, None, role):
            binds = _jload(bp, {})
            binds = binds if isinstance(binds, dict) else {}
            if isinstance(binds.get(key), str):
                _fence_check(repo, role, key, binds, binds[key])
                return binds[key]
            lp = Path(repo) / ".claude" / "agent_setup_launch.json"
            q = _jload(lp, [])
            q = [e for e in q if isinstance(e, dict) and time.time() - e.get("ts", 0) < _BIND_TTL] \
                if isinstance(q, list) else []
            mine = [e for e in q if e.get("sid") == sid and e.get("type") == role]
            pick = None
            if len(mine) == 1:
                pick = mine[0]
            elif len(mine) > 1:
                txt = json.dumps(ev.get("tool_input") or {})
                hit = [e for e in mine if re.search(r"\b%s\b" % re.escape(str(e.get("T"))), txt)]
                if hit and len({e.get("T") for e in hit}) == 1:
                    pick = hit[0]
                else:
                    pending = True
            if pick:
                t = pick.get("T")
                q.remove(pick)
                _jsave(lp, q)
            if not t and not pending:
                ti = ev.get("tool_input") or {}
                if ev.get("tool_name") in ("Write", "Edit", "MultiEdit"):
                    m = re.match(r"work/(TASK-[0-9]+)/", _rel(repo, ti.get("file_path") or ""))
                    t = m.group(1) if m else None
            if t and _TASK_ID.match(t):
                binds[key] = t
                if role == "lead":
                    binds["gen:" + key] = _task_lead_gen(repo, t)
                _jsave(bp, binds)
                return t
        _BIND_FLAGS["pending"] = pending
    return task_from(cfg, repo)


def record_launch(repo, ev, role="session", tid=None):
    """PreToolUse on Agent/Task by main or a lead: remember {sid,type,T,by}, T = first TASK-N on the prompt's
    line 1. For a lead (97.3) returns a refusal reason unless the child is a role type and line 1 names
    the lead's own bound task; None otherwise."""
    ti = ev.get("tool_input") or {}
    typ = ti.get("subagent_type") or ""
    first = (ti.get("prompt") or "").strip().split("\n", 1)[0]
    m = re.search(r"TASK-[0-9]+", first)
    if role == "lead":
        if typ not in _LEAD_CHILDREN:
            return f"a lead launches only {'/'.join(_LEAD_CHILDREN)} (not '{typ}')"
        if not tid or not re.search(r"\b%s\b" % re.escape(tid), first):
            return f"line 1 of the brief must name your task {tid}"
    if not typ or not m:
        return None
    with _bind_lock(repo, m.group(0), role):
        lp = Path(repo) / ".claude" / "agent_setup_launch.json"
        q = _jload(lp, [])
        q = [e for e in q if isinstance(e, dict) and time.time() - e.get("ts", 0) < _BIND_TTL] \
            if isinstance(q, list) else []
        q.append({"sid": ev.get("session_id", "nosession"), "type": typ, "T": m.group(0),
                  "ts": int(time.time()), "by": ev.get("agent_id")})
        _jsave(lp, q)
    return None


def _req_lists_task(repo, req, tid):
    try:
        txt = (Path(repo) / "docs" / "req" / "items" / f"{req}.md").read_text()
    except OSError:
        return False
    m = re.search(r"^tasks:\s*\[([^\]]*)\]", txt, re.M)
    return bool(m) and tid in [x.strip() for x in m.group(1).split(",")]


# TASK-098 F7 lead req grant
_REQ_ITEM = re.compile(r"docs/req/items/(REQ-[0-9]+)\.md")
_REQ_KEEP = re.compile(r"^[ \t]*(?:id|source|epic|supersedes|status|tasks)[ \t]*:.*$", re.M | re.I)
_REQ_ORIG = re.compile(r"^## Original\b.*?(?=^## |\Z)", re.M | re.S)


def _lead_req_write(repo, la, tid, tool, ti, path):
    """F7: the lead may edit the body of a REQ file whose own task list names its task, never a status
    or tasks line. The list is read from disk before the edit, so the edit cannot grant itself."""
    if not la.get("req_items") or tool not in ("Write", "Edit", "MultiEdit"):
        return False
    m = _REQ_ITEM.fullmatch(path)
    if not m or not tid or not _req_lists_task(repo, m.group(1), tid):
        return False
    fp = Path(repo) / path
    want = os.path.join(os.path.realpath(str(Path(repo) / "docs" / "req" / "items")), m.group(1) + ".md")
    if fp.is_symlink() or not fp.is_file() or os.path.realpath(str(fp)) != want:
        return False
    try:
        old = fp.read_text()
    except (OSError, ValueError):
        return False
    if tool == "Write":
        new = ti.get("content")
    else:
        new = old
        edits = ti.get("edits") if tool == "MultiEdit" else [ti]
        if not isinstance(edits, list) or not edits:
            return False
        for e in edits:
            if not isinstance(e, dict):
                return False
            o, n = e.get("old_string"), e.get("new_string")
            if not isinstance(o, str) or not isinstance(n, str) or not o or o not in new:
                return False
            new = new.replace(o, n) if e.get("replace_all") else new.replace(o, n, 1)
    if not isinstance(new, str):
        return False
    return (_REQ_KEEP.findall(old) == _REQ_KEEP.findall(new)
            and _REQ_ORIG.findall(old) == _REQ_ORIG.findall(new))


def _lead_ok_write(la, tid, path):
    n = str(int(tid.split("-")[1]))
    return any(fnmatch.fnmatch(path, g.replace("{N}", n).replace("{T}", tid)) for g in la.get("write", []))


def _strip_quoted(c):
    """F-97-4: c without its quoted spans, or None when a quote is unbalanced. A single-quoted span, or a
    double-quoted span with no `$(`, backtick or backslash, is dropped; any other span stays so the chain
    check still sees it. A backslash outside quotes keeps itself and its next character."""
    out, i, n = [], 0, len(c)
    while i < n:
        ch = c[i]
        if ch == "\\":
            out.append(c[i:i + 2])
            i += 2
        elif ch in "'\"":
            j = c.find(ch, i + 1)
            if j < 0:
                return None
            span = c[i + 1:j]
            if "`" in span or "$(" in span or (ch == '"' and "\\" in span):
                out.append(c[i:j + 1])
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _lead_ok_cmd(repo, la, tid, cmd):
    """97.2: the lead's allow list for one bound task. Single simple commands only (no chaining)."""
    c = (cmd or "").replace("2>&1", "")
    stripped = _strip_quoted(c)  # F-97-4: quoted text is not chaining; an unbalanced quote is refused
    if stripped is None or re.search(r"[;&|`\n<>]|\$\(", stripped):
        return False
    for rx in la.get("bash", []):
        m = re.search(rx.replace("{T}", re.escape(tid)), c)
        if m:
            req = m.groupdict().get("req")
            if req and not _req_lists_task(repo, req, tid):
                continue
            return True
    return False


def _lead_allow(pr, role, tid):
    la = pr.get("lead_allow")
    if (role == "lead" and isinstance(la, dict) and isinstance(tid, str) and _TASK_ID.match(tid)
            and not _BIND_FLAGS["fence"]):
        return la
    return None


def _lead_stop_reasons(repo, cfg, tid, sid):
    """97.6: why a lead should not stop yet (asked once)."""
    d = _jload(_task_file(repo, tid), {})
    why = []
    cp = d.get("checkpoint") if isinstance(d.get("checkpoint"), dict) else {}
    nx = str(cp.get("next") or "").strip()
    if not nx:
        why.append("checkpoint.next is empty (tasks.sh checkpoint " + tid + " --next ...)")
    elif cp.get("at") and str(d.get("updated_at") or "") > str(cp.get("at")):
        why.append("checkpoint.next is older than the last update")
    scope = d.get("scope") if isinstance(d.get("scope"), list) else []
    if scope:
        try:
            out = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--", *scope],
                                 capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        if out.strip():
            why.append("scope has uncommitted changes (tasks.sh commit " + tid + ")")
    now, live = time.time(), {}
    for c in load_jsonl(cfg["calls_log"], lambda c: c.get("task") == tid and c.get("role") in _LEAD_CHILDREN
                        and c.get("tool") in ("SubagentStart", "SubagentStop")):
        k = c.get("agent") or c.get("sid")
        live[k] = c["tool"] == "SubagentStart" and now - c.get("ts", 0) < 900
    if any(live.values()):
        why.append("a child role of this task is still running")
    return why


def _other_scopes(repo, tid):
    """{U: [globs]} for every task file that is not done and not `tid` (held tasks keep their scope)."""
    done = {i.get("task_id") for i in _jload(Path(repo) / _STATE / "backlog.json", [])
            if isinstance(i, dict) and i.get("status") == "done"}
    out = {}
    try:
        names = os.listdir(Path(repo) / _STATE)
    except OSError:
        return out
    for f in sorted(names):
        m = re.fullmatch(r"task\.(TASK-[0-9]+)\.json", f)
        if not m or m.group(1) in done:
            continue
        d = _jload(Path(repo) / _STATE / f, {})
        sc = d.get("scope") if isinstance(d, dict) else None
        out[m.group(1)] = [g for g in (sc if isinstance(sc, list) else []) if isinstance(g, str)]
    return out


def _scope_match(path, globs):
    for g in globs:
        if g.startswith(_EXCLUDED):
            continue
        g = g + "*" if g.endswith("/") else g
        if fnmatch.fnmatchcase(path, g):
            return g
    return None


_WRITE_VERB = re.compile(r"(>>?|>\||\btee\b|\bsed\s+(-[a-zA-Z]*i|--in-place)|\bperl\s+-[a-zA-Z]*i|"
                         r"\b(cp|mv|rm|truncate|install|ln|touch|chmod|dd)\b)([^;&|\n]|\\\n)*")


def _bash_write_targets(c):
    """Words after a write verb, quotes stripped first (96.18: `>"work/TASK-9/x"` must not slip past)."""
    nq = re.sub(r"['\"]", "", c or "")
    out = []
    for m in _WRITE_VERB.finditer(nq):
        out += [t for t in re.split(r"[\s;&|()<>=,]+", m.group(0)) if "/" in t or t.endswith(".md")]
    return out


def task_boundary(cfg, repo, role, tool, ti, tid, sid):
    """96.7 B1/B2/U2 for a bound role in multi mode: reason string (exit 2) or None. A path outside
    every task scope is allowed and logged as `scope_out` (U2)."""
    if not tid or not _TASK_ID.match(tid) or not multi_mode(repo):
        return None
    if tool in ("Write", "Edit", "MultiEdit"):
        paths = [_rel(repo, ti.get("file_path") or "")]
    elif tool == "Bash":
        paths = [_rel(repo, t) for t in _bash_write_targets(ti.get("command"))]
    else:
        return None
    others = _other_scopes(repo, tid)
    mine = others.pop(tid, [])
    for path in paths:
        m = re.match(r"work/(TASK-[0-9]+)(/|$)", path)
        if m:
            if m.group(1) != tid:
                return f"B1: {path} belongs to {m.group(1)}, this role is bound to {tid}"
            continue
        if not path or path.startswith(_EXCLUDED) or os.path.isabs(path):
            continue
        if _scope_match(path, mine):
            continue
        for u, globs in sorted(others.items()):
            g = _scope_match(path, globs)
            if g:
                return f"B2: {path} is in the scope of {u} ({g}), owned by {u}: send CLAIM REQUEST to main"
        append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role, "task": tid,
                                              "kind": "scope_out", "tool": tool, "detail": path[:200]})
    return None


def pg_alive(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def kill_group(pgid, grace=10):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        t = time.time()
        while time.time() - t < grace:
            if not pg_alive(pgid):
                return
            time.sleep(0.5)


# =========================================================================== hook
NOISY = re.compile(r"(^|[;&|(]\s*)(cat|grep\s+-\w*r\w*|rg|find|tree|ls\s+-\w*R\w*|git\s+(log|diff)|"
                   r"go\s+test|npm\s+(test|run)|yarn\s+test|pytest|mvn|gradle|\./gradlew)\b")
LIMITED = re.compile(r"\|\s*(head|tail|wc|grep\s+-c)\b|--max-count|\s-m\s*\d|\s-q\b|-quiet\b")
ROLE_KEYS = ("agent_type", "subagent_type", "agent_name")


def detect_role(ev):
    r = os.environ.get("CTXGUARD_ROLE")
    if r:
        return r
    for k in ROLE_KEYS:
        v = ev.get(k)
        if isinstance(v, str) and v:
            return v
    return "session"


def _rel(repo, p):
    """Path as matched by protect globs: repo-relative inside the repo, absolute outside."""
    if not p:
        return ""
    ap = Path(p) if os.path.isabs(p) else Path(repo) / p
    ap = Path(os.path.normpath(str(ap)))
    try:
        return str(ap.relative_to(repo))
    except ValueError:
        return str(ap)


_WILD = re.compile(r"[*?\[]")


def _fixed(p):
    """Directory part of a glob before its first wildcard ("a/b*/c" -> "a"); p itself if none."""
    m = _WILD.search(p)
    return os.path.dirname(p[:m.start()]) if m else p


def _root(p):
    """(dir, comp) of a read glob: dir as `_fixed`, comp = the component holding the first
    wildcard ("x/pent*" -> ("x", "pent*"); "x/*" -> ("x", "*")), None when there is no wildcard."""
    d = _fixed(p)
    if not _WILD.search(p):
        return d, None
    rest = p[len(d):].lstrip("/") if d else p
    return d, rest.split("/")[0]


def _reaches(path, roots):
    """The protected root a search from `path` would enter (path inside it or above it), else None.
    Each root is (dir, comp): a path under dir is inside only when its first component after dir
    matches comp (any component when comp is None), so a `<name>*` glob covers every sibling copy
    without protecting the rest of dir."""
    p = path.rstrip("/")
    for r, comp in roots:
        if path == r or r.startswith(p + "/") or (path == "." and not os.path.isabs(r)):
            return r
        if path.startswith(r + "/") and (
                comp is None or fnmatch.fnmatch(path[len(r) + 1:].split("/")[0], comp)):
            return r
    return None


def _bash_paths(c):
    """Words of a Bash command that look like paths (VAR=/x and --opt=/x included)."""
    try:
        toks = shlex.split(c, comments=True)
    except ValueError:
        toks = c.split()
    for t in toks:
        if re.match(r"^(--?[\w-]+|\w+)=", t):
            t = t.split("=", 1)[1]
        elif t.startswith("-"):
            continue
        t = os.path.expanduser(t)
        if "$" in t or t.strip("/") == "" or not ("/" in t or t == ".."):
            continue  # a bare "/" is too common as a plain argument (tr /, cut -d /)
        yield _fixed(t) or "."


def protected(cfg, repo, role, tool, ti, tid=None, sid=None):
    """Reason string when a protect rule refuses this call, else None. Always enforced (not
    advice): the project reserves these paths and commands for the main session.
    cfg["protect"] = {"roles": [...], "write_globs": [...], "read_globs": [...], "bash_deny": [re],
    "grantable": [...]}. A read glob also refuses searches that would enter it from above
    (Grep/Glob over a parent dir, `grep -r x ..`), matched on the glob's fixed directory.
    TASK-064 64.6: a write_globs hit is let through when the main session granted this exact
    glob to this role (task.json roles.grants) AND the glob is in `protect.grantable` - other
    globs are never grantable, so a grant for a non-grantable path is ignored and logged."""
    pr = cfg.get("protect") or {}
    if role not in pr.get("roles", []):
        return None
    la = _lead_allow(pr, role, tid)
    hit = lambda path, globs: next((g for g in globs if fnmatch.fnmatch(path, g)), None)
    roots = [(_rel(repo, _root(g)[0]), _root(g)[1]) for g in pr.get("read_globs", [])]
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = _rel(repo, ti.get("file_path") or ti.get("notebook_path") or "")
        g = hit(path, pr.get("write_globs", []))
        if g and la and (_lead_ok_write(la, tid, path) or _lead_req_write(repo, la, tid, tool, ti, path)):
            g = None  # 97.2: the lead's own task docs
        if g:
            grantable = pr.get("grantable", [])
            grants = role_grants(cfg, repo, role, tid)
            if (g in grantable and g in grants) or scope_grant_hit(path, grantable, grants):
                pass  # granted for this role and this glob is grantable: allow
            else:
                if g in grants:
                    append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid,
                                                          "role": role, "task": tid,
                                                          "kind": "grant_ignored", "tool": tool,
                                                          "detail": f"{g} not in protect.grantable"[:200]})
                return f"write to {path} ({g})"
    if tool in ("Read", "Grep", "Glob", "Write", "Edit", "MultiEdit"):
        path = _rel(repo, ti.get("file_path") or ti.get("path") or "")
        g = path and hit(path, pr.get("read_globs", []))
        if g:
            return f"access to {path} ({g})"
    if tool in ("Read", "Grep", "Glob") and roots:
        base = ti.get("file_path") or ti.get("path") or "."
        cands = [base]
        if tool == "Glob" and ti.get("pattern"):
            cands.append(os.path.join(base, _fixed(ti["pattern"]) or "."))  # absolute pattern wins
        for c in cands:
            ap = c if os.path.isabs(c) else os.path.join(str(repo), c)
            for p in {_rel(repo, c), _rel(repo, os.path.realpath(ap))}:
                r = _reaches(p, roots)
                if r:
                    return f"search from {p} reaches protected {r}"
    if tool in ("Write", "Edit", "MultiEdit", "Bash"):
        b = task_boundary(cfg, repo, role, tool, ti, tid, sid)
        if b:
            return b
    if tool == "Bash":
        c = ti.get("command", "") or ""
        for rx in pr.get("bash_deny", []):
            if re.search(rx, c):
                if la and _lead_ok_cmd(repo, la, tid, c):
                    continue  # 97.2: the lead's own task command
                return f"command matches /{rx}/"
        for t in (_bash_paths(c) if roots else ()):
            r = _reaches(_rel(repo, t), roots)
            if r:
                return f"path {t} reaches protected {r}"
    return None


def task_from(cfg, repo):
    """Task id for a role started without CTXGUARD_TASK (e.g. by Claude Code's Agent tool), read
    from the project's current-task file: cfg["task_from"] = {"file": "...json", "key": "id"}."""
    tf = cfg.get("task_from") or {}
    try:
        v = json.loads((repo / tf["file"]).read_text()).get(tf.get("key", "id"))
    except (KeyError, TypeError, OSError, ValueError, AttributeError):
        return None
    return v if isinstance(v, str) and re.fullmatch(r"[\w.-]+", v) else None


def _task_doc(cfg, repo, tid=None):
    """The bound task's file `task.<T>.json` when it exists (96.7), else the active task.json
    (cfg["task_from"]["file"]), or {} if missing/malformed."""
    tfile = _task_file(repo, tid)
    if tfile is not None and tfile.exists():
        d = _jload(tfile, {})
        return d if isinstance(d, dict) else {}
    tf = cfg.get("task_from") or {}
    try:
        d = json.loads((repo / tf.get("file", ".claude/state/task.json")).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


# TASK-098 scope grant (98.4)
def scope_grant_hit(path, grantable, grants):
    """True when a grant entry is itself inside a grantable glob and matches path (never a wider entry)."""
    return any(isinstance(x, str) and ".." not in x and any(fnmatch.fnmatchcase(x, y) for y in grantable)
               and fnmatch.fnmatchcase(path, x) for x in grants)


def role_grants(cfg, repo, role, tid=None):
    """roles.grants[role] from task.json (TASK-064 64.6): a list of write_globs entries the main
    session granted this role, or [] if missing/malformed. Only the main session writes task.json,
    so a role cannot grant itself."""
    g = (_task_doc(cfg, repo, tid).get("roles") or {}).get("grants") or {}
    v = g.get(role) if isinstance(g, dict) else None
    return v if isinstance(v, list) else []


def role_waiver(cfg, repo, role, tid=None):
    """roles.<role>.waiver from task.json, or None (TASK-064 64.2/64.5)."""
    v = (_task_doc(cfg, repo, tid).get("roles") or {}).get(role)
    w = v.get("waiver") if isinstance(v, dict) else None
    return w if isinstance(w, str) and w.strip() else None


def _in_write_globs_minus_grantable(cfg, repo, fp):
    """True if fp matches a protect.write_globs entry that is not in protect.grantable (TASK-064
    64.5): orch_work skips the main session's own reserved/admin files (it owns those), and only
    warns about hands-on edits to ordinary source/test files."""
    pr = cfg.get("protect") or {}
    grantable = set(pr.get("grantable", []))
    path = _rel(repo, fp)
    return any(fnmatch.fnmatch(path, g) for g in pr.get("write_globs", []) if g not in grantable)


def emit_warn(cfg, hook_event_name, kind, msg):
    """Advisory-only JSON for a PreToolUse/SubagentStart/SubagentStop hook: never
    `permissionDecision` (an allow would skip the prompt) so it only ever warns, never blocks."""
    if kind not in cfg.get("warn", []):
        return False
    print(json.dumps({"systemMessage": f"[guard] {msg}",
                      "hookSpecificOutput": {"hookEventName": hook_event_name,
                                              "additionalContext": f"[guard] {msg}"}}))
    return True


# TASK-069 69.9: tamper check. A role's Bash call can rewrite protected config by a route no command
# text shows (a script that builds the path). So the hook snapshots the git-tracked watched files before
# the call and `post` compares after it. Fail-open: any error logs `tamper_error` and never blocks.
TAMPER_PATHS = (".claude/settings*.json", ".claude/agent_setup.json", ".claude/hooks", ".claude/agents",
                ".claude/skills", ".claude/scripts", ".claude/req", "CLAUDE.md", "security_prompt.md",
                "docs/prompts/phase0-*", "docs/prompts/phase2b-*")
# F-97-3: the guard's runtime files (binds, launch, hookkeys, calls and violations logs, .git/*.lock) are
# written by the guard and other agents' hooks at any time; role writes to them are refused pre-call (97.2b).
_RT_EXTRA = ()


def _watch_stat(repo):
    """{tracked watched path: [size, mtime_ns] | None (missing)}; stat only, no hashing."""
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "--", *TAMPER_PATHS],
                         capture_output=True, timeout=5, check=True).stdout
    snap = {}
    for rel in out.decode("utf-8", "surrogateescape").split("\0"):
        if not rel:
            continue
        try:
            st = os.lstat(os.path.join(str(repo), rel))
            snap[rel] = [st.st_size, st.st_mtime_ns]
        except OSError:
            snap[rel] = None
    for rel in _RT_EXTRA:  # 97.2b: untracked runtime files, stat only
        try:
            st = os.lstat(os.path.join(str(repo), rel))
            snap[rel] = [st.st_size, st.st_mtime_ns]
        except OSError:
            snap[rel] = None
    return snap


def _tamper_file(sid, agent):
    key = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{sid}-{agent or 'none'}")
    return Path(os.environ.get("TMPDIR", "/tmp")) / f"ctxguard-{key}.json"


def _log_tamper(cfg, kind, sid, agent, role, tid, detail):
    append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "agent": agent,
                                         "role": role, "task": tid, "kind": kind, "tool": "Bash",
                                         "detail": str(detail)[:200]})


def _tamper_snapshot(cfg, repo, role, tid, sid, agent):
    """PreToolUse side (role Bash only): watched-file stats plus the calls_log size (the window start)."""
    try:
        off = os.path.getsize(cfg["calls_log"]) if os.path.exists(cfg["calls_log"]) else 0
        _tamper_file(sid, agent).write_text(json.dumps({"files": _watch_stat(repo), "off": off}))
    except Exception as e:  # fail-open by design
        _log_tamper(cfg, "tamper_error", sid, agent, role, tid, f"snapshot: {type(e).__name__}: {e}")


def cmd_post(a):
    """`agent_setup.py post` (TASK-069 69.9): PostToolUse hook for Bash. Role only (never the main
    session). Changed watched file and no other actor's call in the window -> `tamper` + a block that
    names the files; another actor called in the window -> `tamper_unsure`, information only. Nothing is
    undone here (the coordinator may be editing the same file): the coordinator checks `git diff`.
    Always exits 0."""
    sf = None
    try:
        cfg_path = Path(a.config).resolve()
        try:
            raw = json.loads(cfg_path.read_text())
        except (OSError, ValueError):  # a role that broke the config must still be caught
            raw = {"protect": {"roles": ["designer", "coder", "tester", "verifier"]}}
        cfg = resolve_cfg(raw, cfg_path.parent.parent)
        ev = json.load(sys.stdin)
        repo = Path(cfg["repo"])
        role = detect_role(ev)
        if role == "session" or role not in (cfg.get("protect") or {}).get("roles", []):
            return
    except Exception:
        return  # cannot even load the config: nothing to log to
    sid, agent = ev.get("session_id", "nosession"), ev.get("agent_id")
    tid = bound_task(cfg, repo, ev, role, sid)
    try:
        sf = _tamper_file(sid, agent)
        if not sf.exists():
            _log_tamper(cfg, "tamper_error", sid, agent, role, tid, "no snapshot")
            return
        snap = json.loads(sf.read_text())
        now = _watch_stat(repo)
        old = snap["files"]
        changed = sorted(p for p in set(old) | set(now) if old.get(p) != now.get(p))
        # a path this role was granted (task.json roles.grants, grantable globs only) is its own work
        _gb = (cfg.get("protect") or {}).get("grantable", [])
        grants = [g for g in role_grants(cfg, repo, role, tid) if g in _gb or scope_grant_hit(g, _gb, [g])]
        changed = [p for p in changed if not any(fnmatch.fnmatch(p, g) for g in grants)]
        if not changed:
            return
        others = 0
        with open(cfg["calls_log"]) as f:  # a call by anyone else in the window
            f.seek(snap["off"])
            for line in f:
                try:
                    c = json.loads(line)
                except ValueError:
                    continue
                if (c.get("sid"), c.get("agent")) != (sid, agent):
                    others += 1
        if others:  # the hooks of the other callers append to these files themselves
            changed = [p for p in changed if p not in _RT_EXTRA]
            if not changed:
                return
        names = ", ".join(changed)
        if others:
            _log_tamper(cfg, "tamper_unsure", sid, agent, role, tid, names)
            print(f"[guard] tamper_unsure: {names} changed during a {role} Bash call; {others} other call(s) "
                  "in the window. Coordinator: git diff -- <files>", file=sys.stderr)
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                  "additionalContext": f"[guard] protected file(s) changed, not necessarily by you: {names}."}}))
            return
        _log_tamper(cfg, "tamper", sid, agent, role, tid, names)
        print(f"[guard] TAMPER by role {role}: {names}. Coordinator: git diff -- <files>; restore the files "
              "if the change is not yours.", file=sys.stderr)
        reason = (f"[guard] this Bash call changed protected file(s): {names}. Roles must not change them. "
                  "Stop, do not repeat it, name the file(s) in your handoff and reply PARTIAL.")
        print(json.dumps({"decision": "block", "reason": reason,
                          "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": reason}}))
    except Exception as e:  # fail-open by design
        _log_tamper(cfg, "tamper_error", sid, agent, role, tid, f"post: {type(e).__name__}: {e}")
    finally:
        try:
            if sf is not None:
                sf.unlink()
        except OSError:
            pass


def cmd_hook(a):
    cfg_path = Path(a.config).resolve()
    cfg = resolve_cfg(json.loads(cfg_path.read_text()), cfg_path.parent.parent)
    try:
        ev = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    repo = Path(cfg["repo"])
    role = detect_role(ev)
    sid = ev.get("session_id", "nosession")
    # TASK-064 64.4: every role, incl. session; TASK-096 96.7: bound per call (env, bind, launch queue, work/, view)
    tid = bound_task(cfg, repo, ev, role, sid)
    tool, ti = ev.get("tool_name", ""), ev.get("tool_input") or {}
    fp = ti.get("file_path", "") or ""
    in_work = "/work/" in fp or fp.startswith("work/")

    def _refuse(kind, msg):
        append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role,
                                             "task": tid, "kind": kind, "tool": tool, "detail": msg[:200]})
        print(f"[guard] {msg}", file=sys.stderr)
        sys.exit(2)

    if _BIND_FLAGS["fence"]:  # 97.4: this lead was replaced by a newer generation
        _refuse("lead_fence", "this lead was replaced by a newer generation: stop now, write nothing.")
    if _BIND_FLAGS["pending"] and tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        _refuse("bind_pending", "bind: run tasks.sh show <your TASK-N> first (several launches are waiting).")
    if role in ("session", "lead") and tool in ("Agent", "Task") and multi_mode(repo):
        why = record_launch(repo, ev, role, tid)
        if why:
            _refuse("lead_launch", why)

    try:  # record observed keys/roles for `doctor`
        p = Path(cfg["hookkeys"])
        seen = json.loads(p.read_text()) if p.exists() else {"keys": [], "roles": []}
        k2, r2 = sorted(set(seen["keys"]) | set(ev)), sorted(set(seen["roles"]) | {role})
        if (k2, r2) != (seen["keys"], seen["roles"]):
            p.write_text(json.dumps({"keys": k2, "roles": r2}))
    except (OSError, ValueError):
        pass

    refused = protected(cfg, repo, role, tool, ti, tid, sid)
    if refused:
        append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid,
                                             "role": role, "task": tid, "kind": "protected",
                                             "tool": tool, "detail": refused[:200]})
        print(f"[guard] refused for role {role}: {refused}. Leave this to the main session; "
              "note it in your handoff.", file=sys.stderr)
        sys.exit(2)

    # Stop / wrap-up requests: only saving progress into work/ is allowed. They stop roles and
    # pipeline sessions, never an interactive main session (it owns the stop and the state) -
    # keyed on CTXGUARD_TASK, not `tid`, since 64.4 now derives `tid` for "session" too.
    if (role != "session" or os.environ.get("CTXGUARD_TASK")) and stop_flags(repo, tid):
        if (tool in ("Write", "Edit", "MultiEdit", "Read") and in_work):
            sys.exit(0)
        print("[guard] stop requested: save progress to your handoff/state.md, reply STATUS: PARTIAL, end.",
              file=sys.stderr)
        sys.exit(2)

    # TASK-064 64.4: every tool call is logged before the tool filter below, so a SendMessage
    # (not in the filter tuple) still counts toward calls_log / msg_budget (64.8).
    append_jsonl(cfg["calls_log"], dict(
        {"ts": int(time.time()), "sid": sid, "agent": ev.get("agent_id"), "role": role,
         "task": tid, "tool": tool},
        **({"path": fp} if tool in ("Write", "Edit", "MultiEdit") else {})))
    if role == "lead":  # 97.6: warn once at 85 % of the lead's turn cap
        mt = int((cfg["roles"].get("lead") or {}).get("max_turns", 120))
        n = len(load_jsonl(cfg["calls_log"], lambda c: c.get("agent") == ev.get("agent_id")
                           and c.get("sid") == sid and c.get("role") == "lead"
                           and c.get("tool") not in ("SubagentStart", "SubagentStop")))
        if n == int(mt * 0.85):
            append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role,
                                                 "task": tid, "kind": "lead_turns", "tool": tool,
                                                 "detail": f"{n}/{mt}"})
            emit_warn(cfg, "PreToolUse", "lead_turns",
                      f"lead at {n}/{mt} turns: save a checkpoint (tasks.sh checkpoint {tid}) and finish a step.")
    if tool == "Bash" and role in (cfg.get("protect") or {}).get("roles", []):
        _tamper_snapshot(cfg, repo, role, tid, sid, ev.get("agent_id"))  # TASK-069 69.9

    if tool == "SendMessage" and role != "session":
        agent_key = ev.get("agent_id") or sid
        budget = cfg.get("msg_budget", 3)
        n = sum(1 for c in load_jsonl(cfg["calls_log"])
                if c.get("tool") == "SendMessage" and c.get("task") == tid and c.get("role") == role
                and (c.get("agent") or c.get("sid")) == agent_key)
        if n == budget + 1 and emit_warn(cfg, "PreToolUse", "msg_budget",
                                    f"{role} has sent {n} messages this task (budget {budget}): "
                                    "stop and let the coordinator decide."):
            append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role,
                                                 "task": tid, "kind": "msg_budget", "tool": tool,
                                                 "detail": str(n)})

    if tool not in ("Read", "Grep", "Glob", "Bash", "Write", "Edit", "MultiEdit"):
        sys.exit(0)
    lim = cfg["roles"].get(role, cfg["session"])
    enforce = role in cfg.get("enforce", [])
    stf = Path(os.environ.get("TMPDIR", "/tmp")) / f"agent-setup-{sid}-{role}.json"
    st = json.loads(stf.read_text()) if stf.exists() else \
        {"since_state": 0, "reads": [], "files": [], "flagged": []}

    def save():
        try:
            stf.write_text(json.dumps(st))
        except OSError:
            pass

    def violate(kind, msg, detail="", once=False):
        # TASK-064 64.5: always logged; `enforce` roles get a hard stop, otherwise a `kind` in
        # cfg["warn"] gets a visible (but never permissionDecision) warning via emit_warn, and
        # anything else stays a silent advisory log line, same as before 64.5.
        if once:
            if kind in st["flagged"]:
                return
            st["flagged"].append(kind)
        append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role,
                                             "task": tid, "kind": kind, "tool": tool,
                                             "detail": str(detail)[:200]})
        if enforce:
            save()
            print(f"[guard] {msg}", file=sys.stderr)
            sys.exit(2)
        emit_warn(cfg, "PreToolUse", kind, msg)

    if tool in ("Write", "Edit", "MultiEdit"):
        if Path(fp).name == "state.md":
            body = ti.get("content") or ti.get("new_string") or ""
            if len(body) > cfg["state_max_chars"]:
                violate("state_big", f"state.md must be <= {cfg['state_max_chars']} chars.", len(body))
        # TASK-064 64.5: orch_work only fires for the interactive main session's own hands-on
        # Write/Edit/MultiEdit, outside work/ and outside its own reserved/admin paths, and is
        # skipped when task.json records a coder waiver for this.
        if (role == "session" and not os.environ.get("CTXGUARD_TASK")
                and cfg.get("orch_delegate", True) and not in_work
                and not _in_write_globs_minus_grantable(cfg, repo, fp)
                and not role_waiver(cfg, repo, "coder", tid)):
            violate("orch_work", "orchestrator: delegate this to a subagent (or record a coder waiver).", fp)
        save()
        sys.exit(0)

    ctx = ctx_from_transcript(ev.get("transcript_path", ""))
    lsoft = (cfg["roles"].get("lead") or {}).get("soft") if role == "lead" else None
    if lsoft:
        if ctx >= lsoft:
            violate("lead_ctx", f"lead context {ctx//1000}k: checkpoint now (tasks.sh checkpoint {tid}).",
                    ctx, once=True)
    elif ctx >= cfg["soft"]:
        violate("over_soft", f"context {ctx//1000}k: finish, save handoff, stop.", ctx, once=True)
    # interactive_orch: the main session working live, not a role subprocess. CTXGUARD_TASK is
    # unset only for that live session - `tid` alone no longer distinguishes them since 64.4 now
    # derives a task id for role=="session" too.
    interactive_orch = (role == "session" and not os.environ.get("CTXGUARD_TASK")
                         and cfg.get("orch_delegate", True))
    if interactive_orch and ctx >= cfg["orch_soft"]:
        violate("orch_big", "orchestrator context too large: delegate.", ctx, once=True)

    if tool == "Read":
        for g in cfg["deny_globs"]:
            if fnmatch.fnmatch(fp, g) or fnmatch.fnmatch(fp, g.replace("**/", "*/")):
                violate("deny_zone", f"skip {g}.", fp)
                break
        limit, offset = ti.get("limit"), ti.get("offset") or 0
        if limit and int(limit) > lim["read"]:
            violate("big_read", f"limit must be <= {lim['read']}.", f"{fp} limit={limit}")
        if not limit and not in_work:
            try:
                with open(fp, "rb") as f:
                    n = sum(1 for _ in f)
            except OSError:
                n = 0
            if n > lim["read"]:
                violate("big_read", f"{n} lines: Grep first, then Read offset/limit <= {lim['read']}.",
                        f"{fp} {n} lines")
        key = f"{fp}:{offset}:{limit or 'all'}"
        if key in st["reads"] and not in_work:
            violate("reread", "already read; use your notes.", key)
        elif key not in st["reads"]:
            st["reads"].append(key)
        if fp not in st["files"] and not in_work:
            if len(st["files"]) >= lim["files"]:
                violate("max_files", f"file quota {lim['files']} reached: report PARTIAL.",
                        len(st["files"]) + 1, once=not enforce)
            st["files"].append(fp)
    if tool == "Bash":
        c = ti.get("command", "")
        if NOISY.search(c) and not LIMITED.search(c):
            violate("noisy_bash", f"truncate output: | head -n {lim['out']} (tests: | tail).", c)
    if tool == "Grep" and ti.get("output_mode") == "content" and not ti.get("head_limit"):
        violate("grep_nolim", f"set head_limit <= {lim['out']}.", ti.get("pattern", ""))
    st["since_state"] += 1
    save()
    sys.exit(0)


def cmd_event(a):
    """`agent_setup.py event` (TASK-064 64.7): SubagentStart/SubagentStop hook. Neither event can
    deny anything, so this only logs to calls_log and, on a role's stop, warns (emit_warn - never
    blocks) about uncommitted changes outside work/ that it edited itself (dirty_stop) or a handoff left
    PROGRESS: IN_PROGRESS (partial_stop). Always exits 0."""
    cfg_path = Path(a.config).resolve()
    cfg = resolve_cfg(json.loads(cfg_path.read_text()), cfg_path.parent.parent)
    try:
        ev = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    repo = Path(cfg["repo"])
    role = detect_role(ev)
    sid = ev.get("session_id", "nosession")
    tid = bound_task(cfg, repo, ev, role, sid)
    kind = ev.get("hook_event_name", "")  # "SubagentStart" | "SubagentStop"
    append_jsonl(cfg["calls_log"], {"ts": int(time.time()), "sid": sid, "agent": ev.get("agent_id"),
                                    "role": role, "task": tid, "tool": kind})
    if kind != "SubagentStop" or role == "session":
        sys.exit(0)

    try:  # dirty_stop: uncommitted changes outside work/ - never block the stop on a slow/broken git
        out = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    # Only paths THIS agent wrote/edited (calls_log Write/Edit/MultiEdit, same agent id and task;
    # same sid+role when the id is missing) - main's own uncommitted state/docs are not the role's.
    # Known limit: changes made through Bash are not attributed to the agent.
    aid = ev.get("agent_id")
    mine = set()
    for c in load_jsonl(cfg["calls_log"], lambda c: c.get("task") == tid):
        if c.get("tool") in ("Write", "Edit", "MultiEdit") and c.get("path") and (
                c.get("agent") == aid if aid else (c.get("sid") == sid and c.get("role") == role)):
            mine.add(_rel(repo, c["path"]))
    dirty = [ln[3:] for ln in out.splitlines() if len(ln) > 3 and not ln[3:].startswith("work/")
             and any(m == ln[3:] or (ln.endswith("/") and m.startswith(ln[3:])) for m in mine)]
    if dirty:
        detail = ", ".join(dirty[:5])
        append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role,
                                             "task": tid, "kind": "dirty_stop", "tool": kind,
                                             "detail": detail[:200]})
        if "dirty_stop" in cfg.get("warn", []):  # 69.10: coordinator-only note, never in the role's context
            print(json.dumps({"systemMessage": f"[guard] {role} left uncommitted edits: {detail}. "
                                               "Coordinator: wip commit."}))

    if role == "lead" and tid and multi_mode(repo) and _task_file(repo, tid) is not None:
        why = _lead_stop_reasons(repo, cfg, tid, sid)
        if why:
            detail = "; ".join(why)
            if ev.get("stop_hook_active"):
                append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role,
                                                     "task": tid, "kind": "lead_stop_skipped", "tool": kind,
                                                     "detail": detail[:200]})
            else:
                append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role,
                                                     "task": tid, "kind": "lead_stop_ask", "tool": kind,
                                                     "detail": detail[:200]})
                print(f"[guard] before stopping: {detail}. Fix it, or stop again to leave as is.",
                      file=sys.stderr)
                sys.exit(2)

    hf = handoff_name(role)  # partial_stop: the role's own handoff is still PROGRESS: IN_PROGRESS
    if tid and hf and role in ROLES and multi_mode(repo) and _task_file(repo, tid) is not None:
        # 96.17 ask-once: a role stops only with a checkpoint (PROGRESS, and `next:` when PARTIAL)
        # newest work/T/handoff/<stem>*.md counts (per-slice names such as code-s3.md)
        stem = hf[:-3] if hf.endswith(".md") else hf
        try:
            cands = sorted((c for c in (repo / "work" / tid / "handoff").glob(stem + "*.md") if c.is_file()),
                           key=lambda c: c.stat().st_mtime)
            lines = cands[-1].read_text().splitlines() if cands else []
        except OSError:
            lines = []
        first = lines[0].strip() if lines else ""
        miss = ""
        if not first.startswith("PROGRESS:"):
            miss = "missing" if not lines else "no PROGRESS: line"
        elif "PARTIAL" in first and not any(re.match(r"\s*next\s*:\s*\S", ln, re.I) for ln in lines[1:]):
            miss = "PARTIAL without next:"
        if miss:
            if ev.get("stop_hook_active"):
                append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role,
                                                     "task": tid, "kind": "checkpoint_skipped", "tool": kind,
                                                     "detail": miss})
            else:
                append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role,
                                                     "task": tid, "kind": "checkpoint_missing", "tool": kind,
                                                     "detail": miss})
                print(f"[guard] write work/{tid}/handoff/{hf} checkpoint (PROGRESS, done, next) before "
                      f"stopping ({miss}).", file=sys.stderr)
                sys.exit(2)
    if tid and hf:
        p = repo / "work" / tid / "handoff" / hf
        try:
            first = p.read_text().splitlines()[0]
        except (OSError, IndexError):
            first = ""
        if first.strip() == "PROGRESS: IN_PROGRESS":
            append_jsonl(cfg["violations_log"], {"ts": int(time.time()), "sid": sid, "role": role,
                                                 "task": tid, "kind": "partial_stop", "tool": kind,
                                                 "detail": str(p)})
            emit_warn(cfg, kind, "partial_stop",
                      f"{role}'s handoff {p} is still PROGRESS: IN_PROGRESS at stop.")
    sys.exit(0)


def cmd_stats(a):
    """`agent_setup.py stats [--task T]` (TASK-064 64.9): read-only, $0, always exits 0. Reports
    per role: SubagentStart/Stop counts, dirty_stop/partial_stop/violation counts, tool-call and
    SendMessage counts and edited paths, from calls_log + violations_log; plus max turns and
    error_max_turns count from runs_log."""
    cfg_path = Path(a.config).resolve()
    cfg = resolve_cfg(json.loads(cfg_path.read_text()), cfg_path.parent.parent)
    pred = (lambda c: c.get("task") == a.task) if a.task else (lambda c: True)
    calls = load_jsonl(cfg["calls_log"], pred)
    viols = load_jsonl(cfg["violations_log"], pred)
    if not calls and not viols:
        print("No agent_setup data yet." + (f" (task {a.task})" if a.task else ""))
        return

    by_role = collections.defaultdict(lambda: {"starts": 0, "stops": 0, "calls": 0,
                                                "sendmessage": 0, "paths": set(),
                                                "violations": collections.Counter()})
    for c in calls:
        r = by_role[c.get("role", "session")]
        tool = c.get("tool", "")
        if tool == "SubagentStart":
            r["starts"] += 1
        elif tool == "SubagentStop":
            r["stops"] += 1
        else:
            r["calls"] += 1
            if tool == "SendMessage":
                r["sendmessage"] += 1
            if c.get("path"):
                r["paths"].add(c["path"])
    for v in viols:
        by_role[v.get("role", "session")]["violations"][v.get("kind", "?")] += 1

    print(f"=== agent_setup stats{f' (task {a.task})' if a.task else ''} ===")
    for role in sorted(by_role):
        r = by_role[role]
        vs = ", ".join(f"{k}={n}" for k, n in sorted(r["violations"].items())) or "none"
        print(f"{role}: starts={r['starts']} stops={r['stops']} calls={r['calls']} "
              f"sendmessage={r['sendmessage']} paths={len(r['paths'])} violations=[{vs}]")

    runs = load_jsonl(cfg["runs_log"], pred) if Path(cfg["runs_log"]).exists() else []
    if runs:
        max_turns = max((r.get("turns", 0) for r in runs), default=0)
        hit_limit = sum(1 for r in runs if r.get("status") == "error_max_turns")
        print(f"runs: {len(runs)}  max_turns={max_turns}  error_max_turns={hit_limit}")


# =========================================================================== pipeline
INTERRUPTS = {"count": 0}


def _on_signal(signum, frame):
    INTERRUPTS["count"] += 1
    print(f"\n[signal] {'graceful stop requested' if INTERRUPTS['count'] == 1 else 'killing now'}",
          file=sys.stderr)


def load_agent(repo, role):
    p = repo / ".claude" / "agents" / f"{role}.md"
    if not p.exists():
        sys.exit(f"agent file missing: {p}")
    m = re.match(r"---\n(.*?)\n---\n(.*)", p.read_text(), re.S)
    if not m:
        sys.exit(f"agent file has no frontmatter: {p}")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def handoff_name(role):
    return ROLES[role]["handoff"] if role in ROLES else f"{role}.md"


def run_role(repo, cfg, task, pipe, idx, a):
    step = pipe["steps"][idx]
    role, tid = step["role"], task["id"]
    d = repo / "work" / tid
    meta, body = load_agent(repo, role)
    tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
    disallowed = sorted((WRITE_TOOLS - set(tools)) | {"Task", "Agent"})
    inputs = ["plan.md"] + (["kit.md"] if (d / "kit.md").exists() else [])
    inputs += [f"handoff/{handoff_name(s['role'])}" for s in pipe["steps"][:idx]
               if (d / "handoff" / handoff_name(s["role"])).exists()]
    extra = []
    if step["status"] in ("IN_PROGRESS", "PARTIAL") and (d / "handoff" / handoff_name(role)).exists():
        extra.append("RESUME: an earlier run of this step was interrupted. Continue from your partial "
                     "handoff; do not redo finished parts.")
    if role == DEFAULT_LOOP[1] and pipe.get("loops"):
        extra.append(f"FIX ROUND {pipe['loops']}: handoff/{handoff_name(DEFAULT_LOOP[0])} reports failures. "
                     f"Fix those first.")
        inputs.append(f"handoff/{handoff_name(DEFAULT_LOOP[0])}")
    prompt = ROLE_PROMPT.format(id=tid, role=role, n=idx + 1, total=len(pipe["steps"]),
                                pipeline=" -> ".join(s["role"] for s in pipe["steps"]),
                                goal=task["goal"], scope=task.get("scope", "-"),
                                inputs=", ".join(f"work/{tid}/{x}" for x in dict.fromkeys(inputs)),
                                handoff=handoff_name(role), extra="\n".join(extra))
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--append-system-prompt", body, "--max-turns", str(a.max_turns),
           "--allowedTools", ",".join(tools), "--disallowedTools", ",".join(disallowed)]
    cmd += shlex.split(a.claude_args or "")
    env = dict(os.environ, CTXGUARD_ROLE=role, CTXGUARD_TASK=tid)

    step["status"], step["attempts"] = "IN_PROGRESS", step["attempts"] + 1
    save_pipe(d, pipe)
    proc = subprocess.Popen(cmd, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            bufsize=1, start_new_session=True, env=env)
    pgid = proc.pid
    RUNNING.mkdir(parents=True, exist_ok=True)
    reg = RUNNING / f"{pgid}.json"
    reg.write_text(json.dumps(dict(pgid=pgid, runner=os.getpid(), repo=str(repo), task=tid,
                                   role=role, started=int(time.time()))))
    q, err_tail = queue.Queue(), collections.deque(maxlen=20)

    def pump(stream, sink):
        for line in stream:
            sink(line)
        sink(None) if sink is q.put else None

    threading.Thread(target=pump, args=(proc.stdout, q.put), daemon=True).start()
    threading.Thread(target=pump, args=(proc.stderr, err_tail.append), daemon=True).start()

    r = dict(role=role, task=tid, peak=0, first_ctx=0, turns=0, sid=None, result="", is_error=False,
             subtype=None, stopped=None, wrapup=False)
    stop_since, eof = None, False
    try:
        while True:
            if INTERRUPTS["count"] == 1 and not (d / "STOP").exists():
                (d / "STOP").touch()
            if INTERRUPTS["count"] >= 2:
                kill_group(pgid, 3); r["stopped"] = "killed"; break
            if stop_flags(repo, tid) and stop_since is None:
                stop_since = time.time()
            if stop_since and time.time() - stop_since > a.grace:
                kill_group(pgid); r["stopped"] = r["stopped"] or "killed_after_grace"; break
            try:
                line = q.get(timeout=1)
            except queue.Empty:
                if eof or proc.poll() is not None and q.empty():
                    break
                continue
            if line is None:
                eof = True
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            r["sid"] = r["sid"] or ev.get("session_id")
            if ev.get("type") == "assistant" and not ev.get("parent_tool_use_id"):
                r["turns"] += 1
                n = ctx_from_usage((ev.get("message") or {}).get("usage"))
                r["first_ctx"] = r["first_ctx"] or n
                r["peak"] = max(r["peak"], n)
                if n >= cfg["hard"] and a.hard_action == "wrapup" and not r["wrapup"]:
                    (d / ".wrapup").touch(); r["wrapup"] = True
                    print(f"    [hard] {n//1000}k: asking {role} to wrap up before compact")
            elif ev.get("type") == "result":
                r["result"] = str(ev.get("result") or "")
                r["is_error"] = bool(ev.get("is_error"))
                r["subtype"] = ev.get("subtype")
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            kill_group(pgid)
    finally:
        for f in (reg, d / ".wrapup"):
            f.unlink(missing_ok=True)
    if stop_since and not r["stopped"]:
        r["stopped"] = "graceful"
    text = r["result"] + "\n" + "".join(err_tail)
    if (r["is_error"] or proc.returncode) and LIMIT_RE.search(text):
        r["limit"] = True
        m = re.search(r"\|(\d{10})\b", text)
        r["reset_at"] = int(m.group(1)) if m else None
    m = re.search(r"STATUS:\s*(DONE|PARTIAL|BLOCKED|FAILED)", r["result"])
    r["status"] = m.group(1) if m else None
    r["rc"] = proc.returncode
    return r


def save_pipe(d, pipe):
    (d / "pipeline.json").write_text(json.dumps(pipe, indent=2))


def load_pipe(d, task):
    p = d / "pipeline.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"status": "IN_PROGRESS", "loops": 0,
            "steps": [{"role": r, "status": "TODO", "attempts": 0} for r in task["roles"]]}


def update_state_md(d, pipe, note=""):
    steps = pipe["steps"]
    cur = next((i for i, s in enumerate(steps) if s["status"] != "DONE"), len(steps))
    lines = [f"STATUS: {pipe['status']}",
             f"Current step: {cur + 1 if cur < len(steps) else '-'}",
             "Steps: " + ", ".join(f"{s['role']}={s['status']}" for s in steps),
             f"Fix loops: {pipe['loops']}"]
    if note:
        lines.append(f"Note: {note}")
    (d / "state.md").write_text("\n".join(lines) + "\n")


def wait_for_reset(r, a, repo, tid):
    reset = r.get("reset_at") or int(time.time()) + a.limit_wait
    until = min(reset + 60, int(time.time()) + a.max_wait)
    print(f"  [limit] usage limit; waiting until {time.strftime('%Y-%m-%d %H:%M', time.localtime(until))}")
    while time.time() < until:
        if stop_flags(repo, tid) or INTERRUPTS["count"]:
            return False
        time.sleep(15)
    return True


def pipeline(repo: Path, tid: str, a) -> dict:
    cfg = load_cfg(repo)
    d = repo / "work" / tid
    if not (d / "task.json").exists():
        sys.exit(f"{d}/task.json missing: run `task` first")
    task = json.loads((d / "task.json").read_text())
    (d / "STOP").unlink(missing_ok=True)
    pipe = load_pipe(d, task)
    if pipe["status"] in ("DONE", "BLOCKED") and not a.reset:
        return dict(task=tid, repo=str(repo), status=pipe["status"], code=0 if pipe["status"] == "DONE" else 3)
    pipe["status"] = "IN_PROGRESS"
    code, note, runs = None, "", []
    while code is None:
        if stop_flags(repo, tid) or INTERRUPTS["count"]:
            pipe["status"], code, note = "PARTIAL", 130, "stopped by request"
            break
        idx = next((i for i, s in enumerate(pipe["steps"]) if s["status"] != "DONE"), None)
        if idx is None:
            pipe["status"], code = "DONE", 0
            break
        step = pipe["steps"][idx]
        if step["attempts"] >= MAX_ATTEMPTS:
            pipe["status"], code, note = "PARTIAL", 2, f"{step['role']} not done after {MAX_ATTEMPTS} runs"
            break
        print(f"  [{tid}] step {idx+1}/{len(pipe['steps'])} {step['role']} (attempt {step['attempts']+1})")
        r = run_role(repo, cfg, task, pipe, idx, a)
        runs.append(r)
        append_jsonl(cfg["runs_log"], dict(r, ts=int(time.time()), repo=str(repo), result=r["result"][:300]))
        print(f"    -> {r['status'] or r.get('stopped') or ('LIMIT' if r.get('limit') else 'no status')}, "
              f"peak {r['peak']//1000}k, overhead {r['first_ctx']//1000}k, turns {r['turns']}")
        if r.get("limit"):
            step["attempts"] -= 1                   # a limit is not the role's fault
            step["status"] = "IN_PROGRESS"
            save_pipe(d, pipe)
            if a.on_limit == "wait" and wait_for_reset(r, a, repo, tid):
                continue
            pipe["status"], code, note = "PARTIAL", 75, f"usage limit; reset_at={r.get('reset_at')}"
            break
        if r.get("stopped"):
            step["status"] = "PARTIAL"
            pipe["status"], code, note = "PARTIAL", 130, f"stopped during {step['role']}"
            break
        st = r["status"] or "PARTIAL"
        if st == "FAILED" and step["role"] == DEFAULT_LOOP[0] and DEFAULT_LOOP[1] in [s["role"] for s in pipe["steps"]]:
            pipe["loops"] += 1
            if pipe["loops"] > MAX_LOOPS:
                step["status"], pipe["status"], code = "BLOCKED", "BLOCKED", 3
                note = f"tests still failing after {MAX_LOOPS} fix rounds"
                break
            back = [s["role"] for s in pipe["steps"]].index(DEFAULT_LOOP[1])
            for s in pipe["steps"][back:idx + 1]:
                s["status"], s["attempts"] = "TODO", 0
            (d / "handoff" / handoff_name(DEFAULT_LOOP[1])).unlink(missing_ok=True)
        elif st == "BLOCKED":
            step["status"], pipe["status"], code = "BLOCKED", "BLOCKED", 3
            note = f"{step['role']} blocked; see handoff/{handoff_name(step['role'])}"
        else:
            step["status"] = "DONE" if st == "DONE" else "PARTIAL"
        save_pipe(d, pipe)
        update_state_md(d, pipe)
    save_pipe(d, pipe)
    update_state_md(d, pipe, note)
    return dict(task=tid, repo=str(repo), status=pipe["status"], code=code, note=note,
                runs=len(runs), peak=max((r["peak"] for r in runs), default=0))


def install_signals():
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)


def cmd_pipeline(a):
    install_signals()
    res = pipeline(Path(a.repo).resolve(), a.id, a)
    print(json.dumps(res))
    sys.exit(res["code"])


def cmd_start_all(a):
    install_signals()
    GLOBAL_STOP.unlink(missing_ok=True)
    jobs = []
    if a.batch:
        for j in load_jsonl(a.batch):
            repo = Path(j["repo"]).resolve()
            if "goal" in j and not (repo / "work" / j["id"] / "task.json").exists():
                cmd_task(argparse.Namespace(repo=str(repo), id=j["id"], goal=j["goal"], kit=j.get("kit"),
                                            roles=j.get("roles"), scope=j.get("scope", "-")))
            jobs.append((repo, j["id"]))
    for r in a.repo or []:
        repo = Path(r).resolve()
        for t in sorted((repo / "work").glob("*/task.json")):
            jobs.append((repo, t.parent.name))
    results, worst = [], 0
    for repo, tid in jobs:
        if GLOBAL_STOP.exists() or INTERRUPTS["count"]:
            break
        print(f"[start-all] {repo.name}/{tid}")
        res = pipeline(repo, tid, a)
        results.append(res)
        print("  " + json.dumps(res))
        if res["code"] == 130:
            break
    print("\n== summary ==")
    for s, n in collections.Counter(r["status"] for r in results).items():
        print(f"  {s}: {n}")
    left = len(jobs) - len(results)
    if left:
        print(f"  not started: {left}")
    codes = {r["code"] for r in results}
    for c in (130, 75, 3, 2):
        if c in codes:
            worst = c
            break
    sys.exit(worst)


def cmd_stop(a):
    targets = []
    if a.repo and a.id:
        flag = Path(a.repo).resolve() / "work" / a.id / "STOP"
        match = lambda j: j["repo"] == str(Path(a.repo).resolve()) and j["task"] == a.id
    elif a.repo:
        flag = Path(a.repo).resolve() / "work" / "STOP_ALL"
        match = lambda j: j["repo"] == str(Path(a.repo).resolve())
    else:
        HOME.mkdir(parents=True, exist_ok=True)
        flag, match = GLOBAL_STOP, (lambda j: True)
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.touch()
    for p in RUNNING.glob("*.json") if RUNNING.exists() else []:
        try:
            j = json.loads(p.read_text())
        except ValueError:
            continue
        if not pg_alive(j["pgid"]):
            p.unlink(missing_ok=True)
            continue
        if match(j):
            targets.append(j)
    print(f"[stop] flag {flag}")
    if a.now:
        for j in targets:
            kill_group(j["pgid"], 5)
            print(f"  killed {Path(j['repo']).name}/{j['task']}/{j['role']} (pgid {j['pgid']})")
    else:
        for j in targets:
            print(f"  asked {Path(j['repo']).name}/{j['task']}/{j['role']} to save and stop "
                  f"(runner kills it after its grace period)")
    if not targets:
        print("  no running role sessions")
    print("  flags are cleared automatically by the next pipeline/start-all run")


def cmd_status(a):
    print("Running role sessions:")
    any_run = False
    for p in RUNNING.glob("*.json") if RUNNING.exists() else []:
        j = json.loads(p.read_text())
        if pg_alive(j["pgid"]):
            any_run = True
            print(f"  {Path(j['repo']).name}/{j['task']}/{j['role']}  pgid {j['pgid']}  "
                  f"{(time.time()-j['started'])//60:.0f} min")
        else:
            p.unlink(missing_ok=True)
    if not any_run:
        print("  none")
    if GLOBAL_STOP.exists():
        print(f"  global stop flag set: {GLOBAL_STOP}")
    for r in a.repo or []:
        repo = Path(r).resolve()
        print(f"\nTasks in {repo}:")
        for t in sorted((repo / "work").glob("*/task.json")):
            pp = t.parent / "pipeline.json"
            pipe = json.loads(pp.read_text()) if pp.exists() else {"status": "NEW", "steps": []}
            steps = " ".join(f"{s['role'][0]}:{s['status'][:4]}" for s in pipe["steps"])
            print(f"  {t.parent.name:20} {pipe['status']:12} {steps}")


# =========================================================================== lessons / doctor
def cmd_lessons(a):
    viol, runs = [], []
    for r in a.repo:
        cfg = load_cfg(r)
        viol += load_jsonl(cfg["violations_log"])
        runs += load_jsonl(cfg["runs_log"])
    print(f"== Lessons across {len(a.repo)} repo(s) ==")
    if runs:
        print("\nPer role (context tokens):")
        by = collections.defaultdict(list)
        for r in runs:
            by[r["role"]].append(r)
        for role, rs in by.items():
            peaks = [r["peak"] for r in rs if r["peak"]]
            ovh = [r["first_ctx"] for r in rs if r.get("first_ctx")]
            lim = sum(1 for r in rs if r.get("limit"))
            print(f"  {role:9} runs {len(rs):3}  avg peak {sum(peaks)//max(len(peaks),1)//1000:>3}k  "
                  f"max {max(peaks, default=0)//1000:>3}k  fixed overhead ~{sum(ovh)//max(len(ovh),1)//1000}k"
                  f"  wrap-ups {sum(1 for r in rs if r.get('wrapup'))}  limits {lim}")
        ovh_all = [r["first_ctx"] for r in runs if r.get("first_ctx")]
        peak_all = [r["peak"] for r in runs if r["peak"]]
        if ovh_all and peak_all and sum(ovh_all) / len(ovh_all) > 0.5 * sum(peak_all) / len(peak_all):
            print("  ! Fixed overhead is over half of the average peak: steps are too small. "
                  "Merge roles (e.g. designer+coder) or give each run more scope.")
    if not viol:
        print("\nNo violations logged.")
        return
    cnt = collections.defaultdict(collections.Counter)
    ex = collections.defaultdict(list)
    for v in viol:
        cnt[v["role"]][v["kind"]] += 1
        e = ex[(v["role"], v["kind"])]
        if v["detail"] not in e and len(e) < 2:
            e.append(v["detail"])
    print("\nViolations (advise mode logs; fix the most frequent first):")
    for role, c in sorted(cnt.items(), key=lambda x: -sum(x[1].values())):
        print(f"  [{role}]")
        for kind, n in c.most_common():
            desc, fix = LESSONS.get(kind, (kind, ""))
            print(f"    - {desc}: {n}x -> {fix}")
            for e in ex[(role, kind)]:
                print(f"        e.g. {e}")


def cmd_doctor(a):
    cfg = load_cfg(a.repo)
    p = Path(cfg["hookkeys"])
    if not p.exists():
        print("No hook events yet. Run one small task first.")
        return
    seen = json.loads(p.read_text())
    print("Hook input keys:", ", ".join(seen["keys"]))
    print("Roles seen by hook:", ", ".join(seen["roles"]))
    pipeline_roles = set(seen["roles"]) & set(ROLES)
    if pipeline_roles:
        print("OK: roles are detected (pipeline sets CTXGUARD_ROLE; per-role budgets apply).")
    else:
        print("WARNING: no role detected. In pipeline mode this means hooks do not inherit the\n"
              "environment; in interactive mode subagent calls look like 'session'.\n"
              "Per-role budgets then apply only through .claude/agents/*.md instructions.")


# =========================================================================== main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--window", type=int, default=200_000)
    p = sub.add_parser("init")
    p.add_argument("--repo", required=True); p.add_argument("--window", type=int, default=200_000)
    p.add_argument("--enforce", default="", help="roles to block instead of advise, e.g. tester,verifier")
    p.add_argument("--overwrite-agents", action="store_true", help="replace existing .claude/agents/*.md")
    p.add_argument("--profile", help="project profile dir (profile.json, project-rules.md, claude-block.md)")
    p.add_argument("--update-tool", action="store_true",
                   help="replace .claude/hooks/agent_setup.py even if it was edited in the repo")
    p = sub.add_parser("task")
    p.add_argument("--repo", required=True); p.add_argument("--id", required=True)
    p.add_argument("--goal", required=True); p.add_argument("--kit")
    p.add_argument("--roles", help="comma-separated pipeline, default designer,coder,tester,verifier")
    p.add_argument("--scope", default="-")
    for name in ("pipeline", "start-all"):
        p = sub.add_parser(name)
        if name == "pipeline":
            p.add_argument("--repo", required=True); p.add_argument("--id", required=True)
        else:
            p.add_argument("--batch", help="JSONL: {repo, id, goal?, kit?, roles?, scope?} per line")
            p.add_argument("--repo", action="append", help="run all tasks under <repo>/work/")
        p.add_argument("--on-limit", choices=["exit", "wait"], default="exit" if name == "pipeline" else "wait")
        p.add_argument("--limit-wait", type=int, default=1800, help="seconds to wait if reset time unknown")
        p.add_argument("--max-wait", type=int, default=6 * 3600)
        p.add_argument("--grace", type=int, default=180, help="seconds a role gets to save after a stop request")
        p.add_argument("--hard-action", choices=["wrapup", "none"], default="wrapup")
        p.add_argument("--max-turns", type=int, default=60)
        p.add_argument("--reset", action="store_true", help="re-run a DONE/BLOCKED task")
        p.add_argument("--claude-args", default="", help='extra args, e.g. "--model sonnet"')
    p = sub.add_parser("stop")
    p.add_argument("--repo"); p.add_argument("--id"); p.add_argument("--now", action="store_true")
    p = sub.add_parser("status"); p.add_argument("--repo", action="append")
    p = sub.add_parser("lessons"); p.add_argument("--repo", action="append", required=True)
    p = sub.add_parser("doctor"); p.add_argument("--repo", required=True)
    p = sub.add_parser("hook"); p.add_argument("--config", required=True)
    p = sub.add_parser("event"); p.add_argument("--config", required=True)  # TASK-064 64.7
    p = sub.add_parser("post"); p.add_argument("--config", required=True)  # TASK-069 69.9
    p = sub.add_parser("stats")  # TASK-064 64.9
    p.add_argument("--config", default=".claude/agent_setup.json")
    p.add_argument("--task")
    a = ap.parse_args()
    {"plan": cmd_plan, "init": cmd_init, "task": cmd_task, "pipeline": cmd_pipeline,
     "start-all": cmd_start_all, "stop": cmd_stop, "status": cmd_status, "lessons": cmd_lessons,
     "doctor": cmd_doctor, "hook": cmd_hook, "event": cmd_event, "post": cmd_post,
     "stats": cmd_stats}[a.cmd.replace("_", "-")](a)


if __name__ == "__main__":
    main()
