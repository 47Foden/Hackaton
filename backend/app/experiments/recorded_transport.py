"""Bounded, no-retry transport journal. Never stores auth headers or loads keys."""
from datetime import datetime, timezone
import json

from app.services.llm_direct import DirectError


def recorded_transport(transport, path, max_calls):
    if max_calls < 1:
        raise DirectError('INVALID_CALL_LIMIT')
    if path.exists():
        raise DirectError('PREVIOUS_ATTEMPT_EXISTS')
    entries = []

    def persist():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(json.dumps({'max_calls': max_calls, 'retries': 0, 'calls': entries},
                                        ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)

    def send(payload):
        if len(entries) >= max_calls:
            raise DirectError('CALL_LIMIT_REACHED')
        request = dict(payload)
        if request['model'].startswith('gpt-5.4-mini'):
            request['reasoning'] = {'effort': 'none'}
        entry = {'call_number': len(entries)+1, 'state': 'started',
                 'started_at_utc': datetime.now(timezone.utc).isoformat()}
        entries.append(entry)
        persist()  # Record an attempt before network access, even if interrupted later.
        print(f"API call {len(entries)}/{max_calls} started.", flush=True)
        try:
            envelope = transport(request)
            entry.update(state='response_received', finished_at_utc=datetime.now(timezone.utc).isoformat(),
                         response={key: envelope.get(key) for key in ('status', 'model', 'usage', 'output', 'incomplete_details')})
            persist()
            return envelope
        except BaseException as error:
            entry.update(state='error_or_interrupted',
                         error_code=str(error) if isinstance(error, DirectError) else 'INTERRUPTED_OR_UNEXPECTED_ERROR')
            persist()
            raise

    return send
