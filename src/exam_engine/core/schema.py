"""Mini JSON-schema validator (Python 3.8 stdlib only); schemas live in schemas/*.schema.json.

validate(obj, schema) -> list of "path: problem" strings; empty = valid.
Subset: type (name or list), required, enum, properties, items, additionalProperties
(bool), minimum.
"""
from exam_engine import settings

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


SOLVE_OUT = settings.load_schema("solve_out")  # what prompts/exam/solve.md emits
QA_OUT = settings.load_schema("qa_out")
RESULT = settings.load_schema("result")
