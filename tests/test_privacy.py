from app.services.privacy import desensitize, desensitize_messages


def test_desensitize_sensitive_entities():
    text = (
        "我叫张三，身份证110101199001011234，"
        "手机号13912345678，银行卡6222021234567890123"
    )
    out = desensitize(text)
    assert "110101199001011234" not in out
    assert "110101********1234" in out
    assert "13912345678" not in out
    assert "139****5678" in out
    assert "6222021234567890123" not in out
    assert "6222****0123" in out
    assert "张**" in out


def test_desensitize_messages_keeps_structure():
    messages = [
        {"role": "user", "content": "联系我13800001111"},
        {"role": "system", "content": "正常内容"},
    ]
    out = desensitize_messages(messages)
    assert out[0]["role"] == "user"
    assert "138****1111" in out[0]["content"]
    assert out[1]["content"] == "正常内容"
    assert "13800001111" not in out[0]["content"]
