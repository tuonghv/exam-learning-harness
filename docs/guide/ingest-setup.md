# Ingest setup (PDF, DOCX, OCR)

The Markdown adapter needs nothing. PDF (and later DOCX/image) ingest uses optional libraries.

## Install
    pip install pymupdf python-docx pillow

The harness runs as `python3 -I`, which hides the user site where `pip install --user` puts
packages. `exam_engine/ingest/optional.py` retries an import once with the user site appended to
the END of `sys.path` (the current folder is never added). If the library is still missing the
error is `missing_dependency: pip install <package>`.

## OCR (scanned pages)
Install the tesseract binary (e.g. `apt install tesseract-ocr`) and the language data. Vietnamese
needs `vie.traineddata` in a tessdata folder, for example:

    apt install tesseract-ocr-vie
    # or copy vie.traineddata into the tessdata folder and point to it:
    export TESSDATA_PREFIX=/path/to/tessdata

Folders searched: `TESSDATA_PREFIX`, `/usr/share/tesseract-ocr/*/tessdata`,
`/usr/local/share/tessdata`, `/usr/share/tessdata`. With `vie` missing the adapter uses `eng` and
warns `ocr_language_missing`; with no data a flagged page gets status `needs_review`. OCR runs only
on pages whose native text looks wrong; `--ocr off` disables it.

## Self-check
    python3 -I scripts/exam.py ingest --check

Prints the fitz/docx/PIL versions (or MISSING), the tesseract binary, the tessdata folder, the
OCR languages found (vie/eng) and the user-site path used by the loader.

## Usage
    python3 -I scripts/exam.py ingest exam.pdf --out doc.json [--assets DIR] [--ocr auto|off]

Page crops go to `--assets` (default `work/ingest/<sha8>/`). Math in PDFs is kept as text plus a
page image, not LaTeX.
