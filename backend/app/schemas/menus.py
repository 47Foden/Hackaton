from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Temperature = Literal["HOT", "COLD"]
Category = Literal["커피", "티", "에이드", "논커피라떼", "라떼"]


class MenuVariant(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    temperature: Temperature
    image_url: str = Field(pattern=r"^/images/menus/.+")


class MenuResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    menu_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    categories: list[Category] = Field(min_length=1)
    price_krw: int = Field(ge=0)
    available_temperatures: list[Temperature] = Field(min_length=1, max_length=2)
    variants: list[MenuVariant] = Field(min_length=1, max_length=2)
    image_url: str = Field(pattern=r"^/images/menus/.+")
    is_available: bool
    display_order: int = Field(gt=0)
    is_featured: bool

    @model_validator(mode="after")
    def validate_options(self):
        temperatures = [variant.temperature for variant in self.variants]
        if temperatures != self.available_temperatures or len(set(temperatures)) != len(temperatures):
            raise ValueError("Menu temperatures and variants must match without duplicates")
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("Duplicate menu categories")
        return self


class MenusResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    menus: list[MenuResponse]
