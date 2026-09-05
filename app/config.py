"""애플리케이션 설정.

pydantic-settings로 .env 파일을 읽어들인다. 환경변수 > .env 파일 > 기본값 순으로 우선한다.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ChromaDB PersistentClient가 데이터를 저장하는 경로
    chroma_persist_dir: str = "./data/chroma"

    # 임베딩 모델명 (fastembed TextEmbedding에 전달)
    # BAAI/bge-m3는 fastembed 0.8.0이 지원하지 않아 다국어 대체 모델을 사용한다.
    embedding_model: str = "intfloat/multilingual-e5-large"

    # fastembed 모델 다운로드 캐시 경로 (최초 실행 시 다운로드됨, 용량이 커서 .gitignore 처리)
    embedding_cache_dir: str = "./data/model_cache"

    # 업로드된 원본 PDF 저장 경로
    upload_dir: str = "./data/uploads"

    # 청킹 기준선. 검색 품질이 이상하면 가장 먼저 조정할 값.
    chunk_size: int = 600
    chunk_overlap: int = 100

    # 검색 결과 채택 임계값 (cosine distance 기준, 작을수록 유사).
    # 최상위 결과의 distance가 이 값을 넘으면 "관련 문서 없음"으로 응답한다.
    # 시작 값이며, 실제 검색 결과를 보고 조정한다.
    search_distance_threshold: float = 0.5

    # 검색 결과 기본 개수(top_k)
    search_top_k: int = 5


settings = Settings()
