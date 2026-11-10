from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.menus import MenuOption, Temperature

ServiceType = Literal["DINE_IN", "TAKEOUT"]


class OrderSelection(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    menu_id: str = Field(pattern=r"^[^\x00]+$")
    temperature: Temperature
    service_type: ServiceType


class OrderItem(OrderSelection):
    quantity: int = Field(default=1, ge=1, le=99)
    option_ids: list[Annotated[str, Field(pattern=r"^[a-z_]+:[a-z_]+$")]] = Field(default_factory=list, max_length=32)


class CreateOrderRequest(OrderSelection):
    items: list[OrderItem] | None = Field(default=None, min_length=1, max_length=20)
    request_id: str = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
    option_ids: list[Annotated[str, Field(pattern=r"^[a-z_]+:[a-z_]+$")]] = Field(default_factory=list, max_length=32)


class OrderResponse(OrderSelection):
    items: list[dict] = Field(default_factory=list)
    order_id: str
    order_number: str
    menu_name: str
    quantity: Literal[1]
    total_price_krw: int = Field(ge=0)
    selected_options: list[MenuOption] = Field(default_factory=list)
    created_at: AwareDatetime
