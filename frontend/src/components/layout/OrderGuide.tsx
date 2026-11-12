import { useEffect, useRef } from 'react';
import { BrandLogo } from '../BrandLogo';

interface OrderGuideProps {
  title: string;
  description: string;
  voiceDescription?: string;
  onHome?: () => void;
  onBack?: () => void;
}

export function OrderGuide({ title, description, voiceDescription, onHome, onBack }: OrderGuideProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  // 주문 단계가 바뀌면 보조기술과 키보드 사용자도 새 안내부터 읽는다.
  useEffect(() => { headingRef.current?.focus(); }, [title]);

  return (
    <header className="order-guide">
      <div className="order-guide__brand">
        <BrandLogo compact />
        <div className="order-guide__navigation">
          <button type="button" className="text-button order-guide__back" disabled={!onBack} onClick={onBack}><span aria-hidden="true">〈</span> 이전</button>
          <button type="button" className="text-button" disabled={!onHome} onClick={onHome}>처음으로</button>
        </div>
      </div>
      <div className="order-guide__text">
        <h1 ref={headingRef} tabIndex={-1}>{title}</h1>
        <p>{description}</p>
        {voiceDescription && <p className="order-guide__voice">{voiceDescription}</p>}
      </div>
    </header>
  );
}
