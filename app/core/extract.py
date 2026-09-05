"""PDF에서 텍스트를 추출한다.

한국어 처리의 가장 큰 함정:
PowerPoint로 만든 PDF는 pypdf 기본 추출 모드에서 단어 사이 띄어쓰기가 사라진다.
예) "오픈뱅킹 데이터 이동성을 활용해" -> "오픈뱅킹데이터이동성을활용해"

대응 방법:
1. pypdf의 extract_text(extraction_mode="layout")과 기본 모드를 "둘 다" 시도한다.
2. 각 결과에서 (한글 어절 수 / 한글 글자 수) 비율을 계산해 더 높은 쪽을 채택한다.
   - 어절 수는 공백으로 분리한 토큰 중 한글이 포함된 것의 개수, 글자 수는 한글 음절 총 개수.
   - 띄어쓰기가 사라지면 어절 하나가 비정상적으로 길어지므로 이 비율이 낮게 나온다.

섹션(상위 제목) 추출:
실제 리포트(글로벌 ICT 월간동향리포트)를 확인한 결과, 소제목은 "▶"로 시작하는
줄로 표시된다 (예: "▶은행의 데이터기반 혁신: 오픈뱅킹의 현황"). 이 마커를 기준으로
현재 섹션을 추적하고, 마커가 없는 페이지는 직전 섹션을 그대로 이어받는다.
주의: 이 마커는 이 리포트 시리즈에서 관찰된 값이며, 다른 형식의 PDF에서는
소제목 규칙이 다를 수 있다 - 새로운 문서 형식을 다룰 때는 재확인이 필요하다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

_HANGUL_RE = re.compile(r"[가-힣]")
_SECTION_MARKER = "▶"
_DEFAULT_SECTION = "머리말"


@dataclass
class ExtractedPage:
    page: int
    text: str
    section: str  # 이 페이지 본문이 속한 상위 제목 (청킹 시 prefix로 사용)


def _hangul_word_ratio(text: str) -> float:
    """한글 어절 수 / 한글 글자 수. 값이 낮을수록 단어 사이 띄어쓰기가 소실된 것으로 본다."""
    hangul_char_count = len(_HANGUL_RE.findall(text))
    if hangul_char_count == 0:
        return 0.0
    word_count = sum(1 for token in text.split() if _HANGUL_RE.search(token))
    return word_count / hangul_char_count


def _pick_better_text(default_text: str, layout_text: str) -> str:
    """기본/레이아웃 두 추출 결과 중 한글 어절 비율이 더 높은(=띄어쓰기가 더 온전한) 쪽을 선택한다."""
    if _hangul_word_ratio(layout_text) > _hangul_word_ratio(default_text):
        return layout_text
    return default_text


def _find_section_heading(text: str) -> str | None:
    """텍스트에서 '▶'로 시작하는 첫 소제목 줄을 찾는다. 없으면 None."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_SECTION_MARKER):
            heading = stripped.lstrip(_SECTION_MARKER).strip()
            if heading:
                return heading
    return None


def extract_text(pdf_path: Path) -> list[ExtractedPage]:
    """PDF 파일에서 페이지별 텍스트를 추출한다.

    Args:
        pdf_path: 추출할 PDF 파일 경로 (파일명은 이미 NFC 정규화되어 있어야 함).

    Returns:
        페이지별 ExtractedPage 목록.

    Raises:
        ValueError: PDF를 읽을 수 없거나 손상된 경우.
    """
    try:
        reader = PdfReader(str(pdf_path))
    except (PdfReadError, OSError) as exc:
        raise ValueError(f"PDF를 읽을 수 없습니다: {exc}") from exc

    pages: list[ExtractedPage] = []
    current_section = _DEFAULT_SECTION

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            default_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - pypdf 내부 파싱 실패 시 빈 텍스트로 대체
            default_text = ""
        try:
            layout_text = page.extract_text(extraction_mode="layout") or ""
        except Exception:  # noqa: BLE001
            layout_text = ""

        text = _pick_better_text(default_text, layout_text)

        heading = _find_section_heading(text)
        if heading:
            current_section = heading

        pages.append(ExtractedPage(page=page_number, text=text, section=current_section))

    return pages
