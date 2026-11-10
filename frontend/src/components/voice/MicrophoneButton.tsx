import { useId } from 'react';
import { MicrophoneIcon } from '../MicrophoneIcon';
import './MicrophoneButton.css';

type MicrophoneButtonProps = {
  label?: string;
  describedBy?: string;
} & (
  | { disabled: true; helpText?: string; onClick?: never }
  | { disabled?: false; helpText?: string; onClick: () => void }
);

export function MicrophoneButton({
  label = '음성 주문', disabled = false, helpText, onClick, describedBy,
}: MicrophoneButtonProps) {
  const helpId = useId();

  return (
    <div className="microphone-control">
      <button type="button" className="microphone-button" disabled={disabled}
        aria-describedby={[describedBy, helpText ? helpId : undefined].filter(Boolean).join(' ') || undefined} onClick={onClick}>
        <MicrophoneIcon /><span>{label}</span>
      </button>
      {helpText && <span id={helpId} role="status">{helpText}</span>}
    </div>
  );
}
