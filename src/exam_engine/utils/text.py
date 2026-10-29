"""Small text helpers shared by the pipeline."""
import unicodedata


def norm(s):
    s = unicodedata.normalize("NFC", s).casefold()
    s = " ".join(s.split())
    while s.endswith("."):
        s = s[:-1].rstrip()
    return s
