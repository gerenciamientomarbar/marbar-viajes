import streamlit as st
import pandas as pd
from datetime import datetime

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
        # Intentamos leer el archivo para ver si existe
        df_nuevo = pd.DataFrame([datos_viaje])
        try:
            with pd.ExcelWriter(nombre_db, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                # Si el archivo existe, agregamos la fila al final
                df_existente = pd.read_excel(nombre_db)
                df_nuevo.to_excel(writer, startrow=len(df_existente)+1, header=False, index=False)
        except FileNotFoundError:
            # Si el archivo no existe, lo creamos de cero
            df_nuevo.to_excel(nombre_db, index=False)
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

# 1. Título de la aplicación (Lo que se verá arriba de todo en el celular)
st.title("Gestión de Viajes - MARBAR")
st.subheader("Formulario de Despacho Seguro")

# 2. La Agenda de MARBAR (Copiamos la que ya teníamos)
AUTORIDADES = {
    "Operaciones": {"Jefe": "Ivan Perez", "Nivel": 2},
    "Mantenimiento": {"Jefe": "Fabiana Retamozo", "Nivel": 2},
    "Seguridad (SSA)": {"Jefe": "Paula Inda", "Nivel": 3},
    "Logística": {"Jefe": "Gerencia Operativa", "Nivel": 3}
}

# 3. Creamos el primer selector en la web
lista_sectores = list(AUTORIDADES.keys())
sector_elegido = st.selectbox("Selecciona tu Sector:", lista_sectores)

# 4. Mostramos quién es el jefe según el sector (solo para informar)
jefe = AUTORIDADES[sector_elegido]["Jefe"]
st.info(f"Autoridad de despacho para este sector: {jefe}")

# 5. Entrada de datos del Chofer (Caja de texto)
nombre_chofer = st.text_input("Nombre completo del Chofer:")

# 6. Datos del Vehículo
# Primero definimos la lista de camionetas como hacíamos antes
unidades = ["C-101", "C-102", "C-103", "F-201", "F-202", "Particular"]
unidad_elegida = st.selectbox("Selecciona la Unidad / Vehículo:", unidades)

# 7. Datos del Trayecto
col1, col2 = st.columns(2) # Esto divide la pantalla en dos columnas, queda muy bien en el celular
with col1:
    origen = st.text_input("Origen:")
with col2:
    destino = st.text_input("Destino:")

    # 8. Evaluación de Riesgos
st.markdown("---") # Esto dibuja una línea horizontal para separar secciones
st.subheader("⚠️ Evaluación de Seguridad")

# Creamos interruptores (toggle switches) que son fáciles de usar en el celular
descanso = st.toggle("¿Cumplió con las 12hs de descanso?")
clima_ok = st.toggle("¿El clima es apto para transitar?")
documentacion = st.toggle("¿Tiene licencia y papeles del vehículo al día?")

# 9. Preguntas con opciones (Radio buttons)
st.markdown("---")

# Pregunta de Fatiga
fatiga = st.radio(
    "Estado de Fatiga:",
    ["Bien (Descansado)", "Fatiga Leve (Cansancio normal)", "Fatiga Moderada / Alta"],
    index=0 # Esto hace que la primera opción esté marcada por defecto
)

# Pregunta de Comunicación
comunicacion = st.radio(
    "Nivel de Comunicación en la ruta:",
    ["Comunicación total", "Tramos sin señal", "Sin señal en todo el trayecto"],
    index=0
)

# 10. CALCULADORA INVISIBLE DE RIESGO
# Transformamos los "Sí/No" y las opciones en puntos, igual que antes

puntaje = 0

# Sumamos por los interruptores (Si está activo, suma 0. Si está apagado, suma puntos de riesgo)
if not descanso: puntaje += 10
if not clima_ok: puntaje += 10
if not documentacion: puntaje += 5

# Sumamos por la Fatiga
if fatiga == "Fatiga Leve (Cansancio normal)":
    puntaje += 5
elif fatiga == "Fatiga Moderada / Alta":
    puntaje += 15

# Sumamos por la Comunicación
if comunicacion == "Tramos sin señal":
    puntaje += 5
elif comunicacion == "Sin señal en todo el trayecto":
    puntaje += 10

# 11. DETERMINAR EL NIVEL (Lógica de Marbar)
if puntaje <= 10:
    nivel_viaje = 1
    estado_viaje = "VIAJE AUTORIZADO"
    color_alerta = "green"
elif puntaje <= 20:
    nivel_viaje = 2
    estado_viaje = "REQUIERE AUTORIZACIÓN (Jefe de Sector)"
    color_alerta = "orange"
else:
    nivel_viaje = 3
    estado_viaje = "ALERTA: REQUIERE AUTORIZACIÓN GERENCIAL"
    color_alerta = "red"

    # 12. MOSTRAR RESULTADOS EN PANTALLA
st.markdown("---")
st.subheader("📋 Resultado del Gerenciamiento")

# Mostramos el puntaje y el estado con el color que corresponda
if color_alerta == "green":
    st.success(f"**{estado_viaje}** (Puntaje: {puntaje})")
elif color_alerta == "orange":
    st.warning(f"**{estado_viaje}** (Puntaje: {puntaje})")
else:
    st.error(f"**{estado_viaje}** (Puntaje: {puntaje})")

# 13. BOTÓN FINAL PARA REGISTRAR
# 13. BOTÓN FINAL PARA REGISTRAR (Versión Completa)
if st.button("CONFIRMAR Y GUARDAR VIAJE"):
    if nombre_chofer == "":
        st.error("Por favor, ingresa el nombre del chofer antes de guardar.")
    else:
        # Preparamos la "ficha" con todos los datos para el Excel
        nuevo_id = obtener_siguiente_id("Base_Datos_Viajes_Marbar.xlsx")
        
        datos_para_guardar = {
            "ID": nuevo_id,
            "Fecha": datetime.now().strftime("%d/%m/%Y"),
            "Hora": datetime.now().strftime("%H:%M"),
            "Chofer": nombre_chofer,
            "Unidad": unidad_elegida,
            "Origen": origen,
            "Destino": destino,
            "Puntaje": puntaje,
            "Nivel": nivel_viaje,
            "Estado": estado_viaje,
            "Autoridad": jefe
        }
        
        # Intentamos guardar
        exito = guardar_en_excel(datos_para_guardar)
        
        if exito:
            st.balloons()
            st.success(f"¡Éxito! Viaje ID {nuevo_id} registrado en el sistema de Marbar.")
            st.info("Ya puedes cerrar esta pestaña o cargar un nuevo viaje.")

            # 14. PANEL DE ESTADÍSTICAS (Resumen de Gestión)
st.sidebar.markdown("---") # Esto crea una barra lateral a la izquierda
st.sidebar.header("📊 Resumen de hoy")

try:
    df_excel = pd.read_excel("Base_Datos_Viajes_Marbar.xlsx")
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    
    # Filtramos los viajes que tengan la fecha de hoy
    viajes_hoy = df_excel[df_excel['Fecha'] == fecha_hoy]
    cantidad_hoy = len(viajes_hoy)
    
    # Mostramos el número grande en la barra lateral
    st.sidebar.metric("Viajes registrados hoy", cantidad_hoy)
    
    # Si hay viajes, mostramos los nombres de los choferes que salieron
    if cantidad_hoy > 0:
        st.sidebar.write("Choferes en ruta:")
        st.sidebar.dataframe(viajes_hoy[['Chofer', 'Destino', 'Estado']])
except:
    st.sidebar.write("Aún no hay viajes registrados.")