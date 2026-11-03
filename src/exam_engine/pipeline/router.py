"""Subject policy lookup from config/subjects.json (a new subject needs no code change)."""
import re

from exam_engine import settings
from exam_engine.utils import text
from exam_engine.utils.text import fold

DEFAULT_POLICY = {"task": "Closed", "checks": ["format", "computed", "quote"],
                  "score_basis": "official_key", "language": "vi", "prompt": None,
                  "answer_shapes": []}


def subjects(config_dir=None):
    return settings.load_config("subjects", config_dir)


def subject_key(name, config_dir=None):
    """Config key for a header Subject value (aliases; case and diacritics ignored), else None."""
    low = fold(name)
    for key, pol in subjects(config_dir).items():
        if low == fold(key) or low in [fold(a) for a in pol.get("aliases", [])]:
            return key
    return None


_PART_PREFIX = re.compile(r"^(?:PH[ẦA]N|PART)\s+\S+\s*[:.\-–]?\s*", re.I)
_NUM_PREFIX = re.compile(r"^\d+(?:\.\d+)*\.?\s*")


def heading_subject(heading, config_dir=None):
    """Subject key named by a section heading (last ` > ` segment that maps), else None."""
    for seg in reversed((heading or "").split(" > ")):
        seg = _NUM_PREFIX.sub("", _PART_PREFIX.sub("", seg.strip()), count=1).strip()
        key = seg and subject_key(seg, config_dir)
        if key:
            return key
    return None


def known_names(config_dir=None):
    names = []
    for key, pol in subjects(config_dir).items():
        names += [fold(key)] + [fold(a) for a in pol.get("aliases", [])]
    return names


def policy(name, config_dir=None):
    """Policy dict of a subject; the defaults for an unknown one."""
    key = subject_key(name, config_dir)
    out = dict(DEFAULT_POLICY)
    if key:
        out.update(subjects(config_dir)[key])
        out["key"] = key
    return out


def language(exam, override=None):
    """Explanation language: override (CLI) > header > subject policy > vi; "auto" is detected."""
    f = exam["fields"]
    lang = (override or "").strip() or (f.get("Language") or "").strip()
    if not lang:
        lang = policy(f.get("Subject"))["language"] if subject_key(f.get("Subject")) else "vi"
    if lang == "auto":
        lang = text.detect_lang(" ".join(q.get("text", "") for q in exam.get("questions", [])))
    return lang


def apply_lang(exam, lang):
    """Pin the run's language into the header so every later language() call agrees."""
    if lang:
        exam["fields"]["Language"] = lang
