import logging

import psycopg
from fastapi import APIRouter, HTTPException, status

from app.db.connection import DatabaseConfigurationError
from app.schemas.orders import CreateOrderRequest, OrderResponse
from app.services.orders import OrderRejected, create_order

router = APIRouter(prefix="/api/orders", tags=["orders"])
logger = logging.getLogger(__name__)

ORDER_REJECTIONS = {
    "MENU_NOT_FOUND": (404, "등록되지 않은 메뉴입니다."),
    "MENU_UNAVAILABLE": (409, "현재 판매하지 않는 메뉴입니다."),
    "INVALID_OPTION": (422, "선택할 수 없는 온도입니다."),
}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OrderResponse)
def post_order(request: CreateOrderRequest) -> OrderResponse:
    try:
        return create_order(request)
    except OrderRejected as error:
        status_code, message = ORDER_REJECTIONS[error.code]
        raise HTTPException(status_code=status_code, detail={"code": error.code, "message": message}) from None
    except (psycopg.Error, DatabaseConfigurationError) as error:
        logger.warning("Order storage unavailable (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail={
            "code": "ORDER_STORAGE_UNAVAILABLE",
            "message": "주문 접수 여부를 확인할 수 없어요.",
        }) from None
