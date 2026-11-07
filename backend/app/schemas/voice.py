from pydantic import BaseModel


class VoiceAudioResponse(BaseModel):
    mime_type: str
    container: str
    codec: str
    duration_seconds: float
    size_bytes: int
    source_sample_rate_hz: int
    source_channels: int
    sample_rate_hz: int
    channels: int
