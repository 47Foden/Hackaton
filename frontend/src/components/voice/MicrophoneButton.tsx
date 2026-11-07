import { useId } from 'react';
import { MicrophoneIcon } from '../MicrophoneIcon';
import './MicrophoneButton.css';

type MicrophoneButtonProps = {
  label?: string;
} & (
  | { disabled: true; helpText: string; onClick?: never }
  | { disabled?: false; helpText?: string; onClick: () => void }
);

export function MicrophoneButton({
  label = '음성 주문', disabled = false, helpText, onClick,
}: MicrophoneButtonProps) {
  const helpId = useId();

  return (
    <div className="microphone-control">
      <button type="button" className="microphone-button" disabled={disabled}
        aria-describedby={helpText ? helpId : undefined} onClick={onClick}>
        <MicrophoneIcon /><span>{label}</span>
      </button>
      {helpText && <span id={helpId}>{helpText}</span>}
    </div>
  );
}
