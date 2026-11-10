from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.menus import Temperature
from app.schemas.orders import ServiceType

VoiceStage = Literal["menu", "temperature", "service_type", "recommendations", "menu_confirmation", "review"]
MenuId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,64}$")]
RetryReason = Literal["EMPTY_TRANSCRIPT", "UNRECOGNIZED", "MENU_UNAVAILABLE", "INVALID_OPTION", "OUTSIDE_CANDIDATES"]


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


class SelectMenu(BaseModel):
    type: Literal["select_menu"] = "select_menu"
    menu_id: MenuId


class SetTemperature(BaseModel):
    type: Literal["set_temperature"] = "set_temperature"
    temperature: Temperature


class SetServiceType(BaseModel):
    type: Literal["set_service_type"] = "set_service_type"
    service_type: ServiceType


class Retry(BaseModel):
    type: Literal["retry"] = "retry"
    reason: RetryReason


class DirectCandidate(BaseModel):
    menu_id: MenuId
    temperature: Temperature
    reason: str


class DirectRecommendation(BaseModel):
    type: Literal['direct_recommendation'] = 'direct_recommendation'
    status: Literal['recommend', 'clarify', 'insufficient_data']
    recommendations: list[DirectCandidate] = Field(max_length=1)
    questions: list[str] = Field(max_length=1)
    missing_information: list[str]
    engine: Literal['llm-direct'] = 'llm-direct'


class RestartRecommendation(BaseModel):
    type: Literal["restart_recommendation"] = "restart_recommendation"


class Confirm(BaseModel):
    type: Literal["confirm"] = "confirm"


VoiceAction = Annotated[DirectRecommendation | RestartRecommendation | Confirm | SelectMenu | SetTemperature | SetServiceType | Retry, Field(discriminator="type")]


class VoiceInterpretResponse(BaseModel):
    transcript: str
    action: VoiceAction
