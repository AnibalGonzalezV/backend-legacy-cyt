"""#*def convertir_a_int(valor):
    if valor == 'SPK':
        return valor
    else:
        return int(valor)


"""
from datetime import datetime, timedelta, timezone
from datetime import date
import datetime as dt # Import datetime as dt
import PyPDF2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
import pandas as pd
from fpdf import FPDF
from PIL import Image
from PyPDF2 import PdfMerger
from datetime import datetime
import os
import re
import math
import pytz
from io import BytesIO
from pyomo.environ import *
from pyomo.opt import SolverFactory
from time import time
import shutil
import requests
import json
import glob
from matplotlib.patheffects import withStroke
import matplotlib.patches as mpl_patches

#--------------------
def modelo2(request=None, **kwargs):
    execute_visuals = kwargs.get('execute_visuals', True)
    df_machines_override = kwargs.get('df_machines', None)
    df_vendimia_override = kwargs.get('df_vendimia', None)
    df_camiones_override = kwargs.get('df_camiones', None)
    # --- Configuraciones Parametrizables ---
    # Limite de tiempo del solver en segundos
    TIME_LIMIT_SECONDS = 3600 
    # Gap permitido cuando la cantidad de camiones es alta (> 70)
    RATIO_GAP_HIGH = 10 
    # Gap permitido cuando la cantidad de camiones es baja (<= 70)
    RATIO_GAP_LOW = 5 
    # Porcentaje de capacidad mínima de las máquinas
    BMIN_FACTOR = 0.40 
    # ---------------------------------------

    def _discretize_hour(hour):
        """Discretiza la hora."""
        return np.ceil(hour) if (hour % 1 >= 0.5) else np.floor(hour)
    
    #--------------------------------------

    def _extract_data_from_json(data):
       """Extrae la información relevante del JSON."""
       extracted_data = []
       for item in data['viajes']:
         extracted_data.append({
             'Hr Bodega': item['Hora de llegada a bodega estimada'],
             'Productor': item['Productor'],
             'Fundo': item['Fundo origen'],
             'ID_Material': item['Codigo Material'],
             'Patente': item.get('Patente', 'Sin Patente'),
             'Kilos': item['Kilos programados'],
             'Estado': item['Estado\u00a0del\u00a0viaje'],
             'Fecha': current_date
         })
       return extracted_data

    def _fetch_data_from_api(current_date, url, user, password):
       """Realiza la solicitud a la API y maneja errores."""
       try:
         response = requests.get(url, auth=(user, password))
         response.raise_for_status()
         data = response.json()
         return _extract_data_from_json(data)
       except requests.exceptions.RequestException as e:
         print(f"An error occurred: {e}")
         return []
       except json.JSONDecodeError as e:
         print(f"Invalid JSON response: {e}")
         return []

    def fetch_data_from_api(current_date):
         import glob
         import os
         directory = "./dssProject/Modelo_matemático/"
         # Buscar todos los xlsx que no sean el de vendimia ni los de resultados
         archivos = glob.glob(os.path.join(directory, '*.xlsx'))
         archivos_camiones = [f for f in archivos if "vendimia" not in f.lower() and "resultado" not in f.lower() and "resumen" not in f.lower() and "input" not in f.lower() and "~" not in f]
         
         if not archivos_camiones:
             print("No se encontró ningún archivo de camiones.")
             return pd.DataFrame()
             
         # Ordenar por fecha de modificación
         archivos_camiones.sort(key=os.path.getmtime, reverse=True)
         file_path = archivos_camiones[0]
         print(f"Usando archivo de camiones: {file_path}")
         
         try:
             # Leemos el archivo estático
             df = pd.read_excel(file_path)
             
             # Usar el Día original del Excel si existe, sino simular con current_date
             if 'Día' in df.columns:
                 df['Fecha'] = pd.to_datetime(df['Día']).dt.strftime('%Y-%m-%d')
             elif 'Fecha' not in df.columns:
                 df['Fecha'] = current_date

             # Filtrar estrictamente por el current_date solicitado
             df = df[df['Fecha'] == current_date].copy()

             # Aseguramos que los tipos sean string para el cruce
             if 'CTTO' in df.columns:
                 df['CTTO'] = df['CTTO'].astype(str)
             if 'ID_Material' in df.columns:
                 df['ID_Material'] = df['ID_Material'].astype(str)
                 
             return df

         except Exception as e:
             print(f"An error occurred reading local file: {e}")
             return pd.DataFrame()

     # Get current date in YYYY-MM-DD format
    #current_date = date.today().strftime('%Y-%m-%d')
    current_date = '2024-03-18'
    current_date_dt = datetime.strptime(current_date, '%Y-%m-%d').date()

     # Calculate next_date by adding timedelta
    next_date = (current_date_dt + timedelta(days=1)).strftime('%Y-%m-%d')

    # Fetch data for current and next date
    df_c = fetch_data_from_api(current_date)
    df_n = fetch_data_from_api(next_date)

    # Create 'Hr Bodega Num' column
    if not df_c.empty:
        df_c['Hr Bodega Num'] = pd.to_datetime(df_c['Hr Bodega']).dt.hour + pd.to_datetime(df_c['Hr Bodega']).dt.minute / 60
    else:
        print("df_c is empty, skipping 'Hr Bodega Num' transformation.")

    if not df_n.empty:
        df_n['Hr Bodega Num'] = pd.to_datetime(df_n['Hr Bodega']).dt.hour + pd.to_datetime(df_n['Hr Bodega']).dt.minute / 60
    else:
        print("df_n is empty, skipping 'Hr Bodega Num' transformation.")

    # Apply filters with a check for empty DataFrames
    if not df_c.empty:
        #df_c = df_c[df_c['Hr Bodega Num'] > 6]
        df_c = df_c[(df_c['Hr Bodega Num'] > 6) | ((df_c['Estado'] != 'C') & (df_c['Hr Bodega Num'] > 6))]
    else:
        print("df_c is empty, skipping filter for > 6 o estado de viaje != C")

    if not df_n.empty:
        df_n = df_n[df_n['Hr Bodega Num'] <= 6]
    else:
        print("df_n is empty, skipping filter for <= 6.")

    # Combine the filtered DataFrames with a check for empty df_n
    if not df_n.empty:
        all_data = pd.concat([df_c, df_n])
    else:
        all_data = df_c  # Assign df_c to all_data if df_n is empty
        print("df_n is empty, all_data will only contain data from df_c.")

    all_data.reset_index(drop=True, inplace=True)

    def _load_excel_data(file_path):
      """Carga el archivo Excel."""
      if df_vendimia_override is not None:
          return df_vendimia_override.copy()
      return pd.read_excel(file_path, skiprows=4)

    #----------------------- buscar archivo vendimia

    def find_latest_vendimia_file(directory):
        """Busca el archivo más reciente que comienza con 'Programa Vendimia' y termina con '.xlsx'."""
        # Listar todos los archivos en el directorio
        archivos = os.listdir(directory)
        
        # Filtrar archivos que empiecen con 'Programa Vendimia' y terminen con '.xlsx'
        archivos_vendimia = [archivo for archivo in archivos if archivo.startswith('Programa Vendimia') and archivo.endswith('.xlsx')]
        
        if not archivos_vendimia:
            raise FileNotFoundError("No se encontró el archivo 'Programa Vendimia' en el directorio.")
        
        # Obtener la ruta completa de cada archivo
        rutas_archivos = [os.path.join(directory, archivo) for archivo in archivos_vendimia]
        
        # Ordenar los archivos por fecha de modificación, de más reciente a más antiguo
        archivo_mas_reciente = max(rutas_archivos, key=os.path.getmtime)
        
        return archivo_mas_reciente

    #--------------------------------




    def cleaning_vendimia(file_path):
      """Limpia los datos del programa de vendimia."""
      df = _load_excel_data(file_path)
      columnas_deseadas = ['CTTO', 'PRODUCTOR', 'VARIEDAD', 'CODIGO', 'BLOQUE','PROGRAMADO']
      df = df[columnas_deseadas]
      #df['CTTO'] = pd.to_numeric(df['CTTO'], errors='coerce').astype(int)
      df['CTTO'] = df['CTTO'].astype(str)
      df['BLOQUE'] = df['BLOQUE'].fillna(0).astype(int)
      df['CODIGO'] = df['CODIGO'].fillna(0).astype(str)
      df['PROGRAMADO'] = df['PROGRAMADO'].fillna(0).astype(int)
      df = df[df['PROGRAMADO'] != 0]
      return df

    # Llamar a la función para obtener el DataFrame
    # Forzado estáticamente según requerimiento arquitectónico
    archivo_vendimia = './dssProject/Modelo_matemático/Programa Vendimia 2024.xlsx'
    df_vendimia = cleaning_vendimia(archivo_vendimia)

    #++++++++++++++++++++++  Probar ++++++++++++++++++++++++++++

    df_vendimia = df_vendimia[~((df_vendimia['CODIGO'] == '0') & (df_vendimia['VARIEDAD'].isnull()) & (df_vendimia['PRODUCTOR'].isnull()))]
    # Mostrar el DataFrame resultante
    # df_vendimia.head()
    df_vendimia

    #-------------------------    
    def merge_api_and_vendimia(dfAPI, df_vendimia):
        """
        Bypasses strict CTTO/CODIGO match and blindly loads Mixtures (Bloques) from trucks.
        """
        df_final = dfAPI.copy()
        
        # Ensure Bloque is numeric
        if 'Bloque' in df_final.columns:
            df_final['BLOQUE'] = pd.to_numeric(df_final['Bloque'], errors='coerce').fillna(0).astype(int)
        elif 'BLOQUE' in df_final.columns:
            df_final['BLOQUE'] = pd.to_numeric(df_final['BLOQUE'], errors='coerce').fillna(0).astype(int)
        else:
            df_final['BLOQUE'] = 0
            
        if 'Estado' not in df_final.columns:
            df_final['Estado'] = 'A'
            
        if 'Patente' not in df_final.columns:
            df_final['Patente'] = 'N/A'

        if 'Fecha' not in df_final.columns:
            df_final['Fecha'] = '2024-03-11'

        # Select the desired columns
        try:
            df_final = df_final[['Hr Bodega', 'Kilos', 'BLOQUE', 'Patente', 'Fecha', 'Hr Bodega Num','Estado']]
        except KeyError as e:
            print("Missing columns in truck file. Available columns:", df_final.columns)
            raise e

        # Rename the 'BLOQUE' column
        df_final = df_final.rename(columns={'BLOQUE': 'Bloque'})

        # Filter out rows where 'Bloque' is equal to 0
        df_final = df_final[df_final['Bloque'] != 0]

        # Remove duplicates based on specific columns
        df_final = df_final.drop_duplicates(subset=['Hr Bodega', 'Kilos', 'Patente'])

        # Reset index
        df_final.reset_index(drop=True, inplace=True)

        return df_final

    df_final = merge_api_and_vendimia(all_data, df_vendimia)

    #---------------------------

    def process_vendimia_data(input_df):
        """Procesa el DataFrame de vendimia para agregar columnas discretizadas."""
        input_df['Hr Bodega Up'] = input_df['Hr Bodega Num'].apply(_discretize_hour)

        # Define intervals and labels for discretization
        intervalos = [[i, i + 1] for i in range(0, 30, 1)]
        miniTIME = [i for i in range(len(intervalos))]

        # Create the 't' column based on the discretized 'Hr Bodega Up'
        input_df['t'] = pd.cut(input_df['Hr Bodega Up'],
                                bins=[intervalo[0] for intervalo in intervalos] + [intervalos[-1][1]],
                                labels=miniTIME, right=False)

        # Sort the DataFrame by 'Fecha', 'Hr Bodega', and 't'
        input_df.sort_values(by=['Fecha', 'Hr Bodega', 't'], inplace=True)

        return input_df

    # Llamar a la función con el DataFrame df_final (o el DataFrame que corresponda)
    df_final_processed = process_vendimia_data(df_final)

    # Mostrar el DataFrame resultante
    df_final_processed

    #+++++++++++++++++++++++++++++
    #       SIN APII
    """
    def process_vendimia_data(file_path, fecha):
        #Procesa el DataFrame de vendimia para agregar columnas discretizadas y filtrar por fecha.
        if df_camiones_override is not None:
            input_df = df_camiones_override.copy()
        else:
            input_df = pd.read_excel(file_path, usecols=['Día', 'Hr Bodega', 'Kilos', 'Bloque', 'Patente', 'Hr Bodega Num', 't'])

        # Imprimir las columnas del DataFrame para diagnóstico
        print("Columnas disponibles en el DataFrame:", input_df.columns.tolist())

        # Filtrar por la fecha requerida
        input_df = input_df[input_df['Día'] == fecha]

        # Verificar si hay datos para la fecha solicitada
        if input_df.empty:
            print(f"No hay datos para la fecha: {fecha}")
            return None

        # Discretizar la hora
        input_df['Hr Bodega Up'] = input_df['Hr Bodega Num'].apply(_discretize_hour)

        # Definir intervalos y etiquetas para la discretización
        intervalos = [[i, i + 1] for i in range(0, 30, 1)]
        miniTIME = [i for i in range(len(intervalos))]

        # Crear la columna 't' basada en 'Hr Bodega Up' discretizada
        input_df['t'] = pd.cut(input_df['Hr Bodega Up'],
                                bins=[intervalo[0] for intervalo in intervalos] + [intervalos[-1][1]],
                                labels=miniTIME, right=False)

        # Ordenar el DataFrame por 'Día', 'Hr Bodega', y 't'
        input_df.sort_values(by=['Día', 'Hr Bodega', 't'], inplace=True)

        # Eliminar columnas vacías
        input_df.dropna(axis=1, how='all', inplace=True)

        return input_df

    # Obtener la fecha actual en formato YYYY-MM-DD
    current_date = '2024-03-18'
    current_date_dt = datetime.strptime(current_date, '%Y-%m-%d').date()

    # Calcular la fecha siguiente
    next_date = (current_date_dt + datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    # Ejemplo de cómo llamar a la función
    file_path = "./dssProject/Modelo_matemático/Planificación de camiones.xlsx"
    df_current = process_vendimia_data(file_path, current_date)
    df_next = process_vendimia_data(file_path, next_date)

    # Crear 'Hr Bodega Num' para el DataFrame actual
    if df_current is not None:
        df_current['Hr Bodega Num'] = pd.to_datetime(df_current['Hr Bodega']).dt.hour + pd.to_datetime(df_current['Hr Bodega']).dt.minute / 60
    else:
        print("df_current es None, omitiendo la transformación 'Hr Bodega Num'.")

    # Crear 'Hr Bodega Num' para el DataFrame del día siguiente
    if df_next is not None:
        df_next['Hr Bodega Num'] = pd.to_datetime(df_next['Hr Bodega']).dt.hour + pd.to_datetime(df_next['Hr Bodega']).dt.minute / 60
    else:
        print("df_next es None, omitiendo la transformación 'Hr Bodega Num'.")
    
    # Filtrar los datos del día actual
    if df_current is not None:
        df_current = df_current[(df_current['t'] > 6) | (df_current['Estado de viaje'] != 'c')]
    else:
        print("df_current es None, omitiendo el filtro para t > 6 o estado de viaje != c")

    # Filtrar los datos del día siguiente
    if df_next is not None:
        df_next = df_next[(df_next['t'] >= 0) & (df_next['t'] <= 6)]
    else:
        print("df_next es None, omitiendo el filtro para 0 <= t <= 6.")

    # Combinar los DataFrames filtrados
    if df_current is not None and df_next is not None:
        df_final_processed = pd.concat([df_current, df_next], ignore_index=True)
    else:
        df_final_processed = df_current if df_current is not None else df_next

    df_final_processed"
    """
    #+++++++++++++++++++++++++++++


    def preprocess_machines_data(file_path):
        if df_machines_override is not None:
            df = df_machines_override.copy()
        else:
            df = pd.read_excel(file_path)
        df['Bmin'] = df['Bmax'] * BMIN_FACTOR
        CubasDisp = df[df['Máquina'].str.startswith('CubaF')]
        df=df[df['Estado'] == 'Habilitado'].reset_index(drop=True)
        Bminprom = CubasDisp['Bmin'].mean()
        ReqCfer = max(1, round(ReqTon*0.96*0.84*0.94*760/Bminprom,0))
        df['Estado'] = ['Deshabilitado' if 'CubaF' in maquina and int(maquina.split('_')[1]) > ReqCfer else 'Habilitado' for maquina in df['Máquina']]
        df=df[df['Estado'] == 'Habilitado'].reset_index(drop=True)
        rho_convert = {'Despalillado': 1.0,
                'Prensado': 1.0,
                'Pre-flotacion': 1/760,
                'Flotacion': 1/760,
                'Fermentacion': 1/760}
        UNITS_TASKS = {(df['Máquina'][i],df['Tarea'][i]): {'Bmin': round(df['Bmin'][i]*rho_convert[df['Tarea'][i]],0),
                                                        'Bmax': round(df['Bmax'][i]*rho_convert[df['Tarea'][i]],0),
                                                        'T. Proc': df['T. Proc'][i], 'Tclean':0} for i in range(len(df))}
        return UNITS_TASKS

    #--------------------
    if df_machines_override is not None:
        df = df_machines_override.copy()
    else:
        df = pd.read_excel("./dssProject/Modelo_matemático/settings.xlsx")
        df=df[df['Estado'] == 'Habilitado'].reset_index(drop=True)
    df

    #--------------------

    UNITS = list(df['Máquina'])

    #--------------------
 
    def obtener_hora_actual():
        """Obtiene la hora actual en la zona horaria de Santiago de Chile."""
        # Forzado estáticamente a 8 para que filtre correctamente los camiones matutinos
        # de la base de prueba 'Planificación de camiones.xlsx' y no genere Pyomo Error
        return 8

    def definir_hora_horizonte(current_hour):
        """Define la hora de planificación y el horizonte de planificación en función de la hora actual."""
        H1 = 9  # H1 : 8 (9) +2
        H2 = 13  # H2 : 12 (13) + 5
        H3 = 20  # H3 : 19 (20) + 11

        if current_hour < H1:
            hora_planificacion = H1
            horizonte_planificacion = H2  # Fin del horizonte es H2
        elif H1 <= current_hour < H2:
            hora_planificacion = H2
            horizonte_planificacion = H3  # Fin del horizonte es H3
        else:
            hora_planificacion = H3
            horizonte_planificacion = 31  # Fin del horizonte es H2

        return hora_planificacion, horizonte_planificacion

    def ajustar_columna_t(df):
        """Ajusta los valores de la columna 't'."""
        df['t'] = pd.to_numeric(df['t'], errors='coerce')  # Convertir 't' a numérico
        for index in df.index:
            if df.loc[index, 't'] < 7:
                df.loc[index, 't'] += 24
            elif df.loc[index, 't'] < 9 and df.loc[index, 't'] >= 7:
                df.loc[index, 't'] = 9
        return df

    def filtrar_input(df, current_hour):
        """Filtra el DataFrame de entrada en función de la hora actual."""
        global H1, H2, H3 # Declare H1, H2, H3 as global
        H1 = 9  # H1 : 8 (9) +2
        H2 = 13  # H2 : 12 (13) + 5
        H3 = 20  # H3 : 19 (20) + 11
        maxtNum = 7  # Valor máximo para el rango H_

        if current_hour < H1:
            H_ = range(H1, int(maxtNum))  # Store range for H1
            filtered_df = df[(df['t'] >= (H1)) | (df['Estado'] != 'C')]
            filtered_df.loc[(filtered_df['Estado'] != 'C') & (filtered_df['t'] <= H1), 't'] = H1 # Modificar 't' si Estado != 'C' y t <= H1
        elif H1 <= current_hour < H2:
            H_ = range(H2, int(maxtNum))  # Store range for H1
            filtered_df = df[(df['t'] >= (H2)) | (df['Estado'] != 'C')]
            filtered_df.loc[(filtered_df['Estado'] != 'C') & (filtered_df['t'] <= H2), 't'] = H2 # Modificar 't' si Estado != 'C' y t <= H2
        else:
            H_ = range(H3, int(maxtNum))  # Store range for H1
            filtered_df = df[(df['t'] >= (H3)) | (df['Estado'] != 'C')]
            filtered_df.loc[(filtered_df['Estado'] != 'C') & (filtered_df['t'] <= H3), 't'] = H3 # Modificar 't' si Estado != 'C' y t <= H3
    

        filtered_df.sort_values(by=['t'], ascending=True, inplace=True)  # Ordenar dentro de la función
        return filtered_df, H_


    # Llamada a las funciones en el orden correcto:
    current_hour = 8
    #current_hour = obtener_hora_actual()
    #Llamar a la hora manualmmente:
    #current_hour = 8
    hora_planificacion, horizonte_planificacion = definir_hora_horizonte(current_hour)
    #Sin api df_final_processed
    input_df = ajustar_columna_t(df_final_processed)
    #Con api
    #input_df = ajustar_columna_t(input_df) # Asegúrate de que 'input_df' es tu DataFrame de entrada
    filtered_input, H_ = filtrar_input(input_df, current_hour)
    cantidad_input = len(filtered_input)

    #--------------------

    def procesar_input_y_guardar_recibo(filtered_input):
        """
        Procesa el DataFrame filtered_input, calcula el recibo y lo guarda en un archivo Excel.

        Args:
            filtered_input (pd.DataFrame): DataFrame filtrado de entrada.

        Returns:
            tuple: Una tupla que contiene los grupos únicos (GROUPS) y el DataFrame de recibo (Recieve).
        """
        GROUPS = set(filtered_input['Bloque'].unique())

        filtered_input = filtered_input.sort_values(by=['t'], ascending=True)
        filtered_input['Kilos'] = pd.to_numeric(filtered_input['Kilos'], errors='coerce')

        Rgrup = filtered_input.groupby(['t', 'Bloque'])['Kilos'].sum() / 1000
        Recieve = Rgrup.reset_index()
        Recieve.to_excel('input_model.xlsx', index=False)
        return GROUPS, Recieve

    #--------------------

    # Llama a la función filtrar_input para obtener el DataFrame filtrado
    filtered_input, _ = filtrar_input(input_df, current_hour)

    # Display the filtered and sorted data
    filtered_input

    #--------------------

    GROUPS, Recieve = procesar_input_y_guardar_recibo(filtered_input)

    ReqTon = Recieve['Kilos'].sum()
    ReqTon

    # Leer el archivo de resultados anteriores
    if os.path.exists('./dssProject/Modelo_matemático/Resultados_planificación.xlsx'):
        if current_hour >= H1:  # Added condition
            df_resultados = pd.read_excel('./dssProject/Modelo_matemático/Resultados_planificación.xlsx')
            df_resultados = df_resultados.sort_values(by=['Fin'])
            print(df_resultados)
        else:
            print("Resultados_planificación.xlsx ignored as current_hour is less than H1.")
            df_resultados = None  # or you could assign an empty DataFrame: pd.DataFrame()
    else:
        print("Resultados_planificación.xlsx file not found. Skipping...")
        df_resultados = None  # or you could assign an empty DataFrame: pd.DataFrame()


    #--------------------

    def filtrar_y_agrupar_resultados(df_resultados, hora_planificacion):
        """
        Filtra y agrupa los resultados anteriores en función de la hora de planificación.

        Args:
            df_resultados (pd.DataFrame): DataFrame con los resultados de la planificación anterior.
            hora_planificacion (int): Hora de planificación actual.

        Returns:
            tuple: Una tupla que contiene dos DataFrames: grouped_results y prensado_results.
        """
        filtered_results = df_resultados[df_resultados['Fin'] <= hora_planificacion]
        grouped_results = filtered_results.groupby(['Bloque', 'Tarea']).agg({
            'Tamaño [Ton]': 'sum',
            'Lote de salida': 'sum'
        }).reset_index()

        prensado_results = df_resultados[df_resultados['Tarea'] == 'Prensado']
        prensado_results = prensado_results[(prensado_results['Fin'] > hora_planificacion) &
                                            (prensado_results['Inicio'] < hora_planificacion)]

        if not prensado_results.empty:
            prensado_results = prensado_results.groupby(['Bloque', 'Tarea', 'Fin']).agg({
                'Tamaño [Ton]': 'sum',
                'Lote de salida': 'sum'
            }).reset_index()
            grouped_results = pd.concat([grouped_results, prensado_results], ignore_index=True)

        return grouped_results, prensado_results

    def procesar_resultados_agrupados(grouped_results):
        """
        Procesa los resultados agrupados para mantener la coherencia entre tareas.

        Args:
            grouped_results (pd.DataFrame): DataFrame con los resultados agrupados.

        Returns:
            pd.DataFrame: DataFrame con los resultados procesados.
        """
        tareas = grouped_results['Tarea'].unique()
        resultado_final = pd.DataFrame(columns=grouped_results.columns)

        for idx, tarea_actual in enumerate(tareas):
            tarea_actual_data = grouped_results[grouped_results['Tarea'] == tarea_actual]

            if idx < len(tareas) - 1:
                tarea_siguiente = tareas[idx + 1]
                tarea_siguiente_data = grouped_results[grouped_results['Tarea'] == tarea_siguiente]

                for _, row_actual in tarea_actual_data.iterrows():
                    bloque = row_actual['Bloque']
                    lote_salida = row_actual['Lote de salida']

                    registros_siguientes = tarea_siguiente_data[tarea_siguiente_data['Bloque'] == bloque]
                    if not registros_siguientes.empty:
                        total_tamano_siguiente = registros_siguientes['Tamaño [Ton]'].sum()
                        disponible = lote_salida - total_tamano_siguiente
                        if disponible > 0:
                            row_actual['Lote de salida'] = disponible
                            if not pd.DataFrame([row_actual]).empty:
                                resultado_final = pd.concat([resultado_final, pd.DataFrame([row_actual])], ignore_index=True)
                    else:
                        if not pd.DataFrame([row_actual]).empty:
                            resultado_final = pd.concat([resultado_final, pd.DataFrame([row_actual])], ignore_index=True)
            else:
                resultado_final = pd.concat([resultado_final, tarea_actual_data], ignore_index=True)

        return resultado_final

    if df_resultados is not None and not df_resultados.empty:
        grouped_results, prensado_results = filtrar_y_agrupar_resultados(df_resultados, hora_planificacion)
        resultado_final = procesar_resultados_agrupados(grouped_results)
        print("Resultados agrupados finales:")
        print(resultado_final)
    else:
        print("No hay datos disponibles para filtrar y agrupar.")
        resultado_final = pd.DataFrame()
        prensado_results = pd.DataFrame()
        grouped_results = pd.DataFrame()
    #--------------------

    UNITS_TASKS = preprocess_machines_data("./dssProject/Modelo_matemático/settings.xlsx")
    UNITS_TASKS

    #--------------------

    def create_VCT(H1, H2, H3, cantidad_input, current_hour):

        # Inicializar el diccionario Kondili
        Kondili = {
            'TIME': None,  # Inicializar TIME a None

            # estados
            'STATES': {
                'Racimo_uva': {'capacity': float("inf"), 'initial': 0, 'price': 100},
                'Uva_despalillada': {'capacity': float("inf"), 'initial': 0, 'price': 80},
                'Escobajo': {'capacity': float("inf"), 'initial': 0, 'price': 1},
                'Jugo_uva_I': {'capacity': float("inf"), 'initial': 0, 'price': 60},
                'Orujo': {'capacity': float("inf"), 'initial': 0, 'price': 1},
                'Jugo_uva_II': {'capacity': float("inf"), 'initial': 0, 'price': 40},
                'Borra': {'capacity': float("inf"), 'initial': 0, 'price': 1},
                'Mosto': {'capacity': float("inf"), 'initial': 0, 'price': 20},
                'Vino': {'capacity': float("inf"), 'initial': 0, 'price': 1}
            },

            # arcos estado-tarea indexados por (estado, tarea)
            'ST_ARCS': {
                ('Racimo_uva', 'Despalillado'): {'rho': 1.0},
                ('Uva_despalillada', 'Prensado'): {'rho': 1.0},
                ('Jugo_uva_I', 'Pre-flotacion'): {'rho': 1.0},
                ('Jugo_uva_II', 'Flotacion'): {'rho': 1.0},
                ('Mosto', 'Fermentacion'): {'rho': 1.0}
            },

            # arcos tarea-estado indexados por (tarea, estado)
            'TS_ARCS': {
                ('Despalillado', 'Uva_despalillada'): {'dur': 1, 'rho': 0.96},
                ('Despalillado', 'Escobajo'): {'dur': 1, 'rho': 0.04},
                ('Prensado', 'Jugo_uva_I'): {'dur': 4, 'rho': 0.86},
                ('Prensado', 'Orujo'): {'dur': 4, 'rho': 0.14},
                ('Pre-flotacion', 'Jugo_uva_II'): {'dur': 1, 'rho': 1.0},
                ('Flotacion', 'Mosto'): {'dur': 2, 'rho': 0.94},
                ('Flotacion', 'Borra'): {'dur': 2, 'rho': 0.06},
                ('Fermentacion', 'Vino'): {'dur': 8, 'rho': 1.0}
            }
        }

        # Lógica para definir el horizonte de tiempo
        if cantidad_input > 70:
            if current_hour < H1:
                Kondili['TIME'] = np.arange(0, 20 + 1, 1)
                print(f"Para {cantidad_input} valores a programar, ejecutado en rango de H1 hasta las 21")
            elif H1 <= current_hour < H2:
                Kondili['TIME'] = np.arange(0, 24 + 3 + 1, 1)
                print(f"Para {cantidad_input} valores a programar, ejecutado en rango de H2 hasta las 04")
            else:
                Kondili['TIME'] = np.arange(0, 24 + 7, 1)
                print(f"Para {cantidad_input} valores a programar, ejecutado en rango de H3 hasta las 07")
        elif cantidad_input > 50:
            if H1 - 1 <= current_hour < H3 -  1:
                Kondili['TIME'] = np.arange(0, 24 + 3 + 1, 1)
                print(f"Para {cantidad_input} valores a programar, pudiendo ser ejecutado en rango de H1 hasta las 04")
            else:
                Kondili['TIME'] = np.arange(0, 24 + 7, 1)
                print(f"Para {cantidad_input} valores a programar, ejecutado fuera del rango H3 hasta las 07")
        else:
            Kondili['TIME'] = np.arange(0, 24 + 7, 1)
            print(f"Para {cantidad_input} valores a programar, ejecutado para todo el horizonte")
        
        return Kondili

    # Llamar a la función
    Kondili = create_VCT(H1, H2, H3, cantidad_input, current_hour)

    #--------------------

    def initialize_R_and_Pt(Recieve, filtered_input, resultado_final, prensado_results, STATES, GROUPS, TIME, hora_planificacion):
        # Inicializar Pt y R
        Pt = {(g, t): [] for g in GROUPS for t in TIME}
        R = {(s, g, t): 0 for s in STATES for g in GROUPS for t in TIME}

        # Llenar R con los datos de Recieve
        for i in range(len(Recieve)):
            R['Racimo_uva', Recieve['Bloque'][i], Recieve['t'][i]] = Recieve['Kilos'][i]

            clave = (Recieve['Bloque'][i], Recieve['t'][i])
            if clave in Pt:  # Verificar si la clave existe
                Pt[clave].extend(filtered_input.loc[
                    (filtered_input['Bloque'] == Recieve['Bloque'][i]) &
                    (filtered_input['t'] == Recieve['t'][i]),
                    'Patente'
                ].tolist())
        
        # Llenar R con los datos de resultado_final
        for index, row in resultado_final.iterrows():
            bloque = row['Bloque']
            tarea = row['Tarea']
            lote_salida = row['Lote de salida']

            # Definir el estado según la etapa
            estado = {
                'Despalillado': 'Uva_despalillada',
                'Pre-flotacion': 'Jugo_uva_II',
                'Flotacion': 'Mosto',
                'Fermentacion': 'Vino'
            }.get(tarea)

            if estado:  # Si el estado es válido
                R[estado, bloque, hora_planificacion] = lote_salida
                print(f"estado: {estado}, bloque: {bloque}, hora_planificacion: {hora_planificacion}, lote_salida: {lote_salida}")

        # Llenar R con los datos de prensado_results
        for index, row in prensado_results.iterrows():
            bloque = row['Bloque']
            tarea = row['Tarea']
            lote_salida = row['Lote de salida']
            fin = row['Fin']  # Usar 'Fin' como el tiempo

            # Definir el estado según la etapa
            estado = 'Jugo_uva_I' if tarea == 'Prensado' else None

            if estado:  # Si el estado es válido
                R[estado, bloque, fin] = lote_salida
                print(f"estado: {estado}, bloque: {bloque}, fin: {fin}, lote_salida: {lote_salida}")

        return R, Pt


    #--------------------

    def characterize_tasks(UNIT_TASKS, ST_ARCS, TS_ARCS):
        # set of tasks
        TASKS = set([i for (j,i) in UNIT_TASKS])

        # S[i] input set of states which feed task i
        S = {i: set() for i in TASKS}
        for (s,i) in ST_ARCS:
            S[i].add(s)

        # S_[i] output set of states fed by task i
        S_ = {i: set() for i in TASKS}
        for (i,s) in TS_ARCS:
            S_[i].add(s)

        # rho[(i,s)] input fraction of task i from state s
        rho = {(i,s): ST_ARCS[(s,i)]['rho'] for (s,i) in ST_ARCS}

        # rho_[(i,s)] output fraction of task i to state s
        rho_ = {(i,s): TS_ARCS[(i,s)]['rho'] for (i,s) in TS_ARCS}

        # P[(i,s)] time for task i output to state s
        P = {(i,s): TS_ARCS[(i,s)]['dur'] for (i,s) in TS_ARCS}

        # p[i] completion time for task i
        p = {i: max([P[(i,s)] for s in S_[i]]) for i in TASKS}

        # K[i] set of units capable of task i
        K = {i: set() for i in TASKS}
        for (j,i) in UNIT_TASKS:
            K[i].add(j)

        return TASKS, S, S_, rho, rho_, P, p, K


    #--------------------

    def characterize_states(STATES, ST_ARCS, TS_ARCS):
        # T[s] set of tasks receiving material from state s
        T = {s: set() for s in STATES}
        for (s,i) in ST_ARCS:
            T[s].add(i)

        # set of tasks producing material for state s
        T_ = {s: set() for s in STATES}
        for (i,s) in TS_ARCS:
            T_[s].add(i)

        # C[s] storage capacity for state s
        C = {s: STATES[s]['capacity'] for s in STATES}

        return T, T_, C

    #--------------------

    def characterize_units(UNIT_TASKS, TIME):
        UNITS = set([j for (j,i) in UNIT_TASKS])

        # I[j] set of tasks performed with unit j
        I = {j: set() for j in UNITS}
        for (j,i) in UNIT_TASKS:
            I[j].add(i)


        # Bmax[(i,j,t)] maximum capacity of unit j for task i in the time t
        Bmax = {(i, j, t): UNIT_TASKS[(j, i)]['Bmax'] for (j, i) in UNIT_TASKS for t in TIME}

        # Bmin[(i,j,t)] minimum capacity of unit j for task i in the time t
        Bmin = {(i, j, t): UNIT_TASKS[(j, i)]['Bmin'] for (j, i) in UNIT_TASKS for t in TIME}

        pr = {j:UNIT_TASKS[(j,i)]['T. Proc'] for (j,i) in UNIT_TASKS}

        return UNITS, I, Bmax, Bmin, pr

    #--------------------

    from pyomo.environ import Expression, Constraint, ConstraintList, value

    #--------------------

    def create_maravelias_model(GROUPS,UNITS_TASKS,dfRec):
            STN = Kondili
            STATES = STN['STATES']
            ST_ARCS = STN['ST_ARCS']
            TS_ARCS = STN['TS_ARCS']
            UNIT_TASKS = UNITS_TASKS
            TIME = STN['TIME']

            TIME = np.array(TIME)

            R, Pt = initialize_R_and_Pt(Recieve, filtered_input, resultado_final, prensado_results, STATES, GROUPS, TIME, hora_planificacion)


            TASKS, S, S_, rho, rho_, P, p, K = characterize_tasks(UNIT_TASKS, ST_ARCS, TS_ARCS)
            T, T_, C = characterize_states(STATES, ST_ARCS, TS_ARCS)
            UNITS, I, Bmax, Bmin, pr = characterize_units(UNIT_TASKS, TIME)
            global prensas
            prensas = sorted([item for item in UNITS if item.startswith('PR')])
            indice_medio = len(prensas) // 2
            pr_left = prensas[:indice_medio]
            pr_right = prensas[indice_medio:]
            model = ConcreteModel()


            # W[i,j,t] 1 if task i starts in unit j at time t
            model.W = Var(TASKS, UNITS, GROUPS, TIME, domain=Boolean)

            # B[i,j,t,] size of batch assigned to task i in unit j at time t
            model.B = Var(TASKS, UNITS, GROUPS,TIME, domain=NonNegativeReals)

            # S[s,t] inventory of state s at time t
            model.S = Var(STATES.keys(), GROUPS, TIME, domain=NonNegativeReals)

            # Q[j,t] inventory of unit j at time t
            model.Q = Var(UNITS, TIME, domain=NonNegativeReals)

            model.O = Var(UNITS, TIME, domain=NonNegativeReals)

            # Objective function
            Cost = {(s,t): STATES[s]['price']*(1+t) for s in STATES for t in TIME}
            # project value
            model.Value = Var(domain=NonNegativeReals)
            model.valuec = Constraint(expr = model.Value == sum([Cost[s,t]*model.S[s,g,t] for s in STATES.keys() for g in GROUPS for t in TIME]))
            model.obj = Objective(expr=model.Value, sense = minimize)


            # Create ConstraintList
            model.cons = ConstraintList()

            # Restricción para limitar el inicio de las tareas de prensado
            #prensado_duracion = max([P[('Prensado', s)] for s in S_['Prensado']])  # Duración de prensado (7 horas)
            # Duración fija del prensado
            prensado_duracion = 7  # Duración fija de prensado en horas
            ultimo_inicio_prensado = 31 - prensado_duracion  # Último inicio permitido para prensado
            # flotacion_limite = 32  # Último tiempo permitido para la flotación

            # Imprimir para confirmar los límites
            print(f"Duración fija de la tarea de prensado: {prensado_duracion} horas")
            print(f"Último tiempo permitido para iniciar prensado: {ultimo_inicio_prensado}")
            # print(f"Último tiempo permitido para flotación: {flotacion_limite}")

            # Restricción para limitar el inicio de las tareas de prensado
            for j in UNITS:
                for g in GROUPS:
                    for t in TIME:
                        if 'Prensado' in I[j]:  # Verificar si la unidad realiza prensado
                            if t > ultimo_inicio_prensado:  # Tiempo mayor al límite permitido
                                model.cons.add(model.W['Prensado', j, g, t] == 0)

            # a unit can only be allocated to one task
            for j in UNITS:
                for t in TIME:
                    lhs = 0
                    for i in I[j]:
                        if i == 'Fermentacion':
                            for g in GROUPS:
                                for tprime in TIME:
                                    if tprime <= t:
                                        lhs += model.W[i,j,g,tprime]
                        else:
                            for g in GROUPS:
                                for tprime in TIME:
                                    if tprime >= (t-pr[j]+1-UNIT_TASKS[(j,i)]['Tclean']) and tprime <= t:
                                        lhs += model.W[i,j,g,tprime]
                        if type(lhs) is not int and type(lhs) is not float:
                            model.cons.add(lhs <= 1)


            # Wine SPK Restriction
            POZOS = sorted([item for item in UNITS if item.startswith('P_')])
            for j in POZOS:
                for g in GROUPS:
                    if g != 'SPK' and j == 'P_04':
                        for t in TIME:
                            model.cons.add(model.W['Despalillado',j,g,t]==0)
                    if g == 'SPK' and j != 'P_04':
                        for t in TIME:
                            model.cons.add(model.W['Despalillado',j,g,t]==0)

            # state capacity constraint
            model.sc = Constraint(STATES.keys(), GROUPS, TIME, rule = lambda model, s, g, t: model.S[s,g,t] <= C[s])

            # state mass balances
            for s in STATES.keys():
                for g in GROUPS:
                    rhs = STATES[s]['initial']
                    for t in TIME:
                        for i in T_[s]:
                            for j in K[i]:
                                if t >= pr[j]:
                                    rhs += rho_[(i,s)]*model.B[i,j,g,max(TIME[TIME <= t-pr[j]])]
                        for i in T[s]:
                            rhs -= rho[(i,s)]*sum([model.B[i,j,g,t] for j in K[i]])

                        rhs += R.get((s, g, t), 0)

                        model.cons.add(model.S[s,g,t] == rhs)
                        rhs = model.S[s,g,t]


            # unit capacity constraints
            for t in TIME:
                for g in GROUPS:
                    for j in UNITS:
                        for i in I[j]:
                            # Filtrar restricciones para máquina y tarea en tiempo t

                            if df_resultados is not None:

                                restriccion = df_resultados[
                                    (df_resultados['Máquina'] == j) &
                                    (df_resultados['Tarea'] == i) &
                                    ((df_resultados['Inicio'] <= t) & (df_resultados['Fin'] >= t))
                                ]

                                # Capacidad inicial de la máquina
                                bmax_actual = Bmax[(i, j, t)]

                                # Ajuste de capacidad si la máquina está ocupada en el tiempo actual
                                if not restriccion.empty:
                                    inicio = restriccion['Inicio'].values[0]
                                    fin = restriccion['Fin'].values[0]

                                    # Si estamos dentro del periodo de bloqueo, la capacidad es 0
                                    if inicio < t < fin:
                                        bmax_actual = 0
                                    # Al finalizar el bloqueo (t == fin), se restablece capacidad
                                    elif t == fin:
                                        bmax_actual = Bmax[(i, j, t)]

                                # Comprobar si t está dentro de un rango permitido según current_hour
                                if ((H1 - 1 <= current_hour < H2 - 1 and t < H2) or
                                    (H2 - 1 <= current_hour < H3 - 1 and t < H3) or
                                    (H3 - 1 <= current_hour or current_hour < H1 - 1)):

                                    # Aplicar la restricción de capacidad si hay un bloqueo en el periodo actual
                                    if not restriccion.empty and inicio < t < fin:
                                        bmax_actual = 0

                                # Añadir las restricciones de capacidad en el modelo
                                model.cons.add(model.W[i, j, g, t] * Bmin[i, j, t] <= model.B[i, j, g, t])
                                model.cons.add(model.B[i, j, g, t] <= model.W[i, j, g, t] * bmax_actual)

                            else:
                            # Añadir las restricciones de capacidad en el modelo
                                model.cons.add(model.W[i, j, g, t] * Bmin[i, j, t] <= model.B[i, j, g, t])
                                model.cons.add(model.B[i, j, g, t] <= model.W[i, j, g, t] * Bmax[(i, j, t)])

            # unit mass balances
            for j in UNITS:
                rhs = 0
                for t in TIME:
                    out = 0
                    rhs += sum([model.B[i,j,g,t] for i in I[j] for g in GROUPS])
                    out += sum([model.B[i,j,g,t] for i in I[j] for g in GROUPS])
                    for i in I[j]:
                        for g in GROUPS:
                            for s in S_[i]:
                                if t >= pr[j]:
                                    rhs -= rho_[(i,s)]*model.B[i,j,g,max(TIME[TIME <= t-pr[j]])]
                                    #out += rho_[(i,s)]*model.B[i,j,g,max(TIME[TIME <= t-pr[j]])]
                    model.cons.add(model.Q[j,t] == rhs)
                    model.cons.add(model.O[j,t] == out)
                    rhs = model.Q[j,t]
            # unit terminal condition
            #model.tc = Constraint(prensas, rule = lambda model, j: model.Q[j,H] == 0)
            for t in TIME:
                model.cons.add(sum([model.O[j,t] for j in pr_left]) <= sum([model.O[j,t] for j in pr_right]))

            return model, UNITS, I, TIME, pr, STATES

    # Llamar a la función
    model, UNITS, I, TIME, pr, STATES = create_maravelias_model(GROUPS, UNITS_TASKS, Recieve)
    
    #--------------------

    def solve_maravelias_model(model):
        # Configura el solucionador
        solver = SolverFactory('cbc', executable='./dssProject/Pyomo/CBC/bin/cbc.exe')

        
        #****solver para corren en runserver local****
        #current_dir = os.path.dirname(__file__)
        #parent_dir = os.path.join(os.path.dirname(current_dir), 'Pyomo', 'CBC','bin','cbc')
        #solver = SolverFactory('cbc', executable=parent_dir) 

        solver.options['seconds'] = TIME_LIMIT_SECONDS

        # Condicional para el gap
        if cantidad_input > 70:
            solver.options['ratioGap'] = RATIO_GAP_HIGH
        else:
            solver.options['ratioGap'] = RATIO_GAP_LOW


        solver.options['findInitial'] = True
        # Resuelve el modelo
        results = solver.solve(model)  # Guarda el resultado del solver
        results.write()  # Escribe los resultados

        # Accede a la condición de terminación
        Condition = results.solver.termination_condition
        return Condition

    # Llama a la función del solver
    condition = solve_maravelias_model(model)

    # Imprimir el resultado de la condición de terminación
    print("Condición de terminación del solver:", condition)

    #--------------------

    print("Value of State Inventories = {:,.1f}".format(int(model.Value())).replace(',', '.'))


    #--------------------

    def procesar_despalillado(UNITS, GROUPS, TIME, model, R, Pt, Bmax):

        despalillado_data = []
        excess_kilos_handled = {}

        for j in UNITS:
            for g in GROUPS:
                for t in TIME:
                    if model.W['Despalillado', j, g, t]() == 1:
                        kilos = R.get(('Racimo_uva', g, t), 0)
                        patentes = Pt.get((g, t), [])
                        bmax_actual = Bmax.get(('Despalillado', j, t), float('inf'))

                        excess_key = (g, t)
                        carried_over_excess = excess_kilos_handled.get(excess_key, 0)
                        kilos += carried_over_excess

                        kilos_asignados = min(kilos, bmax_actual)
                        kilos_exceso = kilos - kilos_asignados

                        message = ""
                        if carried_over_excess > 0:
                            message += f"Se asignan {carried_over_excess:.1f} TON anteriores "

                        if kilos_exceso > 0:
                            message += f"Por capacidad de {bmax_actual}, {kilos_exceso:.1f} TON pasan a la siguiente programación."
                            # Handle excess kilos for the next iteration
                            next_time_index = TIME.tolist().index(t) + 1  # Modified to use tolist()
                            if next_time_index < len(TIME):
                                next_time = TIME[next_time_index]
                                excess_kilos_handled[(g, next_time)] = excess_kilos_handled.get((g, next_time), 0) + kilos_exceso

                        despalillado_data.append({
                            'maquina': j,  # Using 'maquina' instead of 'Unidad'
                            'grupo': g,    # Using 'grupo' instead of 'Grupo'
                            'tiempo': t,   # Using 'tiempo' instead of 'Tiempo'
                            'patentes': patentes,
                            'Ton asignadas': kilos_asignados,  # Using 'Ton asignadas' instead of 'Kilos'
                            'Mensaje': message
                        })

        # Ordenar la lista por tiempo
        despalillado_data_ordenado = sorted(despalillado_data, key=lambda item: (item['maquina'], item['tiempo']))

        # --- BITACORA CRONOLOGICA DE PATIO Y PROCESAMIENTO ---
        print("\n" + "="*70)
        print("BITÁCORA CRONOLÓGICA DE RECEPCIÓN Y ESPERA EN PATIO")
        print("="*70)

        patio_inventario = {}
        
        for t in TIME:
            hora_str = f"{t:02d}:00" if t < 24 else f"{t-24:02d}:00 (+1 día)"
            eventos_hora = []
            
            # 1. Llegadas
            for g in GROUPS:
                llegadas = R.get(('Racimo_uva', g, t), 0)
                if llegadas > 0:
                    patentes = Pt.get((g, t), [])
                    patio_inventario[g] = patio_inventario.get(g, 0) + llegadas
                    patentes_str = ", ".join(map(str, patentes)) if patentes else "N/A"
                    eventos_hora.append(f"  [LLEGADA] {llegadas:.1f} TON de la mezcla {g} (Patentes: {patentes_str}). Total en patio: {patio_inventario[g]:.1f} TON.")
            
            # 2. Procesamiento
            for j in UNITS:
                for g in GROUPS:
                    # Chequear si la maquina 'j' fue asignada a despalillado en tiempo 't' para grupo 'g'
                    if ('Despalillado', j, g, t) in model.W and model.W['Despalillado', j, g, t]() == 1:
                        procesado = model.B['Despalillado', j, g, t]()
                        if procesado > 0:
                            patio_inventario[g] = max(0, patio_inventario.get(g, 0) - procesado)
                            bmax_actual = Bmax.get(('Despalillado', j, t), float('inf'))
                            eventos_hora.append(f"  [PROCESO] {procesado:.1f} TON de la mezcla {g} entran a {j}. (Cap. Máx de máquina: {bmax_actual:.1f} TON)")
            
            # 3. Esperas
            for g, cantidad_esperando in patio_inventario.items():
                if cantidad_esperando > 0.01:
                    siguiente_hora = t + 1
                    hora_sig_str = f"{siguiente_hora:02d}:00" if siguiente_hora < 24 else f"{siguiente_hora-24:02d}:00"
                    eventos_hora.append(f"  [EN ESPERA] {cantidad_esperando:.1f} TON de mezcla {g} sobran por falta de capacidad y quedan esperando en el patio para las {hora_sig_str}.")
            
            if eventos_hora:
                print(f"\nHORA: {hora_str}")
                for evento in eventos_hora:
                    print(evento)
                    
        print("="*70 + "\n")

        # --- REFACTORIZACION DE LOGS (Resumen Ejecutivo) ---
        print("\n" + "="*50)
        print("RESUMEN EJECUTIVO DE PROGRAMACION DE RECEPCION")
        print("="*50)
        
        total_asignado = 0
        total_exceso = 0
        camiones_omitidos = []

        for item in despalillado_data_ordenado:
            total_asignado += item['Ton asignadas']
            
        for key, excess in excess_kilos_handled.items():
            g, t = key
            if excess > 0:
                total_exceso += excess
                patentes_omitidas = Pt.get((g, t), [])
                camiones_omitidos.append({
                    'Grupo': g,
                    'Tiempo': t,
                    'Toneladas': excess,
                    'Patentes': patentes_omitidas,
                    'Justificacion': f"Capacidad maxima de pozos excedida en el instante {t}"
                })

        print(f"Total Toneladas Asignadas: {total_asignado:.1f} TON")
        print(f"Total Toneladas NO Procesadas (Exceso total acumulado al final): {sum(patio_inventario.values()):.1f} TON\n")

        if camiones_omitidos:
            print("--- DETALLE DE CAMIONES OMITIDOS PARCIAL/TOTALMENTE DURANTE EL TURNO ---")
            for omitido in camiones_omitidos:
                print(f"-> Grupo/Bloque: {omitido['Grupo']}, Tiempo: {omitido['Tiempo']}, Patentes: {omitido['Patentes']}")
                print(f"   Ton Omitidas/Desplazadas: {omitido['Toneladas']:.1f} TON. Causa: {omitido['Justificacion']}")
        else:
            print("Todos los camiones fueron asignados exitosamente sin esperas.")
        print("="*50 + "\n")
        # ---------------------------------------------------

        return despalillado_data_ordenado  # Return the ordered data

    #--------------------

    # Define R, Pt, and Bmax before using them
    R, Pt = initialize_R_and_Pt(Recieve, filtered_input, resultado_final, prensado_results, Kondili['STATES'], GROUPS, Kondili['TIME'], hora_planificacion)
    UNITS, I, Bmax, Bmin, pr = characterize_units(UNITS_TASKS, Kondili['TIME'])

    # Now call procesar_despalillado with R, Pt, and Bmax
    despalillado_data = procesar_despalillado(UNITS, GROUPS, Kondili['TIME'], model, R, Pt, Bmax)
    # Create the DataFrame from the ordered data
    df_despalillado = pd.DataFrame(despalillado_data)

    # Añadir el mensaje a la columna "Mensaje" si kilos_asignados < 24
    if not df_despalillado.empty and 'Ton asignadas' in df_despalillado.columns:
        df_despalillado.loc[df_despalillado['Ton asignadas'] < 24, 'Mensaje'] = "Por limitacion de Modelo, Faltan Patentes y Kilos Asignados Visualmente"

    df_despalillado

    #--------------------

    def obtener_cargas_entrantes(TIME, GROUPS, R, Pt):
        incoming_loads = []
        for t in TIME:
            # Convertimos el valor de t a un formato de hora
            if t < 24:
                hora = t
                dia = "día actual"
            else:
                hora = t - 24
                dia = "día siguiente"
            hora_str = f"{hora:02d}:00 horas ({dia})"

            # Lista para almacenar los detalles de cargas en este instante
            loads_at_time_t = []

            for g in GROUPS:
                incoming_load = R.get(('Racimo_uva', g, t), 0)
                if incoming_load != 0:  # Sólo si hay carga
                    patentes = Pt.get((g, t), [])
                    patentes_str = ", ".join(str(p) for p in patentes) if patentes else "N/A"  # Manejar patentes vacías
                    load_detail = f"Llegan {incoming_load} Ton de bloque {g} con patentes: {patentes_str}"
                    loads_at_time_t.append(load_detail)

            # Si hay cargas, agregamos el instante y sus detalles
            if loads_at_time_t:
                load_info = f"Instante {t} ({hora_str}):\n" + "\n".join(loads_at_time_t) + "\n"
                incoming_loads.append(load_info)

        return incoming_loads
    #--------------------

    Unit_assigment = pd.DataFrame([[model.O[j,t]() for j in prensas] for t in TIME], columns = prensas, index = TIME)
    Unit_assigment

    #--------------------

    # Sumar las columnas a lo largo del eje de las columnas (axis=1) para cada fila
    Qleft = Unit_assigment.iloc[:, :6].sum(axis=1)
    QRight = Unit_assigment.iloc[:, 6:].sum(axis=1)

    nuevo_df = pd.DataFrame({
        'Prensas 1-6': Qleft,  # Ajusta la columna según tu estructura
        'Prensas 7-12': QRight
    })

    nuevo_df

    #--------------------

    Inv = {(s,t): sum([model.S[s,g,t]() for g in GROUPS]) for s in STATES for t in TIME}


    #--------------------

    states_time=pd.DataFrame([[Inv[s,t] for s in STATES.keys()] for t in TIME], columns = STATES.keys(), index = TIME)
    states_time

    #--------------------

    STN = Kondili
    STATES = STN['STATES']
    ST_ARCS = STN['ST_ARCS']
    TS_ARCS = STN['TS_ARCS']
    UNIT_TASKS = UNITS_TASKS
    TIME = STN['TIME']

    # Call characterize_states to get C
    TASKS, S, S_, rho, rho_, P, p, K = characterize_tasks(UNIT_TASKS, ST_ARCS, TS_ARCS) # Assuming these variables are defined elsewhere
    T, T_, C = characterize_states(STATES, ST_ARCS, TS_ARCS) # Assuming these variables are defined elsewhere
    UNITS, I, Bmax, Bmin, pr = characterize_units(UNIT_TASKS, TIME) # Assuming these variables are defined elsewhere

    for (s,idx) in zip(STATES.keys(),range(0,len(STATES.keys()))):
        plt.subplot(math.ceil(len(STATES.keys())/3),3,idx+1) # Use math.ceil here
        tlast,ylast = 0,STATES[s]['initial']
        for (t,y) in zip(list(TIME),[Inv[s,t] for t in TIME]):
            plt.plot([tlast,t,t],[ylast,ylast,y],'b')
            #plt.plot([tlast,t],[ylast,y],'b.',ms=10)
            tlast,ylast = t,y
        #plt.ylim(0,1.1*C[s])
        H = max(TIME)  # Assign H to the maximum value in TIME
        plt.plot([0,H],[C[s],C[s]],'r--')
        plt.title(s)
    plt.tight_layout()

    #--------------------

    def generate_schedule(model, UNITS, I, GROUPS, TIME, pr):
        """Genera un DataFrame de programación basado en el modelo y los parámetros dados."""
        results = [
            {
                'Tarea': i,
                'Máquina': j,
                'Bloque': str(g),
                'Inicio': t,
                'Duración': pr[j],
                'Fin': t + pr[j],
                'Tamaño [Ton]': model.B[i, j, g, t](),
                'Lote de salida': round(
                    model.B[i, j, g, t]() * (
                        0.96 if i == 'Despalillado' else
                        0.86 * 0.76 if i == 'Prensado' else
                        0.94 * 0.76 if i == 'Flotacion' else
                        1 * 0.76
                    ), 2
                )
            }
            for j in UNITS for i in I[j] for g in GROUPS for t in TIME if model.W[i, j, g, t]() > 0
        ]

        # Crear el DataFrame a partir de los resultados
        schedule = pd.DataFrame(results)

        # Imprimir el horario por tarea
        print('\nSchedule by Job')
        if not schedule.empty:
            print(schedule.sort_values(by=['Máquina', 'Inicio']).set_index(['Tarea', 'Máquina']))

        # Imprimir el horario por máquina
        print('\nSchedule by Machine')
        print(schedule.sort_values(by=['Máquina', 'Inicio']).set_index(['Máquina', 'Tarea']))

        return schedule  # Retornar el DataFrame de programación si es necesario

    # Ejemplo de cómo llamar a la función
    schedule = generate_schedule(model, UNITS, I, GROUPS, TIME, pr)

    #--------------------


    # Crear un DataFrame con los resultados
    df_resultados = pd.DataFrame(schedule)

    # Definir la ruta donde se guardará el archivo en Google Drive
    ruta_archivo = './dssProject/Modelo_matemático/Resultados_planificación.xlsx'  # Cambia la ruta según sea necesario

    # Exportar a XLSX
    df_resultados.to_excel(ruta_archivo, index=False)

    # Imprimir la ruta del archivo para confirmación
    print(f"Archivo guardado en: {ruta_archivo}")

    result = pd.DataFrame(df_resultados)
    result_testeo = result.to_excel("./dssProject/Modelo_matemático/Resultados_planificación.xlsx", index=False)

    #--------------------

    def results_model(model,I,UNITS,GROUPS,TIME,pr):
        RESULTS = []
        ORDERTASK = ['Despalillado','Prensado','Pre-flotacion','Flotacion','Fermentacion']
        for m in ORDERTASK:
            results=[]
            if m == 'Fermentacion' or m == 'Pre-flotacion' or m=='Flotacion':
                rho = 760/1000
            else:
                rho = 1
            result =[{'Machine': j,
                    'Block': g,
                    'Start': t,
                        'Duration': pr[j],
                        'Finish': t+pr[j],
                    'Batch': round(model.B[i,j,g,t]()*rho,2)}
                    for j in UNITS for i in I[j] for g in GROUPS for t in TIME if model.W[i,j,g,t]()>0 and i == m]
            RESULTS.append(result)

        return RESULTS,ORDERTASK

    #--------------------

    def unites(ORDERTASK):
        UnidadMedida = []
        for i in ORDERTASK:
            if i == 'Fermentacion' or i == 'Pre-flotacion' or i=='Flotacion':
                UnidadMedida.append('\n[kLt]')
            else:
                UnidadMedida.append('\n[Ton]')
        UnidadMedida.append('\n[Ton]')
        return UnidadMedida

    #--------------------

    states_time['Desechos'] = states_time['Escobajo']+states_time['Orujo']
    states_time['Desechos']

    #--------------------

    states_time['Desechos'] = states_time['Desechos'].diff()
    states_time.loc[0,'Desechos']=0

    #--------------------

    def collection_truck(df):
        # Lista de camiones
        camiones = {"C1": None, "C2": None, "C3": None, "C4": None}

        # Inicializar variables
        asignaciones = []  # Lista para almacenar las asignaciones
        toneladas_acumuladas = 0  # Toneladas acumuladas
        start = 0
        inicio = True
        # Iterar sobre el DataFrame
        for i, toneladas in enumerate(df):
            toneladas_acumuladas += toneladas
            if toneladas != 0 and inicio:
                inicio = False
                start = i
            if toneladas_acumuladas >= 30 and any(disponibilidad is None for disponibilidad in camiones.values()):
                # Si hay al menos 30 toneladas acumuladas y hay camiones disponibles, asignar uno nuevo
                camion_disponible = next((camion for camion, disponibilidad in camiones.items() if disponibilidad is None), None)
                if camion_disponible:
                    indice = next((indice for indice, (camion, disponibilidad) in enumerate(camiones.items()) if camion == camion_disponible), None)
                    # Asignar el camión disponible
                    asignaciones.append({'Machine': camion_disponible, 'Block': str(indice+1), 'Start': start, 'Duration':i-start,
                                        'Finish': i, 'Batch': round(toneladas_acumuladas,1)})
                    toneladas_acumuladas = 0  # Reiniciar las toneladas acumuladas
                    camiones[camion_disponible] = {'inicio': start, 'fin': i+8}
                    start = i
            # Verificar si algún camión ha regresado y está disponible para una nueva asignación
            for camion, disponibilidad in camiones.items():
                if disponibilidad and i >= disponibilidad['fin']:
                    camiones[camion] = None  # Marcar el camión como disponible

        df_asignaciones = pd.DataFrame(asignaciones)
        return df_asignaciones, toneladas_acumuladas

    #--------------------

    schedl_truck, pending = collection_truck(states_time['Desechos'])
    schedl_truck

    #--------------------

    RESULTS, ORDERTASK = results_model(model, I, UNITS, GROUPS, TIME, pr)
    UnidadMedida = unites(ORDERTASK)

    schedl_truck, pending = collection_truck(states_time['Desechos'])

    RESULTS.append(schedl_truck)
    ORDERTASK.append('Recoleccion')
    UnidadMedida.append('\n[Ton]')

    #--------------------

    def visualize(results, task, um, iteracion, H_):
        schedule = pd.DataFrame(results)
        schedule['Block'] = schedule['Block'].astype(str)
        JOBS = sorted(list(schedule['Block'].astype(str).unique()))
        MACHINES = sorted(list(schedule['Machine'].unique()))

        if task == 'fermentacion':
            ferm = 24 * 10
            schedule['Start'] += 1
        else:
            ferm = 1

        title = 'Bloque de\nMezcla'

        schedule['Finish'] = schedule['Start'] + schedule['Duration'] * ferm
        makespan = schedule['Finish'].max()  # Calculate makespan based on the schedule DataFrame
        minespan = schedule['Start'].min()

        line_style = {'linewidth': 25, 'solid_capstyle': 'butt'}
        text_style = {'color': 'white', 'weight': 'bold', 'ha': 'center', 'va': 'center', 'fontsize': 8}
        colors = ['#05851F', '#009FAD', '#8A3500', '#F9752D', '#D6C400', '#4356FA',
                '#B27BFA', '#FA6F95', '#92E614', '#6E8894', '#FF5733', '#3399FF',
                '#FFD700', '#ADFF2F', '#FF1493']
        color_dict = {}
        for i, color in enumerate(colors):
            color_dict[str(i + 1)] = color

        # Añadir el último color especial
        color_dict['SPK'] = '#FA3C2C'
        title_style = {
            'fontsize': 16,
            'color': 'black',
            'weight': 'bold',
            'ha': 'center',
            'va': 'center',
            'path_effects': [withStroke(linewidth=3, foreground='white')]
        }

        fig, ax = plt.subplots(1, 1, figsize=(15, 5 + len(MACHINES) / 4))
        if task == 'recoleccion':
            title = 'Tipo de\ncamiones'
            colors = ['#E6170E', '#5FB324', '#B3A927', '#1C91E6']
            color_dict = {}
            for i, color in enumerate(colors):
                color_dict[str(i + 1)] = color

        for i in range(len(schedule)):
            xs = schedule['Start'][i]
            xf = schedule['Finish'][i]
            textstart = ""

            if task == 'fermentacion':
                hstart = f"{(xs % 24):02d}:00"
                textstart = "Hora de inicio->" + hstart + " | "
                um = um.replace("\n", "")

            mdx = MACHINES.index(schedule['Machine'][i]) + 1

            # Simular un borde negro agregando dos líneas
            ax.plot([xs - 1 / 60, xf - 1 / 60], [mdx] * 2, color='white', **line_style)
            ax.plot([xs, xf], [mdx] * 2, color=color_dict[schedule['Block'][i]], **line_style)

            # Agregar el número de bloque al texto
            block_number = schedule['Block'][i]
            ax.text((xs + xf) / 2, mdx, f"{textstart}{str(schedule['Batch'][i])} {um} ({block_number})", **text_style)

        fecha_actual = datetime.now()
        fecha_actual = fecha_actual.strftime("%d/%m/%Y")
        ax.set_title('Programación de ' + task + '\n(' + fecha_actual + ')' + f" H_: {H_}", **title_style)
        ax.set_ylabel('Máquinas')
        ax.set_ylim(0.5, len(MACHINES) + 0.5)
        ax.set_yticks(range(1, 1 + len(MACHINES)))
        ax.set_yticklabels(MACHINES)

        # Agregar horas del día en el eje x
        ax.set_xlabel('Tiempo (horas)')  # Etiqueta del eje x
        ax.set_xlim(minespan, makespan)  # Rango del eje x

        # Configurar las horas en el eje x
        if task == 'fermentacion':
            ax.set_xlabel('Tiempo (Días)')
            hours = range(int(minespan), int(makespan) + 1, 24)
            ax.set_xticks(hours)
            ax.set_xticklabels([f"Día {hour // 24 + 1}" for hour in hours], rotation=45, ha='right')
        else:
            hours = range(int(minespan), int(makespan) + 1, 1)
            ax.set_xticks(hours)
            ax.set_xticklabels([f"{(hour % 24):02d}:00" for hour in hours], rotation=45, ha='right')

        ax.plot([makespan] * 2, ax.get_ylim(), 'r--')
        ax.grid(True)

        # Agregar una leyenda fuera del gráfico
        job_labels = [mpl_patches.Patch(color=color_dict[JOBS[i]], label=JOBS[i]) for i in range(len(JOBS))]
        ax.legend(handles=job_labels, bbox_to_anchor=(1, 1), loc='upper left', title=title)

        fig.tight_layout()
        ruta_deseada = os.path.join(os.path.dirname(__file__),'Files','{:02}-{}.pdf'.format(iteracion,task))
        plt.savefig(ruta_deseada)
        plt.close()
        import time
        time.sleep(0.5)

    #--------------------

    # Definir los datos para el gráfico de barras
    categorias = ['1', '2', '3', '4', '5','6','7','8','9','10','11','12','13','14','15','16']
    valores = [20, 35, 30, 25, 40,20, 35, 30, 25, 40,30,20,20,20,20,20]

    # Definir los colores
    #colors = ['#05851F', '#009FAD', '#8A3500', '#F9752D', '#D6C400', '#4356FA',
    #          '#B27BFA', '#FA6F95', '#92E614', '#6E8894', '#FF5733', '#3399FF','#FA3C2C']
    colors = ['#00CED1', '#FF1493', '#7CFC00', '#800080', '#00FF00', '#FF00FF', '#FFFF00', '#00FFFF', '#FF4500', '#FF8C00', '#ADFF2F', '#9400D3', '#00CED1', '#FF1493', '#7CFC00']
    # Crear el gráfico de barras
    plt.bar(categorias, valores, color=colors)

    # Añadir título y etiquetas
    plt.title('Gráfico de barras con colores personalizados')
    plt.xlabel('Categorías')
    plt.ylabel('Valores')

    # Mostrar el gráfico
    plt.xticks(rotation=45)
    plt.tight_layout()
    # plt.show()

    #--------------------
    if not execute_visuals:
        return {"RESULTS": RESULTS, "ORDERTASK": ORDERTASK}

    i = 0
    for result, task, um in zip(RESULTS, ORDERTASK, UnidadMedida):
        if len(result) > 0:
            i+=1
            visualize(result, task.lower(), um, i, H_)

    #--------------------

    TotalProc = [[],[],[]]
    for idx in range(len(TASKS)):
        total=0
        if len(RESULTS[idx]) > 0:
            total=pd.DataFrame(RESULTS[idx])['Batch'].sum()
        TotalProc[0].append(ORDERTASK[idx])
        TotalProc[1].append(total)
        TotalProc[2].append(UnidadMedida[idx])

    result =[{'Proceso':  TotalProc[0][i],
                'Cantidad procesada':  TotalProc[1][i],
                'Unidad de medida':  TotalProc[2][i]}
                    for i in range(len(TotalProc[0]))]
    result = pd.DataFrame(result)
    result_testeo = result.to_excel("./dssProject/Modelo_matemático/Resumen.xlsx", index=False)


    #--------------------

    PD_SCHEDL=pd.DataFrame(RESULTS[4])
    PD_SCHEDL

    #--------------------

    result
    #------------------------------


    def generate_and_merge_pdfs(input_folder, incoming_loads, df_despalillado, output_file, current_date):
        # Determine HoraEje based on current_hour
        if current_hour <= 9:
            HoraEje = '_1era_Iteracion'
        elif 9 < current_hour <= 13:
            HoraEje = '_2nda_Iteracion'
        else:
            HoraEje = '_3era_Iteracion'


        def create_incoming_loads_pdf(loads, output_path):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)

            for load in loads:
                # Usar multi_cell para respetar saltos de línea
                pdf.multi_cell(0, 10, txt=load)  # Ancho automático (0), altura de línea (10)
                pdf.ln(5)  # Espaciado adicional entre bloques de texto (opcional)

            pdf.output(output_path)
            print(f"PDF de cargas entrantes generado: {output_path}")

        def save_dataframe_as_image(df, image_path):
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.axis('tight')
            ax.axis('off')
            table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(14)
            table.scale(1.5, 1.5)
            table.auto_set_column_width(col=list(range(len(df.columns))))
            plt.savefig(image_path, bbox_inches='tight', dpi=72)
            plt.close(fig)
            print(f"Imagen del DataFrame guardada: {image_path}")

        def create_dataframe_pdf(image_path, pdf_path):
            pdf = FPDF(orientation='L')
            pdf.add_page()
            if os.path.exists(image_path):
                img = Image.open(image_path)
                img.thumbnail((4000, 4000), Image.Resampling.LANCZOS)
                temp_img_path = image_path.replace('.png', '_resized.png')
                img.save(temp_img_path)
                img_width, img_height = img.size
                pdf_width = pdf.w - 20
                height = (pdf_width * img_height) / img_width
                pdf.image(temp_img_path, x=10, y=10, w=pdf_width, h=height)
                pdf.output(pdf_path)
                print(f"PDF del DataFrame generado: {pdf_path}")
            else:
                print("La imagen del DataFrame no se generó correctamente.")

        # Crear PDFs individuales


        incoming_loads_pdf = os.path.join(input_folder, "07_incoming_loads.pdf")
        df_image_path = os.path.join(input_folder, "df_despalillado.png")
        df_pdf_path = os.path.join(input_folder, "08_df_despalillado.pdf")

        create_incoming_loads_pdf(incoming_loads, incoming_loads_pdf)
        save_dataframe_as_image(df_despalillado, df_image_path)
        create_dataframe_pdf(df_image_path, df_pdf_path)

        # Fusionar PDFs numerados
        merger = PdfMerger()
        pdf_files = [
            f for f in os.listdir(input_folder)
            if re.match(r'^[0-9].*\.pdf', f)  # Archivos que empiezan con número y terminan en .pdf
        ]
        pdf_files.sort()

        print(f"Archivos que se fusionarán: {pdf_files}")

        for pdf_file in pdf_files:
            pdf_path = os.path.join(input_folder, pdf_file)
            merger.append(pdf_path)

        # Guardar PDF final
        final_output_path = f"{output_file}_Completa_{current_date}{HoraEje}.pdf"  # Added HoraEje
        merger.write(final_output_path)
        merger.close()

        print(f"PDF final generado como: {final_output_path}")

    # Datos de entrada

    input_folder = os.path.join(os.path.dirname(__file__),'Files')
    output_file = "Planificacion"
    incoming_loads = obtener_cargas_entrantes(Kondili['TIME'], GROUPS, R, Pt)
    current_date = '2024-03-18' # Use dt.date.today()

    # Ejecutar el proceso
    generate_and_merge_pdfs(input_folder, incoming_loads, df_despalillado, output_file, current_date)

    return("Ejecutado correctamente")