"""一键演示数据：知识库样例说明书 + 示例对话会话（答辩/演示开箱即用）。

用法（需 MySQL/Redis/Qdrant 服务）：
    python scripts/seed_demo.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from rag_eval import EVAL_DOCS  # noqa: E402

DEMO_SESSION_ID = "sess-demo-0001"
DEMO_DIALOG: list[tuple[str, str]] = [
    (
        "最近嗓子干痒还有点咳嗽，能吃阿莫西林吗？",
        "嗓子干痒、咳嗽多见于上呼吸道感染，是否需要抗生素应由医生判断。"
        "若经诊断为敏感菌感染，常用阿莫西林（青霉素类抗生素）。"
        "注意：对青霉素过敏者禁用；常见不良反应为腹泻、恶心、皮疹。"
        "建议多饮水、清淡饮食，症状持续或加重请及时就医。仅供参考，不能替代执业医师诊断。",
    ),
    (
        "我有青霉素过敏史，那布洛芬呢？",
        "有青霉素过敏史者禁用阿莫西林。布洛芬属于非甾体抗炎药，与青霉素无交叉过敏，"
        "可用于缓解头痛、关节痛及退热。但活动性消化道溃疡、胃出血者禁用，"
        "常见不良反应为胃部不适。服药期间避免空腹，不建议连用超过 5 天。"
        "仅供参考，不能替代执业医师诊断。",
    ),
]


def seed() -> None:
    from app.core.database import SessionLocal
    from app.models.chat import ChatMessage, ChatSession
    from app.services.rag.ingest import ingest_file
    from app.services.rag.store import ensure_collection

    ensure_collection()
    for doc_id, drug_name, text in EVAL_DOCS:
        tmp = Path(ROOT / "data" / "rag_docs" / f"{doc_id}.txt")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        chunks = ingest_file(doc_id, drug_name, str(tmp))
        print(f"[ingest] {drug_name}: {chunks} chunks")

    with SessionLocal() as db:
        existing = (
            db.query(ChatSession).filter(ChatSession.session_id == DEMO_SESSION_ID).first()
        )
        if existing is None:
            sess = ChatSession(
                session_id=DEMO_SESSION_ID,
                user_id=1,
                summary="演示会话：上呼吸道感染用药咨询",
            )
            db.add(sess)
            db.flush()
            for question, answer in DEMO_DIALOG:
                db.add(ChatMessage(session_id=sess.id, role="user", content=question))
                db.add(
                    ChatMessage(
                        session_id=sess.id,
                        role="assistant",
                        content=answer,
                        reference_docs=[],
                    )
                )
            db.commit()
            print(f"[chat] demo session created: {DEMO_SESSION_ID}")
        else:
            print(f"[chat] demo session already exists: {DEMO_SESSION_ID}")

    print("done. 打开前端后可在会话列表中找到该演示会话。")


if __name__ == "__main__":
    seed()
