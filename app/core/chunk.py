"""추출된 텍스트를 임베딩하기 좋은 크기로 나눈다. (1-A 실제 구현 예정 - 현재는 골격만)

청킹(chunking)이란?
임베딩 모델과 벡터 검색은 문서 전체가 아니라 작은 단위(청크)로 쪼개서 다뤄야
질문과 관련된 부분만 정확히 찾아낼 수 있다. 너무 크면 무관한 내용이 섞여
검색 정확도가 떨어지고, 너무 작으면 문맥이 끊겨 의미를 잃는다.

기준선: 600자 / overlap 100자 (langchain-text-splitters의 RecursiveCharacterTextSplitter 사용).
- overlap(겹침)을 두는 이유: 청크 경계에서 문장이 잘리면 그 경계에 걸친 의미를
  어느 쪽 청크도 온전히 담지 못하게 된다. 겹침 구간이 이를 보완한다.
- 검색 결과가 이상하면 이 값(600/100)을 가장 먼저 조정한다.

각 청크 앞에는 상위 제목(section)을 prefix로 붙인다 - 청크만 봐서는 문맥을
알 수 없는 경우(표, 목록 등)에도 어느 섹션 소속인지 임베딩에 반영되도록 하기 위함.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    text: str  # 상위 제목 prefix가 포함된 최종 텍스트
    page: int
    section: str


def chunk_pages(
    pages: list,  # list[ExtractedPage] - 순환 import 방지를 위해 타입은 실제 구현 시 지정
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """페이지별 텍스트를 RecursiveCharacterTextSplitter로 청킹한다.

    Args:
        pages: extract.extract_text()의 결과.
        chunk_size: 청크 최대 길이(문자 수). 기준선 600.
        chunk_overlap: 인접 청크 간 겹치는 길이(문자 수). 기준선 100.

    Returns:
        청크 목록. 각 청크 텍스트 앞에는 소속 section이 prefix로 붙어 있다.
    """
    raise NotImplementedError("1-A 구현 예정: RecursiveCharacterTextSplitter 적용")
