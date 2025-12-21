import docx
import os

def extract_text(file_path):
    try:
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"

docs_dir = "/home/said/agency/1/consultant/docs"
files = ["кп1.docx", "кп2.docx"]

for file in files:
    path = os.path.join(docs_dir, file)
    print(f"--- CONTENT OF {file} ---")
    print(extract_text(path))
    print("\n" + "="*50 + "\n")

