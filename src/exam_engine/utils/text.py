"""Small text helpers shared by the pipeline."""
import unicodedata


def fold(s):
    """Diacritics-free, case-folded, single-spaced form (Toán == toan, Đ == d)."""
    s = unicodedata.normalize("NFD", s or "").replace("đ", "d").replace("Đ", "d")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.casefold().split())


def norm(s):
    s = unicodedata.normalize("NFC", s).casefold()
    s = " ".join(s.split())
    while s.endswith("."):
        s = s[:-1].rstrip()
    return s
