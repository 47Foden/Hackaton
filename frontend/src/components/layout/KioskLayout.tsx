import { useEffect, useRef, type ReactNode } from 'react';
import { OrderGuide } from './OrderGuide';
import { OrderFooter } from './OrderFooter';
import './KioskLayout.css';

interface KioskLayoutProps {
  title: string;
  description: string;
  voiceDescription?: string;
  status?: string;
  microphone?: ReactNode;
  children: ReactNode;
  onHome?: () => void;
}

/** 화면별 콘텐츠만 교체하고 안내와 하단 조작 영역은 유지한다. */
export function KioskLayout({
  title, description, voiceDescription, status, microphone, children, onHome,
}: KioskLayoutProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (contentRef.current) contentRef.current.scrollTop = 0;
  }, [title]);

  return (
    <main className="kiosk-layout">
      <OrderGuide title={title} description={description}
        voiceDescription={voiceDescription} onHome={onHome} />
      <div ref={contentRef} className="kiosk-layout__content">{children}</div>
      <OrderFooter status={status} microphone={microphone} />
    </main>
  );
}
