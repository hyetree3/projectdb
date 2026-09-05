"""업로드 및 작업 상태 조회 API.

전체 흐름: 업로드 -> job_id 즉시 응답 -> BackgroundTasks로 추출/청킹/임베딩/저장
-> 프론트엔드는 SSE(GET /api/jobs/{job_id}/events)로 진행 상태를 구독.
"""

from __future__ import annotations

import asyncio
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core import chunk as chunk_core
from app.core import embed as embed_core
from app.core import extract as extract_core
from app.core import store as store_core
from app.jobs import job_store
from app.models.schemas import ChunkMetadata, UploadResponse

router = APIRouter(prefix="/api", tags=["upload"])


def _process_document(job_id: str, document_id: str, pdf_path: Path, original_filename: str) -> None:
    """BackgroundTasks로 실행되는 동기 함수.

    ChromaDB가 동기 API이므로 이 함수는 async가 아닌 일반 함수로 정의한다.
    Starlette의 BackgroundTask는 동기 함수를 자동으로 스레드풀에서 실행하므로
    이벤트 루프를 막지 않는다.

    document_id(파일명 기반)와 job_id(업로드 시도별 UUID)를 분리하는 이유:
    같은 파일을 재업로드했을 때 job_id는 매번 새로 생기지만, ChromaDB에 저장되는
    청크 id는 document_id를 기반으로 동일하게 재계산되어야 upsert가 "덮어쓰기"로
    동작한다. job_id를 청크 id에 쓰면 재업로드할 때마다 중복 청크가 쌓인다.
    """
    try:
        job_store.update(job_id, status="extracting", message="텍스트 추출 중", progress=0.1)
        pages = extract_core.extract_text(pdf_path)

        job_store.update(job_id, status="chunking", message="청킹 중", progress=0.4)
        chunks = chunk_core.chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)

        if not chunks:
            job_store.update(
                job_id, status="failed", message="추출된 텍스트가 없습니다 (빈 PDF이거나 이미지로만 구성됨).", progress=0.0
            )
            return

        job_store.update(job_id, status="embedding", message=f"임베딩 중 (청크 {len(chunks)}개)", progress=0.7)
        embeddings = embed_core.embed_passages([c.text for c in chunks])

        job_store.update(job_id, status="embedding", message="ChromaDB 저장 중", progress=0.9)
        uploaded_at = datetime.now(UTC)
        ids = [f"{document_id}_{c.chunk_id}" for c in chunks]
        metadatas = [
            ChunkMetadata(
                document_id=document_id,
                chunk_id=c.chunk_id,
                source=original_filename,
                page=c.page,
                section=c.section,
                uploaded_at=uploaded_at,
            ).model_dump(mode="json")
            for c in chunks
        ]
        store_core.upsert_chunks(
            settings.chroma_persist_dir,
            ids=ids,
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=metadatas,
        )

        job_store.update(job_id, status="done", message=f"완료 ({len(chunks)}개 청크 저장)", progress=1.0)
    except NotImplementedError as exc:
        job_store.update(job_id, status="failed", message=f"미구현: {exc}", progress=0.0)
    except Exception as exc:  # noqa: BLE001 - 백그라운드 작업 실패를 상태로 남기기 위해 광범위 처리
        job_store.update(job_id, status="failed", message=f"오류: {exc}", progress=0.0)


@router.post("/upload", response_model=UploadResponse)
def upload_pdf(file: UploadFile, background_tasks: BackgroundTasks) -> UploadResponse:
    """PDF를 업로드받아 저장하고, 임베딩 작업을 백그라운드로 예약한다.

    응답은 즉시 job_id를 돌려준다 (임베딩은 BackgroundTasks로 비동기 처리).
    """
    if file.filename is None or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    # 한글 파일명은 조합형(NFC)/분해형(NFD)이 섞이면 같은 글자도 다른 문자열로
    # 취급될 수 있어 반드시 NFC로 정규화한다.
    filename = unicodedata.normalize("NFC", file.filename)
    document_id = Path(filename).stem

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    job_id = str(uuid.uuid4())
    pdf_path = upload_dir / f"{job_id}_{filename}"

    try:
        with pdf_path.open("wb") as f:
            f.write(file.file.read())
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"파일 저장 실패: {exc}") from exc

    job_store.create(job_id)
    background_tasks.add_task(_process_document, job_id, document_id, pdf_path, filename)

    return UploadResponse(job_id=job_id, filename=filename)


@router.get("/documents")
def list_documents() -> list[dict]:
    """지금까지 저장된 문서 목록과 청크 수를 반환한다 (업로드 진행 상황 확인용).

    ChromaDB는 동기 API이므로 이 라우트도 async가 아닌 일반 함수로 정의한다.
    """
    return store_core.list_documents(settings.chroma_persist_dir)


@router.get("/documents/{document_id}/chunks")
def list_chunks(document_id: str) -> list[dict]:
    """특정 문서가 어떤 청크로 나뉘었는지, 각 청크의 임베딩이 어떻게 나왔는지 보여준다.

    임베딩 벡터는 1024차원 전체를 그대로 내려주면 응답이 지나치게 커지므로,
    확인 목적으로 앞 8개 값만 미리보기로 잘라 보낸다 (전체 차원 수는 별도로 표시).
    """
    chunks = store_core.list_chunks(settings.chroma_persist_dir, document_id)
    return [
        {
            "chunk_id": c["chunk_id"],
            "page": c["page"],
            "section": c["section"],
            "text": c["text"],
            "embedding_preview": [round(float(v), 4) for v in c["embedding"][:8]],
            "embedding_dim": len(c["embedding"]),
        }
        for c in chunks
    ]


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    """작업 진행 상태를 SSE(Server-Sent Events)로 흘려보낸다.

    프론트엔드는 EventSource로 이 엔드포인트를 구독한다.
    작업이 done/failed에 도달하면 스트림을 종료한다.
    """
    if job_store.get(job_id) is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 job_id입니다.")

    async def event_stream():
        while True:
            job = job_store.get(job_id)
            if job is None:
                break
            yield f"data: {job.model_dump_json()}\n\n"
            if job.status in ("done", "failed"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
