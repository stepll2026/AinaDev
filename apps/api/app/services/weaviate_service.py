"""Weaviate 独立向量库服务（应用侧生成向量后写入；集合 vectorizer=NONE）。"""
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_client = None


def get_client():
    """懒加载 Weaviate 客户端。"""
    global _client
    if _client is None:
        import weaviate
        from weaviate.classes.init import AdditionalConfig, Auth, Timeout
        from weaviate.classes.query import Filter

        try:
            _client = weaviate.connect_to_custom(
                http_host=settings.weaviate_host,
                http_port=settings.weaviate_http_port,
                http_secure=False,
                grpc_host=settings.weaviate_host,
                grpc_port=settings.weaviate_grpc_port,
                grpc_secure=False,
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=30, query=60, insert=60),
                ),
            )
        except Exception as exc:
            logger.warning("Weaviate connect failed: %s", exc)
            _client = None
    return _client


def _collection():
    client = get_client()
    if client is None:
        return None
    try:
        return client.collections.get(settings.weaviate_collection)
    except Exception:
        return None


def _filter_eq(prop: str, value: Any):
    from weaviate.classes.query import Filter

    return Filter.by_property(prop).equal(value)


async def upsert_chunk(chunk_id: int, document_id: int, category_id: int, chunk_index: int, title, content: str, filename: str, vector: list[float]) -> None:
    """写入/更新一个切片的向量与元数据。"""
    col = _collection()
    if col is None:
        logger.warning("weaviate 不可用，跳过写入 chunk %s", chunk_id)
        return
    import uuid

    obj_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"ainadev-chunk-{chunk_id}")
    props = {
        "chunk_id": int(chunk_id),
        "document_id": int(document_id),
        "category_id": int(category_id),
        "chunk_index": int(chunk_index),
        "title": title or "",
        "content": content[:20000],
        "filename": filename,
    }
    try:
        col.data.insert(uuid=obj_uuid, properties=props, vector=vector)
    except Exception as exc:
        logger.warning("weaviate upsert failed: %s", exc)


async def search_vectors(category_id: int, qvec: list[float], top: int = 20) -> list[tuple[int, float]]:
    """向量检索，返回 [(chunk_id, 相似度)]。"""
    col = _collection()
    if col is None:
        return []
    from weaviate.classes.query import Filter

    try:
        res = col.query.near_vector(
            near_vector=qvec,
            filters=Filter.by_property("category_id").equal(category_id),
            limit=top,
            return_properties=["chunk_id"],
        )
        out: list[tuple[int, float]] = []
        for obj in res.objects:
            cid = obj.properties.get("chunk_id")
            if cid is None:
                continue
            sim = 1.0 - float(obj.metadata.distance)
            out.append((int(cid), sim))
        return out
    except Exception as exc:
        logger.warning("weaviate search failed: %s", exc)
        return []


async def delete_document_chunks(document_id: int) -> None:
    """删除某文档的全部向量（重建/删除文档时调用）。"""
    col = _collection()
    if col is None:
        return
    try:
        col.data.delete_many(where=_filter_eq("document_id", document_id))
    except Exception as exc:
        logger.warning("weaviate delete failed: %s", exc)
