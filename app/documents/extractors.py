import pdfplumber
from docx import Document as DocxDocument


def extract_text(filepath: str, file_type: str) -> str:
    """Extract text from uploaded file based on type."""
    extractors = {
        'pdf': extract_pdf,
        'docx': extract_docx,
        'txt': extract_txt,
    }
    extractor = extractors.get(file_type)
    if not extractor:
        raise ValueError(f"Unsupported file type: {file_type}")
    return extractor(filepath)


def extract_pdf(filepath: str) -> str:
    """Extract text from a PDF file."""
    pages = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if text:
                pages.append(text)
    return '\n\n'.join(pages)


def extract_docx(filepath: str) -> str:
    """Extract text from a DOCX file."""
    doc = DocxDocument(filepath)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return '\n\n'.join(paragraphs)


def extract_txt(filepath: str) -> str:
    """Read a plain text file."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()
