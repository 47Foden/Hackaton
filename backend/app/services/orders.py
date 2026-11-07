from contextlib import closing
from datetime import timezone
from uuid import UUID

from app.db.connection import connect
from app.repositories.orders import find_order_for_request, has_temperature, insert_order, lock_menu
from app.schemas.orders import CreateOrderRequest, OrderResponse


class OrderRejected(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def create_order(request: CreateOrderRequest) -> tuple[OrderResponse, bool]:
    request_id = UUID(request.request_id)
    with closing(connect()) as connection, connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        order = find_order_for_request(connection, request_id)
        created = order is None
        if order is None:
            # Catalog writers lock the parent menu before changing its temperature variants.
            menu = lock_menu(connection, request.menu_id)
            if menu is None:
                raise OrderRejected("MENU_NOT_FOUND")
            if not menu["is_available"]:
                raise OrderRejected("MENU_UNAVAILABLE")
            if not has_temperature(connection, request.menu_id, request.temperature):
                raise OrderRejected("INVALID_OPTION")

            order = insert_order(
                connection,
                request_id=request_id,
                menu_id=request.menu_id,
                menu_name=menu["name"],
                price_krw=menu["price_krw"],
                temperature=request.temperature,
                service_type=request.service_type,
            )
        elif (order["menu_id"], order["temperature"], order["service_type"]) != (
            request.menu_id, request.temperature, request.service_type
        ):
            raise OrderRejected("IDEMPOTENCY_CONFLICT")

        order_id = str(order["id"])
        response = OrderResponse(
            order_id=order_id,
            order_number=order_id,
            menu_id=order["menu_id"],
            menu_name=order["menu_name_snapshot"],
            temperature=order["temperature"],
            service_type=order["service_type"],
            quantity=order["quantity"],
            total_price_krw=order["total_price_krw"],
            created_at=order["created_at"].astimezone(timezone.utc),
        )
    return response, created
