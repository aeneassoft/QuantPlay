"""Quick probe: page counts + text extractability for the 3 poker PDFs."""
import fitz  # PyMuPDF
from pathlib import Path

INFO = Path(r"C:\Users\hampe\Desktop\PokerB\Information")

for pdf in sorted(INFO.glob("*.pdf")):
    doc = fitz.open(pdf)
    n = doc.page_count
    # Sample text from a few pages spread through the book
    sample_pages = [min(i, n - 1) for i in (5, n // 4, n // 2, 3 * n // 4)]
    total_chars = 0
    img_count = 0
    for i in range(n):
        page = doc[i]
        total_chars += len(page.get_text("text"))
        img_count += len(page.get_images())
    avg_chars = total_chars / n if n else 0
    print(f"\n=== {pdf.name} ===")
    print(f"  pages: {n}")
    print(f"  total text chars: {total_chars:,}")
    print(f"  avg chars/page: {avg_chars:,.0f}")
    print(f"  total embedded images: {img_count}")
    print(f"  -> {'TEXT OK' if avg_chars > 200 else 'LIKELY SCANNED / NEEDS OCR'}")
    # Show a short sample
    sample = doc[sample_pages[1]].get_text('text').strip().replace('\n', ' ')[:300]
    print(f"  sample (p{sample_pages[1]}): {sample!r}")
    doc.close()
