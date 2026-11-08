import type { ReactNode } from 'react';

interface OrderFooterProps {
  status: string;
  microphone?: ReactNode;
}

export function OrderFooter({ status, microphone }: OrderFooterProps) {
  return (
    <footer className="order-footer">
      <p className="order-footer__status" role="status">{status}</p>
      {microphone}
    </footer>
  );
}
