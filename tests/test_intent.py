from app.services.intent import classify, classify_by_rules


def test_image_wins():
    assert classify("帮我看看这个报告", has_images=True) == "image"


def test_greeting_is_chat():
    for q in ("你好", "您好！", "hi", "Hello.", "在吗", "谢谢", "好的"):
        assert classify_by_rules(q) == "chat", q


def test_long_greeting_not_chat():
    """带内容的问候不误判 chat。"""
    assert classify_by_rules("你好，我最近头疼发烧") == "qa"


def test_qa_keywords():
    for q in (
        "布洛芬一次吃几片",
        "奥司他韦有什么副作用",
        "孕妇能吃阿莫西林吗",
        "发烧了吃什么药",
        "这个药饭前吃还是饭后吃",
        "头孢和酒精能一起吗",
    ):
        assert classify_by_rules(q) == "qa", q


def test_followup_with_history():
    assert classify_by_rules("那这个呢", ["最近头疼吃什么药"]) == "followup"
    assert classify_by_rules("刚才说的那个叫什么", ["头疼"]) == "followup"


def test_followup_with_qa_keyword_is_qa():
    """含明确药学词优先判 qa（设计约定）。"""
    assert classify_by_rules("刚才说的那个药叫什么", ["头疼"]) == "qa"


def test_followup_without_history_is_other():
    assert classify_by_rules("那这个呢") == "other"


def test_fallback_other():
    assert classify_by_rules("今天天气不错") == "other"


def test_off_strategy_returns_qa(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "intent_strategy", "off")
    assert classify("今天天气不错") == "qa"
    assert classify("你好") == "qa"


def test_llm_strategy_uses_provider(monkeypatch):
    import app.services.llm.factory as factory
    from app.core.config import settings

    class Fake:
        def classify_intent(self, q, h=None):
            return "chat"

    monkeypatch.setattr(factory, "get_provider", lambda: Fake())
    monkeypatch.setattr(settings, "intent_strategy", "llm")
    assert classify("随便聊聊") == "chat"


def test_llm_strategy_falls_back_on_error(monkeypatch):
    import app.services.llm.factory as factory
    from app.core.config import settings

    class Fake:
        def classify_intent(self, q, h=None):
            raise RuntimeError("api down")

    monkeypatch.setattr(factory, "get_provider", lambda: Fake())
    monkeypatch.setattr(settings, "intent_strategy", "llm")
    assert classify("布洛芬怎么吃") == "qa"


def test_llm_strategy_invalid_output_falls_back(monkeypatch):
    import app.services.llm.factory as factory
    from app.core.config import settings

    class Fake:
        def classify_intent(self, q, h=None):
            return "banana"

    monkeypatch.setattr(factory, "get_provider", lambda: Fake())
    monkeypatch.setattr(settings, "intent_strategy", "llm")
    assert classify("今天天气不错") == "other"
