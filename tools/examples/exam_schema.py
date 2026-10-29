"""Schemas for the exam engine and a small validator (Python 3.8 stdlib only).

validate(obj, schema) -> list of "path: problem" strings; empty = valid.
Subset: type (name or list), required, enum, properties, items, additionalProperties
(bool), minimum.
"""

_TYPES = {"string": str, "array": list, "object": dict, "null": type(None),
          "boolean": bool}


def _is_type(val, name):
    if name == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if name == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    return isinstance(val, _TYPES[name])


def validate(obj, schema, path="$"):
    errs = []
    types = schema.get("type")
    if types is not None:
        names = types if isinstance(types, list) else [types]
        if not any(_is_type(obj, n) for n in names):
            return ["%s: expected %s, got %s" % (path, "|".join(names), type(obj).__name__)]
    if "enum" in schema and obj not in schema["enum"]:
        errs.append("%s: %r not in %s" % (path, obj, list(schema["enum"])))
    if "minimum" in schema and _is_type(obj, "number") and obj < schema["minimum"]:
        errs.append("%s: %r below minimum %r" % (path, obj, schema["minimum"]))
    if isinstance(obj, dict):
        for key in schema.get("required", ()):
            if key not in obj:
                errs.append("%s: missing %s" % (path, key))
        props = schema.get("properties", {})
        for key, val in obj.items():
            if key in props:
                errs.extend(validate(val, props[key], "%s.%s" % (path, key)))
            elif schema.get("additionalProperties") is False:
                errs.append("%s: unexpected %s" % (path, key))
    if isinstance(obj, list) and "items" in schema:
        for i, val in enumerate(obj):
            errs.extend(validate(val, schema["items"], "%s[%d]" % (path, i)))
    return errs


_STR = {"type": "string"}
_STRS = {"type": "array", "items": _STR}
_UNCERT = {"type": "object", "required": ["level", "reason"],
           "properties": {"level": {"type": "string", "enum": ["low", "medium", "high"]},
                          "reason": _STR}}

# What prompts/solve.md emits (D1); extra keys are tolerated, required ones are not.
SOLVE_OUT = {
    "type": "object", "required": ["questions"],
    "properties": {
        "schema_version": _STR,
        "questions": {"type": "array", "items": {
            "type": "object",
            "required": ["id", "answer", "answer_status", "solution", "explanation",
                         "uncertainty", "reasoning_status"],
            "properties": {
                "id": _STR,
                "type": _STR,
                "answer": {"type": ["string", "null"]},
                "answer_status": {"type": "string",
                                  "enum": ["answered", "uncertain", "unanswerable"]},
                "solution": _STRS,
                "explanation": _STR,
                "checks": _STRS,
                "expr": {"type": ["string", "null"]},
                "evidence": {"type": "array", "items": {"type": ["string", "null"]}},
                "uncertainty": _UNCERT,
                "reasoning_status": {"type": "string",
                                     "enum": ["not_independently_verified"]},
                "issues": _STRS,
            }}},
        "input_issues": _STRS,
    }}

QA_OUT = {
    "type": "object", "required": ["reviews"],
    "properties": {"reviews": {"type": "array", "items": {
        "type": "object", "required": ["id", "verdict", "findings"],
        "properties": {"id": _STR,
                       "verdict": {"type": "string",
                                   "enum": ["agree", "disagree", "unsure"]},
                       "findings": _STRS}}}}}

_CHECK = {"type": "object", "required": ["kind", "detail", "result", "independent"],
          "properties": {
              "kind": {"type": "string", "enum": ["computed", "format", "quote",
                                                  "key_match", "ai_review"]},
              "detail": _STR,
              "result": {"type": "string", "enum": ["pass", "fail", "unknown"]},
              "independent": {"type": "boolean"}}}
_NUM_OR_NULL = {"type": ["number", "null"]}

RESULT = {
    "type": "object",
    "required": ["schema_version", "exam", "run", "questions", "summary"],
    "properties": {
        "schema_version": {"type": "integer", "enum": [1]},
        "exam": {"type": "object", "required": ["path", "subject", "task", "mode"],
                 "properties": {k: {"type": ["string", "null"]} for k in
                                ("path", "subject", "level", "exam_type", "task",
                                 "mode", "language")}},
        "run": {"type": "object", "required": ["llm", "calls", "cost_usd"],
                "properties": {
                    "llm": {"type": "string", "enum": ["claude-p", "mock"]},
                    "model": {"type": ["string", "null"]},
                    "max_attempts": {"type": "integer", "minimum": 1},
                    "timeout_s": {"type": "number", "minimum": 0},
                    "max_cost_usd": {"type": "number", "minimum": 0},
                    "cost_usd": {"type": "number", "minimum": 0},
                    "calls": {"type": "integer", "minimum": 0},
                    "stopped": {"type": ["string", "null"]}}},
        "questions": {"type": "array", "items": {
            "type": "object",
            "required": ["id", "answer", "solution", "explanation", "uncertainty",
                         "checks", "verification_status", "status_reason",
                         "qa_findings", "score", "attempts", "unresolved", "error"],
            "properties": {
                "id": _STR,
                "answer": {"type": ["string", "null"]},
                "answer_text": _STR,
                "solution": _STRS,
                "explanation": _STR,
                "uncertainty": _UNCERT,
                "checks": {"type": "array", "items": _CHECK},
                "verification_status": {"type": "string",
                                        "enum": ["PASS", "FAIL", "UNCERTAIN"]},
                "status_reason": _STR,
                "qa_findings": {"type": "array", "items": {
                    "type": "object", "required": ["source", "code", "message"],
                    "properties": {
                        "source": {"type": "string",
                                   "enum": ["deterministic", "ai_review", "score"]},
                        "code": _STR, "message": _STR}}},
                "score": {"type": "object", "required": ["points", "max", "basis"],
                          "properties": {
                              "points": _NUM_OR_NULL, "max": _NUM_OR_NULL,
                              "basis": {"type": "string",
                                        "enum": ["official_key", "rubric", "none"]},
                              "detail": _STR}},
                "attempts": {"type": "integer", "minimum": 1},
                "unresolved": {"type": "boolean"},
                "error": {"type": ["object", "null"],
                          "properties": {"cls": _STR, "message": _STR}},
            }}},
        "summary": {"type": "object",
                    "required": ["pass", "fail", "uncertain", "unresolved"],
                    "properties": {
                        "pass": {"type": "integer", "minimum": 0},
                        "fail": {"type": "integer", "minimum": 0},
                        "uncertain": {"type": "integer", "minimum": 0},
                        "unresolved": {"type": "integer", "minimum": 0},
                        "points": _NUM_OR_NULL, "max_points": _NUM_OR_NULL}},
    }}
