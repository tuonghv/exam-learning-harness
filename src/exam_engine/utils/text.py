"""Small text helpers shared by the pipeline."""
import unicodedata


def fold(s):
    """Diacritics-free, case-folded, single-spaced form (Toán == toan, Đ == d)."""
    s = unicodedata.normalize("NFD", s or "").replace("đ", "d").replace("Đ", "d")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.casefold().split())


_VI_CHARS = set("ăâđêôơưĂÂĐÊÔƠƯàáèéìíòóùúỳýÀÁÈÉÌÍÒÓÙÚỲÝ")


def _is_vi_word(w):
    return any(c in _VI_CHARS or "\u1ea0" <= c <= "\u1ef9" for c in w)


def detect_lang(s):
    """"vi" when >= 15% of the words carry Vietnamese letters, else "en"; empty -> "vi"."""
    s = unicodedata.normalize("NFC", s or "")
    words = ["".join(c for c in w if c.isalpha()) for w in s.split()]
    words = [w for w in words if w]
    if not words:
        return "vi"
    return "vi" if sum(_is_vi_word(w) for w in words) / len(words) >= 0.15 else "en"


def norm(s):
    s = unicodedata.normalize("NFC", s).casefold()
    s = " ".join(s.split())
    while s.endswith("."):
        s = s[:-1].rstrip()
    return s
