from contextlib import closing
from datetime import timezone
from uuid import UUID

from app.db.connection import connect
from app.repositories.orders import find_order_for_request, get_variant_options, insert_order, lock_menu
from app.schemas.orders import CreateOrderRequest, OrderResponse


class OrderRejected(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def select_options(groups: list[dict], option_ids: list[str]) -> list[dict]:
    requested = set(option_ids)
    selected = []
    for group in groups:
        choices = [choice for choice in group["choices"] if choice["id"] in requested]
        if len(choices) > group["max_selections"]:
            raise OrderRejected("INVALID_OPTION")
        selected.extend(choices)
    if len(requested) != len(option_ids) or len(selected) != len(requested):
        raise OrderRejected("INVALID_OPTION")
    return selected


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
            groups = get_variant_options(connection, request.menu_id, request.temperature)
            if groups is None:
                raise OrderRejected("INVALID_OPTION")
            selected_options = select_options(groups, request.option_ids)
            total = menu["price_krw"] + sum(choice["price_delta_krw"] for choice in selected_options)

            order = insert_order(
                connection,
                request_id=request_id,
                menu_id=request.menu_id,
                menu_name=menu["name"],
                price_krw=total,
                temperature=request.temperature,
                service_type=request.service_type,
                selected_options=selected_options,
            )
        elif (order["menu_id"], order["temperature"], order["service_type"]) != (
            request.menu_id, request.temperature, request.service_type
        ) or sorted(choice["id"] for choice in order["selected_options"]) != sorted(request.option_ids):
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
            selected_options=order["selected_options"],
            created_at=order["created_at"].astimezone(timezone.utc),
        )
    return response, created
