"""管理：RAG 知识库（上传文件 / URL / 列表 / 删除 / 重建 / 启停）。"""
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import get_db
from app.core.deps import require_super_admin
from app.models import RagChunk, RagDocument, User
from app.schemas import RagDocumentOut
from app.services.audit_service import audit

router = APIRouter(prefix="/api/admin/rag", tags=["admin-rag"])

ALLOWED_TYPES = {"pdf": ".pdf", "docx": ".docx", "md": ".md", "txt": ".txt"}


def _doc_out(d: RagDocument) -> RagDocumentOut:
    return RagDocumentOut(
        id=d.id, category_id=d.category_id, filename=d.filename, file_type=d.file_type,
        status=d.status, chunk_count=d.chunk_count, enabled=d.enabled, error=d.error, created_at=d.created_at,
    )


@router.get("", response_model=list[RagDocumentOut])
async def list_documents(category_id: int | None = None, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    stmt = select(RagDocument).where(RagDocument.deleted_at.is_(None))
    if category_id:
        stmt = stmt.where(RagDocument.category_id == category_id)
    rows = list(await db.scalars(stmt.order_by(RagDocument.created_at.desc())))
    return [_doc_out(d) for d in rows]


@router.post("/upload", response_model=RagDocumentOut)
async def upload_document(
    category_id: int = Form(...),
    file: UploadFile = File(...),
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()
    file_type = next((k for k, v in ALLOWED_TYPES.items() if v == ext), None)
    if not file_type:
        raise HTTPException(status_code=400, detail="仅支持 PDF / DOCX / MD / TXT")

    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    dest = upload_root / f"doc_{admin.id}_{file.filename}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = RagDocument(
        category_id=category_id, filename=file.filename or "unnamed", file_type=file_type,
        storage_path=str(dest), uploader_id=admin.id, status="parsing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    from app.tasks.worker import enqueue

    try:
        await enqueue("parse_rag_document_task", doc.id)
    except Exception:
        from app.services.document_service import process_document

        await process_document(db, doc.id)
    await audit(db, "user", admin.id, "rag_doc_upload", "rag_document", doc.id, {"filename": doc.filename})
    return _doc_out(doc)


@router.post("/url", response_model=RagDocumentOut)
async def add_url_document(
    category_id: int = Form(...),
    url: str = Form(...),
    name: str | None = Form(None),
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    doc = RagDocument(
        category_id=category_id, filename=name or url[:200], file_type="url",
        storage_path=url, uploader_id=admin.id, status="parsing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    from app.tasks.worker import enqueue

    try:
        await enqueue("parse_rag_document_task", doc.id)
    except Exception:
        from app.services.document_service import process_document

        await process_document(db, doc.id)
    await audit(db, "user", admin.id, "rag_doc_add_url", "rag_document", doc.id, {"url": url})
    return _doc_out(doc)


@router.delete("/{doc_id}")
async def delete_document(doc_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone

    doc = await db.get(RagDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    doc.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    await audit(db, "user", admin.id, "rag_doc_delete", "rag_document", doc_id)
    return {"ok": True}


@router.post("/{doc_id}/toggle")
async def toggle_document(doc_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    doc = await db.get(RagDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    doc.enabled = not doc.enabled
    await db.commit()
    return {"enabled": doc.enabled}


@router.post("/{doc_id}/rebuild")
async def rebuild_document(doc_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """重新 embedding（换模型后使用）。"""
    doc = await db.get(RagDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    from app.services.model_service import get_default_llm_config
    from app.services.rag_service import rebuild_chunks

    try:
        cfg = await get_default_llm_config(db)
        await rebuild_chunks(db, doc_id, cfg)
        return {"ok": True, "chunks": doc.chunk_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"重建失败：{str(e)[:200]}")
