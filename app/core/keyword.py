"""키워드 기반 검색 (BM25). 1-C.

BM25란?
벡터 검색이 "의미"가 비슷한 문서를 찾는다면, BM25는 "단어"가 얼마나 겹치는지로
점수를 매기는 전통적인 키워드 검색 알고리즘이다(TF-IDF의 개선판). 예를 들어
질문에 등장하는 특정 고유명사·법률명·숫자처럼 의미 임베딩이 잘 구분 못 하는
정확한 단어 일치가 중요한 경우 벡터 검색보다 강할 수 있다. 반대로 동의어나
문맥 이해에는 약하다 - 그래서 두 방식을 합치는 것(하이브리드)이 유용하다.

토큰화 한계:
한글은 조사가 단어에 붙어 있어(예: "오픈뱅킹은", "오픈뱅킹이") 단순 공백 분리로는
같은 단어를 다른 토큰으로 셀 수 있다. 정확한 형태소 분석기(예: 별도 라이브러리)를
쓰면 개선되지만, 이 프로젝트는 새 의존성을 최소화하기 위해 공백 기준 분리를
기준선으로 삼는다. 키워드 검색 품질이 낮다고 느껴지면 가장 먼저 의심할 지점이다.

BM25 인덱스는 검색할 때마다 전체 청크로 새로 만든다 - 데이터량이 작아(수백 개
청크) 매번 다시 만들어도 충분히 빠르고, 업로드 직후 바로 최신 상태가 반영된다.
"""

from __future__ import annotations

from rank_bm25 import BM25Okapi

from app.core import store as store_core


def _tokenize(text: str) -> list[str]:
    return text.split()


def bm25_search(persist_dir: str, query: str, top_k: int) -> list[dict]:
    """질문과 키워드가 많이 겹치는 청크 top_k개를 BM25 점수 순으로 반환한다.

    Returns:
        [{"text": ..., "bm25_score": ..., **metadata}, ...] - 점수가 클수록 유사.
    """
    chunks = store_core.get_all_chunks(persist_dir)
    if not chunks:
        return []

    tokenized_corpus = [_tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(_tokenize(query))

    ranked = sorted(zip(chunks, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    return [{**chunk, "bm25_score": float(score)} for chunk, score in ranked[:top_k] if score > 0]
