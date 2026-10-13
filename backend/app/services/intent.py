"""意图路由：将用户输入分类为 qa / chat / followup / image / other，驱动后续链路分支。

策略（settings.intent_strategy）：
- off：恒返回 qa（保持引入前行为）
- rule：关键词/正则规则，零成本零延迟（默认）
- llm：调用 Provider.classify_intent 小模型分类，失败回退规则
任何异常最终兜底 qa/other，绝不阻断主链路。
"""

import logging
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

Intent = str  # "qa" | "chat" | "followup" | "image" | "other"

ALLOWED_INTENTS = frozenset({"qa", "chat", "followup", "image", "other"})
DEFAULT_INTENT: Intent = "qa"

# 整句匹配的问候/寒暄（短句才会命中 chat）
_GREETING_RE = re.compile(
    r"^(你好|您好|hi|hello|嗨|哈喽|在吗|在不在|早上好|早安|中午好|下午好|晚上好|"
    r"谢谢|谢谢你|感谢|多谢|麻烦你了|辛苦了|再见|拜拜|拜拜|嗯|嗯嗯|好的|ok|okay)"
    r"[\uFF01\uFF1F!?.。？~\s]*$",
    re.IGNORECASE,
)

# 药学/症状关键词 → qa（宁可多判 qa 走检索，也比误判 chat 丢检索好）
_QA_RE = re.compile(
    r"(药|剂量|副作用|过敏|服用|用药|用法|禁忌|疗程|适应症|不良反应|相互作用|"
    r"症状|不适|头疼|头痛|发烧|发热|咳嗽|咳痰|感冒|流感|咽痛|嗓子|鼻塞|流涕|"
    r"腹泻|拉肚子|呕吐|恶心|胃|腹痛|止痛|退烧|退热|消炎|镇痛|抗炎|抗生素|"
    r"胶囊|药片|片剂|口服|注射|外用|滴眼|喷雾|皮疹|瘙痒|头晕|眩晕|心悸|"
    r"血压|血糖|血脂|失眠|肝|肾|孕妇|哺乳|儿童|小儿|老人|老年|"
    r"布洛芬|对乙酰氨基酚|阿莫西林|头孢|奥司他韦|玛巴洛沙韦|蒙脱石|益生菌|"
    r"维生素|怎么吃|怎么用|吃多少|用多少|几片|一次|每天|饭前|饭后|空腹|"
    r"多久|几次|可以吃|能吃|能用|服用过量|误服|漏服|停药|换药)"
)

# 追问指示词（需有对话历史才判 followup）
_FOLLOWUP_RE = re.compile(
    r"(那|那么|这个|这个药|它|刚才|刚刚|上面|前面|之前说|继续|另外|除此之外|"
    r"别的|其他药|替代|换成|呢[???]?$|的话)"
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def classify_by_rules(query: str, history: list[str] | None = None) -> Intent:
    """纯规则分类（priority: image > chat > qa > followup > other）。"""
    q = _normalize(query)
    if _GREETING_RE.fullmatch(q):
        return "chat"
    if _QA_RE.search(q):
        return "qa"
    if history and _FOLLOWUP_RE.search(q):
        return "followup"
    return "other"


def classify(
    query: str,
    has_images: bool = False,
    history: list[str] | None = None,
) -> Intent:
    """入口：按配置策略分类；image 优先，off 恒 qa，异常兜底规则结果。"""
    if has_images:
        return "image"
    strategy = settings.intent_strategy
    if strategy == "off":
        return DEFAULT_INTENT
    if strategy == "llm":
        try:
            from app.services.llm.factory import get_provider

            raw = get_provider().classify_intent(query, history)
            intent = (raw or "").strip().lower()
            if intent in ALLOWED_INTENTS:
                return intent
            logger.warning("llm 意图输出非法值 %r，回退规则", raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm 意图分类失败，回退规则: %s", exc)
    return classify_by_rules(query, history)
