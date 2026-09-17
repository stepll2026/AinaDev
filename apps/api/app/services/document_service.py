"""文档入库服务：解析 → 切片 → embedding → 入库。"""
import logging
import re
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RagDocument
from app.services.model_service import get_default_llm_config
from app.services.rag_service import chunk_text, embed_and_store_chunks, parse_document

logger = logging.getLogger(__name__)


async def process_document(db: AsyncSession, doc_id: int) -> None:
    """后台处理单个文档。"""
    doc = await db.get(RagDocument, doc_id)
    if not doc or doc.deleted_at is not None:
        return
    doc.status = "processing"
    await db.commit()
    try:
        text_content = await parse_document(
            doc.storage_path if doc.file_type != "url" else None,
            doc.storage_path if doc.file_type == "url" else None,
            doc.file_type,
            doc.filename,
        )
        chunks = chunk_text(text_content)
        if not chunks:
            raise ValueError("文档没有可索引的文本内容")
        cfg = await get_default_llm_config(db)
        await embed_and_store_chunks(db, doc, chunks, cfg)
    except Exception as e:
        logger.exception("process document failed: %s", e)
        await db.rollback()  # 先回滚被中断的事务，再写入失败状态
        doc.status = "failed"
        doc.error = str(e)[:500]
        await db.commit()
