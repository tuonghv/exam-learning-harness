"""Command line: `solve` and the other subcommands behind scripts/exam.py.

solve: run one exam file through solve -> checks -> QA -> decide -> (key) -> result.json.
Exit 0 all PASS, 1 any FAIL/UNCERTAIN/unresolved, 2 invalid input or usage, 3 blocking stop.
Without --mock, --dry-run or --real nothing runs (never defaults to a real call).
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time

from exam_engine import engine, settings
from exam_engine.adapters import claude
from exam_engine.core import schema as sch
from exam_engine.core.decision import decide
from exam_engine.pipeline import (examples_check, explain, metrics, overlay, parser, planrun, prompts, report_build,
                                  plansmigrate, report_kinds, report_pack, reporter, router, runlayout, scorer, solver, verifier)

COMMANDS = ("solve", "parse", "verify", "report", "plan-import", "check-examples", "score", "prompts",
            "check-prompts", "ingest", "ingest-inspect", "ingest-refine", "cross-solve", "benchmark",
            "extract-eval", "gold-pdf", "gen-exams", "lessons", "review-pack", "review-apply", "run-stats",
            "report-pack", "report-index", "run-list", "run-compare", "plans-migrate", "publish", "report-manifests-migrate")
DEFAULT_HISTORY = os.path.join("plans", "run-history.jsonl")
LEGACY_HISTORY = (os.path.join("reports", "run-history.jsonl"),  # read-only fallbacks (RAW-00174, phase 58)
                  os.path.join("results", "run-history.jsonl"))
DEFAULT_REPORT_ROOT = "reports"
DEFAULT_OUT_ROOT = "plans"  # git-ignored; solve output must never be tracked
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USAGE = "usage: exam.py {%s} ..." % "|".join(COMMANDS)


def solve_main(argv=None):
    d = settings.load_config("engine")
    ap = argparse.ArgumentParser(prog="exam solve",
                                 description="Run one exam file through solve -> checks -> QA "
                                             "-> decide -> (key) -> result.json.")
    ap.add_argument("exam")
    ap.add_argument("--out")
    ap.add_argument("--line", default=runlayout.LINE_DEFAULT, metavar="NAME",
                    help="plan line folder: plans/<exam>/<line>/runs/<id> (default main; not with --out)")
    ap.add_argument("--exam-id", metavar="ID",
                    help="plan exam folder (default: the exam file stem); the file stem then becomes the run subject tag")
    ap.add_argument("--key")
    ap.add_argument("--mock")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--publish", action="store_true",
                    help="allow writing into line main (the published line); default: refused, use --line <dev>")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--max-attempts", type=int, default=d["max_attempts"])
    ap.add_argument("--max-cost-usd", type=float, default=d["max_cost_usd"])
    ap.add_argument("--timeout", type=float, default=d["timeout"])
    ap.add_argument("--model", default=d["model"])
    ap.add_argument("--no-pdf", action="store_true", help="write report.md only")
    ap.add_argument("--fresh", action="store_true", help="--real: skip the solve cache reads and the re-run prompt (paid)")
    ap.add_argument("--yes", action="store_true", help="--real: confirm a re-run of an already solved exam (reads the cache)")
    ap.add_argument("--history", metavar="FILE",
                    help="append a metrics line to FILE (default with --real: plans/run-history.jsonl)")
    ap.add_argument("--lang", choices=("vi", "en", "auto"),
                    help="explanation language (beats the header Language:)")
    ap.add_argument("--channel", choices=("release", "dev"),
                    help="prompt channel (default: prompt_channel in config/engine.json)")
    ap.add_argument("--prompt-version", help="release version, e.g. v1.0.0 (default: prompt_release)")
    ap.add_argument("--pdf", metavar="FILE",
                    help="source PDF or ingest doc.json: re-read questions that need a figure/table from page images")
    ap.add_argument("--max-image-pages", type=int, metavar="N",
                    help="cap on distinct pages in the image call (default 4; needs --pdf)")
    ap.add_argument("--image-scope", choices=("flagged", "declined", "doubt"), default="flagged",
                    help="which questions reach the image call: flagged (default), + declined/cut, + doubtful (needs --pdf)")
    ap.add_argument("--adjudicate", action="store_true",
                    help="one extra text call for ids whose text and image answers differ (needs --pdf; off by default)")
    ap.add_argument("--confidence", action="store_true",
                    help="add a confidence tier per answered question (free; PASS bar unchanged)")
    ap.add_argument("--second-sample", action="store_true",
                    help="paid: re-solve no-check/doubt MCQ answers with permuted options; implies --confidence")
    a = ap.parse_args(argv)
    try:
        a.plan_exam = planrun.safe_id(a.exam_id, "exam id") if a.exam_id else planrun.exam_id_of(a.exam)
        runlayout.safe_line(a.line)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    if a.out and (a.exam_id or a.line != runlayout.LINE_DEFAULT):
        print("usage: --line and --exam-id choose the default plans/ folder; they cannot be combined with --out",
              file=sys.stderr)
        return 2
    if (a.image_scope != "flagged" or a.adjudicate) and not a.pdf:
        print("usage: --image-scope declined|doubt and --adjudicate need --pdf", file=sys.stderr)
        return 2
    if a.max_image_pages is not None and (not a.pdf or a.max_image_pages < 0):
        print("usage: --max-image-pages N (N >= 0) needs --pdf", file=sys.stderr)
        return 2
    try:
        settings.use_prompts(a.channel, a.prompt_version)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    if not os.path.isdir(settings.prompt_root()):
        print("ERROR: no such prompt release: %s" % settings.prompt_root(), file=sys.stderr)
        return 2
    modes = [bool(a.mock), a.dry_run, a.real]
    if sum(modes) != 1:
        print("usage: choose exactly one of --mock FILE, --dry-run, --real (never defaults to real)",
              file=sys.stderr)
        return 2
    if a.max_attempts < 1 or a.max_cost_usd < 0 or a.timeout <= 0:
        print("usage: --max-attempts >= 1, --max-cost-usd >= 0, --timeout > 0", file=sys.stderr)
        return 2
    try:  # before any prompt or call: a main run needs --publish
        if not a.dry_run and not a.out:
            runlayout.require_publish(a.line, a.publish, "solve", DEFAULT_OUT_ROOT, a.plan_exam)
        elif a.out:
            runlayout.require_publish(None, a.publish, "solve --out", a.out)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    cache = None
    if a.real:
        ok, hint = claude.pinned(a.model, d.get("model_pins"))
        if not ok:
            print("ERROR: model '%s' is an alias; the solve cache needs a pinned ID: %s" % (a.model, hint),
                  file=sys.stderr)
            return 2
        prev = None if a.fresh else planrun.last_solved(DEFAULT_OUT_ROOT, a.exam, a.plan_exam)
        if prev and not a.yes:
            print("already solved: %s model=%s cost=$%s calls=%s -> %s" % (
                prev["finished_utc"], prev["model"], prev["cost_usd"], prev["calls"], prev["dir"]), file=sys.stderr)
            print("re-run reads the cache (unchanged calls cost $0); --fresh forces a full paid re-solve",
                  file=sys.stderr)
            if not sys.stdin.isatty():
                print("refused: not a terminal; pass --yes to continue with the cache or --fresh to re-solve",
                      file=sys.stderr)
                return 2
            if input("re-run? [y/N] ").strip().lower() != "y":
                return 0
        from exam_engine.ingest import replycache
        cache = replycache.ReplyCache(runlayout.cache_dir(DEFAULT_OUT_ROOT, a.plan_exam))
    plan_only = not a.dry_run and not a.out  # default layout: report goes to reports/ via report_build
    if plan_only:
        try:
            stem = planrun.exam_id_of(a.exam)
            a.out = planrun.claim_run_dir(DEFAULT_OUT_ROOT, a.plan_exam, line=a.line,
                                          subject=stem if a.plan_exam != stem else None, publish=a.publish)
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 2
    cfg = {"max_attempts": a.max_attempts, "max_cost_usd": a.max_cost_usd, "timeout": a.timeout,
           "model": a.model, "key": a.key, "llm_name": "claude-p" if a.real else "mock",
           "pdf": not a.no_pdf, "lang": a.lang}
    if a.pdf:  # cfg keys only with --pdf: config_sha256 of a text-only run is unchanged
        cfg.update(image_pdf=a.pdf, max_image_pages=4 if a.max_image_pages is None else a.max_image_pages)
        if a.image_scope != "flagged":  # only non-default values enter cfg: default runs stay byte-identical
            cfg["image_scope"] = a.image_scope
        if a.adjudicate:  # 76.2: opt-in (the 2025 re-solve measured no gain)
            cfg["adjudicate"] = True
    if a.second_sample:
        cfg["second_sample"] = True
    if a.confidence or a.second_sample:  # cfg key only when set: default config_sha256 and result.json stay unchanged
        cfg["confidence"] = True
    if a.dry_run:
        try:
            text = parser.strip_unlabelled_pages(parser.read_text(a.exam))
        except (OSError, UnicodeDecodeError) as exc:
            print("ERROR: input: cannot read %s: %s" % (a.exam, exc), file=sys.stderr)
            return 2
        exam = parser.parse_exam(a.exam)
        router.apply_lang(exam, a.lang)
        errs = parser.validate_exam(exam)
        if errs:
            for e in errs:
                print("ERROR: input: %s" % e, file=sys.stderr)
            return 2
        _drop_idle_adjudication(cfg, exam)
        print("calls <= %d, cap $%.2f (dry run: no call made)" % (
            engine.call_cap(cfg), a.max_cost_usd))
        image = None
        if a.pdf:
            try:
                image = _solve_image(a, False, None, None)
            except (OSError, ValueError, _ingest_error()) as exc:
                print("ERROR: --pdf: %s" % exc, file=sys.stderr)
                return 2
            _print_image_header(cfg, exam, image)
        print("=== SOLVE prompt ===")
        skip = engine.incomplete_ids(exam)
        ids = [q["id"] for q in sorted(exam["questions"], key=lambda q: q["id"]) if q["id"] not in skip]
        print(solver.solve_prompt(exam, engine.without_questions(text, skip) if skip else text,
                                  cfg["key"], ids))
        print("=== QA prompt template (answers are filled in from the SOLVE reply) ===")
        print(settings.read_prompt("verification/verify_answer.md"))
        print("=== retry prompt: solve prompt + only the open questions + non-key QA findings ===")
        if image:
            from exam_engine.pipeline import cross
            tg = _image_plan(cfg, exam, image)[0]
            if tg:
                print("=== IMAGE prompt (flagged questions; page images attached) ===")
                print(cross.flagged_prompt(exam, cross.flagged_items(exam, tg), cfg.get("image_scope", "flagged") != "flagged"))
        return 0
    tmp = None
    try:
        image = None
        if cfg.get("adjudicate"):
            _drop_idle_adjudication(cfg, parser.parse_exam(a.exam))
        if a.real:
            print("calls <= %d, cap $%.2f" % (engine.call_cap(cfg), a.max_cost_usd), flush=True)
            tmp = tempfile.mkdtemp(prefix="exam_run_")
            image = _solve_image(a, True, tmp, None) if a.pdf else None

            def llm(prompt):
                return claude.run_claude(prompt, model=a.model, timeout_s=a.timeout, cwd=tmp)
        else:
            llm = engine.mock_llm(a.mock)
            image = _solve_image(a, False, None, llm) if a.pdf else None
        if image:
            _print_image_header(cfg, parser.parse_exam(a.exam), image)
        t0 = time.time()
        pw = planrun.PlanWriter(a.out, a.exam, cfg, repo_root=_REPO_ROOT,
                                plan_exam=a.plan_exam if plan_only else None, line=a.line if plan_only else None)
        pw.start()
        result, code = None, None
        try:
            result, code = engine.run(a.exam, a.out, cfg, llm, sink=pw.record, reports=not plan_only,
                                    **({"image": image} if image else {}),
                                    **({"cache": cache, "fresh": a.fresh} if cache is not None else {}))
        finally:  # a crash still leaves plan.json (failed) and the captured calls
            pw.finish(result, code, time.time() - t0)
        wall = round(time.time() - t0, 1)
        if plan_only and result is not None:
            result["reports"] = _build_default_report(a, result)
    except (OSError, ValueError, _ingest_error()) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    if result is not None:
        s = result["summary"]
        print("pass=%d fail=%d uncertain=%d unresolved=%d calls=%d stopped=%s -> %s" % (
            s["pass"], s["fail"], s["uncertain"], s["unresolved"], result["run"]["calls"],
            result["run"]["stopped"], os.path.join(a.out, "result.json")))
        rep_ = result.get("reports") or {}
        for key in ("md", "html", "pdf"):
            if rep_.get(key):
                print("report %s -> %s" % (key, rep_[key]))
        if rep_.get("pdf_status", "").startswith("skipped"):
            print("PDF %s" % rep_["pdf_status"])
        m = result.get("metrics")
        if m:
            m["cost"]["wall_s"] = wall
            for ln in metrics.block(m):
                print(ln)
            if a.real or a.history:
                _append_history(a, result, m)
    return code


def _ingest_error():
    from exam_engine.ingest.schema import IngestError
    return IngestError


def _load_source_doc(path):
    """Ingest document of a PDF, or the doc.json of an earlier ingest (validated)."""
    from exam_engine.ingest import api
    from exam_engine.ingest.schema import validate_document
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        errs = validate_document(doc)
        if errs:
            raise ValueError("invalid document: %s" % "; ".join(errs[:5]))
        return doc
    return api.ingest_document(path, config={"ocr": "auto"})


def _tiny_png():
    import struct
    import zlib

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00")) + chunk(b"IEND", b""))


_STUB_PNG = _tiny_png()


def _solve_image(a, real, tmp, base):
    """Inputs of engine.run(image=...) for solve --pdf: llm(prompt, pngs), render(page), key and present pages.
    Real: pages rendered from the source PDF; mock: base llm answers, stub PNG bytes."""
    from exam_engine.ingest import refine
    doc = _load_source_doc(a.pdf)
    a.file = a.pdf
    key_pages = set()
    for p in doc.get("parts") or refine.partsmod.find_parts(doc):
        if p["kind"] == "answer_key":
            key_pages.update(range(p["pages"][0], p["pages"][1] + 1))
    have = {p["n"] for p in doc["pages"]}
    if real:
        src = _refine_source(a, doc)

        def llm(prompt, imgs):
            return claude.run_claude_images(prompt, [("image/png", p) for p in imgs],
                                            model=a.model, timeout_s=a.timeout, cwd=tmp)
        render = lambda n: refine.render_page(src, n)  # noqa: E731
    else:
        llm = (lambda prompt, imgs: base(prompt)) if base else None  # noqa: E731
        render = lambda n: _STUB_PNG  # noqa: E731
    return {"llm": llm, "render": render, "key_pages": key_pages, "have_pages": have}


def _image_plan(cfg, exam, image):
    skip = engine.incomplete_ids(exam)
    scope = cfg.get("image_scope", "flagged")
    # dry run: no answers yet, so only the skip ids are known as declined; doubt ids appear after the text rounds
    return engine.image_targets(exam, engine.visual_flags(exam), skip, cfg["max_image_pages"],
                                image["key_pages"], image["have_pages"], scope)


def _print_image_header(cfg, exam, image):
    tg, pages, _sk = _image_plan(cfg, exam, image)
    print("image check: %d questions, pages %s, est. $%.2f" % (
        len(tg), pages, 0.03 + 0.035 * len(pages) if tg else 0.0)
        + (", scope %s, ids %s" % (cfg["image_scope"], tg) if cfg.get("image_scope") else ""), flush=True)


def _build_default_report(a, result):
    """solve without --out: the report goes through report_build into a new reports/<exam>/run-<id>/ (+ manifest under plans)."""
    pexam, pline = runlayout.exam_line_of_plan_dir(a.out)
    out = runlayout.new_report_run(DEFAULT_REPORT_ROOT, pexam if pline != "-" else planrun.exam_id_of(a.exam),
                                   line=pline, publish=a.publish)
    git = reporter.git_info(_REPO_ROOT)
    info = report_build.build(a.out, out, view="sheet", pdf=not a.no_pdf, engine_git=git)
    runlayout.finish_report_run(out, [a.out], "sheet", git, "solve")
    return info["reports"]


def _append_history(a, result, m):
    """One history line per real (or --history) run; a history failure never changes the exit code."""
    hist = a.history or DEFAULT_HISTORY
    try:
        root = _REPO_ROOT
        meta = {"run_id": "%s@%s" % (os.path.basename(os.path.abspath(a.out)), time.strftime("%Y%m%dT%H%M%S")),
                "exam_id": os.path.splitext(os.path.basename(a.exam))[0],
                "exam_sha256": metrics.file_sha256(a.exam), "git": reporter.git_info(root),
                "result_path": os.path.abspath(os.path.join(a.out, "result.json")), "source": "solve",
                "plan_dir": os.path.abspath(a.out),
                "lang": a.lang}
        metrics.append(hist, metrics.history_line(result, m, meta))
    except (OSError, ValueError) as exc:
        print("WARN: history not written: %s" % exc, file=sys.stderr)


def _load_exam(path):
    """(exam, None) or (None, exit code) after printing the errors."""
    try:
        exam = parser.parse_exam(path)
    except (OSError, UnicodeDecodeError) as exc:
        print("ERROR: input: cannot read %s: %s" % (path, exc), file=sys.stderr)
        return None, 2
    errs = parser.validate_exam(exam)
    for e in errs:
        print("ERROR: input: %s" % e, file=sys.stderr)
    return (None, 2) if errs else (exam, None)


def parse_main(argv):
    """parse EXAM.md: print the parsed exam as JSON (exit 2 when invalid)."""
    if len(argv) != 1:
        print("usage: exam.py parse EXAM.md", file=sys.stderr)
        return 2
    exam, code = _load_exam(argv[0])
    if exam is None:
        return code
    print(json.dumps(exam, ensure_ascii=False, indent=2))
    return 0


def verify_main(argv):
    """verify EXAM.md SOLVE_OUT.json: code checks + decision per question, no model call."""
    if len(argv) != 2:
        print("usage: exam.py verify EXAM.md SOLVE_OUT.json", file=sys.stderr)
        return 2
    exam, code = _load_exam(argv[0])
    if exam is None:
        return code
    try:
        obj, err = claude.extract_json(parser.read_text(argv[1]))
    except (OSError, UnicodeDecodeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    problems = [err] if err else sch.validate(obj, sch.SOLVE_OUT)
    if problems:
        print("ERROR: solver output: %s" % problems[0], file=sys.stderr)
        return 2
    qs = dict((str(q["id"]), q) for q in exam["questions"])
    out = []
    for a in obj["questions"]:
        q = qs.get(a["id"])
        if q is None:
            continue
        checks = verifier.det_checks(q, a, exam)
        status, reason = decide(checks, None, a)
        out.append({"id": a["id"], "checks": checks, "status": status, "reason": reason})
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _report_plan(argv):
    """report PLAN_RUN [--view sheet|learn] [--no-pdf] [--report-id ID] [--out DIR]"""
    ap = argparse.ArgumentParser(prog="exam report", description="Rebuild a report from a plan run "
                                 "(no model call). Default out: a new reports/<exam-id>/run-<id>/ with its manifest under plans/.")
    ap.add_argument("plan_run")
    ap.add_argument("--view", choices=reporter.VIEWS, default="sheet")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--exam-name", help="exam part of the file names (default: slug of the result exam path)")
    ap.add_argument("--run-name", help="run part of the file names, run-<x> (default: from the out dir name)")
    ap.add_argument("--report-id", "--id", dest="rid", help="report run id (default: new UTC id); same id overwrites that run")
    ap.add_argument("--out", help="override the output dir")
    ap.add_argument("--publish", action="store_true",
                    help="allow writing into line main (the published line); default: refused, use --line <dev>")
    a = ap.parse_args(argv)
    plan = os.path.abspath(a.plan_run.rstrip("/"))
    try:
        meta = planrun.load(plan)["plan"] or {}
        pexam, pline = runlayout.exam_line_of_plan_dir(plan)
        exam_id = planrun.safe_id(pexam if pline != "-" else meta.get("exam_id") or pexam, "exam id")
        planrun.safe_id(meta.get("plan_run_id") or os.path.basename(plan), "plan run id")
        if a.rid:
            planrun.safe_id(a.rid, "report id")
        if a.out:
            runlayout.require_publish(None, a.publish, "report --out", a.out)
        out = a.out or runlayout.new_report_run(DEFAULT_REPORT_ROOT, exam_id, a.rid, line=pline, publish=a.publish)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    try:
        info = report_build.build(plan, out, view=a.view, pdf=not a.no_pdf,
                                  engine_git=reporter.git_info(_REPO_ROOT), exam_name=a.exam_name,
                                  run_name=report_kinds.short_run(a.run_name) if a.run_name else None)
        git = reporter.git_info(_REPO_ROOT)
        if a.out:  # explicit --out: manifest beside --out (never inside it); no INDEX
            runlayout.write_report_manifest(out, [plan], a.view, git, "report")
        else:
            runlayout.finish_report_run(out, [plan], a.view, git, "report")
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    for key in ("md", "answers", "html", "pdf"):
        if info["reports"].get(key):
            print("report %s -> %s" % (key, info["reports"][key]))
    return 0


def _add_overlay_args(ap):
    ap.add_argument("--overlay", action="append", default=[], metavar="PLAN_DIR:PRINTED[,PRINTED...]",
                    help="take answer/solution/status/doubt of these printed numbers from another plan run "
                         "(declined base questions only; in memory, no result.json is written; repeatable)")
    ap.add_argument("--overlay-reason", metavar="TEXT", help="why (required with --overlay; shown on each source line)")


def _ranges(nums):
    """[64, 65, 66, 67, 70] -> '64-67,70'."""
    out, nums = [], sorted(nums)
    while nums:
        j = 0
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[0]) if j == 0 else "%d-%d" % (nums[0], nums[j]))
        nums = nums[j + 1:]
    return ",".join(out)


def report_pack_main(argv):
    """report-pack PLAN_RUN... --out DIR --exam NAME --run ID [--key FILE] [--no-pdf]: standard-named pack, $0."""
    ap = argparse.ArgumentParser(prog="exam report-pack", description="Build one standard-named report folder "
                                 "from several stored plan runs (no model call) and write its INDEX.md.")
    ap.add_argument("plans", nargs="+")
    ap.add_argument("--out", help="default: a new reports/<exam>/run-<id>/")
    ap.add_argument("--exam", required=True, help="exam part of the names, [a-z0-9-]+")
    ap.add_argument("--run", help="run part of the names: f or run-f (default: from the out dir name)")
    ap.add_argument("--key", help="answer key file: adds score-vs-key and score-summary")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--publish", action="store_true",
                    help="allow writing into line main (the published line); default: refused, use --line <dev>")
    _add_overlay_args(ap)
    a = ap.parse_args(argv)
    try:
        plan_dirs = [os.path.abspath(p.rstrip("/")) for p in a.plans]
        overlays = overlay.resolve(a.overlay, plan_dirs, a.overlay_reason)  # every check before any write
        line = runlayout.exam_line_of_plan_dir(a.plans[0])[1]  # mirror the line of the first plan run
        if a.out:
            runlayout.require_publish(None, a.publish, "report-pack --out", a.out)
        out = a.out or runlayout.new_report_run(DEFAULT_REPORT_ROOT, report_kinds.slug(a.exam) or "exam", line=line,
                                                publish=a.publish)
        run = a.run or os.path.basename(os.path.abspath(out))
        info = report_pack.build_pack(plan_dirs, out, a.exam,
                                      report_kinds.short_run(run) if not run.startswith("run-") else run,
                                      key=a.key, pdf=not a.no_pdf, engine_git=reporter.git_info(_REPO_ROOT),
                                      overlays=overlays)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    print("report-pack %d file(s) + %s -> %s" % (len(info["files"]), report_kinds.INDEX_NAME, out))
    if info["total"]:
        print("score %d/%d" % (info["correct"], info["total"]))
    return 0


def _publish_selection(plans_root, reports_root, exam, line):
    """([(plan dir, subject)], source report run row or None): plan runs of the latest complete pack of `line`
    (manifest cmd report-pack/publish, every plan run in `line` and present), else the latest plan run per subject."""
    rows = runlayout.list_report_runs(reports_root, exam, line=line)
    bad = [r["id"] for r in rows if r["warn"] == "unmigrated"]
    if bad:  # no fallback to the old in-folder run.json: never drop silently to "latest per subject"
        raise ValueError("report run(s) %s of line %s still have run.json in the folder; "
                         "run exam report-manifests-migrate --apply" % (", ".join("run-" + b for b in bad), line))
    packs = [r for r in rows
             if r["layout"] == "run" and (r["manifest"] or {}).get("cmd") in ("report-pack", "publish")]
    for r in sorted(packs, key=lambda r: (runlayout.id_time(r["id"]), r["id"]), reverse=True):
        prs = r["manifest"].get("plan_runs") or []
        dirs = [runlayout.plan_run_dir(plans_root, exam, p.get("plan_run_id"), line=line)
                for p in prs if isinstance(p, dict) and p.get("line") == line and p.get("exam_id") == exam
                and p.get("plan_run_id")]
        if prs and len(dirs) == len(prs) and all(os.path.isdir(d) for d in dirs):
            return [(d, None) for d in dirs], r
    latest = {}
    for r in runlayout.list_plan_runs(plans_root, exam, line=line):
        latest[r["subject"]] = r  # list is time-sorted: the last of a subject wins
    return [(r["dir"], r["subject"]) for r in sorted(latest.values(), key=lambda r: r["id"])], None


def publish_main(argv):
    """publish EXAM --from LINE [--view sheet|learn] [--run ID] [--key FILE] [--no-pdf]: new main report run, $0."""
    ap = argparse.ArgumentParser(prog="exam publish", description="Publish a dev line: build a NEW report run in "
                                 "line main from the line's plan runs (no model call; earlier main runs stay).")
    ap.add_argument("exam")
    ap.add_argument("--from", dest="line", required=True, metavar="LINE", help="dev line to publish (not main)")
    ap.add_argument("--view", choices=reporter.VIEWS, default="sheet")
    ap.add_argument("--run", help="run part of the file names (default: the new main run id, run-YYYYMMDD-HHMMSS)")
    ap.add_argument("--key", dest="keyfile", help="answer key file (default: the key recorded in the source pack manifest)")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--plans", default=DEFAULT_OUT_ROOT)
    ap.add_argument("--reports", default=DEFAULT_REPORT_ROOT)
    _add_overlay_args(ap)
    a = ap.parse_args(argv)
    out = None
    try:
        exam, line = planrun.safe_id(a.exam, "exam id"), runlayout.safe_line(a.line)
        if runlayout.is_published_line(line):
            raise ValueError("--from LINE must be a dev line, not %r" % line)
        sel, src = _publish_selection(a.plans, a.reports, exam, line)
        if not sel:
            raise ValueError("no plan runs in line %s of %s under %s" % (line, exam, a.plans))
        for d, _s in sel:
            if not os.path.isfile(os.path.join(d, "result.json")):
                raise ValueError("%s has no result.json" % d)
        print("publish %s from line %s (%s):" % (exam, line, "pack run-" + src["id"] if src else "latest per subject"))
        for d, _s in sel:
            print("  %s" % d)
        kf = a.keyfile or ((src or {}).get("manifest") or {}).get("key")
        if kf and not os.path.isfile(kf):
            raise ValueError("answer key %s not found; pass --key" % kf)
        if not kf:
            print("WARN: no key: score files skipped; pass --key", file=sys.stderr)
        specs, reason = a.overlay, a.overlay_reason
        if not specs:  # inherit the source pack's overlays like the key
            inherited = [o for o in ((src or {}).get("manifest") or {}).get("overlays") or [] if isinstance(o, dict)]
            specs = ["%s:%s" % (o["dir"], ",".join(str(q["printed"]) for q in o["questions"])) for o in inherited]
            reason = reason or "; ".join(sorted({o.get("reason") or "" for o in inherited})) or None
            for o in inherited:
                print("overlay inherited: %s printed %s" % (o["plan_run_id"], _ranges([q["printed"] for q in o["questions"]])))
        overlays = overlay.resolve(specs, [d for d, _s in sel], reason)
        out = runlayout.new_report_run(a.reports, exam, line=runlayout.LINE_DEFAULT, publish=True)
        run = a.run or os.path.basename(out)  # date-style run-<id> of the new main run (REQ-0107)
        info = report_pack.build_pack([d for d, _s in sel], out, report_kinds.slug(exam) or "exam",
                                      report_kinds.short_run(run) if not run.startswith("run-") else run,
                                      key=kf, pdf=not a.no_pdf, engine_git=reporter.git_info(_REPO_ROOT),
                                      view=a.view, cmd="publish", overlays=overlays,
                                      extra={"published_from": line, "source_report_run": src["id"] if src else None})
    except (OSError, ValueError) as exc:
        if out and not os.path.isfile(runlayout.manifest_path(out)):
            shutil.rmtree(out, ignore_errors=True)  # a half-built run never stays as an incomplete main run
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    print("publish %d file(s) -> %s" % (len(info["files"]), out))
    man = runlayout.read_report_manifest(out) or {}
    prev = man.get("prev_report_run")
    print("main: %s -> %s" % ("run-" + prev if prev else "(none)", os.path.basename(out)))
    if info["total"]:
        print("score %d/%d" % (info["correct"], info["total"]))
    return 0


def report_manifests_migrate_main(argv):
    """report-manifests-migrate [--reports reports] [--apply]: move each in-folder run.json to plans/ (TASK-102)."""
    ap = argparse.ArgumentParser(prog="exam report-manifests-migrate", description="Move every report run's in-folder "
                                 "run.json to plans/<exam>[/<line>]/report-runs/run-<id>.json (dry run unless --apply; "
                                 "a custom --reports root not named `reports` puts them beside the run folder).")
    ap.add_argument("--reports", default=DEFAULT_REPORT_ROOT)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.reports):
        print("ERROR: %s is not a folder" % a.reports, file=sys.stderr)
        return 2
    moves, done, problems = runlayout.migrate_run_json(a.reports, apply=a.apply)
    for src, dst in moves:
        print("%s %s -> %s" % ("moved" if a.apply else "would move", src, dst))
    for p in problems:
        print("PROBLEM: %s" % p, file=sys.stderr)
    print("%d %s, %d already migrated, %d problems" % (len(moves), "moved" if a.apply else "to move", done, len(problems)))
    return 2 if problems else 0


def report_index_main(argv):
    """report-index DIR...: (re)write INDEX.md of each exam report folder."""
    if not argv or any(not os.path.isdir(d) for d in argv):
        for d in argv:
            if not os.path.isdir(d):  # an old reports folder that plans-migrate moved: say where its files went
                new = runlayout.migrated_run_dirs(os.path.dirname(os.path.abspath(d)), d)
                if new:
                    print("report-index: %s was moved to %s (run folders below %s)" % (
                        d, ", ".join(new), os.path.dirname(os.path.abspath(d))), file=sys.stderr)
                    return 2
        print("usage: exam.py report-index DIR...", file=sys.stderr)
        return 2
    for d in argv:
        print("report-index -> %s" % report_kinds.write_index(d))
    return 0


def plan_import_main(argv):
    """plan-import DIR [--exam EXAM.md] [--exam-id ID] [--trace FILE...] [--ingest-cache DIR]: old run dir -> plan run."""
    ap = argparse.ArgumentParser(prog="exam plan-import", description="Import an old run dir "
                                 "(result.json, run.log, *.trace.json) into a plan run. No model call.")
    ap.add_argument("dir")
    ap.add_argument("--exam", help="exam file to store as input/exam.md (default: result exam.path if readable)")
    ap.add_argument("--exam-id", help="default: basename of the result exam.path")
    ap.add_argument("--line", default=runlayout.LINE_DEFAULT, metavar="NAME",
                    help="plan line folder: plans/<exam>/<line>/runs/<id> (default main)")
    ap.add_argument("--publish", action="store_true",
                    help="allow writing into line main (the published line); default: refused, use --line <dev>")
    ap.add_argument("--trace", metavar="FILE", action="append", default=[],
                    help="refine *.trace.json to copy into ingest/ (repeatable; <= 20 MB, no symlinks)")
    ap.add_argument("--ingest-cache", metavar="DIR",
                    help="ingest reply-cache dir to copy (default: the only <DIR>/../work/ingest/<hash>)")
    a = ap.parse_args(argv)
    try:
        plan, status = planrun.import_dir(a.dir, DEFAULT_OUT_ROOT, exam_path=a.exam, exam_id=a.exam_id,
                                          ingest_cache=a.ingest_cache,
                                          traces_extra=[os.path.abspath(t) for t in a.trace],
                                          line=runlayout.safe_line(a.line), publish=a.publish)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    print("plan-import %s -> %s" % (status, plan))
    return 0


def report_main(argv):
    if argv and os.path.isdir(argv[0]):
        return _report_plan(argv)
    """report RESULT.json --out DIR [--no-pdf] [--view sheet|learn]: write report files from a result."""
    usage = "usage: exam.py report RESULT.json --out DIR [--no-pdf] [--view sheet|learn]"
    args, view, i = [], "sheet", 0
    while i < len(argv):
        a = argv[i]
        if a == "--view":
            view = argv[i + 1] if i + 1 < len(argv) else None
            i += 1
        elif a.startswith("--view="):
            view = a.split("=", 1)[1]
        elif a != "--no-pdf":
            args.append(a)
        i += 1
    if len(args) != 3 or args[1] != "--out" or view not in reporter.VIEWS:
        print(usage, file=sys.stderr)
        return 2
    try:
        result = settings.load_json(args[0])
        log = metrics.load_log(os.path.join(os.path.dirname(os.path.abspath(args[0])), "run.log"))
        rep = reporter.write_reports(result, args[2], pdf="--no-pdf" not in argv, view=view,
                                     metrics=metrics.compute(result, log) if log is not None else None)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    for key in ("md", "answers", "html", "pdf"):
        if rep.get(key):
            print("report %s -> %s" % (key, rep[key]))
    return 0


def _ingest_check():
    """Print the optional-library and OCR setup that `ingest` would use."""
    from exam_engine.ingest import optional
    from exam_engine.ingest.adapters import pdf
    for mod, pip in (("fitz", "pymupdf"), ("docx", "python-docx"), ("PIL", "pillow")):
        try:
            m = optional.load(mod, pip)
            ver = getattr(m, "VersionBind", None) or getattr(m, "__version__", None) or "ok"
            print("%s: %s" % (mod, ver))
        except Exception as exc:  # noqa: BLE001 - report, keep checking
            print("%s: MISSING (%s)" % (mod, exc))
    print("tesseract: %s" % (shutil.which("tesseract") or "not found"))
    d, lang, have = pdf.pick_ocr_language({})
    print("tessdata: %s" % (d or "not found"))
    print("ocr languages (vie/eng): %s" % (", ".join(have) or "none"))
    print("user site: %s" % (optional.user_site() or "none"))
    return 0


def ingest_main(argv):
    """ingest FILE [--out DOC.json] [--meta K=V ...] [--exam-out EXAM.md]: canonical document."""
    from exam_engine.ingest import api
    from exam_engine.ingest.schema import IngestError
    ap = argparse.ArgumentParser(prog="exam.py ingest")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--exam-out")
    ap.add_argument("--assets", metavar="DIR")
    ap.add_argument("--ocr", choices=["auto", "on", "off"], default="auto",
                    help="images: OCR text only with 'on' (auto = off)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--pages", metavar="SPEC", help="keep only these pages, e.g. 1-4 or 1,3,5-6")
    ap.add_argument("--allow-key-pages", action="store_true",
                    help="allow --exam-out although answer-key pages are present")
    ap.add_argument("--refined", metavar="DOC.json", help="exam text from the AI-refined questions of this document")
    ap.add_argument("--questions", metavar="SPEC", help="with --refined: keep only these question numbers, e.g. 61-90")
    ap.add_argument("--min-verification", choices=["verified", "any"],
                    default=settings.load_config("engine").get("min_verification", "verified"),
                    help="with --exam-out: questions below this level are left out (rejected always); recorded as skipped")
    ap.add_argument("--meta", action="append", default=[], metavar="K=V")
    ap.add_argument("--boundary-ai", choices=["off", "haiku"],
                    default=settings.load_config("engine").get("boundary_ai", "off"),
                    help="AI hints for rule-uncertain boundary lines (needs --mock/--dry-run/--real)")
    ap.add_argument("--mock", metavar="FILE")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--max-cost-usd", type=float, default=0.10)
    ap.add_argument("--cache", metavar="DIR", help="boundary reply cache (real mode only)")
    ap.add_argument("--boundary-trace", metavar="FILE")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    if args.check:
        return _ingest_check()
    modes = sum([bool(args.mock), args.dry_run, args.real])
    if (args.boundary_ai == "haiku") != (modes == 1) or modes > 1 or args.max_cost_usd < 0:
        print("usage: --boundary-ai haiku needs exactly one of --mock FILE, --dry-run, --real "
              "(never defaults to real); those flags need --boundary-ai haiku; --max-cost-usd >= 0",
              file=sys.stderr)
        return 2
    if not args.file:
        print("ERROR: ingest: FILE required", file=sys.stderr)
        return 2
    meta = {}
    for item in args.meta:
        key, sep, val = item.partition("=")
        if not sep or not key.strip():
            print("ERROR: --meta expects K=V, got %r" % item, file=sys.stderr)
            return 2
        meta[key.strip()] = val.strip()
    reviewer, tmp = None, None
    try:
        cfg = {"ocr": args.ocr}
        if args.pages:
            cfg["pages"] = args.pages
        if args.assets:
            cfg["asset_dir"] = args.assets
        if args.boundary_ai == "haiku":
            from exam_engine.ingest import boundary, replycache
            ask = None
            bmodel = "haiku"
            if args.real:
                pins = settings.load_config("engine").get("model_pins")
                bmodel = claude.resolve("haiku", pins)
                if not claude.pinned(bmodel, pins)[0]:
                    print("ERROR: boundary model '%s' is not pinned" % bmodel, file=sys.stderr)
                    return 2
                tmp = tempfile.mkdtemp(prefix="exam_boundary_")
                ask = boundary.make_real_ask(bmodel, settings.load_config("engine")["timeout"], tmp)
            elif args.mock:
                ask = engine.mock_llm(args.mock)
            reviewer = boundary.Reviewer(
                ask, bmodel, args.max_cost_usd,
                replycache.ReplyCache(args.cache if args.real else None), dry_run=args.dry_run,
                keep_text=bool(args.boundary_trace), known=router.known_names())
            cfg["boundary"] = reviewer
        doc = api.ingest_document(args.file, config=cfg, meta=meta)
        blob = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(blob)
        if args.exam_out:
            cfg2 = {"allow_key_pages": args.allow_key_pages, "min_verification": args.min_verification}
            if args.refined:
                with open(args.refined, encoding="utf-8") as fh:
                    doc["refined"] = json.load(fh)["refined"]
                cfg2.update(use_refined=True, questions=args.questions)
            text = api.to_exam_text(doc, cfg2)
            with open(args.exam_out, "w", encoding="utf-8") as fh:
                fh.write(text)
            rows = api.assembly(doc, cfg2) if text != (doc["source"].get("text") or None) else []
            if rows:  # an exam-format Markdown source has no assembly to record
                for r in rows:
                    if r.get("structure"):
                        print("WARN: structure: q%s %s" % (r["id"], ", ".join(r["structure"])), file=sys.stderr)
                side = {"schema": "assembly/1", "exam": os.path.basename(args.exam_out), "questions": rows}
                skipped = api.skipped(doc, cfg2)
                if skipped:  # key only when something was left out (REQ-0024)
                    side["skipped"] = skipped
                    for it in skipped:
                        print("WARN: skipped_unverified: q%s %s" % (it["printed"], it["status"]), file=sys.stderr)
                with open(args.exam_out + ".assembly.json", "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(side, ensure_ascii=False, indent=2) + "\n")
    except IngestError as exc:
        print("ERROR: ingest: %s" % exc, file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print("ERROR: ingest: %s" % exc, file=sys.stderr)
        return 2
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    if reviewer is not None:
        if args.boundary_trace:
            with open(args.boundary_trace, "w", encoding="utf-8") as fh:
                fh.write(boundary.trace_lines(reviewer.trace))
        st = reviewer.stats
        print("boundary-ai: windows %d, suspects %d, skipped %d, cached %d, calls %d%s, hints %d, "
              "invalid %d, low_confidence %d, cost $%.4f" % (
                  st["windows"], st["suspects"], st["skipped"], st["cached"], st["calls"],
                  " (dry run: est. %d, about $%.3f)" % (st["est_calls"], st["est_calls"] * boundary.EST_CALL_USD)
                  if args.dry_run else "", st["hints"], st["invalid"], st["low_confidence"],
                  reviewer.spent), file=sys.stderr if not args.dry_run else sys.stdout)
    if not args.out and not args.dry_run:
        sys.stdout.write(blob)
    return 0


def inspect_main(argv):
    """ingest-inspect DOC.json|FILE [--out REPORT.md] [--pages SPEC]: Markdown report, read-only."""
    from exam_engine.ingest import api, inspect, parts
    from exam_engine.ingest.schema import IngestError, validate_document
    ap = argparse.ArgumentParser(prog="exam.py ingest-inspect")
    ap.add_argument("file")
    ap.add_argument("--out")
    ap.add_argument("--pages", metavar="SPEC")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        if args.file.lower().endswith(".json"):
            with open(args.file, encoding="utf-8") as fh:
                doc = json.load(fh)
            errs = validate_document(doc)
            if errs:
                raise IngestError("invalid_document", "; ".join(errs[:5]))
            if args.pages:
                doc = parts.select_pages(doc, args.pages)
        else:
            doc = api.ingest_document(args.file, config={"pages": args.pages} if args.pages else {})
        text = inspect.report(doc)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
    except (IngestError, OSError, ValueError) as exc:
        print("ERROR: ingest-inspect: %s" % exc, file=sys.stderr)
        return 2
    if not args.out:
        sys.stdout.write(text)
    return 0


IMAGE_FORMATS = ("png", "jpg", "jpeg", "webp", "image_seq")


def _refine_source(args, doc, images=False):
    """File to render pages from (real mode): a PDF path, or with `images` the list of image paths
    in page order; IngestError if one is missing or changed (content or order)."""
    import hashlib
    from exam_engine.ingest.schema import IngestError
    src = doc["source"]
    fmt = src.get("format")
    if fmt != "pdf" and not (images and fmt in IMAGE_FORMATS):
        raise IngestError("unsupported_format", "refine renders PDF pages only (got %s)" % fmt)
    given = getattr(args, "files", None)
    if given and not given[0].lower().endswith(".json"):
        paths = list(given)
    else:
        base = os.path.dirname(os.path.abspath(args.file))
        names = [f["name"] for f in src.get("files") or ()] or [src["name"]]
        paths = [os.path.join(base, n) for n in names] if args.file.lower().endswith(".json") \
            else [args.file]
    want = [f["sha256"] for f in src.get("files") or ()] or [src["sha256"]]
    if len(paths) != len(want):
        raise IngestError("corrupt", "%d file(s) given, the document has %d" % (len(paths), len(want)))
    for k, (path, sha) in enumerate(zip(paths, want), 1):
        if not os.path.isfile(path):
            raise IngestError("corrupt", "source file %s not found next to the document"
                              % os.path.basename(path))
        with open(path, "rb") as fh:
            if hashlib.sha256(fh.read()).hexdigest() != sha:
                raise IngestError("corrupt", "source file %d (%s) differs from the ingested hash "
                                  "(content or file order changed)" % (k, os.path.basename(path)))
    return paths if fmt != "pdf" else paths[0]


def refine_main(argv):
    """ingest-refine FILE --pages SPEC (--dry-run|--mock FILE|--real): AI suggestion, exit 0/1/2/3."""
    from exam_engine.ingest import api, refine, replycache
    from exam_engine.ingest.adapters import image as imgmod
    from exam_engine.ingest.schema import IngestError, validate_document
    d = settings.load_config("engine")
    ap = argparse.ArgumentParser(prog="exam.py ingest-refine")
    ap.add_argument("file", nargs="+", help="PDF/DOCX/MD/JSON, or image files in page order")
    ap.add_argument("--pages", required=True, metavar="SPEC")
    ap.add_argument("--out")
    ap.add_argument("--mock")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--max-cost-usd", type=float, default=1.0)
    ap.add_argument("--timeout", type=float, default=d["timeout"])
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--allow-key-pages", action="store_true")
    ap.add_argument("--all-pages", action="store_true", help="send every selected page, not only flagged ones")
    ap.add_argument("--no-recover", action="store_true",
                    help="do not read pages outside --pages to complete a cut question")
    ap.add_argument("--no-window", action="store_true",
                    help="no multi-page window call for a cut question (pre-phase-47 bridge only)")
    ap.add_argument("--cache", metavar="DIR", help="page reply cache (real mode only)")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    if sum([bool(a.mock), a.dry_run, a.real]) != 1:
        print("usage: choose exactly one of --mock FILE, --dry-run, --real (never defaults to real)",
              file=sys.stderr)
        return 2
    if a.max_cost_usd < 0 or a.timeout <= 0:
        print("usage: --max-cost-usd >= 0, --timeout > 0", file=sys.stderr)
        return 2
    if a.real:
        pins = settings.load_config("engine").get("model_pins")
        a.model = claude.resolve(a.model, pins)
        ok, hint = claude.pinned(a.model, pins)
        if not ok:
            print("ERROR: model '%s' is an alias; the refine cache needs a pinned ID: %s" % (a.model, hint),
                  file=sys.stderr)
            return 2
    a.files, a.file = a.file, a.file[0]
    exts = [os.path.splitext(f)[1].lower().lstrip(".") for f in a.files]
    if len(a.files) > 1 and not all(e in IMAGE_FORMATS for e in exts):
        print("usage: several FILEs are allowed for image files only (png, jpg, jpeg, webp)",
              file=sys.stderr)
        return 2
    tmp = None
    trace = []
    try:
        if len(a.files) > 1:
            doc = api.ingest_sequence(a.files, config={"ocr": "auto"})
        elif a.file.lower().endswith(".json"):
            with open(a.file, encoding="utf-8") as fh:
                doc = json.load(fh)
            errs = validate_document(doc)
            if errs:
                raise ValueError("invalid document: %s" % "; ".join(errs[:5]))
        else:
            doc = api.ingest_document(a.file, config={"ocr": "auto"})
        refine.check_key_pages(doc, a.pages, a.allow_key_pages)
        pages = refine.pick_pages(doc, a.pages, a.all_pages)
        if a.dry_run:
            w = 0 if a.no_window else len(refine.planned_windows(doc, pages))
            print("pages %s, windows planned %d (native), calls <= %d, cap $%.2f, est cost $%.2f "
                  "(dry run: no call made)" % (
                      pages or "none", w, (len(pages) + w) * refine.MAX_ATTEMPTS, a.max_cost_usd,
                      (len(pages) + w) * refine.EST_CALL_USD))
            for n in pages:
                print("=== REFINE prompt, page %d (page image attached) ===" % n)
                print(refine.build_prompt(n))
            return 0
        src = None
        if a.real:
            src = _refine_source(a, doc, images=True)
            tmp = tempfile.mkdtemp(prefix="exam_refine_")
            llm = refine.make_real_llm(a.model, a.timeout, tmp)
            print("pages %s, calls <= %d (+ windows), cap $%.2f" % (
                pages, len(pages) * refine.MAX_ATTEMPTS, a.max_cost_usd), flush=True)
        else:
            llm = refine.mock_llm(a.mock)
        is_img = doc["source"].get("format") in IMAGE_FORMATS
        out = refine.refine(doc, a.pages, llm, src, a.max_cost_usd, a.model, a.allow_key_pages,
                            all_pages=a.all_pages, recover=not a.no_recover,
                            window=not a.no_window, trace=trace,
                            cache=replycache.ReplyCache(a.cache if a.real else None),
                            **({"render": imgmod.render} if is_img else {}))
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    except refine.RefineError as exc:
        print("ERROR: ingest-refine: %s" % exc, file=sys.stderr)
        return 3
    except IngestError as exc:
        print("ERROR: ingest-refine: %s" % exc, file=sys.stderr)
        return 3 if exc.code == "answer_key_present" else 2
    except (OSError, ValueError) as exc:
        print("ERROR: ingest-refine: %s" % exc, file=sys.stderr)
        return 2
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        if trace and a.out:
            with open(a.out + ".trace.json", "w", encoding="utf-8") as fh:
                fh.write(json.dumps(trace, ensure_ascii=False, indent=2) + "\n")
    r = out["refined"]
    nr = [q["id"] for q in r["questions"] if q["needs_review"]]
    print("refined pages=%s questions=%d needs_review=%s calls=%d cost=$%.4f%s%s" % (
        r["pages"], len(r["questions"]), nr or "none", r["calls"], r["cost_usd"],
        " orphans=%d" % len(r["orphans"]) if r.get("orphans") else "",
        " -> %s" % a.out if a.out else ""))
    return 1 if nr else 0


def cross_main(argv):
    """cross-solve EXAM.md --pdf FILE --pages SPEC (--dry-run|--mock FILE|--real): exit 0/1/2/3."""
    from exam_engine.ingest import api, refine
    from exam_engine.ingest.schema import IngestError, validate_document
    from exam_engine.pipeline import cross
    d = settings.load_config("engine")
    ap = argparse.ArgumentParser(prog="exam.py cross-solve")
    ap.add_argument("exam")
    ap.add_argument("--pdf", required=True, metavar="FILE")
    ap.add_argument("--pages", required=True, metavar="SPEC")
    ap.add_argument("--out")
    ap.add_argument("--mock")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--max-cost-usd", type=float, default=1.0)
    ap.add_argument("--timeout", type=float, default=d["timeout"])
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--allow-key-pages", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    if sum([bool(a.mock), a.dry_run, a.real]) != 1:
        print("usage: choose exactly one of --mock FILE, --dry-run, --real (never defaults to real)",
              file=sys.stderr)
        return 2
    if a.max_cost_usd < 0 or a.timeout <= 0 or (not a.dry_run and not a.out):
        print("usage: --max-cost-usd >= 0, --timeout > 0, --out DIR required", file=sys.stderr)
        return 2
    exam, code = _load_exam(a.exam)
    if exam is None:
        return code
    tmp = None
    try:
        text = parser.read_text(a.exam)
        doc = _load_source_doc(a.pdf)
        a.file = a.pdf
        refine.check_key_pages(doc, a.pages, a.allow_key_pages)
        pages = refine.partsmod.parse_pages(a.pages)
        absent = [n for n in pages if n not in [p["n"] for p in doc["pages"]]]
        if absent:
            raise IngestError("invalid_pages", "page(s) %s not in the document"
                              % ", ".join(map(str, absent)))
        bound = cross.MAX_ATTEMPTS * 2
        if a.dry_run:
            print("pages %s, calls <= %d, cap $%.2f (dry run: no call made)" % (
                pages, bound, a.max_cost_usd))
            print("=== ROUTE A prompt (exam text) ===")
            print(cross.route_a_prompt(exam, text))
            print("=== ROUTE B prompt (page images attached) ===")
            print(cross.route_b_prompt(exam, text))
            return 0
        if a.real:
            src = _refine_source(a, doc)
            pngs = [refine.render_page(src, n) for n in pages]
            tmp = tempfile.mkdtemp(prefix="exam_cross_")

            def llm_text(prompt):
                return claude.run_claude(prompt, model=a.model, timeout_s=a.timeout, cwd=tmp)

            def llm_images(prompt, imgs):
                return claude.run_claude_images(prompt, [("image/png", p) for p in imgs],
                                                model=a.model, timeout_s=a.timeout, cwd=tmp)
            print("pages %s, calls <= %d, cap $%.2f" % (pages, bound, a.max_cost_usd), flush=True)
        else:
            base = engine.mock_llm(a.mock)
            pngs = [b""] * len(pages)
            llm_text = base
            llm_images = lambda prompt, imgs: base(prompt)  # noqa: E731
        res = cross.cross_solve(exam, text, llm_text, llm_images, pngs, a.max_cost_usd, a.model)
        os.makedirs(a.out, exist_ok=True)
        trace = res.pop("trace")
        for name, obj in (("cross.json", res), ("cross.trace.json", trace)):
            with open(os.path.join(a.out, name), "w", encoding="utf-8") as fh:
                fh.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
        with open(os.path.join(a.out, "review.md"), "w", encoding="utf-8") as fh:
            fh.write(cross.review_md(res))
    except cross.CrossError as exc:
        print("ERROR: cross-solve: %s" % exc, file=sys.stderr)
        return 3
    except IngestError as exc:
        print("ERROR: cross-solve: %s" % exc, file=sys.stderr)
        return 3 if exc.code == "answer_key_present" else 2
    except (OSError, ValueError) as exc:
        print("ERROR: cross-solve: %s" % exc, file=sys.stderr)
        return 2
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    sm = res["summary"]
    print("agree=%d needs_review=%d of %d, calls=%d cost=$%.4f -> %s" % (
        sm["agree"], sm["needs_review"], sm["questions"], res["calls"], res["cost_usd"], a.out))
    return 1 if sm["needs_review"] else 0


def benchmark_main(argv):
    """benchmark --out DIR (--dry-run|--mock FILE|--real): solve + score evals/inputs; exit 0/1/2/3."""
    from exam_engine.pipeline import benchmark
    d = settings.load_config("engine")
    ap = argparse.ArgumentParser(prog="exam.py benchmark")
    ap.add_argument("--inputs", default="evals/inputs")
    ap.add_argument("--keys", default="evals/keys")
    ap.add_argument("--subject")
    ap.add_argument("--set", metavar="FILE", help="fixed keyed regression set (evals/regset.json); "
                    "appends source=regset history lines")
    ap.add_argument("--history", metavar="FILE", help="history file for --set (default: the solve history)")
    ap.add_argument("--out")
    ap.add_argument("--previous", metavar="summary.json")
    ap.add_argument("--mock")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--budget-usd", type=float, default=3.0)
    ap.add_argument("--max-cost-usd", type=float, default=d["max_cost_usd"])
    ap.add_argument("--max-attempts", type=int, default=d["max_attempts"])
    ap.add_argument("--timeout", type=float, default=d["timeout"])
    ap.add_argument("--model", default=d["model"])
    ap.add_argument("--channel", choices=("release", "dev"))
    ap.add_argument("--prompt-version")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        settings.use_prompts(a.channel, a.prompt_version)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    if sum([bool(a.mock), a.dry_run, a.real]) != 1 or (not a.dry_run and not a.out):
        print("usage: choose exactly one of --mock FILE, --dry-run, --real (never defaults to real); "
              "--out DIR required", file=sys.stderr)
        return 2
    if a.max_attempts < 1 or a.budget_usd < 0 or a.max_cost_usd < 0 or a.timeout <= 0:
        print("usage: --max-attempts >= 1, costs >= 0, --timeout > 0", file=sys.stderr)
        return 2
    set_id, bases = None, {}
    if a.set:
        try:
            set_id, items, bases = benchmark.load_set(a.set, _REPO_ROOT)
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 2
        if a.subject:
            items = [x for x in items if x[0] == a.subject]
    else:
        items = benchmark.discover(a.inputs, a.keys, a.subject)
    if not items:
        print("ERROR: no input/key pairs under %s and %s" % (a.inputs, a.keys), file=sys.stderr)
        return 2
    cfg = {"max_attempts": a.max_attempts, "max_cost_usd": a.max_cost_usd, "timeout": a.timeout,
           "model": a.model, "llm_name": "claude-p" if a.real else "mock", "pdf": False}
    calls = len(items) * engine.call_cap(cfg)
    print("%d items, calls <= %d, budget $%.2f%s" % (
        len(items), calls, a.budget_usd, " (dry run: no call made)" if a.dry_run else ""), flush=True)
    if a.dry_run:
        for sub, n, path, key in items:
            print("  %s/%s  %s  (key %s)" % (sub, n, path, key))
        return 0
    prev = None
    if a.previous:
        try:
            with open(a.previous, encoding="utf-8") as fh:
                prev = json.load(fh)
        except (OSError, ValueError) as exc:
            print("ERROR: --previous: %s" % exc, file=sys.stderr)
            return 2
    tmp = None
    try:
        if a.real:
            tmp = tempfile.mkdtemp(prefix="exam_bench_")

            def llm(prompt):
                return claude.run_claude(prompt, model=a.model, timeout_s=a.timeout, cwd=tmp)
        else:
            llm = engine.mock_llm(a.mock)
        rec = None
        if set_id:
            git, hist = reporter.git_info(_REPO_ROOT), a.history or DEFAULT_HISTORY
            stamp = time.strftime("%Y%m%dT%H%M%S")
            paths = dict(((x[0], x[1]), x[2]) for x in items)

            def rec(sub, n, result, outp):
                meta = {"run_id": "%s/%s/%s@%s" % (set_id, sub, n, stamp), "exam_id": "%s/%s" % (sub, n),
                        "exam_sha256": metrics.file_sha256(paths[(sub, n)]), "git": git,
                        "result_path": os.path.abspath(os.path.join(outp, "result.json")),
                        "source": "regset", "set_id": set_id, "key_basis": bases.get((sub, n))}
                try:
                    metrics.append(hist, metrics.history_line(result, metrics.compute(result), meta))
                except (OSError, ValueError) as exc:
                    print("WARN: history not written: %s" % exc, file=sys.stderr)
        rows = benchmark.run_all(items, a.out, cfg, llm, a.budget_usd, rec)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    sm = benchmark.summarize(rows, {"date": benchmark.today(), "model": a.model,
                                    "prompt": os.path.basename(settings.prompt_root())})
    worse = benchmark.regression(prev, sm) if prev else []
    sm["regression"] = worse
    benchmark.write(sm, a.out)
    t = sm["totals"]
    print("items=%d pass=%d fail=%d uncertain=%d unresolved=%d calls=%d cost=$%.4f skipped=%d -> %s" % (
        t["items"], t["pass"], t["fail"], t["uncertain"], t["unresolved"], sm["calls"],
        sm["cost_usd"], len(sm["skipped"]), a.out))
    if worse:
        print("REGRESSION: pass count fell for %s" % ", ".join(worse))
    return 3 if sm["skipped"] else (1 if worse or t["fail"] or t["unresolved"] else 0)


def genexam_main(argv):
    """gen-exams --subject math --n N --out DIR (--dry-run|--mock FILE|--real): exit 0/1/2/3."""
    from exam_engine.pipeline import genexam
    d = settings.load_config("engine")
    ap = argparse.ArgumentParser(prog="exam.py gen-exams")
    ap.add_argument("--subject")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--seed", default=benchmark_today())
    ap.add_argument("--out", default="evals/generated")
    ap.add_argument("--mock")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--level", choices=("easy", "hard", "harder"), default="hard")
    ap.add_argument("--profile", choices=genexam.PROFILES, default=genexam.PROFILES[0])
    ap.add_argument("--no-qa", action="store_true", help="skip the solution review call")
    ap.add_argument("--max-cost-usd", type=float, default=0.5)
    ap.add_argument("--timeout", type=float, default=d["timeout"])
    ap.add_argument("--model", default=d["model"])
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    if sum([bool(a.mock), a.dry_run, a.real]) != 1 or a.n < 1 or a.max_cost_usd < 0 or a.timeout <= 0:
        print("usage: choose exactly one of --mock FILE, --dry-run, --real (never defaults to real); "
              "--n >= 1, --max-cost-usd >= 0", file=sys.stderr)
        return 2
    a.subject = a.subject or genexam.PROFILE_SUBJECT[a.profile]
    if a.subject != genexam.PROFILE_SUBJECT[a.profile]:
        print("ERROR: profile %s writes subject %s, not %s" % (
            a.profile, genexam.PROFILE_SUBJECT[a.profile], a.subject), file=sys.stderr)
        return 2
    if a.subject not in genexam.SUBJECTS:
        print("ERROR: subject %r not supported (have: %s)" % (a.subject, ", ".join(sorted(genexam.SUBJECTS))),
              file=sys.stderr)
        return 2
    print("%d exam(s) of %s, calls <= %d, cap $%.2f%s" % (
        a.n, a.subject, a.n * (genexam.MAX_ATTEMPTS + (0 if a.no_qa else 2 if a.profile in genexam.BLIND else 1)), a.max_cost_usd,
        " (dry run: no call made)" if a.dry_run else ""), flush=True)
    if a.dry_run:
        print(genexam.build_prompt(a.subject, a.seed, 1, a.level, a.profile))
        return 0
    tmp = None
    try:
        if a.real:
            tmp = tempfile.mkdtemp(prefix="exam_gen_")

            def llm(prompt):
                return claude.run_claude(prompt, model=a.model, timeout_s=a.timeout, cwd=tmp)
        else:
            llm = engine.mock_llm(a.mock)
        items, cost = genexam.generate(a.subject, a.n, a.seed, llm, a.max_cost_usd, a.level,
                                       not a.no_qa, a.profile)
        names = genexam.write(a.subject, items, a.out, {"seed": a.seed, "model": a.model,
                                                        "llm": "claude-p" if a.real else "mock",
                                                        "level": a.level, "profile": a.profile,
                                                        "key_basis": ("2 blind reviews" if a.profile in genexam.BLIND
                                                                      else "code check"),
                                                        "cost_usd": cost})
    except genexam.GenError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1 if exc.code == "leak" else 3
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    bad = [o["qa_note"] for o, _, _ in items if o["qa"] == "fail"]
    print("wrote %s cost=$%.4f qa_fail=%d -> %s" % (", ".join(names) or "-", cost, len(bad), a.out))
    for b in bad:
        print("  QA FAIL: %s" % b)
    return 0


def benchmark_today():
    from exam_engine.pipeline import benchmark
    return benchmark.today()


def lessons_main(argv):
    """lessons --summary summary.json [--out DIR]: write lessons.json/.md from a benchmark run; exit 0/2."""
    from exam_engine.pipeline import genexam
    ap = argparse.ArgumentParser(prog="exam.py lessons")
    ap.add_argument("--summary", required=True)
    ap.add_argument("--out")
    try:
        a = ap.parse_args(argv)
        with open(a.summary, encoding="utf-8") as fh:
            ls = genexam.lessons(json.load(fh))
    except SystemExit:
        return 2
    except (OSError, ValueError) as exc:
        print("ERROR: --summary: %s" % exc, file=sys.stderr)
        return 2
    out = a.out or os.path.dirname(os.path.abspath(a.summary))
    with open(os.path.join(out, "lessons.json"), "w", encoding="utf-8") as fh:
        json.dump(ls, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(os.path.join(out, "lessons.md"), "w", encoding="utf-8") as fh:
        fh.write(genexam.lessons_md(ls))
    print("%d lesson(s) -> %s" % (len(ls), out))
    return 0


def extract_eval_main(argv):
    """extract-eval GOLD EXTRACTED [--out DIR] [--completeness] [--refined]: exact extraction accuracy report;
    exit 0 or 2 (no gate); --completeness adds the boundary / cross-page / false-merge rates, 1 if one would
    reach the solver unmarked; --refined scores the AI-refined questions of an ingest-refine document."""
    from exam_engine.pipeline import extract_eval
    ap = argparse.ArgumentParser(prog="exam.py extract-eval")
    ap.add_argument("gold")
    ap.add_argument("extracted")
    ap.add_argument("--out")
    ap.add_argument("--completeness", action="store_true")
    ap.add_argument("--refined", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    cm = None
    try:
        gold = extract_eval.load_questions(a.gold)
        raws = {}
        ext = (extract_eval.load_refined(a.extracted, raws) if a.refined
               else extract_eval.load_questions(a.extracted, raws))
        sm = extract_eval.evaluate(gold, ext)
        if a.completeness:
            cm = extract_eval.completeness(gold, ext, raws)
        if a.out:
            extract_eval.write(sm, a.out, a.gold, a.extracted)
            if cm:
                extract_eval.write_completeness(cm, a.out)
    except (ValueError, OSError) as exc:
        print("ERROR: extract-eval: %s" % exc, file=sys.stderr)
        return 2
    print("\n".join(extract_eval.report_lines(sm)))
    if cm:
        print("\n".join(extract_eval.completeness_lines(cm)))
    return 1 if cm and cm["fail"] else 0


def review_pack_main(argv):
    """review-pack: one readable review file per subject under review/<exam-id>/ plus INDEX.md."""
    from exam_engine.pipeline import review
    ap = argparse.ArgumentParser(prog="exam.py review-pack")
    ap.add_argument("--exam-id", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--exam", required=True)
    ap.add_argument("--refined")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--out", default="review")
    ap.add_argument("--force-reset", action="store_true")
    ap.add_argument("--note", default="", help="one line printed in the pack header")
    ap.add_argument("--qa", action="append", default=[], metavar="FILE",
                    help="QA pipe table (n | answer | conf | flawed | reasoning); repeat, later files win")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        _, msg = review.pack(a.exam_id, a.subject, a.result, a.exam, a.refined, a.offset, a.out, a.force_reset, a.note,
                             a.qa)
    except (ValueError, OSError) as exc:
        print("ERROR: review-pack: %s" % exc, file=sys.stderr)
        return 2
    print(msg)
    return 0


def review_apply_main(argv):
    """review-apply: read the `Your review:` lines, print agreement per subject, write improvements.md."""
    from exam_engine.pipeline import review
    ap = argparse.ArgumentParser(prog="exam.py review-apply")
    ap.add_argument("--exam-id", required=True)
    ap.add_argument("--out", default="review")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        lines, _ = review.apply(a.exam_id, a.out)
    except (ValueError, OSError) as exc:
        print("ERROR: review-apply: %s" % exc, file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


def gold_pdf_main(argv):
    """gold-pdf GOLD OUT.pdf [--variant text|formula-image] [--font TTF] [--layout block|split] [--furniture]
    [--gold-out FILE] [--replies FILE] [--scan]: gold -> PDF (born-digital, or image-only with --scan); exit 0 or 2."""
    from exam_engine.ingest.schema import IngestError
    from exam_engine.pipeline import gold_pdf
    ap = argparse.ArgumentParser(prog="exam.py gold-pdf")
    ap.add_argument("gold")
    ap.add_argument("out")
    ap.add_argument("--variant", choices=gold_pdf.VARIANTS, default="text")
    ap.add_argument("--font")
    ap.add_argument("--layout", choices=gold_pdf.LAYOUTS, default="block",
                    help="split: a question may cross the page at a line")
    ap.add_argument("--furniture", action="store_true", help="header, footer and page number on every page")
    ap.add_argument("--gold-out", metavar="FILE", help="copy of the gold with `pages` per question")
    ap.add_argument("--replies", metavar="FILE", help="oracle mock vision replies per page (ingest-refine --mock)")
    ap.add_argument("--scan", action="store_true", help="replace the PDF by an image-only copy (no text layer)")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        info = gold_pdf.render(a.gold, a.out, a.variant, a.font, a.layout, a.furniture, a.gold_out)
        if a.scan:
            tmp = a.out + ".born.pdf"
            os.replace(a.out, tmp)
            try:
                gold_pdf.scan_pdf(tmp, a.out)
            finally:
                os.remove(tmp)
        if a.replies:
            with open(a.replies, "w", encoding="utf-8") as fh:
                json.dump(gold_pdf.vision_replies(info), fh, ensure_ascii=False, indent=1)
                fh.write("\n")
    except (ValueError, IngestError, OSError) as exc:
        print("ERROR: gold-pdf: %s" % exc, file=sys.stderr)
        return 2
    print("wrote %s pages=%d" % (a.out, info["pages"]))
    return 0


def _drop_idle_adjudication(cfg, exam):
    """76.2: the tie-break call needs an image call; with the default scope and no flagged question none can run."""
    if cfg.get("adjudicate") and cfg.get("image_scope", "flagged") == "flagged" and not any(engine.visual_flags(exam).values()):
        del cfg["adjudicate"]


def _rl_score(report_dirs):
    """'correct/total' from the newest report run (last in list) with a score: manifest `score`, else the
    score-summary json of an old run; '-' when none."""
    for d in reversed(report_dirs):
        try:
            sc = (runlayout.read_report_manifest(d) or {}).get("score")
            if sc:
                return "%d/%d" % (sc["total_correct"], sc["total"])
        except (KeyError, TypeError):
            pass
        try:
            hit = report_kinds.find(d, "score-summary", ext="json")
            with open(hit[0] if isinstance(hit, (list, tuple)) else hit, encoding="utf-8") as fh:
                sm = json.load(fh)
            return "%d/%d" % (sm["total_correct"], sm["total"])
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            continue
    return "-"


def _rl_stats(r):
    """(status, model, calls, cost) of a plan run entry: plan.json first, else result.json run block."""
    p = r.get("plan") or {}
    res = {}
    if not p:
        try:
            res = (settings.load_json(os.path.join(r["dir"], "result.json")) or {}).get("run") or {}
        except (OSError, ValueError):
            res = {}
    return (p.get("status") or ("-" if not res else "result"), p.get("model") or res.get("model") or "-",
            p.get("calls", res.get("calls", "-")), p.get("cost_usd", res.get("cost_usd", "-")))


def _rl_line_order(line):
    return (0 if line == "-" else 1 if line == "main" else 2, line)


def _rl_label(r):
    return r["id"] + (" (%s)" % r["alias"] if r.get("alias") else "")


def _rl_publish(line):
    return runlayout.PUBLISHED if runlayout.is_published_line(line) else runlayout.DEV


def _rl_plan_keys(man, exam):
    """[(line, key)] of a report run's plan_runs; key = plan run id, or `exam/id` for another exam's plan run."""
    out = []
    for pr in man.get("plan_runs", []):
        if isinstance(pr, dict):
            key = pr.get("plan_run_id") if pr.get("exam_id") == exam else "%s/%s" % (pr.get("exam_id"), pr.get("plan_run_id"))
            out.append((pr.get("line"), key))
    for pr in man.get("overlays") or []:  # an overlay plan run counts as part of the report run (TASK-096)
        if isinstance(pr, dict):
            key = pr.get("plan_run_id") if pr.get("exam_id") == exam else "%s/%s" % (pr.get("exam_id"), pr.get("plan_run_id"))
            out.append((pr.get("line"), key))
    return out


def run_list_main(argv):
    """run-list EXAM [--line L] [--plans DIR] [--reports DIR]: plan runs -> report runs, cost, score (all layouts)."""
    ap = argparse.ArgumentParser(prog="exam run-list", description="List the plan runs and report runs of one exam "
                                 "(plans/<exam>/<line>/runs, runs/ and legacy folders; an old folder name maps to its "
                                 "exam and line through plans/MIGRATION.json). No model call.")
    ap.add_argument("exam")
    ap.add_argument("--line", help="only this line folder")
    ap.add_argument("--plans", default=DEFAULT_OUT_ROOT)
    ap.add_argument("--reports", default=DEFAULT_REPORT_ROOT)
    try:
        a = ap.parse_args(argv)
        exam, line = a.exam, a.line
        alias = runlayout.folder_alias(a.plans, exam)
        if alias and alias[0] != exam:  # an old folder name that was migrated
            if line and line != alias[1]:
                print("ERROR: %s was migrated to %s/%s, not line %s" % (exam, alias[0], alias[1], line), file=sys.stderr)
                return 2
            print("note: %s is now %s/%s" % (exam, alias[0], alias[1]), file=sys.stderr)
            exam, line = alias
        plans = runlayout.list_plan_runs(a.plans, exam, line=line)
        main = line == runlayout.LINE_DEFAULT  # reports/<exam>/ (legacy, REQ-0095) belong to main
        reps = runlayout.list_report_runs(a.reports, exam, line=None if main else line)
        if main:
            reps = [r for r in reps if r["line"] in ("-", line)]
        extra = []  # legacy report folders of old plan folders that moved here
        for old, (ex, ln) in sorted(runlayout.migration_folders(a.plans).items()):
            if ex == exam and old != exam and (not line or ln == line):
                extra.extend(dict(r, line=ln) for r in runlayout.scan_report_runs(os.path.join(a.reports, old), False))
        reps = reps + extra
        pubs = [r for r in runlayout.list_report_runs(a.reports, exam)  # publications: whole exam, any --line
                if r["line"] in ("-", runlayout.LINE_DEFAULT) and r["layout"] == "run"
                and (r["manifest"] or {}).get("status") == "complete"]
    except SystemExit as exc:
        return 2 if exc.code else 0
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    if not plans and not reps:
        print("ERROR: no plan or report folder for exam %s under %s / %s" % (exam, a.plans, a.reports),
              file=sys.stderr)
        return 2
    rows = [(_rl_label(r), r) for r in plans]
    links = {}  # (line or None, plan run id or alias) -> report run entries linking that plan run
    pub_links = {}  # same, only from complete main report runs: what `publish` is computed from
    for rr in pubs:
        for k in _rl_plan_keys(rr["manifest"] or {}, exam):
            pub_links.setdefault(k, []).append(rr)
    for rr in reps:
        man = rr["manifest"] or {}
        if rr["layout"] == "run":
            for k in _rl_plan_keys(man, exam):
                links.setdefault(k, []).append(rr)
            for pr in man.get("plan_runs", []):
                if isinstance(pr, dict) and pr.get("exam_id") != exam:
                    label = "%s/%s" % (pr.get("exam_id"), pr.get("plan_run_id"))
                    if label not in [x[0] for x in rows]:
                        try:
                            d = runlayout.plan_ref(pr, a.plans)
                        except (KeyError, ValueError):
                            continue
                        if not d:
                            continue
                        rows.append((label, {"id": label, "dir": d, "line": pr.get("line") or "-", "subject": None, "alias": None,
                                             "layout": "line" if pr.get("line") else
                                             "runs" if os.sep + runlayout.RUNS + os.sep in d else "legacy",
                                             "plan": settings.load_json(os.path.join(d, "plan.json")) if os.path.isfile(os.path.join(d, "plan.json")) else None}))
        elif rr["layout"] == "legacy":
            pid = runlayout.legacy_plan_link(rr["dir"])
            if pid:  # a legacy report links only to the main line (or to the line its old folder moved to)
                links.setdefault((rr["line"] if rr["line"] != "-" else runlayout.LINE_DEFAULT, pid), []).append(rr)
        if rr["warn"]:
            if rr["warn"] == "unmigrated":
                print("WARN: %s still has run.json in the folder; run exam report-manifests-migrate --apply" % rr["dir"],
                      file=sys.stderr)
            else:
                print("WARN: unreadable manifest of %s; shown as incomplete" % rr["dir"], file=sys.stderr)
    rows.sort(key=lambda x: _rl_line_order(x[1].get("line", "-")))  # stable: keeps the time order inside a line

    def linked(label, r, links=links):
        got = []
        for (ln, pid), lst in links.items():
            if pid in (label, r["id"], r.get("alias")) and (ln is None or r.get("line", "-") in ("-", ln)):
                got.extend(x for x in lst if x not in got)
        return got

    print("# Runs: %s" % exam)
    print()
    print("| plan run | line | subject | layout | status | model | calls | cost_usd | report runs | score | publish |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for label, r in rows:
        st, model, calls, cost = _rl_stats(r)
        rl = linked(label, r)
        print("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            label, r.get("line", "-"), r.get("subject") or "-", r["layout"], st, model, calls, cost,
            ", ".join(os.path.basename(x["dir"]) for x in rl) or "-", _rl_score([x["dir"] for x in rl]),
            runlayout.PUBLISHED if linked(label, r, pub_links) else runlayout.DEV))
    print()
    print("## Report runs")
    print()
    print("| report run | layout | view | plan runs | line | publish |")
    print("| --- | --- | --- | --- | --- | --- |")
    for rr in reps:
        man = rr["manifest"] or {}
        pl = ", ".join("%s/%s" % (p.get("exam_id"), p.get("plan_run_id")) for p in man.get("plan_runs", [])
                       if isinstance(p, dict))
        if rr["layout"] == "legacy":
            pl = runlayout.legacy_plan_link(rr["dir"]) or ""
        elif man.get("link") == "line":  # migrated report run (plans-migrate): the plan line is known, the run is not
            pl = "line %s (run unknown)" % man.get("plan_line")
        elif man.get("link") == "unknown":
            pl = "unknown"
        print("| %s | %s | %s | %s | %s | %s |" % (os.path.basename(rr["dir"]), rr["layout"], man.get("view", "-"),
                                                 pl or "-", rr.get("line", "-"), _rl_publish(rr.get("line", "-"))))
    return 0


def run_compare_main(argv):
    """run-compare A B: compare two plan runs (result dir, history run_id or EXAM/PLAN_RUN_ID); run-stats compare."""
    if len(argv) != 2 or any(x.startswith("-") for x in argv):
        print("usage: exam.py run-compare A B   (A, B: result dir, history run_id or EXAM/PLAN_RUN_ID)", file=sys.stderr)
        return 2
    return run_stats_main(["compare"] + list(argv))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd, rest = (argv[0], argv[1:]) if argv else (None, [])
    table = {"solve": solve_main, "parse": parse_main, "verify": verify_main,
             "report": report_main, "plan-import": plan_import_main, "check-examples": examples_check.main,
             "score": scorer.score_main, "prompts": prompts.prompts_main,
             "check-prompts": prompts.check_prompts_main,
             "ingest": ingest_main, "ingest-inspect": inspect_main,
             "ingest-refine": refine_main, "cross-solve": cross_main, "benchmark": benchmark_main,
             "extract-eval": extract_eval_main, "gold-pdf": gold_pdf_main,
             "gen-exams": genexam_main, "lessons": lessons_main,
             "review-pack": review_pack_main, "review-apply": review_apply_main,
             "run-stats": run_stats_main, "report-pack": report_pack_main,
             "report-index": report_index_main, "run-list": run_list_main,
             "run-compare": run_compare_main, "plans-migrate": plansmigrate.main,
             "report-manifests-migrate": report_manifests_migrate_main,
             "publish": publish_main}
    if cmd not in table:
        print(USAGE, file=sys.stderr)
        return 2
    return table[cmd](rest)


def _rs_lines(a):
    """(history lines, malformed count); the default history also reads the legacy results/ file."""
    lines, bad = metrics.read_history(a.history)
    for leg in ([a.legacy] if isinstance(a.legacy, str) else a.legacy or ()):
        lines2, bad2 = metrics.read_history(leg)
        lines, bad = lines2 + lines, bad + bad2
    return lines, bad


def _rs_plan_ref(ref):
    """Plan run dir of 'EXAM/ID', 'EXAM/LINE/ID' or an OLD 'FOLDER/OLDID' (all layouts, via MIGRATION.json), else None.
    A bare id found in two lines raises ValueError (use EXAM/LINE/ID)."""
    parts = ref.split("/")
    if len(parts) not in (2, 3) or not all(parts):
        return None
    try:
        d = (runlayout.plan_run_dir(DEFAULT_OUT_ROOT, parts[0], parts[2], line=parts[1]) if len(parts) == 3
             else runlayout.plan_run_dir(DEFAULT_OUT_ROOT, parts[0], parts[1]))
    except ValueError as exc:
        if "ambiguous" in str(exc):
            raise
        return None
    return d if os.path.isfile(os.path.join(d, "result.json")) else None


def _rs_moved(path):
    """Path after a plans migration (old absolute/relative path -> new), else the path itself."""
    return runlayout.migrated(DEFAULT_OUT_ROOT, path) or path


def _rs_resolve(ref, hist, legacy=None):
    """(result, log lines, history line or None) for a result dir or a history run_id; ValueError if unknown."""
    lines = _rs_lines(argparse.Namespace(history=hist, legacy=legacy))[0]
    path = ref
    if not os.path.isfile(os.path.join(ref, "result.json")):
        hit = [ln for ln in lines if ln.get("run_id") == ref]
        path = os.path.dirname(hit[-1]["result_path"]) if hit else _rs_plan_ref(ref)
        if path and not os.path.isfile(os.path.join(path, "result.json")):
            path = _rs_moved(path)  # an old path from a history line, MIGRATION.json maps it
        if not path:
            moved = _rs_moved(ref)
            path = moved if os.path.isfile(os.path.join(moved, "result.json")) else None
        if not path:
            raise ValueError("%s: not a result dir, not a run_id in %s and not EXAM/PLAN_RUN_ID" % (ref, hist))
    rp = os.path.abspath(os.path.join(path, "result.json"))
    line = ([ln for ln in lines if ln.get("result_path") == rp or
             (ln.get("result_path") and os.path.abspath(_rs_moved(ln["result_path"])) == rp)] or [None])[-1]
    return settings.load_json(rp), metrics.load_log(os.path.join(path, "run.log")), line


def _rs_compute(ref, a):
    result, log, line = _rs_resolve(ref, a.history, a.legacy)
    exam = qa = None
    keymap = scorer.key_letters(a.ans_key) if a.ans_key else None
    if not os.path.isfile(os.path.join(ref, "result.json")):
        ref = _rs_plan_ref(ref) or _rs_moved(ref)
    if a.exam:
        exam, _code = _load_exam(a.exam)
    elif os.path.isfile(os.path.join(ref, "input", "exam.md")):  # plan run: exam copy beside the result
        exam, _code = _load_exam(os.path.join(ref, "input", "exam.md"))
    if a.review_pack:
        qa = metrics.load_qa(a.review_pack, a.offset)
    sha = metrics.file_sha256(a.exam) if a.exam else (line or {}).get("exam_sha256")
    why = metrics.load_refined_why(a.refined) if getattr(a, "refined", None) else None
    return metrics.compute(result, log, exam=exam, key=keymap, qa=qa, needs_review_why=why), sha, line, qa


def _rs_recheck(a):
    """Re-run the current code checks (option value -> letter, quote folding) on a saved run's
    check_failed questions. Read-only, no LLM (60.2). "cleared" = no code check fails now; a mapped
    letter is not proven correct."""
    if len(a.refs) != 1 or not a.exam:
        print("usage: exam.py run-stats recheck RESULT_DIR --exam FILE [--json]", file=sys.stderr)
        return 2
    result = _rs_resolve(a.refs[0], a.history, a.legacy)[0]
    exam, code = _load_exam(a.exam)
    if exam is None:
        return code
    qs = {str(q["id"]): q for q in exam["questions"]}
    rows, cleared = [], 0
    for sq in result.get("questions") or []:
        reason = sq.get("status_reason") or ""
        eq = qs.get(str(sq.get("id")))
        if not reason.startswith("check_failed") or eq is None:
            continue
        ans = dict(sq, answer_status="answered")  # saved results do not keep it; declined() would skip all
        mapped = "-"
        if eq.get("options") and not re.match(r"^[A-D]$", str(ans.get("answer")).strip()):
            mapped = verifier.option_for_value(ans.get("answer"), eq["options"]) or "-"
            if mapped != "-":
                ans["answer"] = mapped
        # saved checks keep the quotes (first 80 chars) in their detail text
        ans["evidence"] = [c["detail"].split(": ", 1)[1] for c in sq.get("checks") or []
                           if c.get("kind") == "quote" and ": " in c.get("detail", "")
                           and c["detail"].startswith("verbatim in passage/question")]
        fails = [c["kind"] for c in verifier.det_checks(eq, ans, exam) if c["result"] == "fail"]
        cleared += not fails
        rows.append({"id": str(sq.get("id")), "old": reason, "now": "no_check_fails" if not fails else
                     "fail:" + ",".join(fails), "mapped": mapped})
    summary = {"cleared": cleared, "still_failed": len(rows) - cleared}
    if a.json:
        print(json.dumps({"rows": rows, **summary}, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for r in rows:
            print("\t".join((r["id"], r["old"], r["now"], r["mapped"])))
        print("cleared %d still_failed %d" % (cleared, summary["still_failed"]))
    return 0


def _rs_stats(a):
    m = _rs_compute(a.refs[0], a)[0]
    if a.json:
        print(json.dumps(m, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("\n".join(metrics.block(m)))
    return 0


def _rs_commit(x):
    return (x.get("git") or {}).get("commit")


def _rs_diff_header(la, lb):
    if not (la and lb):
        return "changed: unknown (no history line for one run)"
    ch = [n for n, get in (("commit", _rs_commit), ("prompt", lambda x: x.get("prompt")),
                           ("model", lambda x: x.get("model"))) if get(la) != get(lb)]
    ca, cb = la.get(metrics.CFG_FIELD) or {}, lb.get(metrics.CFG_FIELD) or {}
    ch += ["config." + k for k in sorted(set(ca) | set(cb)) if ca.get(k) != cb.get(k)]
    return "changed: " + (", ".join(ch) if ch else "nothing")


def _rs_compare(a):
    if len(a.refs) != 2:
        print("usage: exam.py run-stats compare A B", file=sys.stderr)
        return 2
    ma, sa, la, qa = _rs_compute(a.refs[0], a)
    mb, sb, lb, _qb = _rs_compute(a.refs[1], a)
    if sa and sb and sa != sb:
        print("ERROR: different exam (sha %s vs %s)" % (sa[:12], sb[:12]), file=sys.stderr)
        return 2
    if not (sa and sb):
        print("WARN: exam sha unknown for one run; same exam not checked", file=sys.stderr)
    print(_rs_diff_header(la, lb))
    for name, m in (("A", ma), ("B", mb)):
        print("%s %s" % (name, " | ".join(metrics.block(m)[:2])))
    d = metrics.classify(ma, mb, qa)
    f, r = len(d["fixed"]), len(d["regressed"])
    label = {"key": "vs key", "QA": "vs QA"}.get(d["basis"], "no reference")
    for name, shown, note in (("fixed", "fixed", label), ("regressed", "regressed", label),
                              ("changed", "changed", "answer differs"), ("status_up", "status+", "H"),
                              ("status_down", "status-", "H")):
        if d[name]:
            print("%s (%s): %s" % (shown, note, ", ".join(d[name])))
    print("unchanged: %d" % d["unchanged"])
    sig = metrics.decisive(f, r) and not metrics.noise(f, r)
    if d["basis"] is None:
        verdict = "unmeasured (no key, no QA)"
    elif sig:
        verdict = "signal (%s)" % ("improved" if f > r else "regressed")
    elif not metrics.decisive(f, r):
        verdict = "insufficient (flips %d<%d)" % (f + r, metrics.MIN_FLIPS)
    else:
        verdict = "within noise"
    print("n=%d flips=%d fixed=%d regressed=%d: %s" % (ma["n"], f + r, f, r, verdict))
    return 1 if sig and r > f else 0


def _pct_rate(x):
    return "-" if x is None else "%d%%" % round(x * 100)


def _rs_group(ln):
    return metrics.version_key(ln)


def _rs_trend(a):
    lines, bad = _rs_lines(a)
    if bad:
        print("WARN: %d history line(s) skipped" % bad, file=sys.stderr)
    rows = [ln for ln in lines if (not a.exam_id or ln.get("exam_id") == a.exam_id)
            and (not a.subject or ln.get("subject") == a.subject)
            and (not a.source or (ln.get("source") or "solve") == a.source)]
    rows.sort(key=lambda ln: ln.get("ts") or "")
    if a.last:
        rows = rows[-a.last:]
    groups = {}
    for ln in rows:
        groups.setdefault(_rs_group(ln), []).append(ln)
    for ln in rows:
        m = ln.get("metrics") or {}
        acc = m.get("accuracy") or {}
        k, q = acc.get("key"), acc.get("qa")
        print("%s commit %s prompt %s model %s n %s answered %s key %s qa %s cost %s%s" % (
            ln.get("ts"), (_rs_commit(ln) or "-")[:7], (ln.get("prompt") or {}).get("version", "-"),
            ln.get("model") or "-", m.get("n", "-"), (m.get("counts") or {}).get("answered", "-"),
            "%d/%d" % (k["correct"], k["keyed"]) if k else "-",
            _pct_rate(q.get("agree_rate")) if q else "-", (m.get("cost") or {}).get("cost_usd", "-"),
            " repeat" if len(groups[_rs_group(ln)]) > 1 else ""))
    for gk, grp in groups.items():
        rates = [g["metrics"]["accuracy"]["key"]["rate"] for g in grp
                 if ((g.get("metrics") or {}).get("accuracy") or {}).get("key")]
        if len(grp) > 1 and rates:
            print("noise band (%d repeats, commit %s): key rate %.2f..%.2f" % (
                len(grp), (gk[0] or "-")[:7], min(rates), max(rates)))
    return 0


def _rs_backfill(a):
    dirs = [d for d in a.refs if os.path.isfile(os.path.join(d, "result.json"))]
    added, skipped = metrics.backfill(dirs, a.history, a.exam)
    bad = metrics.read_history(a.history)[1]
    if bad:
        print("WARN: %d history line(s) skipped" % bad, file=sys.stderr)
    print("backfill: added %d skipped %d -> %s" % (added, skipped, a.history))
    return 0


def _rs_board_load(line, qa):
    """Metrics (with quality) of the run a history line points to; None when its result.json is gone."""
    rp = line.get("result_path")
    try:
        result = settings.load_json(rp)
    except (OSError, ValueError, TypeError):
        return None, None
    return metrics.compute(result, metrics.load_log(os.path.join(os.path.dirname(rp), "run.log")),
                           qa=qa, quality=True, structure=_rs_board_structure(rp)), metrics.kind(result)


def _rs_board_structure(result_path):
    """{id: [structure flag codes]} from <run dir>/input/assembly.json (69.4); None when absent or unreadable."""
    try:
        side = settings.load_json(os.path.join(os.path.dirname(result_path), "input", "assembly.json"))
        return {str(r["id"]): list(r.get("structure") or []) for r in side["questions"]}
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _rs_board_gold(a):
    """69.5: structure_scores of the shown exam against --structure-gold FILE (None without the flag)."""
    if not a.structure_gold:
        return None
    if not a.exam:
        raise ValueError("--structure-gold needs --exam")
    try:
        gold = settings.load_json(a.structure_gold)
        gold = gold.get("gold") if isinstance(gold, dict) else gold
        if not isinstance(gold, list) or not all(isinstance(g, dict) and isinstance(g.get("id"), int)
                                                 for g in gold):
            raise ValueError("not a list of rows with an int id")
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("--structure-gold %s: %s" % (a.structure_gold, exc))
    return metrics.structure_scores(parser.parse_exam(a.exam), gold)


def _rs_gold_text(g):
    cells = " ".join("%s %s" % (k, "-" if v["rate"] is None else "%.1f%%" % (100 * v["rate"]))
                     for k, v in g["scores"].items())
    return "  parsing gold n=%d %s tok/q~%s" % (g["n_gold"], cells, "-" if g["tokens_per_question_est"] is None
                                                  else g["tokens_per_question_est"])


def _rs_board_baseline(a, lines):
    """History line (or synthetic one) of --baseline RUN_ID|DIR; ValueError when it cannot be resolved."""
    ref = a.baseline
    hit = [ln for ln in lines if ln.get("run_id") == ref]
    if not hit and os.path.isfile(os.path.join(ref, "result.json")):
        rp = os.path.abspath(os.path.join(ref, "result.json"))
        hit = [ln for ln in lines if ln.get("result_path") == rp] or [
            {"run_id": ref, "result_path": rp, "exam_sha256": metrics.file_sha256(a.exam) if a.exam else None}]
    if not hit:
        raise ValueError("%s: not a result dir and not a run_id in %s" % (ref, a.history))
    return hit[-1]


def _rs_board_packs(specs, n_exams):
    """{scope or None: [files]} from --review-pack [SHA_PREFIX|EXAM_ID=]FILE. Ids repeat across exams, so an
    unscoped pack is only valid when the board shows one exam (D6)."""
    out = {}
    for sp in specs:
        m = re.match(r"^([A-Za-z0-9_.-]+)=(.+)$", sp)
        out.setdefault(m.group(1) if m else None, []).append(m.group(2) if m else sp)
    if None in out and n_exams > 1:
        raise ValueError("--review-pack needs SHA_PREFIX=FILE when several exams are shown")
    return out


def _rs_explain(a):
    """77.7: free cause table of the wrong / flagged-right answers of saved runs. The key only scores;
    no output cell holds a letter or exam text."""
    if not a.refs or not (a.ans_key or a.calibrate):
        print("usage: exam.py run-stats explain RESULT_DIR[=EXAM]... --key FILE [--exam FILE] [--pdf FILE] "
              "[--calibrate] [--json]", file=sys.stderr)
        return 2
    key = explain.load_key(a.ans_key) if a.ans_key else {}
    pages = explain.pdf_pages(a.pdf) if a.pdf else None
    rows, multi, matched, total, cal, unreliable = [], 0, 0, 0, [], 0
    for ref in a.refs:
        d, _, e = ref.partition("=")
        path = e or a.exam or os.path.join(d, "input", "exam.md")
        exam, code = _load_exam(path)
        if exam is None:
            return code
        result = _rs_resolve(d, a.history, a.legacy)[0]
        subj = re.sub(r"[^A-Za-z0-9_-]", "_", str((result.get("exam") or {}).get("subject") or os.path.basename(d)))
        calls = os.path.join(d, "calls")
        if a.calibrate:
            cal += ["subject %s" % subj] + explain.calibrate(
                explain.analyze(explain.join(result, exam, calls, subj)), pages or [])
            continue
        got, m, mt, ok = explain.explain(result, exam, calls, pages, key, subj)
        rows += got
        unreliable += pages is not None and not ok
        multi, matched, total = multi + m, matched + mt, total + len(result.get("questions") or [])
    if a.calibrate:
        print("\n".join(cal) if pages else "calibrate: pdf_text=na")
        return 0
    if not matched:
        print("ERROR: key matches 0 of %d ids" % total, file=sys.stderr)
        return 2
    foot = explain.footer(rows, multi, pages is not None, unreliable)
    if a.json:
        print(json.dumps({"rows": [{c: r.get(c) for c in explain.COLUMNS} for r in rows], "footer": foot},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(explain.tsv(rows))
        print(foot)
    return 0


def _rs_gain(a):
    """77.8: before/after accuracy on the learn and held-out exams from an explicit spec file."""
    if not a.spec:
        print("usage: exam.py run-stats gain --spec FILE [--json]", file=sys.stderr)
        return 2
    spec = settings.load_json(a.spec)
    rows = metrics.gain_rows(spec, lambda ref: _rs_resolve(ref, a.history, a.legacy)[0])
    if a.json:
        print(json.dumps({"rows": rows, "rules": list(metrics.GAIN_RULES)}, ensure_ascii=False, indent=2,
                         sort_keys=True))
    else:
        print(metrics.gain_tsv(rows))
    return 0


def _rs_board_qa(packs, line, offset):
    files = list(packs.get(None, []))
    for scope, fs in packs.items():
        if scope and ((line.get("exam_sha256") or "").startswith(scope) or line.get("exam_id") == scope):
            files += fs
    return metrics.load_qa(files, offset) if files else None


def _rs_board(a):
    """Free scoreboard (63.5): per exam kind coverage, quality, cost, delta and verdict; reads history + result.json."""
    gold = _rs_board_gold(a)
    lines, bad = _rs_lines(a)
    if bad:
        print("WARN: %d history line(s) skipped" % bad, file=sys.stderr)
    lines = [ln for ln in lines if not a.source or (ln.get("source") or "solve") == a.source]
    sha = metrics.file_sha256(a.exam) if a.exam else None
    if a.exam and sha is None:
        raise ValueError("%s: cannot read exam" % a.exam)
    base = _rs_board_baseline(a, lines) if a.baseline else None
    if base is not None:
        sha = sha or base.get("exam_sha256")
        if not base.get("exam_sha256") or base["exam_sha256"] != sha:
            print("ERROR: different exam (sha %s vs %s)" % ((base.get("exam_sha256") or "?")[:12], (sha or "?")[:12]),
                  file=sys.stderr)
            return 2
    if sha:
        lines = [ln for ln in lines if ln.get("exam_sha256") == sha]
    pairs, no_sha = metrics.pair(lines, base)
    packs = _rs_board_packs(a.review_pack or [], len(pairs))
    kinds, skipped = {}, []
    for cur, prev in pairs:
        qa = _rs_board_qa(packs, cur, a.offset)
        mc, kc = _rs_board_load(cur, qa)
        if mc is None:
            print("result missing: %s" % cur.get("run_id"))
            skipped.append(cur.get("run_id"))
            continue
        mp = None
        if prev is not None:
            mp = _rs_board_load(prev, qa)[0]
            if mp is None:
                print("result missing: %s" % prev.get("run_id"))
                skipped.append(prev.get("run_id"))
        if a.kind and kc != a.kind:
            continue
        # 64.6: tiers are never pooled; 66.2: a regset line with a generated key is its own tier
        tier = "exploratory"
        if cur.get("source") == "regset":
            tier = "generated" if str(cur.get("key_basis") or "").startswith("generated") else "official"
        kinds.setdefault((tier, kc), []).append({
            "cur": mc, "base": mp, "qa": qa, "line": cur, "tier": tier,
            "repeat": prev is not None and metrics.version_key(prev) == metrics.version_key(cur)})
    if no_sha:
        print("no_sha %d" % no_sha)
    out = {"%s|%s" % k: metrics.board_kind(v) for k, v in sorted(kinds.items())}
    if a.json:
        doc = {"kinds": out, "no_sha": no_sha, "skipped": skipped}
        if gold is not None:
            doc["structure_gold"] = gold
        if a.explain:
            doc["causes"] = metrics.causes_text(a.explain)
        if a.gain:
            doc["gain"] = metrics.gain_board_lines(a.gain)
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for k, blk in out.items():
            print("\n".join(metrics.board_text(k.split("|", 1)[1], blk)))
            if gold is not None:
                print(_rs_gold_text(gold))
        if a.explain:
            print(metrics.causes_text(a.explain))
        if a.gain:
            print("\n".join(metrics.gain_board_lines(a.gain)))
    return 1 if any(b["verdict"] == "regression" for b in out.values()) else 0


def run_stats_main(argv):
    """run-stats stats|compare|trend|backfill|board: metrics of solve runs (TASK-056); exit 0 ok, 1 regression, 2 error."""
    ap = argparse.ArgumentParser(prog="exam run-stats")
    ap.add_argument("sub", choices=("stats", "compare", "trend", "backfill", "recheck", "board", "explain", "gain"))
    ap.add_argument("refs", nargs="*", help="stats: RESULT_DIR; compare: A B; backfill: DIR...")
    ap.add_argument("--exam")
    ap.add_argument("--key", dest="ans_key")
    ap.add_argument("--review-pack", metavar="FILE", action="append")
    ap.add_argument("--refined", metavar="FILE", help="ingest-refine output: fills needs_review_by_why")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--history", default=None,
                    help="default %s (+ legacy %s read-only)" % (DEFAULT_HISTORY, LEGACY_HISTORY))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--exam-id")
    ap.add_argument("--subject")
    ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--baseline", metavar="RUN_ID|DIR", help="board: baseline run (same exam), else the previous run")
    ap.add_argument("--structure-gold", metavar="FILE", help="board: parsing scores of --exam against a gold list")
    ap.add_argument("--kind", help="board: only this subject/language/level")
    ap.add_argument("--source", choices=("solve", "backfill", "regset"), help="board, trend: only this history source")
    ap.add_argument("--pdf", metavar="FILE", help="explain: the exam PDF (extraction check)")
    ap.add_argument("--calibrate", action="store_true", help="explain: score quantiles instead of the table")
    ap.add_argument("--spec", metavar="FILE", help="gain: spec of changes, exams, keys and before/after runs")
    ap.add_argument("--explain", metavar="TSV", action="append", help="board: explain output(s) to summarise")
    ap.add_argument("--gain", metavar="TSV", help="board: gain output to print")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    a.legacy = LEGACY_HISTORY if a.history is None else None
    a.history = a.history or DEFAULT_HISTORY
    try:
        if a.sub == "stats" and len(a.refs) != 1:
            print("usage: exam.py run-stats stats RESULT_DIR", file=sys.stderr)
            return 2
        return {"stats": _rs_stats, "compare": _rs_compare, "trend": _rs_trend,
                "backfill": _rs_backfill, "recheck": _rs_recheck, "board": _rs_board,
                "explain": _rs_explain, "gain": _rs_gain}[a.sub](a)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
