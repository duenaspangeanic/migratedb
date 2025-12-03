# 🛠️ Migración MySQL/MariaDB

Este proyecto automatiza la migración de bases de datos entre servidores **MariaDB → MariaDB** y **MySQL → MySQL**, aplicando reglas de transformación de datos, recreando índices y generando reportes finales.  
También puede usarse en migraciones cruzadas (MariaDB ↔ MySQL), con precaución en tipos de datos y collations.

---

## 🚀 Características principales

- **Recreación de bases y tablas** en el destino, eliminando previamente si existen.
- **Migración de datos** con aplicación de reglas definidas en `.env`.
- **Validación de reglas antes de migrar**: si alguna apunta a una tabla o columna inexistente, el proceso se detiene mostrando el error.
- **Manejo de foreign keys en dos fases**:
  - Fase 1: creación de tablas sin FKs.
  - Fase 2: adición de FKs con `ALTER TABLE`.
- **Ajuste automático de índices AUTO_INCREMENT** según valor configurado en `.env` (por defecto 800000).
- **Generación de reportes JSON y CSV** con:
  - Tablas migradas y sus índices.
  - Reglas aplicadas y número de reemplazos.
  - Foreign keys añadidas o fallidas.
- **Compatibilidad multiplataforma**: funciona en Windows y Linux.

## ⚙️ Configuración

En el archivo `.env` define:

```env
# Conexión origen
SOURCE_HOST=localhost
SOURCE_PORT=3306
SOURCE_USER=root
SOURCE_PASSWORD=1234

# Conexión destino
TARGET_HOST=localhost
TARGET_PORT=3306
TARGET_USER=root
TARGET_PASSWORD=1234

# Bases a migrar
DATABASES=dev_pgweb,dev_eco

# Reglas de migración
MIGRATION_RULE_1=dev_pgweb|files|notiflink||notification_link
MIGRATION_RULE_2=dev_eco|users|email|old.com|new.com

# Configuración adicional
AUTO_INCREMENT_MIN=800000
REPORTS_PATH=C:/Users/ale/Desktop/reports   # Ejemplo Windows
# REPORTS_PATH=/home/alejandro/reports      # Ejemplo Linux
```

Formato de reglas:

```
MIGRATION_RULE_X = db | tabla | columna | original | replacement
```

- `db`: nombre de la base.
- `tabla`: nombre de la tabla.
- `columna`: nombre de la columna.
- `original`: valor a reemplazar (vacío = reemplazo directo).
- `replacement`: nuevo valor.

---

## 📂 Carpeta de reportes

- Si `REPORTS_PATH` está definido:
  - El script verifica la carpeta y la crea automáticamente si no existe.
  - Los reportes se guardan en esa ruta.
- Si **no** está definido:
  - Los reportes se guardan en el mismo directorio del script.
- Los nombres de archivo incluyen la **fecha/hora** para evitar sobrescribir:

  ```
  migration_report_20251203_095800.json
  migration_report_20251203_095800.csv
  ```

---

## ▶️ Ejecución

1. Instala dependencias:

```bash
pip install mysql-connector-python python-dotenv
```

2. Ejecuta el script:

```bash
python migrate.py
```

3. El proceso:
   - Valida reglas.
   - Recrea bases y tablas.
   - Migra datos aplicando reglas.
   - Ajusta índices.
   - Añade foreign keys.
   - Genera reportes.

---

## 📊 Reportes

- **migration_report_YYYYMMDD_HHMMSS.json**: detalle completo de tablas, reglas y foreign keys.
- **migration_report_YYYYMMDD_HHMMSS.csv**: resumen de tablas y valores AUTO_INCREMENT.

---

## ✅ Validación de reglas

Antes de migrar, el script valida que cada regla apunte a una base, tabla y columna existente.  
Si alguna es inválida:

```
❌ Se encontraron reglas inválidas, abortando migración:
 - dev_pgweb.files.notifilink: Columna notifilink no existe en dev_pgweb.files
```

El proceso se detiene inmediatamente (`exit(1)`).

---

## 🎉 Resultado

Un flujo de migración **robusto, reproducible y seguro**, con validación previa de reglas, configuración flexible desde `.env` y reportes finales para trazabilidad.

