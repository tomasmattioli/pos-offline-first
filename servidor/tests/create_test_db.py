import os
from urllib.parse import urlparse
import psycopg2

test_db_url = os.environ.get("TEST_DB_URL")
if test_db_url:
    parsed = urlparse(test_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    password = parsed.password or ""
    dbname = parsed.path.lstrip("/") or "pos_central_test"
else:
    host = os.environ.get("PGHOST", "localhost")
    port = int(os.environ.get("PGPORT", 5432))
    user = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("PGPASSWORD", "")
    dbname = "pos_central_test"

conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname="postgres")
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
if not cur.fetchone():
    cur.execute(f'CREATE DATABASE "{dbname}"')
    print(f"Base de datos {dbname} creada.")
else:
    print(f"Base de datos {dbname} ya existe.")
conn.close()
