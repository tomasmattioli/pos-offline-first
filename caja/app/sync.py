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
    de la base local. La caja los seguirá mostrando hasta que se reinicie la base.
    Se dejó así para v1 por el costo de implementación y prueba del borrado
    diferencial, no por riesgo de correr con operaciones pendientes (download_catalog
    aborta antes de tocar nada si hay pendientes, así que ese caso no puede ocurrir).
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
    Envía al servidor cada operación local en estado 'pending', en orden de inserción.
    Por cada operación:
      - hace POST /pending_operations con los cuatro campos que el servidor espera.
      - guarda el status recibido ('confirmed' o 'rejected') con commit inmediato.
        Esto garantiza que si se corta la conexión a la mitad, el próximo intento
        retoma desde la primera operación que sigue en 'pending'.
      - 422: el body está malformado (bug de la caja). Se marca 'format_error' para
        sacarlo de la cola sin perder la operación.
      - cualquier código que no sea 200 ni 422 (5xx, 401, 404, 400 inesperado, etc.):
        la operación se deja 'pending' y se corta el bucle. Ante un código desconocido
        lo seguro es no marcar nada y no perder la venta.

    Retorna True solo si todas las operaciones pendientes fueron procesadas.
    """
    operations = (
        db.query(PendingOperation)
        .filter(PendingOperation.status == "pending")
        .order_by(PendingOperation.id)
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
            # Se marca 'format_error': sale de la cola de pendientes sin
            # fingir que el servidor la procesó.
            print(
                f"[sync] Operación {op.operation_uuid} devolvió 422. "
                "Body inválido — marcando como 'format_error'."
            )
            op.status = "format_error"
            db.commit()
            continue

        if response.status_code != 200:
            # Cualquier código que no sea 200 ni 422 (5xx, 401, 404, 400 inesperado...).
            # Ante un código desconocido lo seguro es no marcar nada:
            # la operación queda 'pending' y reintentará en el próximo ciclo.
            print(
                f"[sync] Código inesperado {response.status_code} para "
                f"{op.operation_uuid}. Dejando 'pending' e interrumpiendo sync."
            )
            return False

        try:
            result = response.json()
        except ValueError as e:
            print(f"[sync] Respuesta no JSON del servidor para {op.operation_uuid}: {e}")
            return False

        if not isinstance(result, dict):
            print(
                f"[sync] Respuesta JSON no es un diccionario para {op.operation_uuid}. "
                "Interrumpiendo sync."
            )
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
