# POS Offline-First

Sistema de Punto de Venta (POS) con arquitectura **Offline-First**, diseñado para operar en comercios minoristas donde la continuidad operativa es crítica.

El sistema se compone de dos aplicaciones desacopladas:
- **Servidor Central:** API REST construida con **FastAPI** y base de datos relacional **PostgreSQL**, encargada de la consolidación de ventas, inventario centralizado y catálogo maestro.
- **Terminal de Caja:** Aplicación de consola (CLI) construida en **Python** con base de datos local embebida en **SQLite**, capaz de registrar ventas y descontar stock local de manera 100% autónoma ante cortes de conexión.

---

## 1. ¿Por qué existe este proyecto? (El problema)

En un comercio minorista, un corte de suministro de internet no puede paralizar la atención al público ni la facturación. Las soluciones POS basadas exclusivamente en la nube ("Cloud-Only") fallan en este escenario: si se corta el enlace, no se puede cobrar, se generan colas y se pierde dinero.

Este proyecto resuelve ese problema mediante una arquitectura **Offline-First**:
1. La caja tiene una copia local del catálogo y de su stock en un archivo **SQLite** en el disco de la terminal.
2. Cada venta se procesa localmente en milisegundos sin depender de la red, descontando el stock local y guardando la transacción en una cola de operaciones pendientes.
3. Al restablecerse la conectividad, la caja sincroniza en diferido con el servidor central mediante transacciones idempotentes, asegurando que ninguna venta se pierda ni se duplique.

---

## 2. ¿Cómo funciona?

### Flujo general

```
+-----------------------------------------------------------------------+
|                           TERMINAL DE CAJA                            |
|                                                                       |
|  [Cajero] ---> Escaneo de productos (Barcode o #ID)                   |
|                   |                                                   |
|                   v                                                   |
|           Valida stock local en SQLite                                |
|                   |                                                   |
|                   v                                                   |
|           Descuenta stock local y encola en 'pending_operations'       |
|           (UUID único generado en caja + timestamp UTC)               |
+-----------------------------------------------------------------------+
                                    |
                         ¿Hay conexión a Internet?
                                    |
                  [SÍ]              |              [NO]
                   v                |               v
+-----------------------------+     |     +-----------------------------+
| Sincronización diferida     |     |     | Continúa vendiendo          |
| POST /pending_operations    |<----+     | offline con stock local     |
+-----------------------------+           +-----------------------------+
                |
                v
+-----------------------------------------------------------------------+
|                           SERVIDOR CENTRAL                            |
|                                                                       |
|  1. ¿UUID ya fue procesado?                                          |
|     -> SÍ: Devuelve resultado ya guardado (Idempotencia).             |
|     -> NO: Valida stock central acumulado en PostgreSQL.              |
|                                                                       |
|  2. ¿Hay stock central suficiente?                                    |
|     -> SÍ: Crea 'Sale', 'SaleDetail', descuenta stock y marca         |
|            la operación como 'confirmed'.                             |
|     -> NO: Guarda la operación como 'rejected'.                       |
+-----------------------------------------------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                      ACTUALIZACIÓN DE CATÁLOGO                        |
|  Una vez vaciada la cola pendiente, la caja ejecuta:                  |
|  GET /products -> Actualiza precios y stock real en la base local.    |
+-----------------------------------------------------------------------+
```

---

## 3. Tecnologías y Justificación del Stack

| Componente | Tecnologías | Justificación |
| :--- | :--- | :--- |
| **Servidor Central** | Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Pydantic | **FastAPI** provee validación estricta de esquemas con Pydantic y documentación interactiva automática en `/docs` (los endpoints síncronos se delegan al threadpool de FastAPI). **PostgreSQL** garantiza transaccionalidad ACID y tipos numéricos exactos (`Numeric(10, 3)` para stock y `Numeric(10, 2)` para dinero). **Alembic** asegura migraciones de esquema reproducibles. |
| **Terminal de Caja** | Python, SQLite, SQLAlchemy, Requests | **SQLite** es un motor embebido serverless que reside en un único archivo (`caja.db`), eliminando la necesidad de instalar o mantener motores de bases de datos pesados en cada PC de caja. Se utiliza **SQLAlchemy** con un tipado estricto: números como `String` en la DB y `Decimal` en memoria, evitando los errores de redondeo de punto flotante binario (`float`). |

---

## 4. Cómo levantar el proyecto

### Prerrequisitos
- Python 3.10 o superior instalado.
- Servidor PostgreSQL activo con una base de datos creada (ej: `pos_central`).

---

### Paso 1: Configurar y levantar el Servidor

1. Abrir una terminal y posicionarse en el directorio del servidor:
   ```bash
   cd servidor
   ```

2. Crear y activar un entorno virtual:
   - **Windows:**
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Crear el archivo `.env` en la raíz de `servidor/`:
   ```env
   DB_URL=postgresql://postgres:tu_password@localhost:5432/pos_central
   ```

5. Ejecutar las migraciones para crear las tablas en PostgreSQL:
   ```bash
   alembic upgrade head
   ```

6. Iniciar la API con Uvicorn:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
    La documentación interactiva de Swagger quedará disponible en: `http://127.0.0.1:8000/docs`.

7. **Primer uso — Carga inicial de datos:**
   Antes de que la caja pueda operar, el servidor debe tener registrados al menos un usuario, una terminal de caja y productos en catálogo. Ejecutá el script incluido en el repo:
   ```bash
   python scripts/seed.py
   ```
   El script crea un usuario (`tomas`), una caja (`Caja Principal`) y cuatro productos de ejemplo con sus códigos de barras. Si ya existen datos, falla con un mensaje claro en lugar de duplicar registros.

   > **Nota:** `password_hash` en el seed es un placeholder. En producción reemplazarlo con un hash bcrypt real antes de usar el endpoint `/login`.

8. **Ejecutar tests automatizados con pytest:**
   El servidor cuenta con una suite completa de pruebas de integración con aislamiento transaccional (`SAVEPOINT`):
   ```bash
   # 1. Crear la base de test si aún no existe
   python tests/create_test_db.py

   # 2. Definir la variable de entorno con la URL de la base de test
   # Linux / macOS:
   export TEST_DB_URL=postgresql://postgres:tu_password@localhost:5432/pos_central_test
   # Windows PowerShell:
   $env:TEST_DB_URL="postgresql://postgres:tu_password@localhost:5432/pos_central_test"

   # 3. Correr los tests
   pytest tests/ -v
   ```
   > **Nota:** `TEST_DB_URL` es obligatoria y debe apuntar a una base que termine en `_test`. Si falta o apunta a producción, pytest aborta antes de tocar cualquier tabla.

---

### Paso 2: Configurar y levantar la Terminal de Caja

1. Abrir **otra terminal** y posicionarse en el directorio de la caja:
   ```bash
   cd caja
   ```

2. Crear y activar el entorno virtual:
   - **Windows:**
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Crear el archivo `.env` en la raíz de `caja/`:
   ```env
   SERVER_URL=http://127.0.0.1:8000
   CASH_REGISTER_ID=1
   USER_ID=1
   ```
   *(Nota: Asegurarse de que `CASH_REGISTER_ID` y `USER_ID` coincidan con los IDs creados en el servidor).*

5. Iniciar la interfaz CLI interactiva:
   ```bash
   python -m app.main
   ```

6. **Primer arranque:** En el menú principal, seleccionar la opción `1. Sincronizar catálogo` para descargar el catálogo maestro de productos y stock desde el servidor central.

### Demostración de Operación Offline y Sincronización

![demo](docs/demo.gif)

### Ejemplo de uso de la CLI (Terminal de Caja)

```text
=== SISTEMA DE CAJA (POS OFFLINE-FIRST) ===
1. Sincronizar
2. Ver catálogo
3. Vender
4. Ver cola
5. Salir

Seleccione una opción (1-5): 1

--- INICIANDO SINCRONIZACIÓN ---
[INFO] No hay operaciones pendientes en la cola local.
[1/1] Descargando catálogo actualizado desde el servidor...
[sync] Catálogo sincronizado: 4 productos.

[ÉXITO] Catálogo actualizado correctamente.

=== SISTEMA DE CAJA (POS OFFLINE-FIRST) ===
1. Sincronizar
2. Ver catálogo
3. Vender
4. Ver cola
5. Salir

Seleccione una opción (1-5): 3

--- NUEVA VENTA ---
Ingrese código de barras directamente, o '#ID' para buscar por ID.
Presione Enter sin texto o escriba 'FIN' para finalizar la carga.

Código de barras o #ID (o FIN para terminar): #4
-> Encontrado: Pan Criollo (kg) (ID 4) | Precio: $90.00 | Stock local: 15.000
   Cantidad a vender: 1
   [+] Agregado: Pan Criollo (kg) x 1.000

Código de barras o #ID (o FIN para terminar): FIN

=================================================================
RESUMEN DE LA VENTA
-----------------------------------------------------------------
Producto                       Cantidad     Precio Unit. Subtotal
-----------------------------------------------------------------
Pan Criollo (kg)               1.000        $90.00       $90.00
-----------------------------------------------------------------
TOTAL A COBRAR:                                         $90.00
=================================================================

¿Confirmar venta y descontar stock? (s/n): s

[ÉXITO] Venta registrada con éxito.
Venta encolada con UUID: eca41114-885b-4584-a7c8-e142baade794 (Estado: pending)

=== SISTEMA DE CAJA (POS OFFLINE-FIRST) ===
1. Sincronizar
2. Ver catálogo
3. Vender
4. Ver cola
5. Salir

Seleccione una opción (1-5): 4

================================================================================
ID    Hora Local           Estado             Ítems    UUID (primeros 8)
--------------------------------------------------------------------------------
1     2026-11-04 17:34:06  pending            1        eca41114
================================================================================

=== SISTEMA DE CAJA (POS OFFLINE-FIRST) ===
1. Sincronizar
2. Ver catálogo
3. Vender
4. Ver cola
5. Salir

Seleccione una opción (1-5): 1

--- INICIANDO SINCRONIZACIÓN ---
[1/2] Enviando 1 operación(es) pendiente(s) al servidor...

--- RESUMEN DE COLA PROCESADA ---
Operaciones enviadas en esta sincronización: 1
  - Confirmadas: 0
  - Rechazadas por servidor: 1
  - Error de formato (422): 0

[2/2] Descargando catálogo actualizado desde el servidor...
[sync] Catálogo sincronizado: 4 productos.

[ÉXITO] Sincronización completada.
- Catálogo local actualizado exitosamente con los precios y stock del servidor.

=== SISTEMA DE CAJA (POS OFFLINE-FIRST) ===
1. Sincronizar
2. Ver catálogo
3. Vender
4. Ver cola
5. Salir

Seleccione una opción (1-5): 4

================================================================================
ID    Hora Local           Estado             Ítems    UUID (primeros 8)
--------------------------------------------------------------------------------
1     2026-11-04 17:34:06  rejected           1        eca41114
================================================================================
```

---

## 5. Decisiones de Diseño

### 5.1. Servidor Central
- **Ventas inmutables (Sin `PUT` ni `DELETE`):** En un sistema contable y de auditoría, las ventas son registros de solo adición (*append-only*). No se permite modificar ni borrar una venta realizada. Cualquier corrección o anulación debe registrarse como una transacción compensatoria independiente.
- **Precio unitario congelado en `SaleDetail`:** Cada detalle de venta almacena el `unit_price` exacto con el que se cobró el producto. Si el precio del artículo cambia en el futuro en la tabla `products`, el histórico de ventas pasadas conserva el valor monetario real original.
- **Validación de stock acumulado:** Si una venta incluye múltiples líneas del mismo producto (por ejemplo, dos pesajes sucesivos de mercadería fraccionable), el servidor totaliza la cantidad pedida por `product_id` antes de contrastarla contra el inventario disponible.
- **Idempotencia por `operation_uuid`:** Para evitar duplicación de ventas ante reintentos de red, el servidor consulta por `operation_uuid`. Si la operación ya fue procesada, retorna la fila existente sin volver a descontar stock ni duplicar registros.
- **Transacción atómica unificada:** Tanto `create_sale` como `create_pending_operation` agrupan la creación de `Sale`, sus `SaleDetail`, el descuento de stock y la confirmación de la operación en una única transacción con un solo `commit()`. Utilizan `db.flush()` intermedio para resolver claves foráneas y `db.rollback()` ante cualquier falla, garantizando consistencia total sin registros a medias.

### 5.2. Terminal de Caja
- **Fail-Fast en configuración:** Variables críticas como `CASH_REGISTER_ID` y `USER_ID` no poseen valores por defecto. Si faltan en el `.env` o no son enteros válidos, la aplicación falla ruidosamente al inicio antes de operar.
- **`USER_ID` en v1:** Identifica a la terminal física ante el servidor para permitir operar de forma autónoma sin exigir un login de usuario por sesión que requeriría validar credenciales contra un servidor remoto potencialmente caído.
- **Precisión monetaria y de peso:** Uso exclusivo de `Decimal` en memoria y persistencia como `String` en SQLite y payloads JSON. El tipo `float` está prohibido para evitar pérdida de centavos y fracciones de gramo.
- **Transacción atómica única en venta:** El descuento de stock local y la inserción de la `PendingOperation` se realizan en la misma transacción SQLite, con un único `commit()` y `rollback()` explícito ante cualquier excepción.
- **Protección de catálogo (El problema de la leche):** `download_catalog()` aborta inmediatamente si detecta operaciones en estado `pending` en la cola local. De no hacerlo, el stock del servidor (que aún no computó las ventas locales no sincronizadas) sobreescribiría el stock local con valores ficticios más altos.
- **Búsqueda explícita de artículos:** Se ingresa directamente el código de barras (`barcode`), o bien `#ID` anteponiendo `#` para artículos sin código (S/C). Esto evita colisiones silenciosas entre códigos de barras numéricos cortos y números de ID.
- **Unicidad de códigos de barras:** La unicidad de `barcode` (`unique=True`) es garantizada por el modelo en el servidor central (PostgreSQL). Como la base local es una réplica descargada, la caja consulta por `.first()` sin necesidad de redundancias de validación.

---

## 6. Limitaciones Conocidas y Deuda Técnica (v1)

1. **Resolución de conflictos: Gana el primero en llegar al servidor (First-to-Arrive):** Las ventas no se ordenan según el timestamp de ocurrencia (`occurred_at`). Si la Caja A vende a las 14:00 offline y la Caja B vende a las 14:15 online, cuando la Caja B comunique primero consumirá el stock central. Al sincronizar más tarde, la venta de la Caja A será rechazada por el servidor.
2. **Ventas rechazadas (`rejected`):** Una venta `rejected` significa que la mercadería física ya fue entregada al cliente offline, pero el servidor no pudo asentar la transacción (por falta de stock central o datos inválidos). Requiere conciliación administrativa manual; en v1 no existe resolución automática.
3. **Peligro al borrar `caja.db` con cola pendiente:** Si la base local se borra mientras contiene operaciones `pending`, esas ventas no existen en ningún otro lugar y se perderán de forma definitiva e irrecuperable.
4. **Discrepancia de precios offline:** El cajero cobra al cliente el precio del catálogo local al momento de la venta. Si un precio se actualizó en el servidor mientras la caja operaba offline, el servidor registrará la venta con el precio vigente en el servidor al momento de la sincronización. En v2 se resolverá incluyendo el precio unitario pactado dentro del payload de la operación.
5. **Autenticación preliminar:** El endpoint `/login` verifica contraseñas con bcrypt, pero no emite tokens JWT ni protege los demás endpoints en v1.
6. **Productos borrados en el servidor:** No se eliminan de la base local en v1 por el costo y complejidad de implementar y auditar un borrado diferencial seguro.
7. **Concurrencia en chequeo de stock en servidor:** El endpoint no utiliza bloqueo pesimista (`SELECT ... FOR UPDATE`) al verificar `product.stock`, lo que podría generar una condición de carrera si dos terminales sincronizan en el mismo milisegundo.
8. **Mensaje venenoso en la cola de sincronización:** Si una operación `pending` provoca sistemáticamente un error 500 en el servidor (por ejemplo, un dato que dispara un bug del endpoint), `sync_pending` corta el bucle de envío ante cualquier respuesta inesperada. Como `download_catalog` no se ejecuta mientras queden operaciones `pending`, **una sola operación defectuosa bloquea indefinidamente la descarga del catálogo y el procesamiento de todas las ventas encoladas detrás**. En v2 se resolverá contando los intentos fallidos por operación y marcándola como `format_error` después de N reintentos, para que el resto de la cola siga fluyendo.
