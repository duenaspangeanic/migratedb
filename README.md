Aquí tienes el **README.md completo** listo para copiar y pegar en tu proyecto 👇  

```markdown
# 🛠️ Proyecto de Migración de Bases de Datos MySQL

Este proyecto permite migrar bases de datos completas desde un servidor **origen** hacia un servidor **destino**, asegurando que:

- La estructura de las tablas se mantiene idéntica al origen.
- Los datos se copian preservando los IDs originales.
- Se aplican reglas de reemplazo dinámicas en columnas específicas.
- Los índices (`AUTO_INCREMENT`) se ajustan automáticamente a **≥ 50 000** después de la migración.
- Se genera un **reporte JSON y CSV** con trazabilidad de índices y reemplazos aplicados.

---

## 📂 Estructura del proyecto

```

.
├── migrate.py             # Script principal de migración
├── .env                   # Configuración de conexiones y reglas
├── requirements.txt       # Dependencias del proyecto
├── .gitignore             # Archivos ignorados en Git
└── README.md              # Documentación del proyecto

```

---

## ⚙️ Configuración

Crea un archivo `.env` en la raíz del proyecto con el siguiente contenido:

```env
# Conexión origen
SOURCE_HOST=192.168.1.10
SOURCE_PORT=3306
SOURCE_USER=root
SOURCE_PASSWORD=clave_origen

# Conexión destino
TARGET_HOST=192.168.1.20
TARGET_PORT=3306
TARGET_USER=root
TARGET_PASSWORD=clave_destino

# Lista de bases a migrar (separadas por coma)
DATABASES=bd1,bd2

# Reglas de migración
# Formato: DB|TABLE|COLUMN|ORIGINAL|REPLACEMENT
# Si ORIGINAL está vacío, se reemplaza todo el contenido de la columna por REPLACEMENT
MIGRATION_RULE_1=Relay|files|notifilink|https://eco.pangeanic.com|http://localhost
MIGRATION_RULE_2=Relay|files|description||TextoNuevo
MIGRATION_RULE_3=Relay|logs|message|error,critical|warning,important
```

👉 Notas sobre las reglas:

- `ORIGINAL` vacío → reemplazo total del contenido por `REPLACEMENT`.
- `ORIGINAL` con valor → reemplazo parcial de coincidencias.

---

## 🐍 Instalación

### 1. Crear entorno virtual

```bash
python3 -m venv venv
```

### 2. Activar entorno

- **Linux/macOS**:

  ```bash
  source venv/bin/activate
  ```

- **Windows (PowerShell)**:

  ```powershell
  venv\Scripts\Activate.ps1
  ```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## ▶️ Ejecución

Ejecuta el script principal:

```bash
python migrate.py
```

El proceso realizará:

1. **DROP DATABASE IF EXISTS** en el destino.  
2. **CREATE DATABASE** con el mismo nombre.  
3. **DROP TABLE IF EXISTS** y recreación de cada tabla con `SHOW CREATE TABLE`.  
4. Migración de datos con aplicación de reglas de reemplazo.  
5. Ajuste de índices (`AUTO_INCREMENT`) a **50 000** si quedaron por debajo.  
6. Generación de **reportes JSON y CSV** con trazabilidad de índices y reemplazos.

---

## 📊 Logs

Durante la ejecución verás:

- Progreso de migración por tabla (con porcentaje).  
- Progreso global de todas las filas migradas.  
- Mensajes de recreación de bases y tablas.  
- Ajustes de índices con valores antes y después.  
- Conteo de reemplazos aplicados por cada regla.  

Ejemplo:

```
🚀 Migrando base: bd1
🗑️ Eliminando tabla files en destino si existe...
📐 Tabla files recreada en destino
📊 Tabla files: 12000 filas a migrar
   → Tabla files: 1200/12000 (10.0%)
🌍 Progreso global: 1200/35000 (3.4%)
...
✅ Migración de tabla files completada
🔧 Ajustando índices en base: bd1
   → Tabla files: índice 340 → ajustando a 50000
✅ Índices ajustados en bd1

📄 Reporte generado: migration_report.json, migration_report.csv
🎉 Migración finalizada con reporte
```

---

## 📄 Reportes generados

- **migration_report.json** → detalle de cada tabla y reglas aplicadas.  
- **migration_report.csv** → índices finales por tabla.  

Ejemplo JSON:

```json
{
    "tables": [
        {"database": "bd1", "table": "files", "auto_increment": 50000},
        {"database": "bd1", "table": "logs", "auto_increment": 50234}
    ],
    "rules": [
        {"database": "Relay", "table": "files", "column": "notifilink", "original": "https://eco.pangeanic.com", "replacement": "http://localhost", "replacements_done": 12000},
        {"database": "Relay", "table": "files", "column": "description", "original": "", "replacement": "TextoNuevo", "replacements_done": 12000}
    ]
}
```
