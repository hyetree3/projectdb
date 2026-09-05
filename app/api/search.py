"""검색 API. 벡터 유사도 검색(1-B) + 키워드(BM25) 검색과 하이브리드 결합(1-C).

흐름 (모드에 따라 다름):
- vector: 질문 -> embed_query() -> ChromaDB 코사인 거리 검색.
- keyword: 질문 -> BM25 점수 계산 (app.core.keyword) -> 점수 높은 순.
- hybrid: 위 둘을 각각 넉넉히 뽑은 뒤 RRF(Reciprocal Rank Fusion)로 순위를 합친다.

문장 단위 하이라이트:
청크(수백 자) 전체가 질문과 얼마나 비슷한지는 이미 알지만, "청크 중 정확히 어느
문장이" 가장 가까운지는 별도로 계산해야 한다. 방법: 결과 청크를 문장으로 쪼갠 뒤
그 문장들을 다시 임베딩해서 질문 벡터와 코사인 유사도를 구하고, 가장 높은 문장을
표시한다. 검색 결과 개수 x 문장 수만큼 추가 임베딩이 필요해 정확하지만 느리다.

이 라우트는 async가 아닌 일반 함수(def)로 선언한다. ChromaDB 조회(store_core)가
동기 API라서, 만약 async def 안에서 직접 호출하면 이벤트 루프가 멈춘다.
FastAPI/Starlette는 동기 라우트를 자동으로 스레드풀에서 실행해주므로 이걸로 충분하다.
"""

from __future__ import annotations

import math
import re

from fastapi import APIRouter

from app.config import settings
from app.core import embed as embed_core
from app.core import keyword as keyword_core
from app.core import store as store_core
from app.models.schemas import SearchRequest, SearchResponse, SearchResultItem, SentenceMatch

router = APIRouter(prefix="/api", tags=["search"])

# 한국어 문장 분리 휴리스틱: '다./음./함./임./됨./까?/요?' 등 종결 어미 뒤 공백이나 줄바꿈을 경계로 본다.
# 완벽한 문장 분리기는 아니지만(예: 약어의 마침표), 이 프로젝트 데이터에는 충분하다.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# 하이브리드에서 결합 전 각 방식으로부터 얼마나 넉넉히 후보를 뽑을지.
_CANDIDATE_MULTIPLIER = 4
_MIN_CANDIDATES = 20

# RRF(Reciprocal Rank Fusion) 상수. 값이 클수록 상위/하위 순위 차이를 완만하게 만든다.
_RRF_K = 60


def _split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text)]
    return [s for s in sentences if len(s) >= 5]  # 너무 짧은 조각(제목 prefix 등)은 제외


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _attach_sentence_highlights(
    raw_results: list[dict], query_embedding: list[float]
) -> list[list[SentenceMatch]]:
    """결과별 문장을 한 번에 배치 임베딩해서 하이라이트를 계산한다."""
    per_result_sentences = [_split_sentences(item["text"]) for item in raw_results]

    all_sentences = [s for sentences in per_result_sentences for s in sentences]
    if not all_sentences:
        return [[] for _ in raw_results]

    all_embeddings = embed_core.embed_passages(all_sentences)

    highlights: list[list[SentenceMatch]] = []
    cursor = 0
    for sentences in per_result_sentences:
        count = len(sentences)
        embeddings = all_embeddings[cursor : cursor + count]
        cursor += count

        similarities = [_cosine_similarity(query_embedding, emb) for emb in embeddings]
        best_index = similarities.index(max(similarities)) if similarities else -1

        highlights.append(
            [
                SentenceMatch(text=sentence, similarity=sim, is_best=(i == best_index))
                for i, (sentence, sim) in enumerate(zip(sentences, similarities, strict=True))
            ]
        )

    return highlights


def _chunk_key(item: dict) -> tuple[str, str]:
    return (item["document_id"], item["chunk_id"])


def _reciprocal_rank_fusion(vector_results: list[dict], keyword_results: list[dict]) -> list[dict]:
    """벡터 검색과 BM25 검색의 순위를 합쳐 하나의 순위로 만든다.

    두 방식은 점수 스케일이 완전히 달라(distance는 0~2, BM25는 0~수십) 점수를
    그대로 더할 수 없다. RRF는 점수 대신 "순위"만 이용해 이 문제를 피한다:
    각 결과의 1/(k+순위)를 두 리스트에 걸쳐 더한다. k(=60)는 순위 차이를
    완만하게 만드는 관용적인 상수다.
    """
    merged: dict[tuple[str, str], dict] = {}
    rrf_scores: dict[tuple[str, str], float] = {}

    for rank, item in enumerate(vector_results):
        key = _chunk_key(item)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (_RRF_K + rank + 1)
        merged.setdefault(key, dict(item))

    for rank, item in enumerate(keyword_results):
        key = _chunk_key(item)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (_RRF_K + rank + 1)
        if key in merged:
            merged[key]["bm25_score"] = item.get("bm25_score")
        else:
            merged[key] = dict(item)

    ordered_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)
    results = []
    for key in ordered_keys:
        item = merged[key]
        item["rrf_score"] = rrf_scores[key]
        results.append(item)
    return results


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    query = request.query.strip()
    if not query:
        return SearchResponse(results=[], message="검색어를 입력하세요.")

    # 문장 하이라이트는 모드와 무관하게 항상 필요하므로 질문 임베딩은 매번 계산한다.
    query_embedding = embed_core.embed_query(query)
    candidate_k = max(request.top_k * _CANDIDATE_MULTIPLIER, _MIN_CANDIDATES)

    vector_results: list[dict] = []
    keyword_results: list[dict] = []

    if request.mode in ("vector", "hybrid"):
        vector_results = store_core.query_similar(
            settings.chroma_persist_dir,
            query_embedding=query_embedding,
            top_k=candidate_k if request.mode == "hybrid" else request.top_k,
        )

    if request.mode in ("keyword", "hybrid"):
        keyword_results = keyword_core.bm25_search(
            settings.chroma_persist_dir,
            query=query,
            top_k=candidate_k if request.mode == "hybrid" else request.top_k,
        )

    # distance는 작을수록 유사하다. 벡터 검색의 최상위 결과조차 임계값보다 멀면
    # 관련성이 낮다고 판단한다. vector 모드는 그걸로 바로 "결과 없음"이지만,
    # hybrid 모드는 키워드 쪽에서라도 뭔가 찾았으면 그 결과를 보여준다.
    vector_is_weak = not vector_results or vector_results[0]["distance"] > settings.search_distance_threshold

    if request.mode == "vector" and vector_is_weak:
        return SearchResponse(results=[], message="관련 문서를 찾을 수 없습니다.")

    if request.mode == "hybrid" and vector_is_weak and not keyword_results:
        return SearchResponse(results=[], message="관련 문서를 찾을 수 없습니다.")

    if request.mode == "vector":
        raw_results = vector_results[: request.top_k]
    elif request.mode == "keyword":
        raw_results = keyword_results[: request.top_k]
    else:
        raw_results = _reciprocal_rank_fusion(vector_results, keyword_results)[: request.top_k]

    if not raw_results:
        return SearchResponse(results=[], message="관련 문서를 찾을 수 없습니다.")

    sentence_highlights = _attach_sentence_highlights(raw_results, query_embedding)

    results = [
        SearchResultItem(
            text=item["text"],
            source=item["source"],
            page=item["page"],
            section=item["section"],
            sentences=sentences,
            distance=item.get("distance"),
            bm25_score=item.get("bm25_score"),
            rrf_score=item.get("rrf_score"),
        )
        for item, sentences in zip(raw_results, sentence_highlights, strict=True)
    ]
    return SearchResponse(results=results)
