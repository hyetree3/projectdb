"""텍스트를 벡터로 변환한다 (임베딩). (1-A 실제 구현 예정 - 현재는 골격만)

임베딩(embedding)이란?
텍스트의 의미를 고정 길이의 숫자 벡터로 바꾼 것. 의미가 비슷한 문장은
벡터 공간에서 가까운 위치에 놓이므로, "키워드가 정확히 일치하지 않아도"
의미가 비슷한 문서를 찾을 수 있게 해준다. 이것이 '의미 기반 검색'의 핵심이다.

모델 선정 경위:
CLAUDE.md 기준 모델은 BAAI/bge-m3(1024차원, 접두사 불필요)였으나,
fastembed(PyPI 최신 0.8.0 기준) 지원 모델 목록에 bge-m3가 없어
다국어 지원 모델인 intfloat/multilingual-e5-large(1024차원)로 대체했다.
(app/config.py의 embedding_model 참고)

주의 - bge-m3와의 차이점:
multilingual-e5 계열은 검색 품질을 위해 텍스트 앞에 접두사를 붙이는 것을
권장한다: 검색 질문에는 "query: ", 저장할 문서(청크)에는 "passage: ".
이 접두사를 빠뜨리면 검색 정확도가 떨어질 수 있으니, 청크 저장 시와
질문 임베딩 시 각각 다른 접두사를 적용해야 한다 (1-B에서 질문 임베딩 시에도 동일 규칙 적용).

모델은 첫 실행 시 EMBEDDING_CACHE_DIR로 다운로드된다 (약 1~2GB).
"""

from __future__ import annotations


def embed_passages(texts: list[str]) -> list[list[float]]:
    """청크(문서) 텍스트들을 벡터로 변환한다. 내부적으로 "passage: " 접두사를 붙인다.

    질문 임베딩(embed_query, "query: " 접두사)은 1-B(검색) 단계에서 추가한다.
    지금은 업로드->저장 파이프라인(1-A)만 다루므로 미리 만들지 않는다.
    """
    raise NotImplementedError("1-A 구현 예정: fastembed TextEmbedding 적용")
