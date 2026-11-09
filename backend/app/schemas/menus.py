from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Temperature = Literal["HOT", "COLD"]
Category = Literal["커피", "디카페인", "음료", "에스프레소", "라떼", "콜드브루",
                   "에이드", "프라페", "스무디/주스", "논커피라떼", "티"]


class MenuOption(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z_]+:[a-z_]+$")
    label: str = Field(min_length=1)
    price_delta_krw: int = Field(ge=0)


class MenuOptionGroup(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z_]+$")
    label: str = Field(min_length=1)
    max_selections: int = Field(ge=1)
    choices: list[MenuOption] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_choices(self):
        ids = {choice.id for choice in self.choices}
        if len(ids) != len(self.choices) or self.max_selections > len(ids):
            raise ValueError("Invalid option group choices")
        if any(not option_id.startswith(f"{self.id}:") for option_id in ids):
            raise ValueError("Option must belong to its group")
        return self


class MenuVariant(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    temperature: Temperature
    image_url: str = Field(pattern=r"^/images/menus/.+")
    option_groups: list[MenuOptionGroup] = Field(default_factory=list)


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
