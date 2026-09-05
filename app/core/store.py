"""ChromaDB 벡터 저장소 래퍼. (1-A 실제 구현 예정 - 현재는 골격만)

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


def get_collection(persist_dir: str):
    """컬렉션을 가져오거나 없으면 생성한다. cosine distance로 고정한다."""
    raise NotImplementedError(
        "1-A 구현 예정: get_or_create_collection(name=COLLECTION_NAME, "
        'metadata={"hnsw:space": "cosine"})'
    )


def upsert_chunks(persist_dir: str, ids: list[str], embeddings: list, documents: list[str], metadatas: list[dict]) -> None:
    """청크를 upsert한다 (add가 아님 - 재업로드 대응)."""
    raise NotImplementedError("1-A 구현 예정: collection.upsert(...)")
