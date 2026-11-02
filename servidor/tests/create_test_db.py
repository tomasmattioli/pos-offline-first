import psycopg2

conn = psycopg2.connect(host="localhost", port=5432, user="postgres", password="usuario", dbname="postgres")
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = 'pos_central_test'")
if not cur.fetchone():
    cur.execute("CREATE DATABASE pos_central_test")
    print("Base de datos pos_central_test creada.")
else:
    print("Base de datos pos_central_test ya existe.")
conn.close()
