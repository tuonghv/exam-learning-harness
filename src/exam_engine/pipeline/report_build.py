"""Report builder (TASK-058 58.3): a plan run dir in, report files out.

Pure and deterministic: no model call, no network, no clock. The only process it may start is the
local PDF renderer behind reporter.md_to_pdf (pdf=True). Guarded by tests/unit/test_report_build.py.
"""
import hashlib
import json
import os

from exam_engine.pipeline import metrics, parser, planrun, reporter, router


def _dump(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def _config(plan_dir):
    try:
        with open(os.path.join(plan_dir, "config.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _exam(plan_dir, text, lang):
    """Parsed exam from the text stored in the plan input (D-3), or None."""
    if text is None:
        return None
    try:
        exam = parser.parse_exam(os.path.join(plan_dir, "input", "exam.md"))
        router.apply_lang(exam, lang)
        return exam
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def build(plan_dir, out_dir, *, view="sheet", pdf=False, renderer=None, runner=None, engine_git=None):
    """Write the report of plan_dir into out_dir; returns dict(reports, metrics, result).
    ValueError when the plan has no result.json."""
    if view not in reporter.VIEWS:
        raise ValueError("unknown view %r" % view)
    loaded = planrun.load(plan_dir)
    result = loaded["result"]
    if result is None:
        raise ValueError("plan incomplete: no result.json in %s" % plan_dir)
    exam = _exam(plan_dir, loaded["exam_text"], _config(plan_dir).get("lang"))
    try:
        m = metrics.compute(result, loaded["log"], exam=exam)
    except Exception:  # noqa: BLE001 - metrics are extra; the report must still build
        m = None
    kw = {} if runner is None else {"runner": runner}
    reports = reporter.write_reports(result, out_dir, pdf=pdf, renderer=renderer, view=view,
                                     metrics=m, **kw)
    _dump(os.path.join(out_dir, "metrics.json"), m)
    plan = loaded["plan"] or {}
    with open(os.path.join(plan_dir, "result.json"), "rb") as fh:
        rsha = hashlib.sha256(fh.read()).hexdigest()
    _dump(os.path.join(out_dir, "report.json"),
          {"plan_run_id": plan.get("plan_run_id"), "exam_id": plan.get("exam_id"),
           "result_sha256": rsha, "view": view, "engine_git": engine_git})
    return {"reports": reports, "metrics": m, "result": result}
