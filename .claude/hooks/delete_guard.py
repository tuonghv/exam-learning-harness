#!/usr/bin/env python3
"""Delete guard (TASK-150, REQ-0156): PreToolUse hook for Bash, every session and role.

Incident (RAW-00376..00378): a QA agent meant to clean ./work and a bash `rm` deleted the repo.
RAW-00380: deleting inside the repo or a temp folder is normal; what must never happen is an unrecoverable loss.
- Allowed: targets strictly inside the repo (git restores tracked files, work/ is scratch) or strictly inside /tmp.
- Denied: the repo root, a parent of it, home, /, a glob over any of them (`rm -rf ./*` at the root), anything
  under plans/ reports/ input/ results/ .git/ (not restorable from git), and recursive deletes outside the repo
  and /tmp. Recursive deletes with an unresolved variable, `$(...)`, xargs input or no target are denied (the
  classic `rm -rf "$DIR"/*` with DIR empty); `git clean -x/-X` and `git clean` without a path are denied.
Deny = PreToolUse JSON `permissionDecision: deny` with the reason; otherwise silent exit 0.
Usage (settings.json): python3 -I "$CLAUDE_PROJECT_DIR/.claude/hooks/delete_guard.py"
"""
import fnmatch
import json
import os
import re
import shlex
import sys

REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PROTECTED = ("plans", "reports", "input", "results", ".git")
WRAPPERS = ("sudo", "env", "command", "nohup", "time", "nice", "timeout", "stdbuf", "exec", "xargs", "builtin")
DELETE_WORD = re.compile(r"\b(rm|rmdir|unlink|rmtree|-delete)\b|\bgit\b.*\bclean\b")
KEYWORDS = ("{", "}", "!", "do", "then", "else", "elif", "if", "while", "until", "time")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
HELP = ("Deletes are allowed inside the repo (not plans/ reports/ input/ results/ .git) and /tmp; clean work/ with "
        "`bash .claude/scripts/clean-work.sh TASK-NNN`; ask the user to run anything else with `!`.")


# ------------------------------------------------------------------ splitting
def split_commands(cmd):
    """[[text, [heredoc bodies]]] simple commands: unquoted ; & | ( ) newline split, heredoc bodies kept apart."""
    out, cur, pending = [], [], []
    i, n, q = 0, len(cmd), None

    def flush():
        text = "".join(cur).strip()
        if text:
            out.append([text, []])
        del cur[:]

    while i < n:
        c = cmd[i]
        if q:
            cur.append(c)
            if c == "\\" and q == '"' and i + 1 < n:
                cur.append(cmd[i + 1])
                i += 2
                continue
            if c == q:
                q = None
            i += 1
            continue
        if c in "'\"":
            q = c
            cur.append(c)
        elif c == "\\" and i + 1 < n:
            if cmd[i + 1] != "\n":
                cur.append(c + cmd[i + 1])
            i += 2
            continue
        elif c == "#" and (not cur or cur[-1] in " \t"):
            j = cmd.find("\n", i)
            i = n if j < 0 else j
            continue
        elif c == "<" and cmd.startswith("<<", i) and not cmd.startswith("<<<", i):
            m = re.match(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2", cmd[i:])
            if m:
                pending.append((m.group(3), m.group(1) == "-", len(out)))
                cur.append(" ")
                i += m.end()
                continue
            cur.append(c)
        elif c == "&" and ((cur and cur[-1] in "<>") or cmd.startswith("&>", i)):
            cur.append(c)  # redirection 2>&1 / &>file, not a separator
        elif c in ";&|()\n":
            flush()
            if c == "\n" and pending:
                i += 1
                for delim, strip, owner in pending:
                    body = []
                    while i < n:
                        j = cmd.find("\n", i)
                        line = cmd[i:] if j < 0 else cmd[i:j]
                        i = n if j < 0 else j + 1
                        if (line.lstrip("\t") if strip else line) == delim:
                            break
                        body.append(line)
                    if owner < len(out):
                        out[owner][1].append("\n".join(body))
                pending = []
                continue
        else:
            cur.append(c)
        i += 1
    flush()
    return out


# ------------------------------------------------------------------ paths
def expand(tok, env, cwd):
    """Token with ~ and $VAR expanded from env; None when a part cannot be known."""
    if "`" in tok or "$(" in tok:
        return None
    if tok == "~" or tok.startswith("~/"):
        tok = env.get("HOME", "") + tok[1:]
    bad = []

    def sub(m):
        name = m.group(1) or m.group(2)
        if name == "PWD" and cwd:
            return cwd
        if name in env and env[name] != "":
            return env[name]
        bad.append(name)
        return ""
    out = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)[^}]*\}|\$([A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!-])", sub, tok)
    return None if bad or "$" in out else out


def resolve(tok, env, cwd):
    """(realpath, is_glob) or (None, reason)."""
    exp = expand(tok, env, cwd)
    if exp is None:
        return None, "unresolved variable or command substitution in %r" % tok
    if exp == "":
        return None, "empty target"
    glob = re.search(r"[*?\[]", exp)
    base, first = exp, None
    if glob:
        cut = exp.rfind("/", 0, glob.start()) + 1  # the glob's own path component starts here
        base, first = exp[:cut] or ".", exp[cut:].split("/")[0]
    if not os.path.isabs(base):
        if not cwd:
            return None, "relative target %r after an unknown cd" % tok
        base = os.path.join(cwd, base)
    return os.path.realpath(base), first


def inside(p, root):
    return p.startswith(root.rstrip("/") + "/")


def scope_ok(tok, env, cwd, repo, recursive):
    """None if deleting tok is recoverable or scratch; else the reason (RAW-00380: guard the unrecoverable)."""
    p, glob = resolve(tok, env, cwd)
    if p is None:
        if not recursive and "unresolved" in glob:
            return None  # plain rm "$F": one file, no recursion
        return glob  # the reason
    home = os.path.realpath(env.get("HOME", "/nonexistent"))
    if glob and p in (repo, "/tmp") and glob[0] in "*?[":
        return "%r is a glob over all of %s" % (tok, "the repo root" if p == repo else p)
    for d in PROTECTED:
        full = os.path.join(repo, d)
        if p == full or inside(p, full):
            return "%r is under %s/ (git-ignored or git data, not restorable)" % (tok, d)
        if glob and os.path.dirname(full) == p and fnmatch.fnmatchcase(os.path.basename(full), glob):
            return "glob %r can match protected %s/" % (tok, d)
    if inside(p, repo) or (glob and p == repo):
        return None  # tracked files come back from git; work/ is scratch
    if inside(p, "/tmp") or (glob and p == "/tmp"):
        return None
    if p == repo or inside(repo, p) or p in ("/", home):
        what = "%s the repo root, a parent of it, home or /" % ("a glob over" if glob else "")
        return "%r resolves to %s: %s" % (tok, p, what.strip())
    if recursive:
        return "recursive delete of %r resolves to %s, outside this repo and /tmp" % (tok, p)
    return None


def recursive_ok(tok, env, cwd, repo):
    return scope_ok(tok, env, cwd, repo, True)


def plain_ok(tok, env, cwd, repo):
    return scope_ok(tok, env, cwd, repo, False)


# ------------------------------------------------------------------ commands
def strip_redirects(toks):
    out, skip = [], False
    for t in toks:
        if skip:
            skip = False
            continue
        if re.match(r"^\d*(>>?|<|>&|&>>?)$", t):
            skip = True
            continue
        if re.match(r"^\d*(>>?|<|&>>?)\S", t) or re.match(r"^\d*>&\d$", t):
            continue
        out.append(t)
    return out


def unwrap(toks):
    """(tokens without wrappers, from_xargs)."""
    xargs = False
    while toks and os.path.basename(toks[0]) in WRAPPERS:
        w = os.path.basename(toks.pop(0))
        xargs = xargs or w == "xargs"
        while toks and (toks[0].startswith("-") or (w == "env" and "=" in toks[0])
                        or (w == "timeout" and re.match(r"^\d", toks[0]))):
            flag = toks.pop(0)
            if w in ("nice", "xargs") and flag in ("-n", "-I", "-P", "-L", "-d") and toks:
                toks.pop(0)
    return toks, xargs


def check_rm(args, env, cwd, repo, xargs, name):
    recursive, targets, opts = False, [], True
    for a in args:
        if opts and a == "--":
            opts = False
        elif opts and a.startswith("--"):
            recursive = recursive or a == "--recursive"
        elif opts and a.startswith("-") and len(a) > 1:
            recursive = recursive or (name == "rm" and bool(re.search(r"[rR]", a)))
        else:
            targets.append(a)
    if recursive and (xargs or not targets):
        return "recursive %s with targets from xargs/stdin cannot be checked" % name
    fn = recursive_ok if recursive else plain_ok
    for t in targets:
        why = fn(t, env, cwd, repo)
        if why:
            return why
    return None


def check_find(args, env, cwd, repo):
    if "-delete" not in args and not any(a in ("-exec", "-execdir", "-ok") and i + 1 < len(args)
                                         and os.path.basename(args[i + 1]) == "rm"
                                         for i, a in enumerate(args)):
        return None
    roots = []
    for a in args:
        if a.startswith("-") or a in ("(", "!", ")"):
            break
        roots.append(a)
    for r in roots or ["."]:
        why = recursive_ok(r, env, cwd, repo)
        if why:
            return "find -delete: " + why
    return None


def check_git(args, env, cwd, repo):
    base = cwd
    while args and args[0] in ("-C", "-c"):
        if args[0] == "-C" and len(args) > 1:
            e = expand(args[1], env, cwd)
            base = os.path.realpath(os.path.join(cwd or "/", e)) if e else None
        args = args[2:]
    if not args or args[0] != "clean":
        return None
    flags = [a for a in args[1:] if a.startswith("-") and a != "--"]
    paths = [a for a in args[1:] if not a.startswith("-")]
    if any(f in ("-n", "--dry-run") or (not f.startswith("--") and "n" in f) for f in flags):
        return None
    if any(not f.startswith("--") and re.search(r"[xX]", f) for f in flags):
        return "git clean -x/-X also deletes the ignored plans/ reports/ (not restorable from git)"
    if not paths:
        return "git clean without a path deletes every untracked file in the repo (input/ PDFs, new RAW files)"
    for p in paths:
        why = recursive_ok(p, env, base, repo)
        if why:
            return "git clean: " + why
    return None


def check_python(args, bodies, env, cwd, repo):
    code = list(bodies)
    if "-c" in args and args.index("-c") + 1 < len(args):
        code.append(args[args.index("-c") + 1])
    for text in code:
        for m in re.finditer(r"rmtree\(", text):
            lit = re.match(r"rmtree\(\s*[rbu]?(['\"])([^'\"]+)\1\s*[,)]", text[m.start():])
            if not lit:
                return "inline python shutil.rmtree on a computed path"
            why = recursive_ok(lit.group(2), env, cwd, repo)
            if why:
                return "inline python " + why
    return None


def check(command, cwd, repo=REPO, env=None, depth=0):
    """Deny reason or None."""
    env = dict(env if env is not None else {"HOME": os.path.expanduser("~"), "CLAUDE_PROJECT_DIR": repo})
    cwd = os.path.realpath(cwd) if cwd else None
    for text, bodies in split_commands(command):
        try:
            toks = shlex.split(text, posix=True)
        except ValueError:
            if DELETE_WORD.search(text):
                return "cannot parse a command that deletes: %r" % text[:80]
            continue
        toks = strip_redirects(toks)
        while toks and "=" in toks[0] and NAME.match(toks[0].split("=", 1)[0]):
            k, v = toks.pop(0).split("=", 1)
            env[k] = expand(v, env, cwd) or ""
        toks, xargs = unwrap(toks)
        while toks and toks[0] in KEYWORDS:
            toks = toks[1:]
        toks, more = unwrap(toks)
        xargs = xargs or more
        if not toks:
            continue
        name, args = os.path.basename(toks[0]), toks[1:]
        why = None
        if name in ("cd", "pushd"):
            dest = [a for a in args if not a.startswith("-")]
            if not dest:
                cwd = os.path.realpath(env.get("HOME", "/")) if not args else cwd
            else:
                e = expand(dest[0], env, cwd)
                cwd = os.path.realpath(os.path.join(cwd, e)) if (e and (cwd or os.path.isabs(e))) else None
        elif name == "popd":
            cwd = None
        elif name in ("rm", "rmdir", "unlink"):
            why = check_rm(args, env, cwd, repo, xargs, name)
        elif name == "find":
            why = check_find(args, env, cwd, repo)
        elif name == "git":
            why = check_git(args, env, cwd, repo)
        elif re.match(r"^python[0-9.]*$", name):
            why = check_python(args, bodies, env, cwd, repo)
        elif name in ("bash", "sh", "zsh", "dash") and "-c" in args and depth < 3:
            i = args.index("-c")
            if i + 1 < len(args):
                why = check(args[i + 1], cwd, repo, env, depth + 1)
        if why:
            return why
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not DELETE_WORD.search(cmd):
        return 0
    try:
        why = check(cmd, data.get("cwd") or os.getcwd())
    except Exception as exc:  # noqa: BLE001 - a guard bug must not stop all Bash work
        print("delete_guard: internal error, allowed: %s" % exc, file=sys.stderr)
        return 0
    if why:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "delete guard (REQ-0156): %s. %s" % (why, HELP)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
