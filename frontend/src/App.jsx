import { useEffect, useState } from 'react'

function App() {
  // 골격 단계 확인용: 백엔드 /api/health가 Vite 프록시를 통해 응답하는지만 확인한다.
  // 업로드 UI/검색 UI는 각 단계(1-A/1-B)에서 실제로 구현한다.
  const [health, setHealth] = useState('확인 중...')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setHealth(data.status))
      .catch(() => setHealth('연결 실패 (백엔드가 켜져 있는지 확인하세요)'))
  }, [])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-2">
      <h1 className="text-2xl font-medium">글로벌 ICT 동향 리포트 조회</h1>
      <p className="text-gray-500">백엔드 상태: {health}</p>
    </div>
  )
}

export default App
