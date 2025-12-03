# 🛠️ Proyecto de Migración MySQL/MariaDB

Este proyecto automatiza la migración de bases de datos entre servidores MySQL/MariaDB, aplicando reglas de transformación de datos, recreando índices y generando reportes finales.

---

## 🚀 Características principales

- **Recreación de bases y tablas** en el destino, eliminando previamente si existen.
- **Migración de datos** con aplicación de reglas definidas en `.env`.
- **Validación de reglas antes de migrar**: si alguna apunta a una tabla o columna inexistente, el proceso se detiene mostrando el error.
- **Manejo de foreign keys** en dos fases:
  - Fase 1: creación de tablas sin FKs.
  - Fase 2: adición de FKs con `ALTER TABLE`.
- **Ajuste automático de índices AUTO_INCREMENT** (mínimo 50,000).
- **Generación de reportes JSON y CSV** con:
  - Tablas migradas y sus índices.
  - Reglas aplicadas y número de reemplazos.
  - Foreign keys añadidas o fallidas.

---

## 📂 Estructura del proyecto

```
migrate.py        # Script principal
.env              # Variables de entorno (conexiones y reglas)
migration_report.json  # Reporte detallado en JSON
migration_report.csv   # Reporte resumido en CSV
```

---

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

- **migration_report.json**: detalle completo de tablas, reglas y foreign keys.
- **migration_report.csv**: resumen de tablas y valores AUTO_INCREMENT.

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

Un flujo de migración **robusto, reproducible y seguro**, con validación previa de reglas y reportes finales para trazabilidad.
