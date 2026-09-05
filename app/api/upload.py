"""업로드 및 작업 상태 조회 API. (1-A 실제 구현 예정 - 배관(plumbing)만 연결됨)

실제 추출/청킹/임베딩/저장 로직은 app.core.* 모듈에 있으며 아직 NotImplementedError를
던진다. 여기서는 그 예외를 잡아 작업 상태를 "failed"로 기록해, 골격 단계에서도
업로드 -> job_id 발급 -> SSE로 상태 확인까지 전체 흐름을 테스트할 수 있게 한다.
"""

from __future__ import annotations

import asyncio
import unicodedata
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core import chunk as chunk_core
from app.core import embed as embed_core
from app.core import extract as extract_core
from app.jobs import job_store
from app.models.schemas import UploadResponse

router = APIRouter(prefix="/api", tags=["upload"])


def _process_document(job_id: str, pdf_path: Path, original_filename: str) -> None:
    """BackgroundTasks로 실행되는 동기 함수.

    ChromaDB가 동기 API이므로 이 함수는 async가 아닌 일반 함수로 정의한다.
    Starlette의 BackgroundTask는 동기 함수를 자동으로 스레드풀에서 실행하므로
    이벤트 루프를 막지 않는다.
    """
    try:
        job_store.update(job_id, status="extracting", message="텍스트 추출 중", progress=0.1)
        pages = extract_core.extract_text(pdf_path)

        job_store.update(job_id, status="chunking", message="청킹 중", progress=0.4)
        chunks = chunk_core.chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)

        job_store.update(job_id, status="embedding", message="임베딩 중", progress=0.7)
        embed_core.embed_passages([c.text for c in chunks])

        job_store.update(job_id, status="embedding", message="ChromaDB 저장 중", progress=0.9)
        # store_core.upsert_chunks(...)  # 1-A 구현 예정

        job_store.update(job_id, status="done", message="완료", progress=1.0)
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
    background_tasks.add_task(_process_document, job_id, pdf_path, filename)

    return UploadResponse(job_id=job_id, filename=filename)


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
