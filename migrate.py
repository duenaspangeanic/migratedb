import os
import mysql.connector
from dotenv import load_dotenv
import json
import csv

load_dotenv()  # carga variables desde .env

def parse_rules():
    rules = []
    for key, value in os.environ.items():
        if key.startswith("MIGRATION_RULE_"):
            parts = value.strip().split("|")
            if len(parts) == 5:
                rules.append({
                    "db": parts[0],
                    "table": parts[1],
                    "column": parts[2],
                    "original": parts[3],
                    "replacement": parts[4],
                    "replacements_done": 0  # contador de reemplazos
                })
            else:
                print(f"⚠️ Regla mal formada: {value}")
    return rules

def get_env_list(var_name):
    val = os.getenv(var_name, "")
    return [x.strip() for x in val.split(",") if x.strip()]

def connect_db(prefix):
    return mysql.connector.connect(
        host=os.getenv(f"{prefix}_HOST"),
        port=int(os.getenv(f"{prefix}_PORT")),
        user=os.getenv(f"{prefix}_USER"),
        password=os.getenv(f"{prefix}_PASSWORD"),
        database=""  # se cambia dinámicamente
    )

def recreate_database(target_conn, dbname):
    tgt_cur = target_conn.cursor()
    print(f"\n🗑️ Eliminando base {dbname} en destino si existe...")
    tgt_cur.execute(f"DROP DATABASE IF EXISTS {dbname}")
    tgt_cur.execute(f"CREATE DATABASE {dbname}")
    tgt_cur.execute(f"USE {dbname}")
    tgt_cur.close()
    print(f"📐 Base {dbname} recreada en destino")

def migrate_db(source_conn, target_conn, dbname, rules, total_rows_global, processed_rows_global):
    print(f"\n🚀 Migrando base: {dbname}")
    src_cur = source_conn.cursor(dictionary=True)
    tgt_cur = target_conn.cursor()

    src_cur.execute(f"USE {dbname}")
    tgt_cur.execute(f"USE {dbname}")

    src_cur.execute("SHOW TABLES")
    tables = [row[f"Tables_in_{dbname}"] for row in src_cur.fetchall()]

    for table in tables:
        print(f"\n🗑️ Eliminando tabla {table} en destino si existe...")
        tgt_cur.execute(f"DROP TABLE IF EXISTS {table}")

        # Crear tabla destino con misma estructura
        src_cur.execute(f"SHOW CREATE TABLE {table}")
        create_stmt = src_cur.fetchone()["Create Table"]
        tgt_cur.execute(create_stmt)
        print(f"📐 Tabla {table} recreada en destino")

        # Contar filas
        src_cur.execute(f"SELECT COUNT(*) as total FROM {table}")
        total_rows = src_cur.fetchone()["total"]
        total_rows_global[0] += total_rows
        print(f"📊 Tabla {table}: {total_rows} filas a migrar")

        # Seleccionar todas las filas
        src_cur.execute(f"SELECT * FROM {table}")
        rows = src_cur.fetchall()

        for idx, row in enumerate(rows, start=1):
            # Aplicar reglas si existen
            for rule in [r for r in rules if r["db"] == dbname and r["table"] == table]:
                col = rule["column"]
                if rule["original"] == "":
                    row[col] = rule["replacement"]
                    rule["replacements_done"] += 1
                else:
                    if row[col] and rule["original"] in str(row[col]):
                        row[col] = str(row[col]).replace(rule["original"], rule["replacement"])
                        rule["replacements_done"] += 1

            # Insertar fila con IDs originales
            cols = ", ".join(row.keys())
            vals = ", ".join(["%s"] * len(row))
            tgt_cur.execute(
                f"INSERT INTO {table} ({cols}) VALUES ({vals})",
                list(row.values())
            )

            processed_rows_global[0] += 1

            # Log progreso tabla
            if idx % max(1, total_rows // 10) == 0 or idx == total_rows:
                percent = (idx / total_rows) * 100
                print(f"   → Tabla {table}: {idx}/{total_rows} ({percent:.1f}%)")

            # Log progreso global
            if processed_rows_global[0] % max(1, total_rows_global[0] // 20) == 0 or processed_rows_global[0] == total_rows_global[0]:
                percent_global = (processed_rows_global[0] / total_rows_global[0]) * 100
                print(f"🌍 Progreso global: {processed_rows_global[0]}/{total_rows_global[0]} ({percent_global:.1f}%)")

        target_conn.commit()
        print(f"✅ Migración de tabla {table} completada")

    src_cur.close()
    tgt_cur.close()

def adjust_indexes(target_conn, dbname):
    print(f"\n🔧 Ajustando índices en base: {dbname}")
    tgt_cur = target_conn.cursor(dictionary=True)
    tgt_cur.execute(f"USE {dbname}")
    tgt_cur.execute("SHOW TABLES")
    tables = [row[f"Tables_in_{dbname}"] for row in tgt_cur.fetchall()]

    for table in tables:
        tgt_cur.execute("""
            SELECT AUTO_INCREMENT
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """, (dbname, table))
        result = tgt_cur.fetchone()

        if result and result["AUTO_INCREMENT"]:
            current_index = result["AUTO_INCREMENT"]
            if current_index < 50000:
                print(f"   → Tabla {table}: índice {current_index} → ajustando a 50000")
                tgt_cur.execute(f"ALTER TABLE {table} AUTO_INCREMENT = 50000")
            else:
                print(f"   → Tabla {table}: índice ya >= 50000 ({current_index}), no se cambia")

    target_conn.commit()
    tgt_cur.close()
    print(f"✅ Índices ajustados en {dbname}")

def generate_report(target_conn, databases, rules, output_json="migration_report.json", output_csv="migration_report.csv"):
    report_data = []

    tgt_cur = target_conn.cursor(dictionary=True)

    for dbname in databases:
        tgt_cur.execute(f"USE {dbname}")
        tgt_cur.execute("SHOW TABLES")
        tables = [row[f"Tables_in_{dbname}"] for row in tgt_cur.fetchall()]

        for table in tables:
            tgt_cur.execute("""
                SELECT AUTO_INCREMENT
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """, (dbname, table))
            result = tgt_cur.fetchone()
            auto_inc = result["AUTO_INCREMENT"] if result else None

            report_data.append({
                "database": dbname,
                "table": table,
                "auto_increment": auto_inc
            })

    tgt_cur.close()

    # Añadir reglas y conteo de reemplazos
    rules_report = [
        {
            "database": r["db"],
            "table": r["table"],
            "column": r["column"],
            "original": r["original"],
            "replacement": r["replacement"],
            "replacements_done": r["replacements_done"]
        }
        for r in rules
    ]

    final_report = {
        "tables": report_data,
        "rules": rules_report
    }

    # Guardar JSON
    with open(output_json, "w", encoding="utf-8") as fjson:
        json.dump(final_report, fjson, indent=4, ensure_ascii=False)

    # Guardar CSV (solo tablas)
    with open(output_csv, "w", newline="", encoding="utf-8") as fcsv:
        writer = csv.DictWriter(fcsv, fieldnames=["database", "table", "auto_increment"])
        writer.writeheader()
        writer.writerows(report_data)

    print(f"\n📄 Reporte generado: {output_json}, {output_csv}")

if __name__ == "__main__":
    source_conn = connect_db("SOURCE")
    target_conn = connect_db("TARGET")

    databases = get_env_list("DATABASES")
    rules = parse_rules()

    total_rows_global = [0]      # contador total de filas
    processed_rows_global = [0]  # contador procesadas

    for db in databases:
        recreate_database(target_conn, db)
        migrate_db(source_conn, target_conn, db, rules, total_rows_global, processed_rows_global)
        adjust_indexes(target_conn, db)

    generate_report(target_conn, databases, rules)

    source_conn.close()
    target_conn.close()
    print("\n🎉 Migración finalizada con reporte")