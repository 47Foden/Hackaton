import './MenuImage.css';
import { useState } from 'react';

interface MenuImageProps { src?: string; className?: string; }

function ImageContent({ src, className }: MenuImageProps) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return <span className={`${className ?? ''} menu-image-placeholder`}>사진 준비 중</span>;
  }
  return <img className={className} src={src} alt="" onError={() => setFailed(true)} />;
}

export function MenuImage(props: MenuImageProps) {
  // 이미지 주소가 바뀌면 이전 주소의 실패 상태도 초기화한다.
  return <ImageContent key={props.src ?? ''} {...props} />;
}
