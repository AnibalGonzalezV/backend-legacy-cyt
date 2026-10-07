# Sistema de Planificación de Vendimia - Viña Concha y Toro (Backend Legacy 2024)

Este repositorio contiene el código fuente correspondiente al backend del Sistema de Apoyo a la Toma de Decisiones (DSS) para la programación logística de patio y vendimia de Viña Concha y Toro.

El modelo subyacente utiliza Programación Lineal Entera Mixta (MILP), formulado mediante la librería **Pyomo** y resuelto a través del motor matemático **CBC**. La orquestación de los servicios y la exposición de los endpoints se realiza utilizando **Django REST Framework**.

---

## Requisitos Previos

- **Entorno de ejecución:** Python 3.10 o superior (Recomendado 3.10/3.11).
- **Herramientas de compilación:** Dependiendo del sistema operativo, podría requerirse un compilador de C++ nativo para la correcta instalación de librerías de manipulación de datos (e.g., `pandas`, `pyomo`).
- **Solver Matemático (CBC):** 
  - **Entornos Windows:** No requiere instalación adicional. El binario ejecutable (`cbc.exe`) se encuentra empaquetado en el repositorio y referenciado de forma estática en la configuración del modelo.
  - **Entornos UNIX (macOS / Linux):** Es estricto instalar el solver CBC a nivel de sistema operativo y asegurar que se encuentre en el PATH del sistema o modificar la referencia dentro del modelo.

---

## Instrucciones de Despliegue en Entorno Local

Para inicializar el entorno de desarrollo local, deben seguirse los pasos detallados a continuación. (Se ha corregido la dependencia hacia bases de datos cloud obsoletas, orientando la ejecución hacia una instancia local SQLite).

### 1. Configuración de Variables de Entorno
El servicio requiere la definición de variables de entorno estáticas para la inicialización del ORM y parámetros de seguridad. En el directorio raíz del proyecto (mismo nivel que el archivo `manage.py`), genere un archivo denominado `.env` con la siguiente configuración:

```env
DATABASE_URL=sqlite:///db.sqlite3
DEBUG=true
SECRET_KEY=clave_de_desarrollo_estandar
```

### 2. Generación del Entorno Virtual
Se requiere aislar las dependencias del proyecto. Ejecute los comandos correspondientes según su intérprete de comandos:

**Sistemas Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Sistemas UNIX (macOS / Linux):**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalación de Dependencias
Con el entorno virtual debidamente activado, instale los paquetes listados en el manifiesto. (El archivo `requirements.txt` ha sido estandarizado a codificación UTF-8 para garantizar su portabilidad).

```bash
pip install -r requirements.txt
```

### 4. Ejecución de Migraciones
Ejecute el motor de migraciones de Django para aprovisionar el esquema de base de datos relacional local (`db.sqlite3`). Este proceso inicializará las tablas necesarias correspondientes a las entidades del sistema (Maquinas, Mantenciones, Schedule).

```bash
python manage.py makemigrations dssProject
python manage.py migrate
```

### 5. Inicialización del Servidor de Desarrollo
Inicie el proceso del orquestador web. Por defecto, el servidor se vinculará a la interfaz local en el puerto 8000 (`http://127.0.0.1:8000`).

```bash
python manage.py runserver
```

---

## Flujo Arquitectónico y Lógica de Procesamiento

Para propósitos de mantenimiento y comprensión del equipo de TI, el ciclo de vida del procesamiento de datos se estructura de la siguiente manera:

1. **Ingesta de Archivos y Parseo Estructurado (`dssProject/Lectura/lectura.py`):**
   - El endpoint `/postFile` recepciona dos documentos: un reporte logístico de camiones (formato PDF) y el programa general de vendimia (formato Excel).
   - A través de los módulos `pdfplumber` y `pandas`, el motor raspa y vectoriza las tablas de datos.
   - La función `bridge_inputs()` ejecuta un cruce relacional (Match) fundamentado en el **Número de Contrato** y la **Variedad de Uva**. Al coincidir los registros entre ambas fuentes, el algoritmo le asigna un identificador de bloque logístico a cada camión.
   - El output intermedio consolida estos datos en un archivo transaccional denominado `input.xlsx`.

2. **Gatillado y Formulación de Optimización Matemática:**
   - La invocación al endpoint `/iniciarPlanificacion` inicializa la ejecución del script del modelo matemático (`modelo.py`).
   - El script captura las restricciones dinámicas, como la capacidad volumétrica y el estado habilitado/deshabilitado de la maquinaria (cuyos parámetros base se almacenan en `dssProject/Modelo_matemático/settings.xlsx`) e inyecta el `input.xlsx` generado en la etapa anterior.
   - Posteriormente, se construye una formulación MILP mediante la API de modelado **Pyomo**.

3. **Resolución:**
   - El grafo de operaciones y restricciones es enviado al binario matemático **CBC**, ejecutado localmente (`Pyomo/CBC/bin/cbc.exe`).

4. **Retorno de Resultados e IO:**
   - Una vez convergida una solución óptima o factible, el backend traduce el output matemático en un "Schedule" (Cronograma) de tareas.
   - El sistema persiste los resultados tabulares en la Base de Datos para consumo directo vía API y serializa reportes físicos en formato Excel (`Resultados_planificación.xlsx`) y proyecciones gráficas en formato PDF, almacenados dentro del sistema de archivos local para su descarga final.
