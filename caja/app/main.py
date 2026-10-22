import json
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import Session

from app.database import init_db, SessionLocal
from app.models.product import Product
from app.models.pending_operation import PendingOperation
from app.sales import register_sale
from app.sync import sync_pending, download_catalog
from app.utils import to_decimal


def leer_entero(mensaje: str, minimo: int = None) -> int:
    """Lee un entero desde teclado asegurando manejo de error ante tipeo inválido."""
    while True:
        entrada = input(mensaje).strip()
        try:
            valor = int(entrada)
            if minimo is not None and valor < minimo:
                print(f"Error: el número debe ser como mínimo {minimo}.")
                continue
            return valor
        except ValueError:
            print("Error: debe ingresar un número entero válido.")


def leer_decimal(mensaje: str, mayor_a_cero: bool = False, max_decimales: int = 3) -> Decimal:
    """
    Lee un Decimal desde teclado asegurando:
    - Que sea un número finito válido (rechaza NaN, Infinity, -Infinity).
    - Que sea mayor a 0 si mayor_a_cero es True.
    - Que no tenga más de max_decimales (el servidor usa Numeric(10, 3)).
    """
    while True:
        entrada = input(mensaje).strip()
        try:
            valor = Decimal(entrada)
        except InvalidOperation:
            print("Error: debe ingresar un número decimal válido (ej: 1.5, 2, 0.750).")
            continue

        if not valor.is_finite():
            print("Error: no se permiten valores especiales como NaN o Infinito.")
            continue

        if mayor_a_cero and valor <= Decimal(0):
            print("Error: la cantidad debe ser mayor a 0.")
            continue

        # Normalizar ceros finales redundantes (ej: 0.7500 -> 0.75) para evaluar exponente
        valor_norm = valor.normalize() if valor != Decimal(0) else valor
        if valor_norm.as_tuple().exponent < -max_decimales:
            print(f"Error: la cantidad no puede tener más de {max_decimales} decimales (ej: 0.250).")
            continue

        return valor


def menu_ver_catalogo(db: Session):
    """
    Opción 2: Consulta y muestra los productos y el stock del catálogo local.
    Muestra precios con 2 decimales y stock con 3 decimales (peso).
    Si está vacío, alerta que se requiere sincronizar al primer arranque.
    """
    productos = db.query(Product).order_by(Product.id.asc()).all()

    if not productos:
        print("\n" + "=" * 60)
        print("[AVISO] El catálogo local está vacío.")
        print("Si es el primer arranque, conectá la caja a la red y ejecutá")
        print("la opción 1 (Sincronizar) para descargar los productos.")
        print("=" * 60)
        return

    print("\n" + "=" * 77)
    print(f"{'ID':<6} {'Nombre':<30} {'Precio':<12} {'Stock':<12} {'Código de barras'}")
    print("-" * 77)
    for p in productos:
        precio_num = to_decimal(p.price)
        stock_num = to_decimal(p.stock)
        codigo = p.barcode if p.barcode else "S/C"
        print(f"{p.id:<6} {p.name:<30} ${precio_num:<11.2f} {stock_num:<12.3f} {codigo}")
    print("=" * 77)


def menu_ver_cola(db: Session):
    """
    Opción 4: Muestra el listado de operaciones en cola con su estado.
    - Convierte la hora UTC a la hora local del sistema con astimezone().
    - Para no saturar la pantalla en v1, muestra todas las operaciones activas/problemáticas
      (pending, format_error, rejected) y hasta las últimas 5 confirmadas como historial.
    - Destaca 'format_error' con alerta visual ya que requiere revisión manual.
    """
    ops_activas = (
        db.query(PendingOperation)
        .filter(PendingOperation.status != "confirmed")
        .order_by(PendingOperation.id.asc())
        .all()
    )
    ops_confirmadas = (
        db.query(PendingOperation)
        .filter(PendingOperation.status == "confirmed")
        .order_by(PendingOperation.id.desc())
        .limit(5)
        .all()
    )
    total_confirmadas = (
        db.query(PendingOperation)
        .filter(PendingOperation.status == "confirmed")
        .count()
    )

    operaciones = sorted(ops_activas + ops_confirmadas, key=lambda x: x.id)

    if not operaciones:
        print("\n[INFO] La cola de operaciones está vacía.")
        return

    print("\n" + "=" * 80)
    print(f"{'ID':<5} {'Hora Local':<20} {'Estado':<18} {'Ítems':<8} {'UUID (primeros 8)'}")
    print("-" * 80)
    for op in operaciones:
        # Convertir timestamp ISO en UTC a la zona horaria local de la caja
        try:
            dt_local = datetime.fromisoformat(op.occurred_at).astimezone()
            fecha_legible = dt_local.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            fecha_legible = op.occurred_at[:19] if op.occurred_at else "Fecha corrupta"

        # Extraer cantidad de ítems del payload
        try:
            payload_data = json.loads(op.payload)
            total_items = len(payload_data.get("items", []))
        except (ValueError, TypeError):
            total_items = "?"

        # Destacar format_error porque queda fuera del circuito de reintentos automáticos
        if op.status == "format_error":
            estado_visual = "FORMAT_ERROR (!)"
        else:
            estado_visual = op.status

        uuid_corto = op.operation_uuid[:8]
        print(f"{op.id:<5} {fecha_legible:<20} {estado_visual:<18} {total_items:<8} {uuid_corto}")
    print("=" * 80)
    if total_confirmadas > 5:
        print(f"(* Ocultando {total_confirmadas - 5} operaciones confirmadas más antiguas para mantener la vista legible)")


def menu_sincronizar(db: Session):
    """
    Opción 1: Ejecuta sync_pending() y, únicamente si retorna True,
    ejecuta download_catalog().
    - Anota los IDs de las operaciones pendientes antes de iniciar para reportar
      únicamente el desenlace de esta corrida (evita repetir alertas de corridas viejas).
    - Evita mensajes contradictorios entre ventas confirmadas y rechazadas.
    """
    print("\n--- INICIANDO SINCRONIZACIÓN ---")

    # 1. Anotar los IDs de las operaciones pendientes antes de enviar
    pending_ops = (
        db.query(PendingOperation.id)
        .filter(PendingOperation.status == "pending")
        .order_by(PendingOperation.id.asc())
        .all()
    )
    pending_ids = [row[0] for row in pending_ops]

    if not pending_ids:
        print("[INFO] No hay operaciones pendientes en la cola local.")
        print("[1/1] Descargando catálogo actualizado desde el servidor...")
        catalog_ok = download_catalog(db)
        if catalog_ok:
            print("\n[ÉXITO] Catálogo actualizado correctamente.")
        else:
            print("\n[AVISO] No se pudo descargar el catálogo (servidor caído o corte de red).")
            print("La caja continúa operando con el catálogo local actual.")
        return

    # 2. Enviar operaciones pendientes
    print(f"[1/2] Enviando {len(pending_ids)} operación(es) pendiente(s) al servidor...")
    sync_ok = sync_pending(db)

    # 3. Evaluar el estado final EXCLUSIVAMENTE de los IDs procesados en esta tanda
    ops_procesadas = (
        db.query(PendingOperation)
        .filter(PendingOperation.id.in_(pending_ids))
        .all()
    )
    confirmadas = sum(1 for op in ops_procesadas if op.status == "confirmed")
    rechazadas = sum(1 for op in ops_procesadas if op.status == "rejected")
    format_errors = sum(1 for op in ops_procesadas if op.status == "format_error")
    siguen_pending = sum(1 for op in ops_procesadas if op.status == "pending")

    print("\n--- RESUMEN DE COLA PROCESADA ---")
    print(f"Operaciones enviadas en esta sincronización: {len(pending_ids)}")
    print(f"  - Confirmadas: {confirmadas}")
    print(f"  - Rechazadas por servidor: {rechazadas}")
    print(f"  - Error de formato (422): {format_errors}")
    if siguen_pending > 0:
        print(f"  - Sin enviar (por corte de red): {siguen_pending}")

    if not sync_ok:
        print("\n[SINCRONIZACIÓN INTERRUMPIDA]")
        print("- Se cortó la conexión con el servidor o se recibió una respuesta inesperada.")
        print("- Por seguridad, NO se descargó el catálogo para evitar sobreescribir el stock local.")
        print("- Las operaciones no confirmadas continúan seguras en la caja y se reintentarán al volver la red.")
        return

    # 4. Si la cola se vació sin errores de red, descargar catálogo
    print("\n[2/2] Descargando catálogo actualizado desde el servidor...")
    catalog_ok = download_catalog(db)

    if catalog_ok:
        print("\n[ÉXITO] Sincronización completada.")
        print("- Catálogo local actualizado exitosamente con los precios y stock del servidor.")
    else:
        print("\n[SINCRONIZACIÓN PARCIAL]")
        print("- Las operaciones fueron procesadas por el servidor, pero falló la descarga del nuevo catálogo.")
        print("- La caja puede continuar operando con el catálogo local actual.")



def menu_vender(db: Session):
    """
    Opción 3: Flujo interactivo de venta.
    - Requiere catálogo cargado.
    - Carga interactiva: busca por barcode directamente o por #ID con '#'.
    - Muestra datos del producto encontrado antes de pedir cantidad.
    - Lee cantidad con leer_decimal(..., mayor_a_cero=True).
    - Muestra resumen consolidado con subtotales y total antes de confirmar.
    - Solicita confirmación y llama a register_sale(db, items).
    """
    total_productos = db.query(Product).count()
    if total_productos == 0:
        print("\n" + "=" * 60)
        print("[AVISO] El catálogo local está vacío.")
        print("Debe sincronizar con el servidor (Opción 1) antes de vender.")
        print("=" * 60)
        return

    items_cargados: list[tuple[Product, Decimal]] = []

    print("\n--- NUEVA VENTA ---")
    print("Ingrese código de barras directamente, o '#ID' para buscar por ID.")
    print("Presione Enter sin texto o escriba 'FIN' para finalizar la carga.\n")

    while True:
        entrada = input("Código de barras o #ID (o FIN para terminar): ").strip()

        if not entrada or entrada.upper() == "FIN":
            break

        producto = None
        if entrada.startswith("#"):
            id_str = entrada[1:].strip()
            try:
                prod_id = int(id_str)
                producto = db.query(Product).filter(Product.id == prod_id).first()
            except ValueError:
                print("Error: luego de '#' debe ingresar un número de ID válido (ej: #2).")
                continue
        else:
            producto = db.query(Product).filter(Product.barcode == entrada).first()

        if not producto:
            print(f"Producto no encontrado para '{entrada}'. Intente nuevamente.")
            continue

        precio_dec = to_decimal(producto.price)
        stock_dec = to_decimal(producto.stock)
        print(f"-> Encontrado: {producto.name} (ID {producto.id}) | Precio: ${precio_dec:.2f} | Stock local: {stock_dec:.3f}")

        cantidad = leer_decimal("   Cantidad a vender: ", mayor_a_cero=True)
        items_cargados.append((producto, cantidad))
        print(f"   [+] Agregado: {producto.name} x {cantidad:.3f}\n")

    if not items_cargados:
        print("\n[INFO] Venta cancelada: no se cargaron productos.")
        return

    # Consolidar ítems por producto para el resumen claro del cajero
    resumen_por_producto: dict[int, dict] = {}
    total_venta = Decimal("0.00")

    for prod, cant in items_cargados:
        if prod.id not in resumen_por_producto:
            resumen_por_producto[prod.id] = {
                "producto": prod,
                "cantidad": Decimal("0.000"),
                "precio": to_decimal(prod.price),
            }
        resumen_por_producto[prod.id]["cantidad"] += cant

    print("\n" + "=" * 65)
    print("RESUMEN DE LA VENTA")
    print("-" * 65)
    print(f"{'Producto':<30} {'Cantidad':<12} {'Precio Unit.':<12} {'Subtotal'}")
    print("-" * 65)

    items_para_register: list[tuple[int, Decimal]] = []

    for pid, datos in resumen_por_producto.items():
        prod = datos["producto"]
        cant = datos["cantidad"]
        precio = datos["precio"]
        subtotal = precio * cant
        total_venta += subtotal
        items_para_register.append((pid, cant))
        print(f"{prod.name:<30} {cant:<12.3f} ${precio:<11.2f} ${subtotal:.2f}")

    print("-" * 65)
    print(f"{'TOTAL A COBRAR:':<55} ${total_venta:.2f}")
    print("=" * 65)

    confirmar = input("\n¿Confirmar venta y descontar stock? (s/n): ").strip().lower()
    if confirmar != "s":
        print("\n[INFO] Venta descartada por el cajero. No se realizaron cambios.")
        return

    # Registrar venta localmente
    ok, mensaje, op = register_sale(db, items_para_register)

    if not ok:
        print(f"\n[AVISO] No se pudo registrar la venta: {mensaje}")
    else:
        print(f"\n[ÉXITO] {mensaje}")
        print(f"Venta encolada con UUID: {op.operation_uuid} (Estado: {op.status})")



def main():
    # Inicializar tablas en SQLite al arrancar
    init_db()

    # Abrir una única sesión y garantizar su cierre al salir en el finally
    db = SessionLocal()
    try:
        while True:
            print("\n=== SISTEMA DE CAJA (POS OFFLINE-FIRST) ===")
            print("1. Sincronizar")
            print("2. Ver catálogo")
            print("3. Vender")
            print("4. Ver cola")
            print("5. Salir")

            opcion = input("\nSeleccione una opción (1-5): ").strip()

            if opcion == "1":
                menu_sincronizar(db)
            elif opcion == "2":
                menu_ver_catalogo(db)
            elif opcion == "3":
                menu_vender(db)
            elif opcion == "4":
                menu_ver_cola(db)
            elif opcion == "5":
                print("\nCerrando sistema de caja. Hasta luego.")
                sys.exit(0)
            else:
                print("\nOpción no válida. Por favor, ingrese un número del 1 al 5.")
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupción manual recibida. Cerrando caja.")
        sys.exit(0)
