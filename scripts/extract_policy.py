"""Print the text of data/policies.pdf to stdout (used to draft data/policies.md)."""

from pathlib import Path

from pypdf import PdfReader

PDF = Path(__file__).resolve().parents[1] / "data" / "policies.pdf"

if __name__ == "__main__":
    for number, page in enumerate(PdfReader(PDF).pages, start=1):
        print(f"--- page {number} ---")
        print(page.extract_text(extraction_mode="layout"))
