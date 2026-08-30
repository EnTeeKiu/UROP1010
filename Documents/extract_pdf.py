import PyPDF2
import sys

pdf_path = r"c:\Users\Dell\Desktop\Code project\Code project\UROP1010\Documents\Experiment details.pdf"
out_path = r"c:\Users\Dell\Desktop\Code project\Code project\UROP1010\Documents\experiment_details_text.txt"

with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    all_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        all_text.append(f"=== PAGE {i+1} ===\n{text}\n")

with open(out_path, 'w', encoding='utf-8') as out:
    out.write('\n'.join(all_text))

print(f"Extracted {len(reader.pages)} pages to {out_path}")
