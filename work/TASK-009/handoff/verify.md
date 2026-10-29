PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency

Verifier: Argus. TASK-009 / REQ-0013. Static plus saved evidence (no Bash; suite.txt not re-read, 219 OK per REQ-0013 ledger).

## AC verdicts
- AC1 VERIFIED: prompts/dev and prompts/releases/v1.0.0 with MANIFEST.json (version, created, per-file sha256); writer prompts.py:41-55, hashing prompts.py:27-38. Real release intact: evidence/verify-release.txt (rc 0, "ok"), test_prompt_channels.py:103-107.
- AC2 VERIFIED (with D1 caveat): config/engine.json:1 prompt_channel=release, prompt_release=v1.0.0; settings.py:45-51 default release; cli.py:40-44 flags; engine.py:88 writes run.prompt = {channel, version}; schema requires both, additionalProperties false (result.schema.json:117-125). Test test_prompt_channels.py:63-71 validates the result against the schema.
- AC3 VERIFIED: release() refuses an existing dir and bad semver (prompts.py:43-47; test :75-84). verify_release reports changed, missing and extra files (prompts.py:66-71; tests :86-101); CLI returns rc 1 (test :93).
- AC4 VERIFIED: default never reads dev (test :50-51); dev edit leaves release unchanged (setUp appends MARK to dev, default dry-run has no MARK). Test bites: evidence/channel-mutation.txt shows marker_count 0 for default and 1 for --channel dev, and release verify rc 0 after the dev edit. Tests run on a temp copy via PROMPTS_DIR patch, so real files are untouched.

## Other checks
- Default = release: VERIFIED (settings.py:48). The dryrun-default.txt header shows rc 0, head dd65bf6+dirty.
- Engine never writes under releases: VERIFIED by grep. The only writer is release() (prompts.py:48-54); engine and settings only read.
- Hash mismatch detected: VERIFIED (test :86-91, one-byte append).
- Path traversal via --prompt-version: REFUTED, see D1.

## Defects
- D1 (major) path traversal on the read side. cli.py:42-44 passes --prompt-version unvalidated to settings.use_prompts (settings.py:38-42 checks only channel). prompt_root() (settings.py:59) does os.path.join(PROMPTS_DIR, "releases", version), so `../x` or `../../x` makes the engine read prompts from outside releases/, for example `--prompt-version ../dev`, which gives dev content while result.json says channel=release. This breaks the frozen-release guarantee and the integrity record. `prompts verify ../x` (prompts.py:92) is also unchecked. Only release() applies VERSION_RE (prompts.py:43). Fix: validate with VERSION_RE in use_prompts (or prompt_root), and add a test for `../dev` and `v1.0.0/../../dev`.
- D2 (minor) no test covers an invalid --prompt-version or a missing release directory (the error path). The evidence has no dryrun for them.
- D3 (minor) prompts.py:50 uses datetime.utcnow(), deprecated since Python 3.12. It works but is noisy.
- D4 (minor) --prompt-version together with --channel dev is silently ignored (settings.py:49-50). Warn or reject it.
