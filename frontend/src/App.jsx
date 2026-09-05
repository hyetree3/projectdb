import { useEffect, useState } from 'react'

const TOTAL_EXPECTED = 11 // 이번 테스트에서 업로드할 전체 파일 수 (참고용 표시)

function DocumentRow({ doc }) {
  const [expanded, setExpanded] = useState(false)
  const [chunks, setChunks] = useState(null) // null = 아직 안 불러옴

  const toggle = () => {
    const next = !expanded
    setExpanded(next)
    if (next && chunks === null) {
      fetch(`/api/documents/${encodeURIComponent(doc.document_id)}/chunks`)
        .then((res) => res.json())
        .then((data) => setChunks(data))
        .catch(() => setChunks([]))
    }
  }

  return (
    <li className="border-b border-gray-200 last:border-b-0">
      <button
        type="button"
        onClick={toggle}
        className="w-full px-3 py-2 flex justify-between text-sm text-left hover:bg-gray-50"
      >
        <span>
          {expanded ? '▾' : '▸'} {doc.source}
        </span>
        <span className="text-gray-500">청크 {doc.chunk_count}개</span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 bg-gray-50">
          {chunks === null && <p className="text-xs text-gray-400">불러오는 중...</p>}
          {chunks !== null && chunks.length === 0 && (
            <p className="text-xs text-gray-400">청크가 없습니다.</p>
          )}
          <ul className="space-y-2">
            {chunks?.map((chunk) => (
              <li key={chunk.chunk_id} className="text-xs bg-white border border-gray-200 rounded p-2">
                <div className="text-gray-500 mb-1">
                  {chunk.chunk_id} · {chunk.page}페이지 · {chunk.section}
                </div>
                {/* 청크 원문: 상위 제목 prefix가 포함된 실제 저장 텍스트 그대로 */}
                <pre className="whitespace-pre-wrap font-sans mb-2">{chunk.text}</pre>
                {/* 임베딩 결과 확인용: 1024차원 전체 대신 앞 8개 값만 미리보기로 표시 */}
                <div className="text-gray-400">
                  임베딩({chunk.embedding_dim}차원): [{chunk.embedding_preview.join(', ')}, ...]
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  )
}

function SearchPanel() {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('hybrid')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState(null) // { results, message }

  const runSearch = (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: 5, mode }),
    })
      .then((res) => res.json())
      .then((data) => setResponse(data))
      .catch(() => setResponse({ results: [], message: '검색 중 오류가 발생했습니다.' }))
      .finally(() => setLoading(false))
  }

  return (
    <div className="w-full max-w-xl">
      <h2 className="text-lg font-medium mb-2">검색</h2>

      {/* 검색 방식 비교용 - 벡터(의미)/키워드(BM25)/하이브리드(RRF 결합) */}
      <div className="flex gap-4 mb-2 text-sm">
        {[
          { value: 'vector', label: '벡터(의미)' },
          { value: 'keyword', label: '키워드(BM25)' },
          { value: 'hybrid', label: '하이브리드' },
        ].map((opt) => (
          <label key={opt.value} className="flex items-center gap-1">
            <input
              type="radio"
              name="search-mode"
              value={opt.value}
              checked={mode === opt.value}
              onChange={() => setMode(opt.value)}
            />
            {opt.label}
          </label>
        ))}
      </div>

      <form onSubmit={runSearch} className="flex gap-2 mb-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="질문을 입력하세요 (예: 오픈뱅킹 개인정보 보호)"
          className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 text-sm bg-gray-800 text-white rounded disabled:opacity-50"
        >
          {loading ? '검색 중...' : '검색'}
        </button>
      </form>

      {response && response.results.length === 0 && (
        <p className="text-sm text-gray-500">{response.message}</p>
      )}

      {response && response.results.length > 0 && (
        <ul className="space-y-2">
          {response.results.map((r, i) => (
            <li key={i} className="text-sm border border-gray-200 rounded p-3">
              <div className="text-gray-500 text-xs mb-1">
                {r.source} · {r.page}페이지 · {r.section}
                {r.distance != null && ` · distance ${r.distance.toFixed(4)}`}
                {r.bm25_score != null && ` · bm25 ${r.bm25_score.toFixed(4)}`}
                {r.rrf_score != null && ` · rrf ${r.rrf_score.toFixed(4)}`}
              </div>
              <p>
                {r.sentences.length > 0
                  ? r.sentences.map((s, si) => (
                      <span
                        key={si}
                        className={s.is_best ? 'bg-yellow-200 rounded px-0.5' : undefined}
                        title={`유사도 ${s.similarity.toFixed(4)}`}
                      >
                        {s.text}{' '}
                      </span>
                    ))
                  : r.text}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function App() {
  const [health, setHealth] = useState('확인 중...')
  const [documents, setDocuments] = useState([])

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setHealth(data.status))
      .catch(() => setHealth('연결 실패 (백엔드가 켜져 있는지 확인하세요)'))
  }, [])

  useEffect(() => {
    const fetchDocuments = () => {
      fetch('/api/documents')
        .then((res) => res.json())
        .then((data) => setDocuments(data))
        .catch(() => {})
    }
    fetchDocuments()
    const interval = setInterval(fetchDocuments, 2000) // 2초마다 갱신해서 진행 상황을 실시간으로 확인
    return () => clearInterval(interval)
  }, [])

  const totalChunks = documents.reduce((sum, doc) => sum + doc.chunk_count, 0)

  return (
    <div className="min-h-screen flex flex-col items-center gap-8 py-10 px-4">
      <div className="text-center">
        <h1 className="text-2xl font-medium">글로벌 ICT 동향 리포트 조회</h1>
        <p className="text-gray-500">백엔드 상태: {health}</p>
      </div>

      <div className="w-full max-w-xl">
        <h2 className="text-lg font-medium mb-2">
          업로드 진행 현황 ({documents.length} / {TOTAL_EXPECTED}개 문서, 청크 {totalChunks}개)
        </h2>
        <p className="text-xs text-gray-400 mb-2">문서를 클릭하면 청크 원문과 임베딩 미리보기를 볼 수 있습니다.</p>
        <ul className="divide-y divide-gray-200 border border-gray-200 rounded">
          {documents.map((doc) => (
            <DocumentRow key={doc.document_id} doc={doc} />
          ))}
          {documents.length === 0 && (
            <li className="px-3 py-2 text-sm text-gray-400">아직 저장된 문서가 없습니다.</li>
          )}
        </ul>
      </div>

      <SearchPanel />
    </div>
  )
}

export default App
