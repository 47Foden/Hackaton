import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

function App() {
  const [status, setStatus] = useState('연결 확인 중…');

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/health', { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('서버 연결 실패');
        const data = await response.json();
        setStatus(data.database === 'connected'
          ? '프론트 · 백엔드 · DB 연결 완료'
          : 'DB 연결을 확인해 주세요.');
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setStatus('연결 실패: 백엔드 실행 상태를 확인해 주세요.');
      });
    return () => controller.abort();
  }, []);

  return (
    <main style={{ maxWidth: 720, margin: '80px auto', padding: 24, fontFamily: 'sans-serif', lineHeight: 1.7 }}>
      <h1>카페 키오스크 개발 환경</h1>
      <p role="status">{status}</p>
      <p>여기서 메뉴 화면과 음성 주문 기능을 만들어 나가면 됩니다.</p>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
