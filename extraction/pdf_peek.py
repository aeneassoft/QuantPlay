"""Extract a page range of text from a PDF (robust across libs). Used to mine the exploit book.
Run: python -m extraction.pdf_peek "<path>" <lo> <hi> [outfile]
"""
import sys


def extract(path, lo, hi):
    try:
        import fitz  # PyMuPDF
        d = fitz.open(path)
        return "\n".join(d[i].get_text() for i in range(lo, min(hi, d.page_count)))
    except Exception:  # noqa: BLE001
        pass
    try:
        from pypdf import PdfReader
        r = PdfReader(path)
        return "\n".join((r.pages[i].extract_text() or "") for i in range(lo, min(hi, len(r.pages))))
    except Exception:  # noqa: BLE001
        pass
    try:
        from pdfminer.high_level import extract_text
        return extract_text(path, page_numbers=list(range(lo, hi)))
    except Exception as e:  # noqa: BLE001
        return f"ALL PDF LIBS FAILED: {e}"


if __name__ == "__main__":
    path = sys.argv[1]
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    txt = extract(path, lo, hi)
    if len(sys.argv) > 4:
        open(sys.argv[4], "w", encoding="utf-8").write(txt)
        print(f"wrote {len(txt)} chars -> {sys.argv[4]}")
    else:
        print(txt[:7000])
