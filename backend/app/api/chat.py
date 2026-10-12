import json
import time
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.deps import CurrentUser
from app.core.middleware import get_trace_id
from app.core.response import not_found, success
from app.models.chat import ChatMessage, ChatSession, FileObject
from app.services.llm.factory import get_provider
from app.services.llm.resilience import DEGRADE_MSG, LLMUnavailable, stream_with_resilience
from app.services.rag import search_chunks
from app.services.usage import record_usage

router = APIRouter()

DISCLAIMER = (
    "提示：本内容仅为药品科普参考，不能替代执业医师诊断，"
    "不能作为处方依据，身体不适请前往医疗机构就诊。"
)

SYSTEM_PROMPT = (
    "你是药品科普辅助助手，仅基于召回的药品说明书片段进行科普解答。"
    "禁止给出疾病诊断、禁止开具处方、禁止给出治疗方案。"
    "回答末尾必须附带免责声明。"
)


class ChatBody(BaseModel):
    userDesc: str
    imageList: list[str] = []


def _parse_images(image_list: list[str], db: Session, trace_id: str, user_id: int) -> str:
    if not image_list:
        return ""
    provider = get_provider()
    parts: list[str] = []
    for file_id in image_list:
        row = db.execute(
            select(FileObject).where(FileObject.file_id == file_id)
        ).scalar_one_or_none()
        if row is None:
            continue
        start = time.perf_counter()
        status = "success"
        try:
            text = provider.parse_image(row.file_path)
        except Exception:
            status = "failed"
            raise
        finally:
            record_usage(
                trace_id=trace_id,
                user_id=user_id,
                api_type="vl",
                prompt_text=f"image:{row.file_path}",
                completion_text=text if status == "success" else "",
                duration_ms=int((time.perf_counter() - start) * 1000),
                status=status,
            )
        parts.append(text)
    return "\n".join(parts)


def _build_messages(
    history: list[ChatMessage],
    user_text: str,
    rag_docs: list[dict] | None = None,
) -> list[dict]:
    system = SYSTEM_PROMPT
    if rag_docs:
        ctx = "\n".join(
            f"[{i + 1}]《{d.get('drugName', '')}》{d.get('chunkContent', '')[:300]}"
            for i, d in enumerate(rag_docs)
        )
        system += f"\n以下是召回的药品说明书片段：\n{ctx}\n仅基于以上片段作答，片段不足时提示就医。"
    messages: list[dict] = [{"role": "system", "content": system}]
    for m in history[-10:]:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_text})
    return messages


def _get_session(db: Session, session_id: str, user: dict) -> ChatSession:
    sess = db.execute(
        select(ChatSession).where(ChatSession.session_id == session_id)
    ).scalar_one_or_none()
    if sess is None:
        raise not_found("会话不存在")
    if user.get("role") != "admin" and sess.user_id != int(user["sub"]):
        raise not_found("会话不存在")
    return sess


def _gen_answer(messages: list[dict], trace_id: str, user_id: int) -> str:
    provider = get_provider()
    prompt_text = json.dumps(messages, ensure_ascii=False)
    start = time.perf_counter()
    status = "success"
    text = ""
    try:
        text = "".join(stream_with_resilience(provider, messages))
    except LLMUnavailable:
        status = "degraded"
    except Exception:
        status = "failed"
        raise
    finally:
        record_usage(
            trace_id=trace_id,
            user_id=user_id,
            api_type="llm",
            prompt_text=prompt_text,
            completion_text=text,
            duration_ms=int((time.perf_counter() - start) * 1000),
            status=status,
        )
    if status == "degraded":
        return DEGRADE_MSG + "\n" + DISCLAIMER
    return text + "\n" + DISCLAIMER


@router.post("/session/create")
def create_session(
    request: Request,
    body: ChatBody,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    trace_id = get_trace_id(request)
    user_id = int(user["sub"])
    img_text = _parse_images(body.imageList, db, trace_id, user_id)
    query = body.userDesc + (f"\n[图片解析]\n{img_text}" if img_text else "")
    rag_docs = search_chunks(query)
    answer = _gen_answer(_build_messages([], query, rag_docs), trace_id, user_id)

    sess = ChatSession(
        session_id=f"sess-{uuid.uuid4().hex[:16]}",
        user_id=int(user["sub"]),
        summary=body.userDesc[:50],
    )
    db.add(sess)
    db.flush()
    db.add(
        ChatMessage(
            session_id=sess.id,
            role="user",
            content=body.userDesc,
            trace_id=get_trace_id(request),
        )
    )
    db.add(
        ChatMessage(
            session_id=sess.id,
            role="assistant",
            content=answer,
            reference_docs=rag_docs,
            trace_id=get_trace_id(request),
        )
    )
    db.commit()
    return success(
        request,
        {"sessionId": sess.session_id, "answer": answer, "referenceDocs": rag_docs},
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/session/{session_id}/message")
def send_message(
    session_id: str,
    request: Request,
    body: ChatBody,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    sess = _get_session(db, session_id, user)
    history = list(
        db.execute(
            select(ChatMessage).where(ChatMessage.session_id == sess.id).order_by(ChatMessage.id)
        ).scalars()
    )
    trace_id = get_trace_id(request)
    user_id = int(user["sub"])
    img_text = _parse_images(body.imageList, db, trace_id, user_id)
    query = body.userDesc + (f"\n[图片解析]\n{img_text}" if img_text else "")
    history_texts = [m.content for m in history if m.role == "user"][-3:]
    rag_docs = search_chunks(query, history=history_texts)
    messages = _build_messages(history, query, rag_docs)

    db.add(
        ChatMessage(
            session_id=sess.id,
            role="user",
            content=body.userDesc,
            trace_id=trace_id,
        )
    )
    sess.updated_at = func.now()
    db.commit()

    accept = request.headers.get("accept", "")
    if "text/event-stream" not in accept:
        answer = _gen_answer(messages, trace_id, user_id)
        db.add(
            ChatMessage(
                session_id=sess.id,
                role="assistant",
                content=answer,
                reference_docs=rag_docs,
                trace_id=trace_id,
            )
        )
        db.commit()
        return success(
            request,
            {"sessionId": session_id, "answer": answer, "referenceDocs": rag_docs},
        )

    provider = get_provider()

    def gen() -> Iterator[str]:
        parts: list[str] = []
        prompt_text = json.dumps(messages, ensure_ascii=False)
        start = time.perf_counter()
        status = "success"
        try:
            for chunk in provider.stream_chat(messages):
                parts.append(chunk)
                yield _sse("delta", {"content": chunk})
            answer = "".join(parts) + "\n" + DISCLAIMER
            with SessionLocal() as s:
                s.add(
                    ChatMessage(
                        session_id=sess.id,
                        role="assistant",
                        content=answer,
                        reference_docs=rag_docs,
                        trace_id=trace_id,
                    )
                )
                s.commit()
            yield _sse(
                "done",
                {
                    "sessionId": session_id,
                    "referenceDocs": rag_docs,
                    "disclaimer": DISCLAIMER,
                },
            )
        except LLMUnavailable as exc:
            status = "degraded"
            yield _sse("error", {"code": 50001, "msg": str(exc)})
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            yield _sse("error", {"code": 50001, "msg": f"生成失败：{exc}"})
        finally:
            record_usage(
                trace_id=trace_id,
                user_id=user_id,
                api_type="llm",
                prompt_text=prompt_text,
                completion_text="".join(parts),
                duration_ms=int((time.perf_counter() - start) * 1000),
                status=status,
            )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/session/list")
def session_list(
    request: Request,
    user: CurrentUser,
    page: int = 1,
    size: int = 10,
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    size = min(max(size, 1), 50)
    q = select(ChatSession)
    if user.get("role") != "admin":
        q = q.where(ChatSession.user_id == int(user["sub"]))
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = list(
        db.execute(
            q.order_by(desc(ChatSession.updated_at)).offset((page - 1) * size).limit(size)
        ).scalars()
    )
    items = [
        {
            "sessionId": r.session_id,
            "summary": r.summary,
            "status": r.status,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
            "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    return success(request, {"list": items, "total": total, "page": page, "size": size})


@router.get("/session/{session_id}")
def session_detail(
    session_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    sess = _get_session(db, session_id, user)
    msgs = list(
        db.execute(
            select(ChatMessage).where(ChatMessage.session_id == sess.id).order_by(ChatMessage.id)
        ).scalars()
    )
    return success(
        request,
        {
            "sessionId": sess.session_id,
            "summary": sess.summary,
            "status": sess.status,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "referenceDocs": m.reference_docs or [],
                    "createdAt": m.created_at.isoformat() if m.created_at else None,
                }
                for m in msgs
            ],
        },
    )
