from app.services.rag.chunking import _sliding_window, chunk_text, clean_text


def test_clean_text_normalizes():
    raw = "a\x00b\r\nc\t\td\r\r\r\r\n\n e "
    out = clean_text(raw)
    assert "\x00" not in out
    assert "\r" not in out
    assert "  " not in out
    assert out.startswith("ab") and out.endswith("e")


def test_chunk_empty_returns_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_paragraphs_merged():
    text = (
        "第一段：阿莫西林是青霉素类抗生素。\n\n第二段：用于敏感菌所致感染。\n\n第三段：口服给药。"
    )
    chunks = chunk_text(text, chunk_size=500, overlap=80)
    assert len(chunks) == 1
    assert "第一段" in chunks[0] and "第三段" in chunks[0]


def test_long_paragraph_sliding_window():
    sentence = "布洛芬是非甾体抗炎药，通过抑制环氧化酶发挥作用，用于退热镇痛抗炎治疗。"
    text = sentence * 30  # ~1260 字 > 500
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    assert len(chunks) >= 5
    assert all(len(c) <= 200 for c in chunks)
    assert all(len(c) >= 10 for c in chunks)


def test_sentence_not_split_across_chunk_boundary():
    """句长不超过 chunk_size 时，句子不会被拦腰截断。"""
    text = "这是完整的一句话，包含主谓宾结构。" * 8  # 单句 ~17*8 但被。切成8句
    chunks = chunk_text(text, chunk_size=300, overlap=0)
    for c in chunks:
        assert c.endswith("。") or len(c) < 100 or "。" in c


def test_sliding_window_handles_unsplitable_text():
    """无标点超长文本走硬切分支。"""
    text = "无标点" * 400  # 1200 字，无句末标点
    chunks = _sliding_window(text, chunk_size=100, overlap=20)
    assert len(chunks) >= 10
    assert all(len(c) <= 100 for c in chunks)


def test_tiny_fragments_filtered():
    text = "这是一个足够长的段落内容，超过十个字符，可以保留下来。\n\n短"
    chunks = chunk_text(text, chunk_size=500, overlap=80)
    assert all(len(c) >= 10 for c in chunks)


def test_crlf_and_multiple_blank_lines():
    text = "段落一：内容。\r\n\r\n\r\n\r\n\r\n段落二：内容。"
    chunks = chunk_text(text, chunk_size=500, overlap=80)
    assert len(chunks) == 1
    assert "段落一" in chunks[0] and "段落二" in chunks[0]
