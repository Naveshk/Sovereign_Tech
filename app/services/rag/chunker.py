import re


def clean_text(text: str) -> str:
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def chunk_pages(pages: list[dict], chunk_size: int = 1200, overlap: int = 180) -> list[dict]:
    chunks = []
    for page in pages:
        text = clean_text(page.get('text', ''))
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            if end < len(text):
                boundary = text.rfind('\n', start, end)
                if boundary > start + chunk_size // 2:
                    end = boundary
            piece = text[start:end].strip()
            if piece:
                chunks.append({'text': piece, 'page': page.get('page', 1), 'chunk_index': len(chunks)})
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks
