import re


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；!?;])", text)
    return [p.strip() for p in parts if p.strip()]


def _sliding_window(text: str, chunk_size: int, overlap: int) -> list[str]:
    sentences = _split_sentences(text)
    if not sentences:
        sentences = [text]
    chunks: list[str] = []
    cur = ""
    for sent in sentences:
        if len(sent) > chunk_size:
            if cur:
                chunks.append(cur)
                cur = ""
            start = 0
            while start < len(sent):
                end = min(start + chunk_size, len(sent))
                chunks.append(sent[start:end])
                if end >= len(sent):
                    break
                start = max(end - overlap, start + 1)
            continue
        if not cur:
            cur = sent
        elif len(cur) + len(sent) + 1 <= chunk_size:
            cur = cur + sent
        else:
            chunks.append(cur)
            cur = sent
    if cur:
        chunks.append(cur)
    return chunks


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """段落优先聚合切片，超长段落按句滑窗切片，保证语义完整。"""
    text = clean_text(text)
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    cur = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.extend(_sliding_window(para, chunk_size, overlap))
        elif not cur:
            cur = para
        elif len(cur) + len(para) + 2 <= chunk_size:
            cur = cur + "\n" + para
        else:
            chunks.append(cur)
            cur = para
    if cur:
        chunks.append(cur)
    return [c for c in chunks if len(c) >= 10]
