"""Validate the repository catalogue before opening a write transaction."""

import ast
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
MENU_IDS = {
    "복숭아 아이스티": "peach_iced_tea", "레몬티": "lemon_tea_alias",
    "아이스아메리카노": "iced_americano", "레몬에이드": "lemonade",
    "딸기라떼": "strawberry_latte", "청포도에이드": "green_grape_ade",
    "카페라떼": "cafe_latte", "레몬차": "lemon_tea", "유자차": "citron_tea",
    "에스프레소": "espresso", "녹차라떼": "green_tea_latte",
}
CATEGORY_ORDER = ("커피", "티", "에이드", "논커피라떼", "라떼")


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
    parsed = urlparse(source.get("source_url", ""))
    require(parsed.scheme == "https" and bool(parsed.netloc), "Missing HTTPS source URL")
    try:
        date.fromisoformat(source["checked_date"])
    except (KeyError, TypeError, ValueError) as error:
        raise CatalogError("Invalid source checked_date") from error


def load_catalog(common_dir: Path | None = None, public_dir: Path | None = None) -> list[CatalogMenu]:
    common = common_dir or Path(os.environ.get("COMMON_DIR", ROOT / "common"))
    public = (public_dir or Path(os.environ.get("FRONTEND_PUBLIC_DIR", ROOT / "frontend/public"))).resolve()
    # Read literal definitions rather than executing the Python catalogue.
    definitions = {}
    for node in ast.parse((common / "menu_data.py").read_text(encoding="utf-8-sig")).body:
        if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in {"MENUS", "CATEGORIES", "PRICE_OPTIONS"}):
            definitions[node.targets[0].id] = ast.literal_eval(node.value)
    names = definitions["MENUS"]
    categories = definitions["CATEGORIES"]
    options = definitions["PRICE_OPTIONS"]
    require(isinstance(names, list) and len(names) == len(set(names)) == 11, "Expected 11 unique menus")
    require(set(names) == set(MENU_IDS), "Menu ID mapping differs from common")
    require(tuple(categories) == CATEGORY_ORDER, "Category mapping differs from schema")
    require(all(isinstance(items, list) and len(items) == len(set(items)) and set(items) <= set(names)
                for items in categories.values()), "Invalid category members")
    require(isinstance(options, list) and all(type(p) is int and p >= 0 for p in options), "Invalid PRICE_OPTIONS")
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
    result = []
    for order, name in enumerate(names, 1):
        price = prices[name]
        require(type(price) is int and price >= 0 and price in options, f"Invalid price: {name}")
        source = sources[name]
        validate_source(source)
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
        memberships = tuple(category for category, members in categories.items() if name in members)
        require(bool(memberships), f"Menu has no category: {name}")
        result.append(CatalogMenu(MENU_IDS[name], name, price, order, name in featured, memberships,
                                  tuple((t, variants[t]) for t in ("HOT", "COLD") if t in variants)))
    return result
