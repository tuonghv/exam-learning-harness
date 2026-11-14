"""Report builder (TASK-058 58.3): a plan run dir in, report files out.

Pure and deterministic: no model call, no network, no clock. The only process it may start is the
local PDF renderer behind reporter.md_to_pdf (pdf=True). Guarded by tests/unit/test_report_build.py.
"""
import json
import os

from exam_engine.pipeline import metrics, overlay as overlay_mod, parser, planrun, report_kinds, reporter, router


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


def build(plan_dir, out_dir, *, view="sheet", pdf=False, renderer=None, runner=None, engine_git=None,
          exam_name=None, run_name=None, subject_name=None, overlay=None):
    """Write the standard-named report of plan_dir into out_dir; returns dict(reports, metrics, result, exam, names).
    exam_name/run_name/subject_name override the name parts (default: from the result and the out dir).
    overlay: a resolved overlay.resolve entry for this plan's subject, applied in memory (result.json untouched).
    ValueError when the plan has no result.json."""
    if view not in reporter.VIEWS:
        raise ValueError("unknown view %r" % view)
    loaded = planrun.load(plan_dir)
    result = loaded["result"]
    if result is None:
        raise ValueError("plan incomplete: no result.json in %s" % plan_dir)
    exam = _exam(plan_dir, loaded["exam_text"], _config(plan_dir).get("lang"))
    if overlay:
        ov_result, ov_exam = overlay_mod.load_for_entry(overlay)
        result, exam = overlay_mod.apply(result, exam, overlay, ov_result, ov_exam)
    try:
        m = metrics.compute(result, loaded["log"], exam=exam)
    except Exception:  # noqa: BLE001 - metrics are extra; the report must still build
        m = None
    kw = {} if runner is None else {"runner": runner}
    names = dict(reporter.default_names(result, out_dir))
    names.update({k: v for k, v in (("exam", exam_name), ("run", run_name), ("subject", subject_name)) if v})
    reports = reporter.write_reports(result, out_dir, pdf=pdf, renderer=renderer, view=view,
                                     metrics=m, exam=exam, names=names, **kw)
    reports["solution_public-report"] = reporter.write_public(result, out_dir, pdf=pdf, renderer=renderer, exam=exam,
                                              names=names, **kw)
    return {"reports": reports, "metrics": m, "result": result, "exam": exam, "names": names}
