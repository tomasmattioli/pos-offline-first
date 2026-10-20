# POS Offline-First

Sistema de punto de venta offline-first compuesto por un **servidor central** (FastAPI + PostgreSQL) y una o más terminales de **caja** (SQLite + SQLAlchemy).

## Arquitectura y Decisiones de Diseño

### 1. Modelo de Identificación (`CASH_REGISTER_ID` y `USER_ID`)
- `CASH_REGISTER_ID`: Identifica unívocamente la terminal física ante el servidor central.
- `USER_ID`: En la versión 1 (v1), **`USER_ID` identifica a la caja/terminal en el servidor**, no a la persona física que atiende. La caja opera de forma autónoma y offline sin requerir autenticación de usuario por sesión contra el servidor (lo cual impediría vender si la caja inicia sin conexión).

### 2. Sincronización y Catálogo (`sync.py`)
- **Protección de cola pendiente:** `download_catalog()` aborta inmediatamente si detecta operaciones en estado `pending` en la cola local. De no hacerlo, sobreescribiría el stock local con el del servidor, el cual aún no refleja las ventas locales no sincronizadas.
- **Limitación en productos eliminados (v1):** Los productos borrados en el servidor no se eliminan de la base local en v1. Esto se definió así por el costo de desarrollo y pruebas de un algoritmo de borrado diferencial robusto, y no por riesgo de concurrencia con operaciones pendientes (dado que `download_catalog` aborta si hay pendientes).
- **Idempotencia:** Cada operación genera un `operation_uuid` único en la caja (`PendingOperation`). Si una solicitud se procesa en el servidor pero la respuesta se pierde por un corte de red, el reintento de la caja enviará el mismo UUID y el servidor devolverá el estado ya confirmado sin duplicar ventas ni descontar stock extra.

### 3. Registro de Ventas Locales (`sales.py`)
- **Validación atómica:** Se valida que las cantidades sean mayores a 0, que los productos existan y que la suma acumulada por producto no supere el stock local disponible.
- **Precisión monetaria y de stock:** Se utiliza `Decimal` para todos los cálculos. Para la serialización en JSON del payload (`PendingOperation`), las cantidades se convierten a texto (`str`), formato que el schema Pydantic del servidor interpreta como `Decimal` exacto sin pérdida de precisión de punto flotante.
- **Transacción única:** La deducción de stock y la creación de la `PendingOperation` se realizan en la misma transacción SQLite con un único `commit` y `rollback` explícito ante cualquier falla.
