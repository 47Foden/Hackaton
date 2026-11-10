import type { ReactNode } from 'react';

interface OrderFooterProps {
  status?: string;
  microphone?: ReactNode;
}

export function OrderFooter({ status, microphone }: OrderFooterProps) {
  if (!status && !microphone) return null;

  return (
    <footer className={status ? 'order-footer' : 'order-footer order-footer--controls-only'}>
      {status && <p className="order-footer__status" role="status">{status}</p>}
      {microphone}
    </footer>
  );
}
