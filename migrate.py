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
        connection_timeout=600,   # tiempo máximo de espera en segundos
        #connection_attempts=2,    # reintentos
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

def migrate_db(source_conn, target_conn, dbname, rules, total_rows_global, processed_rows_global, fk_report):
    print(f"\n🚀 Migrando base: {dbname}")
    src_cur = source_conn.cursor(dictionary=True)
    tgt_cur = target_conn.cursor()

    src_cur.execute(f"USE `{dbname}`")
    tgt_cur.execute(f"USE `{dbname}`")

    src_cur.execute("SHOW TABLES")
    tables = [row[f"Tables_in_{dbname}"] for row in src_cur.fetchall()]

    fk_constraints = []  # almacenamos las foreign keys para segunda fase

    # --- Fase 1: crear tablas sin FKs ---
    for table in tables:
        print(f"\n🗑️ Eliminando tabla {table} en destino si existe...")
        tgt_cur.execute(f"DROP TABLE IF EXISTS `{table}`")

        src_cur.execute(f"SHOW CREATE TABLE `{table}`")
        create_stmt = src_cur.fetchone()["Create Table"]

        # Extraer foreign keys y eliminarlas temporalmente
        lines = create_stmt.split("\n")
        new_lines = []
        for line in lines:
            if "FOREIGN KEY" in line:
                fk_constraints.append((table, line.strip().rstrip(",")))
            else:
                new_lines.append(line)

        # Quitar comas colgantes justo antes del cierre
        for i in range(len(new_lines) - 1):
            if new_lines[i].strip().endswith(",") and new_lines[i+1].strip().startswith(")"):
                new_lines[i] = new_lines[i].rstrip(",")

        create_stmt_no_fk = "\n".join(new_lines)

        # Debug opcional para verificar la sentencia final
        print(f"DEBUG CREATE TABLE {table}:\n{create_stmt_no_fk}")

        tgt_cur.execute(create_stmt_no_fk)
        print(f"📐 Tabla {table} recreada en destino (sin FKs)")

        # Migración de datos
        src_cur.execute(f"SELECT COUNT(*) as total FROM `{table}`")
        total_rows = src_cur.fetchone()["total"]
        total_rows_global[0] += total_rows
        print(f"📊 Tabla {table}: {total_rows} filas a migrar")

        src_cur.execute(f"SELECT * FROM `{table}`")
        rows = src_cur.fetchall()

        for idx, row in enumerate(rows, start=1):
            # Aplicar reglas
            for rule in [r for r in rules if r["db"] == dbname and r["table"] == table]:
                col = rule["column"]
                if rule["original"] == "":
                    row[col] = rule["replacement"]
                    rule["replacements_done"] += 1
                else:
                    if row[col] and rule["original"] in str(row[col]):
                        row[col] = str(row[col]).replace(rule["original"], rule["replacement"])
                        rule["replacements_done"] += 1

            # Insertar fila
            cols = ", ".join([f"`{c}`" for c in row.keys()])
            vals = ", ".join(["%s"] * len(row))
            tgt_cur.execute(
                f"INSERT INTO `{table}` ({cols}) VALUES ({vals})",
                list(row.values())
            )

            processed_rows_global[0] += 1

            if idx % max(1, total_rows // 10) == 0 or idx == total_rows:
                percent = (idx / total_rows) * 100
                print(f"   → Tabla {table}: {idx}/{total_rows} ({percent:.1f}%)")

            if processed_rows_global[0] % max(1, total_rows_global[0] // 20) == 0 or processed_rows_global[0] == total_rows_global[0]:
                percent_global = (processed_rows_global[0] / total_rows_global[0]) * 100
                print(f"🌍 Progreso global: {processed_rows_global[0]}/{total_rows_global[0]} ({percent_global:.1f}%)")

        target_conn.commit()
        print(f"✅ Migración de tabla {table} completada")

    # --- Fase 2: añadir FKs ---
    print(f"\n🔗 Añadiendo foreign keys en {dbname}...")
    for table, fk in fk_constraints:
        try:
            alter_stmt = f"ALTER TABLE `{table}` ADD {fk}"
            tgt_cur.execute(alter_stmt)
            fk_report.append({"database": dbname, "table": table, "fk": fk, "status": "added"})
            print(f"   → FK añadida en {table}: {fk}")
        except mysql.connector.Error as e:
            fk_report.append({"database": dbname, "table": table, "fk": fk, "status": f"failed: {e}"})
            print(f"⚠️ No se pudo añadir FK en {table}: {e}")

    target_conn.commit()
    print(f"✅ Foreign keys añadidas en {dbname}")

    src_cur.close()
    tgt_cur.close()

def adjust_indexes(target_conn, dbname):
    print(f"\n🔧 Ajustando índices en base: {dbname}")
    tgt_cur = target_conn.cursor(dictionary=True)
    tgt_cur.execute(f"USE `{dbname}`")
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
                try:
                    tgt_cur.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = 50000")
                except mysql.connector.Error as e:
                    print(f"⚠️ No se pudo ajustar índice en {table}: {e}")
            else:
                print(f"   → Tabla {table}: índice ya >= 50000 ({current_index}), no se cambia")

    target_conn.commit()
    tgt_cur.close()
    print(f"✅ Índices ajustados en {dbname}")



def generate_report(target_conn, databases, rules, fk_report, output_json="migration_report.json", output_csv="migration_report.csv"):
    report_data = []

    tgt_cur = target_conn.cursor(dictionary=True)

    for dbname in databases:
        tgt_cur.execute(f"USE `{dbname}`")
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
        "rules": rules_report,
        "foreign_keys": fk_report
    }

    with open(output_json, "w", encoding="utf-8") as fjson:
        json.dump(final_report, fjson, indent=4, ensure_ascii=False)

    with open(output_csv, "w", newline="", encoding="utf-8") as fcsv:
        writer = csv.DictWriter(fcsv, fieldnames=["database", "table", "auto_increment"])
        writer.writeheader()
        writer.writerows(report_data)

    print(f"\n📄 Reporte generado: {output_json}, {output_csv}")

def validate_rules(conn, rules):
    """
    Valida que cada regla apunte a una base, tabla y columna existente.
    Si encuentra reglas inválidas, las devuelve junto con las válidas.
    """
    cur = conn.cursor(dictionary=True)
    valid_rules = []
    invalid_rules = []

    for rule in rules:
        db = rule["db"]
        table = rule["table"]
        column = rule["column"]

        try:
            # Cambiar a la base indicada
            cur.execute(f"USE `{db}`")

            # Verificar si la tabla existe
            cur.execute("SHOW TABLES")
            tables = [row[f"Tables_in_{db}"] for row in cur.fetchall()]
            if table not in tables:
                invalid_rules.append({**rule, "error": f"Tabla {table} no existe en {db}"})
                continue

            # Verificar si la columna existe
            cur.execute(f"SHOW COLUMNS FROM `{table}`")
            cols = [row["Field"] for row in cur.fetchall()]
            if column not in cols:
                invalid_rules.append({**rule, "error": f"Columna {column} no existe en {db}.{table}"})
                continue

            # Si pasa todas las validaciones
            valid_rules.append(rule)

        except mysql.connector.Error as e:
            invalid_rules.append({**rule, "error": str(e)})

    cur.close()
    return valid_rules, invalid_rules


if __name__ == "__main__":
    source_conn = connect_db("SOURCE")
    target_conn = connect_db("TARGET")

    databases = get_env_list("DATABASES")
    rules = parse_rules()

    # Validar reglas
    valid_rules, invalid_rules = validate_rules(source_conn, rules)
    if invalid_rules:
        print("\n❌ Se encontraron reglas inválidas, abortando migración:")
        for r in invalid_rules:
            print(f" - {r['db']}.{r['table']}.{r['column']}: {r['error']}")
        source_conn.close()
        target_conn.close()
        exit(1)  # detener ejecución inmediatamente

    # Usar solo las válidas
    rules = valid_rules

    total_rows_global = [0]
    processed_rows_global = [0]
    fk_report = []

    for db in databases:
        recreate_database(target_conn, db)
        migrate_db(source_conn, target_conn, db, rules, total_rows_global, processed_rows_global, fk_report)
        adjust_indexes(target_conn, db)

    generate_report(target_conn, databases, rules, fk_report)

    source_conn.close()
    target_conn.close()
    print("\n🎉 Migración finalizada con reporte")