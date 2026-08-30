"""Trich xuat noi dung text tu file PDF ra file .txt de doc/phan tich."""
import sys
from pathlib import Path

from pypdf import PdfReader


def extract(pdf_path: Path, out_path: Path) -> None:
    reader = PdfReader(str(pdf_path))
    parts = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"\n===== PAGE {i} =====\n{text}")
    out_path.write_text("".join(parts), encoding="utf-8")
    print(f"Pages: {len(reader.pages)} -> {out_path}")


if __name__ == "__main__":
    pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "Cach_thuc_Bot_SHORT_F1_F6_Entry_SL_TP-3_1.pdf"
    )
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else pdf.with_suffix(".txt")
    extract(pdf, out)
