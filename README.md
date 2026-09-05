# 글로벌 ICT 동향 리포트 조회

한국어 PDF를 업로드해 의미 기반(벡터)으로 검색하는 웹 앱. **벡터 DB 학습용 실습 프로젝트.**

자세한 설계 원칙과 규칙은 [CLAUDE.md](./CLAUDE.md) 참고.

## 현재 진행 상태

| | 목표 | 상태 |
|---|---|---|
| 1-A | PDF 업로드 → 텍스트 추출 → 청킹 → 임베딩 → ChromaDB 저장 | ✅ 완료 |
| 1-B | 웹 UI에서 유사도(벡터) 검색 + 결과 내 문장 하이라이트 | ✅ 완료 |
| 1-C | 키워드(BM25) 검색 + 하이브리드(RRF) 결합 | ✅ 완료 |
| 2차 | ChromaDB → PostgreSQL + pgvector 교체 | 예정 |

## 요구 사항

- Python 3.12 (`.python-version`으로 고정, `uv`가 자동 설치)
- Node.js (`.mise.toml` 참고)
- [uv](https://docs.astral.sh/uv/) — Python 패키지/실행 관리
- npm

## 처음 실행하기

```bash
# 1. 저장소 루트에서 Python 의존성 설치 (최초 1회, chromadb/fastembed 등 다운로드)
uv sync

# 2. 프론트엔드 의존성 설치 (최초 1회)
cd frontend && npm install && cd ..

# 3. .env 파일이 없으면 예시를 복사
cp .env.example .env
```

`EMBEDDING_MODEL`(기본값 `intfloat/multilingual-e5-large`)은 첫 임베딩 요청 시
`EMBEDDING_CACHE_DIR`(기본 `./data/model_cache`)로 자동 다운로드된다 (약 1GB,
몇 분 소요). 최초 업로드/검색이 느린 건 이 다운로드 때문이다.

## 서버 실행 (Git Bash 필요)

이 프로젝트는 Windows PowerShell에서 `.sh` 스크립트를 직접 실행할 수 없다.
Git Bash로 실행해야 한다.

```bash
# 시작 (백엔드 :8000 + 프론트엔드 :5173)
./scripts/dev.sh start

# 상태 확인 (실행 중인 포트 표시)
./scripts/dev.sh status

# 종료
./scripts/dev.sh stop
```

PowerShell에서 실행하려면:
```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/dev.sh start
```
(Git 설치 경로는 사용자 계정마다 다를 수 있다 - `Get-Command git` 출력의 상위 폴더에서 `bin\bash.exe`를 찾으면 된다.)

브라우저에서 **http://localhost:5173** 접속. 백엔드(:8000)는 프론트엔드의
Vite 프록시를 통해 `/api/*` 요청으로 자동 연결된다 (CORS 설정 불필요).

## 사용 방법

### 1. PDF 업로드

현재 화면은 별도 업로드 버튼 UI 없이 API로 업로드한다 (프론트엔드에는
업로드 진행 현황만 표시됨). PDF를 올리려면:

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@경로/파일명.pdf;type=application/pdf"
```

응답으로 `job_id`가 즉시 돌아오고, 실제 추출·청킹·임베딩·저장은 백그라운드에서
진행된다. 웹 화면(`업로드 진행 현황`)이 2초마다 자동 갱신되며 완료 여부를 보여준다.
문서를 클릭하면 청크 원문과 임베딩(1024차원) 미리보기를 확인할 수 있다.

같은 파일명을 다시 업로드하면 기존 청크를 덮어쓴다(upsert).

### 2. 검색

화면 하단 "검색" 영역에서 질문을 입력하고 검색 방식을 고른다.

| 방식 | 원리 | 특징 |
|---|---|---|
| 벡터(의미) | 질문을 임베딩해 코사인 거리로 유사한 청크를 찾음 | 동의어·문맥 이해에 강함 |
| 키워드(BM25) | 질문과 단어가 얼마나 겹치는지 점수화 | 고유명사·정확한 단어 일치에 강함 |
| 하이브리드 | 위 둘을 RRF(Reciprocal Rank Fusion)로 결합 | 두 방식의 장점을 함께 반영 |

검색 결과에는 항상 출처(파일명·페이지·섹션)가 함께 표시되며, 청크 안에서
질문과 가장 유사한 문장이 노란색으로 하이라이트된다. 가장 유사한 결과조차
너무 멀면(`SEARCH_DISTANCE_THRESHOLD`, 기본 0.5) "관련 문서를 찾을 수 없습니다"로 응답한다.

## 프로젝트 구조

```
app/
  main.py              FastAPI 진입점 (라우터 등록)
  config.py            환경변수 기반 설정 (.env)
  jobs.py              업로드 작업 진행 상태 메모리 저장소
  api/
    upload.py          업로드, 작업 상태 조회(SSE), 문서/청크 목록 API
    search.py          벡터/키워드/하이브리드 검색 API
  core/
    extract.py         PDF 텍스트 추출 (레이아웃/기본 모드 비교)
    chunk.py            RecursiveCharacterTextSplitter 청킹
    embed.py            fastembed 임베딩 (passage/query 접두사)
    store.py            ChromaDB 래퍼 (chromadb를 import하는 유일한 파일)
    keyword.py          BM25 키워드 검색
  models/
    schemas.py          API 요청/응답 Pydantic 모델
frontend/
  src/App.jsx           업로드 현황 + 검색 UI (React, useState만 사용)
scripts/
  dev.sh                서버 start/stop/status 관리 스크립트
data/                   (.gitignore) 업로드 원본, ChromaDB, 임베딩 모델 캐시
```

## 환경 변수 (`.env`)

`.env.example` 참고. 주요 값:

| 변수 | 기본값 | 설명 |
|---|---|---|
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB 저장 경로 |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-large` | 임베딩 모델 (1024차원) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `600` / `100` | 청킹 기준선 |
| `SEARCH_DISTANCE_THRESHOLD` | `0.5` | 검색 결과 채택 임계값 (cosine distance) |
| `SEARCH_TOP_K` | `5` | 검색 결과 기본 개수 |

## 알려진 제약

- `uv run uvicorn --reload`가 Windows에서 파일 변경을 놓치는 경우가 있다.
  백엔드 코드를 수정했는데 반영이 안 되면 `./scripts/dev.sh stop && ./scripts/dev.sh start`로
  완전히 재시작할 것.
- BM25 토큰화는 공백 기준 분리라 한국어 조사가 붙은 단어를 다르게 셀 수 있다
  (예: "오픈뱅킹은"과 "오픈뱅킹이"를 다른 단어로 취급). 형태소 분석기는 아직 도입하지 않았다.
- 업로드 진행 상태(SSE, `/api/jobs/{job_id}/events`)는 프로세스 재시작 시 초기화된다.
