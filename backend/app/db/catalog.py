"""Validate the repository catalogue before opening a write transaction."""

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import get_args
from urllib.parse import urlparse

from pydantic import ValidationError

from app.schemas.menus import Category, MenuOptionGroup

ROOT = Path(__file__).resolve().parents[3]
CATEGORY_ORDER = get_args(Category)


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class CatalogMenu:
    menu_id: str
    name: str
    price_krw: int
    display_order: int
    is_featured: bool
    categories: tuple[str, ...]
    variants: tuple[tuple[str, str], ...]
    option_groups: list[dict]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CatalogError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)


def validate_source(source: dict) -> None:
    require(isinstance(source, dict), "Invalid source record")
    try:
        date.fromisoformat(source["checked_date"])
    except (KeyError, TypeError, ValueError) as error:
        raise CatalogError("Invalid source checked_date") from error


def validate_source_url(source: dict) -> None:
    parsed = urlparse(source.get("source_url", ""))
    require(parsed.scheme == "https" and bool(parsed.netloc), "Missing HTTPS source URL")


def load_option_profiles(common: Path) -> dict[str, list[dict]]:
    data = read_json(common / "order_option_profiles.json")
    result = {}
    for profile, groups in data["profiles"].items():
        try:
            options = [MenuOptionGroup.model_validate(group) for group in data["common"] + groups]
        except ValidationError as error:
            raise CatalogError(f"Invalid options for profile: {profile}") from error
        require(len({group.id for group in options}) == len(options), f"Duplicate option group: {profile}")
        result[profile] = [group.model_dump() for group in options]
    return result


def load_catalog(common_dir: Path | None = None, public_dir: Path | None = None) -> list[CatalogMenu]:
    common = common_dir or Path(os.environ.get("COMMON_DIR", ROOT / "common"))
    public = (public_dir or Path(os.environ.get("FRONTEND_PUBLIC_DIR", ROOT / "frontend/public"))).resolve()
    metadata = read_json(common / "order_catalog.json")
    require(isinstance(metadata, list) and bool(metadata), "Missing order catalog")
    names = [menu["name"] for menu in metadata]
    ids = [menu["menu_id"] for menu in metadata]
    for values in (names, ids):
        require(all(isinstance(value, str) and bool(value.strip()) for value in values)
                and len(values) == len(set(values)), "Invalid or duplicate catalog names or IDs")
    profiles = load_option_profiles(common)
    prices = read_json(common / "menu_prices.json")
    images = read_json(common / "menu_images.json")
    sources = read_json(common / "menu_price_sources.json")
    image_sources = read_json(common / "menu_image_sources.json")
    featured = read_json(common / "menu_display.json")["simplified_menu_names"]
    require(isinstance(featured, list) and len(featured) == len(set(featured))
            and set(featured) <= set(names), "Invalid simplified menu list")
    for data in (prices, images, sources):
        require(isinstance(data, dict) and set(data) == set(names), "Catalogue menu sets differ")
    require(isinstance(image_sources, list), "Invalid image sources")
    for source in image_sources:
        validate_source(source)
        validate_source_url(source)
    result = []
    for order, menu in enumerate(metadata, 1):
        name = menu["name"]
        memberships = menu["categories"]
        require(isinstance(memberships, list) and bool(memberships) and len(memberships) == len(set(memberships))
                and set(memberships) <= set(CATEGORY_ORDER), f"Invalid categories: {name}")
        profile = menu["option_profile"]
        require(profile in profiles, f"Unknown option profile: {name}")
        price = prices[name]
        require(type(price) is int and price >= 0, f"Invalid price: {name}")
        source = sources[name]
        validate_source(source)
        if source.get("source_kind") != "user_provided":
            validate_source_url(source)
        require(type(source.get("price_krw")) is int and source["price_krw"] == price,
                f"Price source mismatch: {name}")
        variants = images[name]
        require(isinstance(variants, dict) and bool(variants) and set(variants) <= {"HOT", "COLD"},
                f"Invalid temperatures: {name}")
        for temperature, image_url in variants.items():
            require(isinstance(image_url, str) and image_url.startswith("/images/menus/"), f"Invalid image: {name}")
            image = (public / image_url.lstrip("/")).resolve()
            require(image.is_relative_to(public / "images/menus") and image.is_file(), f"Missing image: {name}")
            matches = [item for item in image_sources if item.get("official_name") == source.get("official_name")
                       and item.get("temperature") == temperature and item.get("image_path") == image_url]
            require(len(matches) == 1, f"Image source mismatch: {name}/{temperature}")
            require(urlparse(matches[0].get("image_source_url", "")).scheme == "https", "Invalid image source URL")
        result.append(CatalogMenu(menu["menu_id"], name, price, order, name in featured, tuple(memberships),
                                  tuple((t, variants[t]) for t in ("HOT", "COLD") if t in variants),
                                  profiles[profile]))
    return result
