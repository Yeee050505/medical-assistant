import re

_ID_CARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_BANK_CARD = re.compile(r"(?<!\d)\d{16,19}(?!\d)")
_NAME_PATTERNS = [
    re.compile(r"(我叫|我姓名是|姓名[：:]\s*|患者叫|患者姓名[：:]\s*|名字叫)([一-鿿]{2,4})"),
]


def desensitize(text: str) -> str:
    """外发前脱敏：身份证 / 手机号 / 银行卡 / 模式化姓名。内网原始数据不经过此函数。"""
    if not text:
        return text
    text = _ID_CARD.sub(lambda m: m.group()[:6] + "********" + m.group()[-4:], text)
    text = _PHONE.sub(lambda m: m.group()[:3] + "****" + m.group()[-4:], text)
    text = _BANK_CARD.sub(lambda m: m.group()[:4] + "****" + m.group()[-4:], text)
    for pattern in _NAME_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + m.group(2)[0] + "**", text)
    return text


def desensitize_messages(messages: list[dict]) -> list[dict]:
    return [dict(m, content=desensitize(str(m.get("content", "")))) for m in messages]
