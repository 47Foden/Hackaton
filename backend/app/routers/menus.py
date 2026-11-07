import logging

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.db.connection import DatabaseConfigurationError
from app.repositories.menus import CatalogReadError, list_menus
from app.schemas.menus import MenusResponse

router = APIRouter(prefix="/api/menus", tags=["menus"])
logger = logging.getLogger(__name__)


@router.get("", response_model=MenusResponse, responses={503: {"description": "Catalogue unavailable"}})
def get_menus() -> MenusResponse:
    try:
        # Validate before returning so corrupt catalogues also use the public 503 contract.
        return MenusResponse(menus=list_menus())
    except (psycopg.Error, DatabaseConfigurationError, CatalogReadError, ValidationError) as error:
        logger.warning("Menu catalogue unavailable (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail={
            "code": "CATALOG_UNAVAILABLE",
            "message": "메뉴를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
        }) from None
