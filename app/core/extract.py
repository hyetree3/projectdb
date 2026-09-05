"""PDF에서 텍스트를 추출한다. (1-A 실제 구현 예정 - 현재는 골격만)

한국어 처리의 가장 큰 함정:
PowerPoint로 만든 PDF는 pypdf 기본 추출 모드에서 단어 사이 띄어쓰기가 사라진다.
예) "오픈뱅킹 데이터 이동성을 활용해" -> "오픈뱅킹데이터이동성을활용해"

대응 방법 (구현 시 반드시 적용):
1. pypdf의 extract_text(extraction_mode="layout")과 기본 모드를 "둘 다" 시도한다.
2. 각 결과에서 (한글 어절 수 / 한글 글자 수) 비율을 계산해 더 높은 쪽을 채택한다.
   - 어절 수는 공백으로 분리한 한글 토큰 개수, 글자 수는 한글 음절 총 개수.
   - 띄어쓰기가 사라진 텍스트는 이 비율이 비정상적으로 낮게(어절이 거대해짐) 나온다.
3. 추출 직후 결과를 로그/파일로 남겨 "눈으로 확인하는 단계"를 반드시 거친다.
   여기서 잡지 못하면 이후 청킹·임베딩 단계에서는 원인을 찾을 수 없다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractedPage:
    page: int
    text: str
    section: str  # 이 페이지가 속한 상위 제목 (청킹 시 prefix로 사용)


def extract_text(pdf_path: Path) -> list[ExtractedPage]:
    """PDF 파일에서 페이지별 텍스트를 추출한다.

    Args:
        pdf_path: 추출할 PDF 파일 경로 (파일명은 이미 NFC 정규화되어 있어야 함).

    Returns:
        페이지별 ExtractedPage 목록.
    """
    raise NotImplementedError("1-A 구현 예정: pypdf 레이아웃/기본 모드 비교 로직")
