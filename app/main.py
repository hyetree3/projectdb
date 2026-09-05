"""FastAPI 진입점.

CORS 미들웨어는 추가하지 않는다 - 개발 중 프론트엔드(:5173)의 Vite 프록시가
/api 요청을 백엔드(:8000)로 전달해 CORS 문제 자체가 발생하지 않도록 한다.
"""

from fastapi import FastAPI

from app.api.upload import router as upload_router

app = FastAPI(title="글로벌 ICT 동향 리포트 조회")

app.include_router(upload_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
