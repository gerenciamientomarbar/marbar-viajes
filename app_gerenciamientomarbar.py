import streamlit as st
import pandas as pd
from datetime import datetime

# --- FUNCIONES DE BASE DE DATOS ---
def obtener_siguiente_id(nombre_archivo):
    try:
        df_existente = pd.read_excel(nombre_archivo)
        if df_existente.empty: 
            return 1
        return int(df_existente['ID'].max() + 1)
    except:
        return 1

def guardar_en_excel(datos_viaje):
    nombre_db = "Base_Datos_Viajes_Marbar.xlsx"
    try:
        df_nuevo = pd.DataFrame([datos_viaje])
        try:
            with pd.ExcelWriter(nombre_db, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                df_existente = pd.read_excel(nombre_db)
                df_nuevo.to_excel(writer, startrow=len(df_existente)+1, header=False, index=False)
        except FileNotFoundError:
            df_nuevo.to_excel(nombre_db, index=False)
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

# --- INTERFAZ VISUAL ---
st.title("Gestión de Viajes - MARBAR")
st.subheader("Formulario de Despacho Seguro")

# 1. LA AGENDA COMPLETA DE MARBAR
AUTORIDADES = {
    "Higiene y Seguridad": {"Coordinador SSA": 1, "Jefe SSA": 2},
    "Logistica": {"Chofer": 0, "Coordinador de Logistica": 1, "Jefe de Logistica": 2},
    "Fluidos": {"Supervisor de SFP": 1, "Jefe de SFP": 2},
    "Control de solidos": {"Supervisor de CDS": 1, "Jefe de CDS": 2},
    "Mantenimiento": {"Mecanico / Electrico / Soldador": 1, "Jefe de Mantenimiento": 2},
    "Gerencia": {"Jefe de Operaciones / Gerente General": 3}
}

st.markdown("### 1. Datos del Solicitante")
# El selector de cargo ahora depende del sector que elijas
sector_elegido = st.selectbox("Selecciona tu Sector:", list(AUTORIDADES.keys()))
lista_cargos = list(AUTORIDADES[sector_elegido].keys())
cargo_elegido = st.selectbox("Selecciona tu Cargo:", lista_cargos)
nivel_aprobacion_usuario = AUTORIDADES[sector_elegido][cargo_elegido]

st.markdown("### 2. Datos del Viaje")
chofer = st.text_input("Nombre completo del Chofer:")
vehiculos = ["Camioneta Hilux", "Furgón Renault", "Auto Corolla"]
vehiculo_elegido = st.selectbox("Vehículo:", vehiculos)

col1, col2 = st.columns(2)
with col1:
    origen = st.text_input("Origen:")
with col2:
    destino = st.text_input("Destino:")

duracion = st.text_input("Duración estimada (ej: 2 horas):")
tipo_salida = st.radio("Tipo de Salida:", ["Planificada", "Urgencia"])

st.markdown("### 3. Evaluación de Riesgos")
puntaje = 0

# A. Distancia
distancia = st.radio("A. Distancia del viaje:", ["< 50km", "< 100km", "< 200km", "> 200km"])
if distancia == "< 50km": puntaje += 1
elif distancia == "< 100km": puntaje += 2
elif distancia == "< 200km": puntaje += 5
else: puntaje += 7

# B. Clima
clima = st.selectbox("B. Clima:", ["Despejado", "Nublado", "Viento", "Lluvia", "Niebla", "Nieve"])
puntos_clima = {"Despejado": 0, "Nublado": 1, "Viento": 2, "Lluvia": 4, "Niebla": 8, "Nieve": 9}
puntaje += puntos_clima[clima]

# C. Pasajeros
pasajeros = st.radio("C. Vehículos y Pasajeros:", ["Con pasajeros", "Solo conductor"])
puntaje += 1 if pasajeros == "Con pasajeros" else 5

# D. Camino
camino = st.radio("D. Condiciones del camino:", ["Pavimento", "Mixto", "Tierra"])
puntos_camino = {"Pavimento": 1, "Mixto": 2, "Tierra": 4}
puntaje += puntos_camino[camino]

# E. Horas de Trabajo
dormio = st.radio("E1. ¿El conductor durmió más de 8hs consecutivas?", ["Sí", "No"])
horas_totales = st.radio("E2. Suma las HS TRABAJANDO + HS PLANEADAS DE VIAJE:", ["< 12hs", "< 14hs", "< 16hs"])
if dormio == "Sí":
    puntos_h = {"< 12hs": 1, "< 14hs": 3, "< 16hs": 6}
else:
    puntos_h = {"< 12hs": 2, "< 14hs": 5, "< 16hs": 8}
puntaje += puntos_h[horas_totales]

# F. Escolta
escolta = st.radio("F. ¿Necesita escolta?", ["No", "Sí"])
puntaje += 1 if escolta == "No" else 5

# G. Horario
horario = st.radio("G. Condición de viaje:", ["Diurno", "Nocturno"])
if horario == "Nocturno":
    alarma_nocturna = "encendida"
    puntaje += 5
else:
    alarma_nocturna = "apagada"
    puntaje += 1

# H. Comunicación
comunicacion = st.radio("H. Comunicación:", ["Comunicación total", "Tramos sin señal", "Sin señal"])
puntos_com = {"Comunicación total": 1, "Tramos sin señal": 3, "Sin señal": 5}
puntaje += puntos_com[comunicacion]

# --- 4. CÁLCULO DE NIVEL Y APROBACIÓN ---
if puntaje <= 15: nivel_viaje = 1
elif puntaje <= 30: nivel_viaje = 2
else: nivel_viaje = 3

if nivel_aprobacion_usuario >= nivel_viaje:
    estado_viaje = f"AUTORIZADO (Auto-aprobado por {cargo_elegido})"
    color_alerta = "green"
else:
    estado_viaje = "PENDIENTE DE APROBACIÓN (Jefe de Sector / Gerencia)"
    color_alerta = "orange" if nivel_viaje == 2 else "red"

st.markdown("---")
st.subheader("📋 Resultado del Gerenciamiento")

if color_alerta == "green":
    st.success(f"**{estado_viaje}** | Nivel de Riesgo: {nivel_viaje} | Puntaje: {puntaje}")
elif color_alerta == "orange":
    st.warning(f"**{estado_viaje}** | Nivel de Riesgo: {nivel_viaje} | Puntaje: {puntaje}")
else:
    st.error(f"**{estado_viaje}** | Nivel de Riesgo: {nivel_viaje} | Puntaje: {puntaje}")

# --- 5. GUARDADO DE DATOS ---
if st.button("CONFIRMAR Y GUARDAR VIAJE"):
    if chofer == "" or origen == "" or destino == "":
        st.error("Por favor, completa el Nombre del Chofer, Origen y Destino antes de guardar.")
    else:
        nuevo_id = obtener_siguiente_id("Base_Datos_Viajes_Marbar.xlsx")
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        datos_para_guardar = {
            "ID": nuevo_id,
            "Fecha": ahora,
            "Chofer": chofer,
            "Sector": sector_elegido,
            "Cargo": cargo_elegido,
            "Vehiculo": vehiculo_elegido,
            "Origen": origen,
            "Destino": destino,
            "Duracion": duracion,
            "Salida": tipo_salida,
            "Puntaje": puntaje,
            "Nivel": nivel_viaje,
            "Alarma Nocturna": alarma_nocturna,
            "Estado": estado_viaje
        }
        
        exito = guardar_en_excel(datos_para_guardar)
        if exito:
            st.balloons()
            st.success(f"¡Éxito! Viaje ID {nuevo_id} registrado en el sistema de Marbar.")

# --- 6. PANEL LATERAL (RESUMEN) ---
st.sidebar.markdown("---")
st.sidebar.header("📊 Resumen de Gestión")
try:
    df_excel = pd.read_excel("Base_Datos_Viajes_Marbar.xlsx")
    fecha_hoy_str = datetime.now().strftime("%d/%m/%Y")
    
    # Filtramos los viajes que en la columna Fecha contengan el día de hoy
    viajes_hoy = df_excel[df_excel['Fecha'].astype(str).str.startswith(fecha_hoy_str, na=False)]
    cantidad_hoy = len(viajes_hoy)
    
    st.sidebar.metric("Viajes registrados HOY", cantidad_hoy)
    
    if cantidad_hoy > 0:
        st.sidebar.write("Choferes en ruta hoy:")
        st.sidebar.dataframe(viajes_hoy[['Chofer', 'Destino', 'Estado']])
except:
    st.sidebar.write("Aún no hay viajes registrados o el archivo está vacío.")

    # Agregamos un botón para descargar el Excel completo
    st.sidebar.markdown("---")
    with open("Base_Datos_Viajes_Marbar.xlsx", "rb") as archivo_excel:
        st.sidebar.download_button(
            label="📥 DESCARGAR BASE DE DATOS (EXCEL)",
            data=archivo_excel,
            file_name="Base_Datos_Viajes_Marbar_Actualizada.xlsx"
        )