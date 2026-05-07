import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# --- CONEXIÓN A LA BÓVEDA EN LA NUBE (FIREBASE) ---
# El guardia revisa si la conexión ya está abierta
if not firebase_admin._apps:
    try:
        # Lee la llave de oro que escondiste en los Secretos de Streamlit
        llave_secreta = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(llave_secreta)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Error con la llave secreta: {e}")

# Abrimos la puerta de la bóveda
db = firestore.client()

# --- CONECTORES DE USUARIOS Y VEHÍCULOS (NUBE) ---
def obtener_usuarios():
    usuarios_ref = db.collection("usuarios").stream()
    lista = [doc.to_dict() for doc in usuarios_ref]
    if not lista:
        # Si la bóveda está vacía, creamos la llave maestra para no quedarnos afuera
        admin_data = {"DNI_Usuario": "12345678", "Nombre": "ADMIN", "Rol": "ADMIN", "Sector": "Gerencia"}
        db.collection("usuarios").document("12345678").set(admin_data)
        return pd.DataFrame([admin_data])
    return pd.DataFrame(lista)

def obtener_vehiculos():
    vehiculos_ref = db.collection("vehiculos").stream()
    lista = [doc.to_dict() for doc in vehiculos_ref]
    if not lista:
        return pd.DataFrame(columns=["Vehiculo"])
    return pd.DataFrame(lista)

# --- NUEVAS FUNCIONES DE BASE DE DATOS (NUBE) ---
def obtener_siguiente_id():
    try:
        # Busca en Firebase cuál fue el último ID usado
        viajes_ref = db.collection("viajes").order_by("ID", direction=firestore.Query.DESCENDING).limit(1).get()
        if viajes_ref:
            return viajes_ref[0].to_dict().get("ID", 0) + 1
        else:
            return 1 # Si la bóveda está vacía, empezamos en 1
    except:
        return 1

def guardar_en_nube(datos_viaje):
    try:
        # Guardamos el viaje en una "carpeta" con su ID dentro de la colección "viajes"
        doc_ref = db.collection("viajes").document(str(datos_viaje["ID"]))
        doc_ref.set(datos_viaje)
        return True
    except Exception as e:
        st.error(f"Error al guardar en la nube: {e}")
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
        # 1. El guardia primero revisa si es el Jefe con su llave maestra
        if usuario_ingresado == "ADMIN" and contrasena_ingresada == "Marbar2026":
            st.session_state["usuario_actual"] = "ADMIN"
            st.session_state["nombre_empleado"] = "Administrador"
            st.rerun()
            
        # 2. Si no es el jefe, busca el DNI en la libreta de usuarios
        else:
            # Le quitamos el paraguas para ver el error real
            df_usuarios = pd.read_excel("Base_Usuarios.xlsx")
            usuario_encontrado = df_usuarios[df_usuarios["DNI_Usuario"].astype(str) == str(usuario_ingresado)]
            
            if not usuario_encontrado.empty:
                   rol = usuario_encontrado.iloc[0]["Rol"]
                   nombre = usuario_encontrado.iloc[0]["Nombre"]
                   sector = usuario_encontrado.iloc[0]["Sector"] # El guardia ahora lee el sector
                   
                   st.session_state["usuario_actual"] = rol
                   st.session_state["nombre_empleado"] = nombre
                   st.session_state["sector_empleado"] = sector # Le pone la etiqueta en la campera
                   st.rerun()
            else:
                st.error("❌ DNI no registrado.")
            
    # EL GUARDIA DE SEGURIDAD: Si no entró, cortamos la página acá.
    st.stop()


# --- INTERFAZ VISUAL ---
st.title("Gestión de Viajes - MARBAR")
st.subheader("Formulario de Despacho Seguro")

st.title("Gestión de Viajes - MARBAR")

# --- MIS VIAJES EN CURSO (El botón de llegada del Chofer) ---
# Solo se lo mostramos a los usuarios normales (no al ADMIN)
if st.session_state["usuario_actual"] != "ADMIN":
    # 1. Buscamos en la nube y filtramos los viajes aprobados de este chofer
    viajes_ref = db.collection("viajes").stream()
    mis_activos = [doc.to_dict() for doc in viajes_ref if doc.to_dict().get("Chofer") == st.session_state["nombre_empleado"] and doc.to_dict().get("Aprobacion") == "🟢 Aprobado"]
    
    # 2. Si tiene viajes en ruta, le mostramos el cartel y el botón
    if len(mis_activos) > 0:
        st.info("📍 Tienes viajes en curso. ¡No olvides avisar cuando llegues a destino!")
        for viaje in mis_activos:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**Viaje ID {viaje['ID']}** | Destino: {viaje['Destino']}")
            with col2:
                if st.button(f"🏁 Llegué a Destino", key=f"btn_llegar_{viaje['ID']}"):
                    # Le ponemos el sello final en la nube
                    db.collection("viajes").document(str(viaje['ID'])).update({"Aprobacion": "🏁 Finalizado"})
                    st.success("¡Llegada registrada exitosamente! Buen trabajo.")
                    st.rerun()
        st.markdown("---")

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
# El formulario revisa quién entró
if st.session_state["usuario_actual"] == "ADMIN":
    # Si eres tú, te deja la cajita libre para escribir a mano
    chofer = st.text_input("Nombre completo del Chofer:")
else:
    # Si es un chofer, lee su etiqueta y bloquea la cajita (disabled=True) para que no se equivoque
    nombre_automatico = st.session_state["nombre_empleado"]
    chofer = st.text_input("Nombre completo del Chofer:", value=nombre_automatico, disabled=True)

# --- LECTURA AUTOMÁTICA DE VEHÍCULOS ---
# 1. Le decimos al código que abra la libreta de vehículos
try:
    df_v = obtener_vehiculos()
    # Sacamos los nombres de la columna "Vehiculo" y armamos una lista simple
    lista_vehiculos = df_v["Vehiculo"].tolist()
except:
    lista_vehiculos = [] # Si hay un error, dejamos la lista vacía temporalmente

# 2. Si la libreta está vacía, mostramos un aviso. Si tiene datos, los mostramos.
if len(lista_vehiculos) == 0:
    lista_vehiculos = ["⚠️ Pídele al ADMIN que cargue vehículos"]

# 3. Creamos la cajita desplegable usando nuestra lista nueva
vehiculo = st.selectbox("Vehículo o equipo a utilizar:", lista_vehiculos)

col1, col2 = st.columns(2)
with col1:
    origen = st.text_input("Origen:")
with col2:
    destino = st.text_input("Destino:")

duracion = st.text_input("Duración estimada (ej: 2 horas):")
tipo_salida = st.radio("Tipo de Salida:", ["Planificada", "Urgencia"], index=None)

st.markdown("### 3. Evaluación de Riesgos")
puntaje = 0

# A. Distancia
distancia = st.radio("A. Distancia del viaje:", ["< 50km", "< 100km", "< 200km", "> 200km"], index=None)
if distancia == "< 50km": puntaje += 1
elif distancia == "< 100km": puntaje += 2
elif distancia == "< 200km": puntaje += 5
else: puntaje += 7

# B. Clima
clima = st.selectbox("B. Clima:", ["Despejado", "Nublado", "Viento", "Lluvia", "Niebla", "Nieve"], index=None)
puntos_clima = {"Despejado": 0, "Nublado": 1, "Viento": 2, "Lluvia": 4, "Niebla": 8, "Nieve": 9}
puntaje += puntos_clima.get(clima, 0)

# C. Pasajeros
pasajeros = st.radio("C. Vehículos y Pasajeros:", ["Con pasajeros", "Solo conductor"], index=None)
puntaje += 1 if pasajeros == "Con pasajeros" else 5

# D. Camino
camino = st.radio("D. Condiciones del camino:", ["Pavimento", "Mixto", "Tierra"], index=None)
puntos_camino = {"Pavimento": 1, "Mixto": 2, "Tierra": 4}
puntaje += puntos_camino.get(camino, 0)

# E. Horas de Trabajo
dormio = st.radio("E1. ¿El conductor durmió más de 8hs consecutivas?", ["Sí", "No"], index=None)
horas_totales = st.radio("E2. Suma las HS TRABAJANDO + HS PLANEADAS DE VIAJE:", ["< 12hs", "< 14hs", "< 16hs"], index=None)
if dormio == "Sí":
    puntos_h = {"< 12hs": 1, "< 14hs": 3, "< 16hs": 6}
else:
    puntos_h = {"< 12hs": 2, "< 14hs": 5, "< 16hs": 8}
puntaje += puntos_h.get(horas_totales, 0)

# F. Escolta
escolta = st.radio("F. ¿Necesita escolta?", ["No", "Sí"], index=None)
puntaje += 1 if escolta == "No" else 5

# G. Horario
horario = st.radio("G. Condición de viaje:", ["Diurno", "Nocturno"], index=None)
if horario == "Nocturno":
    alarma_nocturna = "encendida"
    puntaje += 5
else:
    alarma_nocturna = "apagada"
    puntaje += 1

# H. Comunicación
comunicacion = st.radio("H. Comunicación:", ["Comunicación total", "Tramos sin señal", "Sin señal"], index=None)
puntos_com = {"Comunicación total": 1, "Tramos sin señal": 3, "Sin señal": 5}
puntaje += puntos_com.get(comunicacion, 0)

# --- 4. CÁLCULO DE NIVEL Y APROBACIÓN ---
if puntaje <= 15: nivel_viaje = 1
elif puntaje <= 30: nivel_viaje = 2
else: nivel_viaje = 3

if nivel_aprobacion_usuario >= nivel_viaje:
    estado_viaje = f"AUTORIZADO (Auto-aprobado por {cargo_elegido})"
    color_alerta = "green"
else:
    if nivel_viaje == 1:
        estado_viaje = "PENDIENTE DE APROBACIÓN (Supervisor / Coordinador de Sector)"
        color_alerta = "orange"
    elif nivel_viaje == 2:
        estado_viaje = "PENDIENTE DE APROBACIÓN (Jefe de Servicio)"
        color_alerta = "orange"
    else:
        estado_viaje = "PENDIENTE DE APROBACIÓN (Gerencia)"
        color_alerta = "red"

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
    # --- EL CANDADO DE SEGURIDAD ---
    if chofer == "" or origen == "" or destino == "" or tipo_salida == None or distancia == None or clima == None or pasajeros == None or camino == None or dormio == None or horas_totales == None or escolta == None or horario == None or comunicacion == None:
        st.error("⛔ ALTO: Por favor, responde TODAS las preguntas y completa todos los campos de texto antes de guardar el viaje.")
    else:
        # Usamos los motores nuevos de la nube
        nuevo_id = obtener_siguiente_id()
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        datos_para_guardar = {
            "ID": nuevo_id,
            "Fecha": ahora,
            "Chofer": chofer,
            "Sector": sector_elegido,
            "Cargo": cargo_elegido,
            "Vehiculo": vehiculo,
            "Origen": origen,
            "Destino": destino,
            "Duracion": duracion,
            "Salida": tipo_salida,
            "Puntaje": puntaje,
            "Nivel": nivel_viaje,
            "Alarma Nocturna": alarma_nocturna,
            "Estado": estado_viaje,
            "Aprobacion": "🟢 Aprobado" if color_alerta == "green" else "🔴 Pendiente"
        }

        # Guardamos en Firebase
        exito = guardar_en_nube(datos_para_guardar)
        if exito:
            st.balloons()
            st.success(f"¡Éxito! Viaje ID {nuevo_id} registrado en el sistema en la nube de Marbar.")
            
            # --- EL TIMBRE DE WHATSAPP ---
            mensaje = f"Hola! Acabo de cargar el viaje ID {nuevo_id} con destino a {destino}. Por favor apruébalo cuando puedas."
            mensaje_internet = mensaje.replace(" ", "%20")
            link_whatsapp = f"https://wa.me/?text={mensaje_internet}"
            st.markdown(f"### [📲 TOCA AQUÍ PARA AVISAR AL JEFE POR WHATSAPP]({link_whatsapp})")

# --- 6. PANEL LATERAL (RESUMEN Y DESCARGA) ---
st.sidebar.markdown("---")
st.sidebar.header("📊 Resumen de Gestión")
try:
    # 1. Buscamos TODOS los viajes en la nube
    viajes_ref = db.collection("viajes").stream()
    lista_viajes = [doc.to_dict() for doc in viajes_ref]
    
    if len(lista_viajes) > 0:
        df_nube = pd.DataFrame(lista_viajes)
        
        fecha_hoy_str = datetime.now().strftime("%d/%m/%Y")
        mes_actual_str = datetime.now().strftime("/%m/%Y")
        
        # Filtramos viajes del día y del mes para las métricas
        viajes_hoy = df_nube[df_nube['Fecha'].astype(str).str.contains(fecha_hoy_str, na=False)]
        viajes_mes = df_nube[df_nube['Fecha'].astype(str).str.contains(mes_actual_str, na=False)]
        
        st.sidebar.metric("Viajes registrados HOY", len(viajes_hoy))
        st.sidebar.metric("Viajes de este MES", len(viajes_mes))
        
        # --- TABLERO EN RUTA ---
        # Solo mostramos los que están APROBADOS pero que aún NO han finalizado
        viajes_en_ruta = viajes_hoy[viajes_hoy['Aprobacion'] == "🟢 Aprobado"]
        
        if not viajes_en_ruta.empty:
            st.sidebar.write("🚚 **En ruta ahora:**")
            st.sidebar.dataframe(viajes_en_ruta[['Chofer', 'Destino']], hide_index=True)
        else:
            st.sidebar.write("✅ No hay vehículos en ruta ahora.")
            
        # Botón de descarga para el ADMIN (Genera el Excel desde la nube)
        if st.session_state["usuario_actual"] == "ADMIN":
            st.sidebar.markdown("---")
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_nube.to_excel(writer, index=False, sheet_name='Viajes_Marbar')
            
            st.sidebar.download_button(
                label="📥 DESCARGAR BASE DE DATOS (EXCEL)",
                data=buffer.getvalue(),
                file_name=f"Reporte_Marbar_{fecha_hoy_str.replace('/','-')}.xlsx",
                mime="application/vnd.ms-excel"
            )
    else:
        st.sidebar.info("Aún no hay viajes en la base de datos.")
except Exception as e:
    st.sidebar.error(f"Error al conectar con la nube: {e}")

# --- BANDEJA DE APROBACIONES (Solo para Autoridades) ---
if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia"]:
    st.markdown("---")
    st.title("📥 Bandeja de Aprobaciones")
    
    try:
        # 1. Traemos la lista actualizada de la nube
        viajes_ref = db.collection("viajes").stream()
        lista_viajes = [doc.to_dict() for doc in viajes_ref]
        df_viajes = pd.DataFrame(lista_viajes)
        
        # 2. Filtramos solo los pendientes
        viajes_pendientes = df_viajes[df_viajes["Aprobacion"] == "🔴 Pendiente"]
        
        # 3. Aplicamos el Filtro Inteligente por Cargo/Sector
        rol_actual = st.session_state["usuario_actual"]
        sector_actual = st.session_state.get("sector_empleado", "")
        
        if rol_actual == "ADMIN":
            mis_pendientes = viajes_pendientes
        elif rol_actual == "Gerencia":
            mis_pendientes = viajes_pendientes[(viajes_pendientes["Nivel"] == 3) | ((viajes_pendientes["Salida"] == "Urgencia") & (viajes_pendientes["Alarma Nocturna"] == "encendida"))]
        elif rol_actual == "Jefe de Servicio":
            mis_pendientes = viajes_pendientes[(viajes_pendientes["Nivel"] == 2) & (viajes_pendientes["Sector"] == sector_actual)]
        elif rol_actual == "Supervisor / Coordinador":
            mis_pendientes = viajes_pendientes[(viajes_pendientes["Nivel"] == 1) & (viajes_pendientes["Sector"] == sector_actual)]
        else:
            mis_pendientes = pd.DataFrame()

        # 4. Interfaz de aprobación
        if mis_pendientes.empty:
            st.info("✅ No tienes viajes pendientes de aprobación en tu nivel/sector.")
        else:
            st.warning(f"⚠️ Tienes {len(mis_pendientes)} viaje(s) esperando tu firma.")
            for index, viaje in mis_pendientes.iterrows():
                with st.expander(f"🚨 ID: {viaje['ID']} | {viaje['Chofer']} | Riesgo: {viaje['Nivel']}"):
                    st.write(f"**Origen/Destino:** {viaje['Origen']} -> {viaje['Destino']}")
                    st.write(f"**Motivo:** {viaje['Estado']}")
                    
                    if st.button(f"✅ Sellar Aprobación {viaje['ID']}", key=f"btn_aprob_{viaje['ID']}"):
                        # ACTUALIZACIÓN EN LA NUBE
                        db.collection("viajes").document(str(viaje['ID'])).update({"Aprobacion": "🟢 Aprobado"})
                        st.success("¡Viaje aprobado en la nube!")
                        st.rerun()
    except:
        st.info("Buscando viajes en la nube...")


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
        
        # Agregamos el selector de Sector 
        nuevo_sector = st.selectbox("Sector al que pertenece:", ["Higiene y Seguridad", "Operaciones", "Mantenimiento", "Gerencia"])
        
        # Actualizamos los roles (Ojo: ADMIN va todo en mayúsculas para que coincida)
        nuevo_rol = st.selectbox("Nivel de Acceso:", ["Chofer", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia", "ADMIN"])
        
        if st.button("💾 Guardar Usuario"):
            if nuevo_dni != "" and nuevo_nombre != "":
                # --- GUARDAMOS DIRECTO EN LA NUBE (FIREBASE) ---
                datos_u = {"DNI_Usuario": str(nuevo_dni), "Nombre": nuevo_nombre, "Rol": nuevo_rol, "Sector": nuevo_sector}
                db.collection("usuarios").document(str(nuevo_dni)).set(datos_u)
                
                st.success(f"¡Listo! {nuevo_nombre} fue registrado en la nube.")
                st.rerun()
            else:
                st.error("Por favor, completa el DNI y el Nombre.")
        
        # Mostramos la lista viva desde la nube
        st.write("Usuarios Registrados en el Sistema:")
        st.dataframe(obtener_usuarios(), hide_index=True)
                
    # Lo que pasa en la pestaña de Vehículos
    with pestaña_vehiculos:
        st.subheader("Registrar Nuevo Vehículo")
        nuevo_vehiculo = st.text_input("Nombre o Patente del Vehículo (ej: Camioneta F-201):")
        
        if st.button("💾 Guardar Vehículo"):
            if nuevo_vehiculo != "":
                # --- GUARDAMOS DIRECTO EN LA NUBE (FIREBASE) ---
                db.collection("vehiculos").document(nuevo_vehiculo).set({"Vehiculo": nuevo_vehiculo})
                
                st.success(f"¡Listo! El vehículo {nuevo_vehiculo} fue agregado a la flota en la nube.")
                st.rerun()
            else:
                st.error("Por favor, escribe el nombre del vehículo.")
                
        # Mostramos la lista viva desde la nube
        st.write("Vehículos en Flota:")
        st.dataframe(obtener_vehiculos(), hide_index=True)
        