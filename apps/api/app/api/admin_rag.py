"""管理：RAG 知识库（上传文件 / URL / 列表 / 删除 / 重建 / 启停 / 下载 / 切片）。"""
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
    stmt = stmt.order_by(RagDocument.created_at.desc())
    return [_doc_out(d) for d in await db.scalars(stmt)]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    category_id: int = Form(...),
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.document_service import process_document
    from app.tasks.worker import enqueue

    ext = Path(file.filename or "").suffix.lower()
    ftype = next((k for k, v in ALLOWED_TYPES.items() if v == ext), None)
    if not ftype:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型 {ext}，仅支持：pdf/docx/md/txt")

    import time

    save_dir = Path(settings.upload_dir) / "rag" / str(time.time())
    save_dir.mkdir(parents=True, exist_ok=True)
    dest = save_dir / (file.filename or "unnamed")
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = RagDocument(
        category_id=category_id, filename=file.filename or "unnamed",
        storage_path=str(dest), file_type=ftype, status="pending", chunk_count=0, enabled=True,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    try:
        await enqueue("parse_rag_document_task", doc.id)
    except Exception:
        await process_document(db, doc.id)
    await audit(db, "user", admin.id, "rag_doc_upload", "rag_document", doc.id, {"filename": doc.filename})
    return _doc_out(doc)


@router.post("/url")
async def add_url_document(
    url: str = Form(...),
    category_id: int = Form(...),
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.document_service import process_document
    from app.tasks.worker import enqueue

    doc = RagDocument(
        category_id=category_id, filename=url[:200], storage_path=url, file_type="url", status="pending", chunk_count=0, enabled=True,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    try:
        await enqueue("parse_rag_document_task", doc.id)
    except Exception:
        await process_document(db, doc.id)
    await audit(db, "user", admin.id, "rag_doc_url", "rag_document", doc.id, {"url": url})
    return _doc_out(doc)


@router.delete("/{doc_id}")
async def delete_document(doc_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone

    from app.config import settings

    doc = await db.get(RagDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    doc.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    # Weaviate 同步清理
    if settings.vector_backend == "weaviate":
        from app.services.weaviate_service import delete_document_chunks

        await delete_document_chunks(doc_id)
    await audit(db, "user", admin.id, "rag_doc_delete", "rag_document", doc_id)
    return {"ok": True}


@router.get("/{doc_id}/download")
async def download_document(doc_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """下载知识库文档（本地文件或 URL 类型跳转）。"""
    from fastapi.responses import FileResponse, RedirectResponse

    doc = await db.get(RagDocument, doc_id)
    if not doc or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文档不存在")
    if doc.file_type == "url":
        return RedirectResponse(url=doc.storage_path or "/")
    path = Path(doc.storage_path or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在或已被清理")
    return FileResponse(path=str(path), filename=doc.filename or path.name)


@router.get("/{doc_id}/chunks")
async def list_doc_chunks(doc_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """查看某文档的切片列表（含内容预览）。"""
    from app.schemas import RagChunkOut

    doc = await db.get(RagDocument, doc_id)
    if not doc or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文档不存在")
    rows = list(
        await db.scalars(
            select(RagChunk).where(RagChunk.document_id == doc_id).order_by(RagChunk.chunk_index).limit(500)
        )
    )
    return [
        RagChunkOut(
            id=r.id, chunk_index=r.chunk_index, title=r.title, content=r.content,
            meta_data=r.meta_data, created_at=r.created_at,
        )
        for r in rows
    ]


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
