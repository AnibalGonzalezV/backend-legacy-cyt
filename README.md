# Sistema de Planificación de Vendimia (Backend Legacy 2024) - Viña Concha y Toro

Este repositorio contiene la versión **Legacy original (2024)** del backend del Sistema de Apoyo a la Toma de Decisiones (DSS) para la programación de patio y vendimia de Viña Concha y Toro. 

El modelo utiliza Programación Lineal Entera Mixta (MILP) bajo una representación de Red Estado-Tarea (STN) formulada en **Pyomo** y resuelta con el motor matemático **CBC**. La orquestación del servicio se realiza mediante **Django REST Framework**.

## Requisitos Previos

- Python 3.10 o superior (Recomendado 3.10/3.11).
- Solver **CBC** instalado localmente o disponible en la ruta especificada.

## Instrucciones de Instalación y Ejecución

Sigue estos pasos para inicializar el proyecto en tu máquina local:

### 1. Clonar el repositorio
\\\ash
git clone https://github.com/AnibalGonzalezV/backend-legacy-cyt.git
cd backend-legacy-cyt
\\\

### 2. Crear y activar un Entorno Virtual
Se recomienda utilizar un entorno virtual aislado para evitar conflictos de dependencias.
\\\ash
# En Windows
python -m venv venv
.\venv\Scripts\activate

# En Linux/Mac
python3 -m venv venv
source venv/bin/activate
\\\

### 3. Instalar las dependencias
Asegúrate de instalar todas las librerías necesarias. (Nota: Es posible que necesites tener herramientas de compilación C++ dependiendo de la versión de Pandas o Pyomo).
\\\ash
pip install -r requirements.txt
\\\
*(Si no existe el archivo equirements.txt, instala manualmente: pip install django djangorestframework django-cors-headers pyomo pandas numpy reportlab matplotlib fpdf pypdf2 openpyxl)*

### 4. Ejecutar el Servidor de Django
El orquestador levantará una API REST local en el puerto 8000.
\\\ash
python manage.py runserver
\\\

### 5. Estructura de Entradas (Archivos de Excel)
El core matemático lee directamente de archivos .xlsx ubicados en la carpeta dssProject/Modelo_matemático/. Para que el modelo corra correctamente, asegúrate de tener:
- settings.xlsx: Configuraciones y capacidades base de la planta.
- Programa Vendimia 2024.xlsx (o similar): Proyección logística de camiones.

Al gatillar el endpoint correspondiente desde el Frontend, el modelo ejecutará Pyomo, inyectará los datos, llamará a CBC, y escribirá los resultados físicamente en un archivo Resultados_planificación.xlsx y diversos reportes en PDF.
