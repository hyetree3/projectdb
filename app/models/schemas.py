"""API 요청/응답 및 내부 데이터 구조를 정의하는 Pydantic 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """업로드 직후 즉시 반환되는 응답.

    임베딩은 BackgroundTasks로 비동기 처리되므로, 여기서는 결과가 아니라
    진행 상태를 조회할 수 있는 job_id만 돌려준다.
    """

    job_id: str
    filename: str


JobStatusValue = Literal["pending", "extracting", "chunking", "embedding", "done", "failed"]


class JobStatus(BaseModel):
    """작업 진행 상태. 메모리(dict)에 저장되며 프로세스 재시작 시 사라진다."""

    job_id: str
    status: JobStatusValue
    message: str = ""
    progress: float = 0.0  # 0.0 ~ 1.0


class ChunkMetadata(BaseModel):
    """ChromaDB에 각 청크와 함께 저장되는 메타데이터. 절대 누락하면 안 된다.

    이 중 하나라도 빠지면 검색 결과에 출처를 표시할 수 없어 전체 재적재가 필요하다.
    """

    document_id: str
    chunk_id: str
    source: str  # 원본 파일명
    page: int
    section: str  # 청크가 속한 상위 제목(섹션)
    uploaded_at: datetime


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    mode: Literal["vector", "keyword", "hybrid"] = "hybrid"


class SentenceMatch(BaseModel):
    """청크를 문장 단위로 쪼갠 뒤, 질문과의 의미 유사도를 각각 계산한 결과.

    화면에서 하이라이트 표시에 사용한다 (is_best=True인 문장을 강조).
    """

    text: str
    similarity: float  # 코사인 유사도. 1에 가까울수록 유사 (distance와 반대 방향).
    is_best: bool


class SearchResultItem(BaseModel):
    """검색 결과 하나. 출처(source/page/section) 없는 결과는 없다 - 항상 함께 반환한다.

    점수 필드 3종은 검색 모드에 따라 일부만 채워진다 (학습용으로 원신호를 그대로 노출):
    - distance: 벡터 검색 cosine distance. 작을수록 유사. (vector/hybrid 모드에서만)
    - bm25_score: 키워드 검색 BM25 점수. 클수록 유사. (keyword/hybrid 모드에서만)
    - rrf_score: 하이브리드 결합 순위 점수. 클수록 상위. (hybrid 모드에서만)
    """

    text: str
    source: str
    page: int
    section: str
    sentences: list[SentenceMatch]  # 문장 단위 하이라이트용
    distance: float | None = None
    bm25_score: float | None = None
    rrf_score: float | None = None


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    message: str = ""  # 결과가 없을 때 사용자에게 보여줄 안내 메시지
