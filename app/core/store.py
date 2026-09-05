"""ChromaDB 벡터 저장소 래퍼.

**이 프로젝트에서 chromadb를 import하는 파일은 이 파일 하나뿐이다.**
2차 단계에서 ChromaDB -> PostgreSQL + pgvector로 교체할 때 이 파일만
바꾸면 되도록 하기 위함이다. 다른 곳에서는 이 모듈이 제공하는 함수만 사용한다.

주의 사항 (구현 시 반드시 지킬 것):
- ChromaDB는 동기(sync) API다. async def 라우트에서 직접 호출하면 이벤트 루프가
  멈춘다. 반드시 동기 함수(def)에서 호출하거나 run_in_threadpool()로 감싼다.
- 거리 척도(distance metric)는 컬렉션 "생성 시점"에 고정된다. metadata에
  {"hnsw:space": "cosine"}을 반드시 지정한다 - 나중에 바꿀 수 없다.
  cosine distance는 두 벡터의 방향이 얼마나 다른지를 나타내며, 값이 "작을수록"
  두 텍스트가 의미적으로 더 가깝다(유사하다). 유사도 점수(score)와는 방향이 반대다.
- 재업로드 시 같은 문서를 다시 넣을 수 있으므로 add()가 아니라 upsert()를 쓴다.
  add()는 같은 id가 이미 있으면 에러가 나거나 중복이 쌓일 수 있다.
- 메타데이터(document_id/chunk_id/source/page/section/uploaded_at)를 절대
  누락하지 않는다 - 이후 검색 결과에 출처를 표시할 때 필요하고, 빠뜨리면
  전체 재적재가 필요하다.
"""

from __future__ import annotations

import chromadb

_client: chromadb.ClientAPI | None = None

COLLECTION_NAME = "ict_reports"


def get_client(persist_dir: str) -> chromadb.ClientAPI:
    """PersistentClient를 생성(또는 캐시된 인스턴스를 반환)한다."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=persist_dir)
    return _client


def get_collection(persist_dir: str) -> chromadb.Collection:
    """컬렉션을 가져오거나 없으면 생성한다. cosine distance로 고정한다.

    hnsw:space는 컬렉션이 이미 존재하면 무시되고 최초 생성 시에만 적용된다.
    """
    client = get_client(persist_dir)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(
    persist_dir: str,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    """청크를 upsert한다 (add가 아님 - 재업로드 대응).

    같은 document_id로 재업로드되면 ids가 동일하게 재계산되어 기존 청크를
    덮어쓴다. 단, 새 문서의 청크 수가 이전보다 줄어든 경우 남는 옛 청크는
    자동으로 삭제되지 않는다 (이 프로젝트 범위 밖의 별도 정리 로직 필요).
    """
    if not ids:
        return
    collection = get_collection(persist_dir)
    collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def query_similar(persist_dir: str, query_embedding: list[float], top_k: int) -> list[dict]:
    """질문 벡터와 가장 유사한 청크 top_k개를 찾는다 (1-B).

    collection.query()는 ChromaDB 버전마다 반환 형태가 다를 수 있어 실제 호출로
    확인한 결과를 기준으로 작성함(chromadb 1.5.9): distances/metadatas/documents가
    각각 "쿼리 1개당 리스트 하나"로 감싸여 반환되므로 [0] 인덱스로 꺼낸다.

    Returns:
        [{"text": ..., "distance": ..., **metadata}, ...] - distance가 작을수록 유사.
    """
    collection = get_collection(persist_dir)
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = result["documents"][0] if result["documents"] else []
    metadatas = result["metadatas"][0] if result["metadatas"] else []
    distances = result["distances"][0] if result["distances"] else []

    return [
        {"text": text, "distance": distance, **metadata}
        for text, metadata, distance in zip(documents, metadatas, distances, strict=True)
    ]


def list_chunks(persist_dir: str, document_id: str) -> list[dict]:
    """특정 문서의 청크 원문 + 임베딩을 페이지/청크 순서대로 반환한다 (확인용 화면).

    where={"document_id": ...}로 해당 문서의 청크만 필터링한다.
    """
    collection = get_collection(persist_dir)
    result = collection.get(
        where={"document_id": document_id},
        include=["documents", "metadatas", "embeddings"],
    )

    items = [
        {
            "chunk_id": metadata["chunk_id"],
            "page": metadata["page"],
            "section": metadata["section"],
            "text": text,
            "embedding": embedding,
        }
        for text, metadata, embedding in zip(
            result["documents"], result["metadatas"], result["embeddings"], strict=True
        )
    ]
    items.sort(key=lambda item: (item["page"], item["chunk_id"]))
    return items


def get_all_chunks(persist_dir: str) -> list[dict]:
    """컬렉션에 저장된 모든 청크를 반환한다 (1-C 키워드/BM25 검색용).

    BM25는 ChromaDB가 제공하지 않는 기능이라 별도 라이브러리(rank-bm25)로
    직접 계산해야 한다. 그러려면 전체 청크 텍스트 말뭉치(corpus)가 필요한데,
    ChromaDB를 아는 파일은 이 파일뿐이므로 여기서 원문+메타데이터를 그대로
    꺼내주고, 실제 BM25 점수 계산은 app/core/keyword.py에서 한다.
    """
    collection = get_collection(persist_dir)
    result = collection.get(include=["documents", "metadatas"])
    return [
        {"text": text, **metadata}
        for text, metadata in zip(result["documents"], result["metadatas"], strict=True)
    ]


def list_documents(persist_dir: str) -> list[dict]:
    """저장된 문서별 청크 수를 집계한다 (업로드 진행 상황 확인용 - 검색 기능은 아님).

    유사도 검색(1-B)과 무관하게, 지금까지 어떤 문서가 몇 개의 청크로
    저장됐는지 확인하기 위한 용도다.
    """
    collection = get_collection(persist_dir)
    data = collection.get(include=["metadatas"])

    counts: dict[str, dict] = {}
    for meta in data["metadatas"]:
        doc_id = meta["document_id"]
        if doc_id not in counts:
            counts[doc_id] = {
                "document_id": doc_id,
                "source": meta["source"],
                "chunk_count": 0,
                "uploaded_at": meta["uploaded_at"],
            }
        counts[doc_id]["chunk_count"] += 1

    return sorted(counts.values(), key=lambda d: d["uploaded_at"])
