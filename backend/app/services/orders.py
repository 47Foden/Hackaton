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
            lines = request.items or [request]
            snapshots = []
            for line in lines:
                menu = lock_menu(connection, line.menu_id)
                if menu is None:
                    raise OrderRejected("MENU_NOT_FOUND")
                if not menu["is_available"]:
                    raise OrderRejected("MENU_UNAVAILABLE")
                groups = get_variant_options(connection, line.menu_id, line.temperature)
                if groups is None:
                    raise OrderRejected("INVALID_OPTION")
                choices = select_options(groups, line.option_ids)
                quantity = getattr(line, "quantity", 1)
                unit = menu["price_krw"] + sum(c["price_delta_krw"] for c in choices)
                snapshots.append(dict(menu_id=line.menu_id, menu_name=menu["name"],
                    temperature=line.temperature, service_type=line.service_type,
                    quantity=quantity, selected_options=choices, unit_price_krw=unit,
                    total_price_krw=unit * quantity))
            first = snapshots[0]
            order = insert_order(connection, request_id=request_id,
                menu_id=first["menu_id"], menu_name=first["menu_name"],
                price_krw=sum(i["total_price_krw"] for i in snapshots),
                temperature=first["temperature"], service_type=first["service_type"],
                selected_options=first["selected_options"])
            if request.items:
                from psycopg.types.json import Jsonb
                connection.execute("UPDATE orders SET items = %s WHERE id = %s",
                                   (Jsonb(snapshots), order["id"]))
                order["items"] = snapshots
        else:
            saved = order.get("items") or [order]
            incoming = request.items or [request]
            def identity(line):
                return (line.menu_id, line.temperature, line.service_type,
                        getattr(line, "quantity", 1), sorted(line.option_ids))
            old = [(i["menu_id"], i["temperature"], i["service_type"], i["quantity"],
                    sorted(c["id"] for c in i["selected_options"])) for i in saved]
            if old != [identity(i) for i in incoming]:
                raise OrderRejected("IDEMPOTENCY_CONFLICT")

        order_id = str(order["id"])
        response = OrderResponse(
            items=order.get("items", []),
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
