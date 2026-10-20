import json
import requests
from sqlalchemy.orm import Session
from app.config import SERVER_URL
from app.models.product import Product
from app.models.pending_operation import PendingOperation
from app.utils import to_decimal, to_text


def download_catalog(db: Session, timeout: int = 5) -> bool:
    """
    Descarga el catálogo de productos desde el servidor y actualiza la base local.

    Regla de seguridad: si hay operaciones en estado 'pending' en la cola local,
    aborta sin tocar nada. El stock del servidor no refleja aún esas ventas, y
    pisarlo generaría un stock local incorrecto (mayor al real).

    Si el producto ya existe (por ID), actualiza sus datos; si no existe, lo crea.
    Si el servidor no responde o devuelve una respuesta inesperada, retorna False
    sin interrumpir la caja.

    Limitación conocida (v1): los productos borrados en el servidor no se eliminan
    de la base local. La caja los seguirá mostrando hasta un reinicio manual. Anotado
    en README como deuda técnica.
    """
    pending_count = (
        db.query(PendingOperation)
        .filter(PendingOperation.status == "pending")
        .count()
    )
    if pending_count > 0:
        print(
            f"[sync] Hay {pending_count} operaciones pendientes en cola. "
            "Sincronizá la cola primero antes de bajar el catálogo."
        )
        return False

    try:
        response = requests.get(f"{SERVER_URL}/products", timeout=timeout)
        response.raise_for_status()
        products_data = response.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"[sync] Error al descargar catálogo del servidor: {e}")
        return False

    for item in products_data:
        product_id = item["id"]
        product = db.query(Product).filter(Product.id == product_id).first()

        price_str = to_text(to_decimal(str(item["price"])))
        stock_str = to_text(to_decimal(str(item["stock"])))

        if product:
            product.name = item["name"]
            product.barcode = item.get("barcode")
            product.price = price_str
            product.stock = stock_str
        else:
            product = Product(
                id=product_id,
                name=item["name"],
                barcode=item.get("barcode"),
                price=price_str,
                stock=stock_str,
            )
            db.add(product)

    db.commit()
    print(f"[sync] Catálogo sincronizado: {len(products_data)} productos.")
    return True


def sync_pending(db: Session, timeout: int = 5) -> bool:
    """
    Envía al servidor cada operación local en estado 'pending'.
    Por cada operación:
      - hace POST /pending_operations con los campos que el servidor espera.
      - lee el status devuelto ('confirmed' o 'rejected') y lo persiste de inmediato.
      - si el servidor devuelve 422 (body inválido por bug de la caja), marca la
        operación como 'format_error' para sacarla de la cola sin fingir que fue
        procesada correctamente.
      - si la red cae, corta el bucle: no tiene sentido seguir si la conexión cayó.

    Retorna True si todas las operaciones pendientes fueron procesadas, False si
    hubo algún error de red o quedaron operaciones sin enviar.
    """
    operations = (
        db.query(PendingOperation)
        .filter(PendingOperation.status == "pending")
        .all()
    )

    if not operations:
        print("[sync] No hay operaciones pendientes.")
        return True

    for op in operations:
        body = {
            "operation_uuid": op.operation_uuid,
            "cash_register_id": op.cash_register_id,
            "occurred_at": op.occurred_at,
            "payload": op.payload,
        }

        try:
            response = requests.post(
                f"{SERVER_URL}/pending_operations",
                json=body,
                timeout=timeout,
            )
        except requests.exceptions.RequestException as e:
            print(f"[sync] Error de red al enviar operación {op.operation_uuid}: {e}")
            print("[sync] Interrumpiendo sync: la conexión cayó.")
            return False

        if response.status_code == 422:
            # El servidor rechazó el formato del body — bug en la caja.
            # Marcamos 'format_error' para sacar la operación del bloqueo
            # de la cola sin fingir que fue aceptada o rechazada por el servidor.
            print(
                f"[sync] Operación {op.operation_uuid} devolvió 422. "
                "Body inválido — marcando como 'format_error'."
            )
            op.status = "format_error"
            db.commit()
            continue

        try:
            result = response.json()
        except ValueError as e:
            print(f"[sync] Respuesta no JSON del servidor para {op.operation_uuid}: {e}")
            return False

        new_status = result.get("status")
        if new_status not in ("confirmed", "rejected"):
            print(
                f"[sync] Status inesperado '{new_status}' para {op.operation_uuid}. "
                "Interrumpiendo sync."
            )
            return False

        op.status = new_status
        db.commit()
        print(f"[sync] Operación {op.operation_uuid}: {new_status}.")

    print("[sync] Todas las operaciones pendientes fueron procesadas.")
    return True
