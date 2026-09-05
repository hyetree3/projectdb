"""추출된 텍스트를 임베딩하기 좋은 크기로 나눈다.

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

페이지 단위로 나눠서 청킹하는 이유:
메타데이터의 page 필드가 청크마다 정확한 페이지 번호를 가리켜야 출처 표시가
가능하다. 문서 전체를 하나로 이어붙여 청킹하면 청크가 여러 페이지에 걸치게 되어
page 번호를 하나로 특정할 수 없다. 대신 페이지가 바뀌는 경계에서 문맥이 약간
끊길 수 있다는 트레이드오프가 있다.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.extract import ExtractedPage


@dataclass
class Chunk:
    chunk_id: str
    text: str  # 상위 제목 prefix가 포함된 최종 텍스트
    page: int
    section: str


def chunk_pages(
    pages: list[ExtractedPage],
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
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    chunks: list[Chunk] = []
    for extracted_page in pages:
        if not extracted_page.text.strip():
            continue  # 빈 페이지(스캔 누락, 표지 등)는 청크를 만들지 않는다.

        pieces = splitter.split_text(extracted_page.text)
        for index, piece in enumerate(pieces):
            prefixed_text = f"[{extracted_page.section}] {piece}"
            chunks.append(
                Chunk(
                    chunk_id=f"p{extracted_page.page}_c{index}",
                    text=prefixed_text,
                    page=extracted_page.page,
                    section=extracted_page.section,
                )
            )

    return chunks
