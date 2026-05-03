import streamlit as st
import pandas as pd
from datetime import datetime
import os # Herramienta para revisar si los archivos existen en la computadora

# --- PREPARAR LIBRETAS (BASES DE DATOS) ---
def preparar_libretas():
    # Si la libreta de Usuarios no existe, la crea con 3 columnas
    if not os.path.exists("Base_Usuarios.xlsx"):
        df_u = pd.DataFrame(columns=["DNI_Usuario", "Nombre", "Rol"])
        df_u.to_excel("Base_Usuarios.xlsx", index=False)
    
    # Si la libreta de Vehículos no existe, la crea con 1 columna
    if not os.path.exists("Base_Vehiculos.xlsx"):
        df_v = pd.DataFrame(columns=["Vehiculo"])
        df_v.to_excel("Base_Vehiculos.xlsx", index=False)

preparar_libretas() # Aquí le damos la orden de ejecutar la revisión

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


# --- SISTEMA DE INGRESO (LOGIN) ---
# 1. Repartimos la "Pulsera VIP" si es la primera vez que entra en la página
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = None

# 2. Si no tiene la pulsera puesta (es None), le mostramos solo la puerta de entrada
if st.session_state["usuario_actual"] == None:
    st.title("🔒 Ingreso Privado - MARBAR")
    
    usuario_ingresado = st.text_input("Usuario o DNI:")
    # type="password" hace que lo que escribas se vea como puntitos negros
    contrasena_ingresada = st.text_input("Contraseña:", type="password") 
    
    if st.button("Entrar al Sistema"):
        # Por ahora, creamos tu Llave Maestra
        if usuario_ingresado == "ADMIN" and contrasena_ingresada == "Marbar2026":
            st.session_state["usuario_actual"] = "ADMIN"
            st.rerun() # Esto recarga la página, pero ahora SÍ tiene la pulsera puesta
        else:
            st.error("❌ Usuario o contraseña incorrectos.")
            
    # EL GUARDIA DE SEGURIDAD: Si no entró, cortamos la página acá.
    st.stop()


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

# --- 6. PANEL LATERAL (RESUMEN Y DESCARGA) ---
st.sidebar.markdown("---")
st.sidebar.header("📊 Resumen de Gestión")
try:
    df_excel = pd.read_excel("Base_Datos_Viajes_Marbar.xlsx")
    
    # Buscamos la fecha de hoy y el mes actual
    fecha_hoy_str = datetime.now().strftime("%d/%m/%Y")
    mes_actual_str = datetime.now().strftime("/%m/%Y") 
    
    # Filtramos
    viajes_hoy = df_excel[df_excel['Fecha'].astype(str).str.contains(fecha_hoy_str, na=False)]
    viajes_mes = df_excel[df_excel['Fecha'].astype(str).str.contains(mes_actual_str, na=False)]
    
    cantidad_hoy = len(viajes_hoy)
    cantidad_mes = len(viajes_mes)
    
    # Mostramos los dos números grandes
    st.sidebar.metric("Viajes registrados HOY", cantidad_hoy)
    st.sidebar.metric("Viajes de este MES", cantidad_mes)
    
    if cantidad_hoy > 0:
        st.sidebar.write("Choferes en ruta hoy:")
        st.sidebar.dataframe(viajes_hoy[['Chofer', 'Destino', 'Estado']])
        
    st.sidebar.markdown("---")
    # Preguntamos si la pulsera VIP dice "ADMIN"
    if st.session_state["usuario_actual"] == "ADMIN":
        with open("Base_Datos_Viajes_Marbar.xlsx", "rb") as archivo_excel:
            st.sidebar.download_button(
                label="📥 DESCARGAR BASE DE DATOS (EXCEL)",
                data=archivo_excel,
                file_name="Base_Datos_Viajes_Marbar_Actualizada.xlsx"
            )
except:
    st.sidebar.write("Aún no hay viajes registrados o el archivo está vacío.")

# --- 7. OFICINA SECRETA DE ADMINISTRACIÓN ---
# El cristal mágico: Solo el ADMIN puede ver lo que hay aquí adentro
if st.session_state["usuario_actual"] == "ADMIN":
    st.markdown("---")
    st.title("🛠️ Oficina de Administración")
    
    # Creamos dos "pestañas" visuales para que quede ordenado
    pestaña_usuarios, pestaña_vehiculos = st.tabs(["👥 Agregar Usuarios", "🚘 Agregar Vehículos"])
    
    # Lo que pasa en la pestaña de Usuarios
    with pestaña_usuarios:
        st.subheader("Registrar Nuevo Usuario")
        nuevo_dni = st.text_input("DNI o Usuario (ej: 35123456):")
        nuevo_nombre = st.text_input("Nombre Completo (ej: Juan Perez):")
        # Aquí repartimos los colores de las pulseras
        nuevo_rol = st.selectbox("Nivel de Acceso:", ["Chofer", "Supervisor", "Admin"])
        
        if st.button("💾 Guardar Usuario"):
            if nuevo_dni != "" and nuevo_nombre != "":
                # 1. Abrimos la libreta
                df_u = pd.read_excel("Base_Usuarios.xlsx")
                # 2. Escribimos al final de la libreta
                df_u.loc[len(df_u)] = [nuevo_dni, nuevo_nombre, nuevo_rol]
                # 3. Guardamos la libreta
                df_u.to_excel("Base_Usuarios.xlsx", index=False)
                st.success(f"¡Listo! {nuevo_nombre} ya tiene permiso para entrar como {nuevo_rol}.")
            else:
                st.error("Por favor, completa el DNI y el Nombre.")
                
    # Lo que pasa en la pestaña de Vehículos
    with pestaña_vehiculos:
        st.subheader("Registrar Nuevo Vehículo")
        nuevo_vehiculo = st.text_input("Nombre o Patente del Vehículo (ej: Camioneta F-201):")
        
        if st.button("💾 Guardar Vehículo"):
            if nuevo_vehiculo != "":
                # 1. Abrimos la libreta
                df_v = pd.read_excel("Base_Vehiculos.xlsx")
                # 2. Escribimos al final
                df_v.loc[len(df_v)] = [nuevo_vehiculo]
                # 3. Guardamos la libreta
                df_v.to_excel("Base_Vehiculos.xlsx", index=False)
                st.success(f"¡Listo! El vehículo {nuevo_vehiculo} fue agregado a la flota.")
            else:
                st.error("Por favor, escribe el nombre del vehículo.")