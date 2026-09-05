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
