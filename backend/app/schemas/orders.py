from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.menus import Temperature

ServiceType = Literal["DINE_IN", "TAKEOUT"]


class OrderSelection(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    menu_id: str = Field(pattern=r"^[^\x00]+$")
    temperature: Temperature
    service_type: ServiceType


class CreateOrderRequest(OrderSelection):
    request_id: str = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class OrderResponse(OrderSelection):
    order_id: str
    order_number: str
    menu_name: str
    quantity: Literal[1]
    total_price_krw: int = Field(ge=0)
    created_at: AwareDatetime
