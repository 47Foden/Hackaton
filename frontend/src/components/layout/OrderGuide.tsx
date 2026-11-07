import { useEffect, useRef } from 'react';
import { BrandLogo } from '../BrandLogo';

interface OrderGuideProps {
  title: string;
  description: string;
  voiceDescription?: string;
  onHome: () => void;
}

export function OrderGuide({ title, description, voiceDescription, onHome }: OrderGuideProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  // 주문 단계가 바뀌면 보조기술과 키보드 사용자도 새 안내부터 읽는다.
  useEffect(() => { headingRef.current?.focus(); }, [title]);

  return (
    <header className="order-guide">
      <div className="order-guide__brand">
        <BrandLogo compact />
        <button type="button" className="text-button" onClick={onHome}>처음으로</button>
      </div>
      <div className="order-guide__text">
        <span className="eyebrow">MAKE YOUR DAY, MEGA</span>
        <h1 ref={headingRef} tabIndex={-1}>{title}</h1>
        <p>{description}</p>
        {voiceDescription && <p className="order-guide__voice">{voiceDescription}</p>}
      </div>
    </header>
  );
}
