"""작업 진행 상태를 메모리에 저장하는 초경량 저장소.

BackgroundTasks는 HTTP 응답을 보낸 '뒤에' 실행되기 때문에 처리 결과를 응답으로
직접 돌려줄 수 없다. 대신 여기 dict에 진행 상태를 기록해두면, 클라이언트가
SSE(GET /api/jobs/{job_id}/events)로 그 상태 변화를 흘려받을 수 있다.

프로세스가 재시작되면 이 dict는 사라진다 (DB가 아니라 메모리이기 때문).
"""

from __future__ import annotations

import threading

from app.models.schemas import JobStatus


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobStatus] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str) -> JobStatus:
        with self._lock:
            job = JobStatus(job_id=job_id, status="pending", message="대기 중")
            self._jobs[job_id] = job
            return job

    def get(self, job_id: str) -> JobStatus | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields) -> JobStatus | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            updated = job.model_copy(update=fields)
            self._jobs[job_id] = updated
            return updated


# 프로세스 전역에서 공유하는 단일 인스턴스
job_store = JobStore()
