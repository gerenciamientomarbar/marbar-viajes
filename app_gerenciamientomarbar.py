import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
import os
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# --- CONEXIÓN A LA BÓVEDA EN LA NUBE (FIREBASE) ---
if not firebase_admin._apps:
    try:
        llave_secreta = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(llave_secreta)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Error con la llave secreta: {e}")

db = firestore.client()

# --- CONECTORES DE USUARIOS Y VEHÍCULOS (NUBE) ---
def obtener_usuarios():
    usuarios_ref = db.collection("usuarios").stream()
    lista = [doc.to_dict() for doc in usuarios_ref]
    if not lista:
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
        viajes_ref = db.collection("viajes").order_by("ID", direction=firestore.Query.DESCENDING).limit(1).get()
        if viajes_ref:
            return viajes_ref[0].to_dict().get("ID", 0) + 1
        else:
            return 1 
    except:
        return 1

def guardar_en_nube(datos_viaje):
    try:
        doc_ref = db.collection("viajes").document(str(datos_viaje["ID"]))
        doc_ref.set(datos_viaje)
        return True
    except Exception as e:
        st.error(f"Error al guardar en la nube: {e}")
        return False

# --- SISTEMA DE INGRESO (LOGIN) ---
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = None

if st.session_state["usuario_actual"] == None:
    st.title("🔒 Ingreso Privado - MARBAR")
    
    usuario_ingresado = st.text_input("Usuario o DNI:")
    contrasena_ingresada = st.text_input("Contraseña:", type="password")
    
    if st.button("Entrar al Sistema"):
        if usuario_ingresado == "ADMIN" and contrasena_ingresada == "Marbar2026":
            st.session_state["usuario_actual"] = "ADMIN"
            st.session_state["nombre_empleado"] = "Administrador"
            st.rerun()
        else:
            df_usuarios = obtener_usuarios()
            usuario_encontrado = df_usuarios[df_usuarios["DNI_Usuario"].astype(str) == str(usuario_ingresado)]
            
            if not usuario_encontrado.empty:
                rol = usuario_encontrado.iloc[0]["Rol"]
                nombre = usuario_encontrado.iloc[0]["Nombre"]
                sector = usuario_encontrado.iloc[0]["Sector"] 
                
                st.session_state["usuario_actual"] = rol
                st.session_state["nombre_empleado"] = nombre
                st.session_state["sector_empleado"] = sector
                st.rerun()
            else:
                st.error("❌ DNI no registrado.")
    st.stop()

# --- INTERFAZ VISUAL ---
st.title("Gestión de Viajes - MARBAR")

# --- MIS VIAJES EN CURSO (Botón de llegada y Aviso) ---
if st.session_state["usuario_actual"] != "ADMIN":
    viajes_ref = db.collection("viajes").stream()
    mis_activos = [doc.to_dict() for doc in viajes_ref if doc.to_dict().get("Chofer") == st.session_state["nombre_empleado"] and doc.to_dict().get("Aprobacion") == "🟢 Aprobado"]
    
    if len(mis_activos) > 0:
        st.info("📍 Tienes viajes en curso.")
        for viaje in mis_activos:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**Viaje ID {viaje['ID']}** | Destino: {viaje['Destino']}")
            with col2:
                if st.button(f"🏁 Llegué a Destino", key=f"btn_llegar_{viaje['ID']}"):
                    db.collection("viajes").document(str(viaje['ID'])).update({"Aprobacion": "🏁 Finalizado"})
                    st.session_state[f"aviso_enviado_{viaje['ID']}"] = True
                    st.rerun()
                    
            if st.session_state.get(f"aviso_enviado_{viaje['ID']}", False):
                st.success("¡Llegada registrada en el sistema!")
                msj_llegada = f"Hola! Aviso que ya llegué a mi destino ({viaje['Destino']}). El viaje ID {viaje['ID']} ya está finalizado en la app."
                msj_llegada_web = msj_llegada.replace(" ", "%20")
                link_llegada = f"https://wa.me/?text={msj_llegada_web}"
                
                st.markdown(f"### [📲 INFORMAR LLEGADA AL JEFE POR WHATSAPP]({link_llegada})")
                if st.button("Limpiar Pantalla"):
                    st.session_state[f"aviso_enviado_{viaje['ID']}"] = False
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
sector_elegido = st.selectbox("Selecciona tu Sector:", list(AUTORIDADES.keys()))
lista_cargos = list(AUTORIDADES[sector_elegido].keys())
cargo_elegido = st.selectbox("Selecciona tu Cargo:", lista_cargos)
nivel_aprobacion_usuario = AUTORIDADES[sector_elegido][cargo_elegido]

st.markdown("### 2. Datos del Viaje")
if st.session_state["usuario_actual"] == "ADMIN":
    chofer = st.text_input("Nombre completo del Chofer:")
else:
    nombre_automatico = st.session_state["nombre_empleado"]
    chofer = st.text_input("Nombre completo del Chofer:", value=nombre_automatico, disabled=True)

try:
    df_v = obtener_vehiculos()
    lista_vehiculos = df_v["Vehiculo"].tolist()
except:
    lista_vehiculos = [] 

if len(lista_vehiculos) == 0:
    lista_vehiculos = ["⚠️ Pídele al ADMIN que cargue vehículos"]

vehiculo = st.selectbox("Vehículo o equipo a utilizar:", lista_vehiculos)

col1, col2 = st.columns(2)
with col1:
    origen = st.text_input("Origen:")
with col2:
    destino = st.text_input("Destino:")

# --- MAPA DE EQUIPOS Y YACIMIENTOS ---
with st.expander("📍 Consultar Mapa de Equipos en Yacimientos"):
    st.write("Consulta la ubicación de los equipos para definir origen y destino con precisión.")
    components.iframe("https://www.google.com/maps/d/u/2/embed?mid=1BPDw99m6vQAC09Kdbw9Onaj5mu-blw4&ehbc=2E312F", height=480)

# --- AYUDA DE RUTA GOOGLE MAPS ---
if origen != "" and destino != "":
    link_maps = f"https://www.google.com/maps/dir/?api=1&origin={origen.replace(' ', '+')}&destination={destino.replace(' ', '+')}"
    st.info("💡 **Cálculo de Distancia:**")
    st.markdown(f"[🗺️ Ver ruta en Google Maps para obtener la distancia exacta]({link_maps})")

duracion = st.text_input("Duración estimada (ej: 2 horas):")
tipo_salida = st.radio("Tipo de Salida:", ["Planificada", "Urgencia"], index=None)

st.markdown("### 3. Evaluación de Riesgos")
puntaje = 0

distancia = st.radio("A. Distancia del viaje:", ["< 50km", "< 100km", "< 200km", "> 200km"], index=None)
if distancia == "< 50km": puntaje += 1
elif distancia == "< 100km": puntaje += 2
elif distancia == "< 200km": puntaje += 5
else: puntaje += 7

clima = st.selectbox("B. Clima:", ["Despejado", "Nublado", "Viento", "Lluvia", "Niebla", "Nieve"], index=None)
puntos_clima = {"Despejado": 0, "Nublado": 1, "Viento": 2, "Lluvia": 4, "Niebla": 8, "Nieve": 9}
puntaje += puntos_clima.get(clima, 0)

pasajeros = st.radio("C. Vehículos y Pasajeros:", ["Con pasajeros", "Solo conductor"], index=None)
puntaje += 1 if pasajeros == "Con pasajeros" else 5

camino = st.radio("D. Condiciones del camino:", ["Pavimento", "Mixto", "Tierra"], index=None)
puntos_camino = {"Pavimento": 1, "Mixto": 2, "Tierra": 4}
puntaje += puntos_camino.get(camino, 0)

dormio = st.radio("E1. ¿El conductor durmió más de 8hs consecutivas?", ["Sí", "No"], index=None)
horas_totales = st.radio("E2. Suma las HS TRABAJANDO + HS PLANEADAS DE VIAJE:", ["< 12hs", "< 14hs", "< 16hs"], index=None)
if dormio == "Sí":
    puntos_h = {"< 12hs": 1, "< 14hs": 3, "< 16hs": 6}
else:
    puntos_h = {"< 12hs": 2, "< 14hs": 5, "< 16hs": 8}
puntaje += puntos_h.get(horas_totales, 0)

escolta = st.radio("F. ¿Necesita escolta?", ["No", "Sí"], index=None)
puntaje += 1 if escolta == "No" else 5

horario = st.radio("G. Condición de viaje:", ["Diurno", "Nocturno"], index=None)
if horario == "Nocturno":
    alarma_nocturna = "encendida"
    puntaje += 5
else:
    alarma_nocturna = "apagada"
    puntaje += 1

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
    if chofer == "" or origen == "" or destino == "" or tipo_salida == None or distancia == None or clima == None or pasajeros == None or camino == None or dormio == None or horas_totales == None or escolta == None or horario == None or comunicacion == None:
        st.error("⛔ ALTO: Por favor, responde TODAS las preguntas y completa todos los campos de texto antes de guardar el viaje.")
    else:
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
        
        exito = guardar_en_nube(datos_para_guardar)
        if exito:
            st.balloons()
            st.success(f"¡Éxito! Viaje ID {nuevo_id} registrado en el sistema en la nube de Marbar.")

            # --- EL TIMBRE DE WHATSAPP (TICKET DETALLADO) ---
            import urllib.parse
            
            # Armamos el ticket con formato de WhatsApp (* para negritas, \n para enter)
            mensaje = (
                f"🚨 *NUEVA SOLICITUD DE VIAJE - ID {nuevo_id}* 🚨\n\n"
                f"👤 *Chofer:* {chofer}\n"
                f"🚙 *Vehículo:* {vehiculo}\n"
                f"📍 *Origen:* {origen}\n"
                f"🏁 *Destino:* {destino}\n"
                f"⏱️ *Duración Est.:* {duracion}\n"
                f"⚠️ *Nivel de Riesgo:* Nivel {nivel_viaje} (Puntaje: {puntaje})\n\n"
                f"👉 Por favor, revisa y aprueba el viaje en la plataforma MARBAR."
            )
            
            # La herramienta urllib traduce los saltos de línea para que WhatsApp los entienda
            mensaje_internet = urllib.parse.quote(mensaje)
            link_whatsapp = f"https://wa.me/?text={mensaje_internet}"
            
            st.markdown(f"### [📲 TOCA AQUÍ PARA ENVIAR EL TICKET AL JEFE]({link_whatsapp})")

# --- 6. PANEL LATERAL (RESUMEN Y DESCARGA) ---
st.sidebar.markdown("---")
st.sidebar.header("📊 Resumen de Gestión")
try:
    viajes_ref = db.collection("viajes").stream()
    lista_viajes = [doc.to_dict() for doc in viajes_ref]

    if len(lista_viajes) > 0:
        df_nube = pd.DataFrame(lista_viajes)
        fecha_hoy_str = datetime.now().strftime("%d/%m/%Y")

        viajes_hoy = df_nube[df_nube['Fecha'].astype(str).str.contains(fecha_hoy_str, na=False)]
        viajes_mes = df_nube[df_nube['Fecha'].astype(str).str.contains(datetime.now().strftime("/%m/%Y"), na=False)]

        st.sidebar.metric("Viajes registrados HOY", len(viajes_hoy))
        st.sidebar.metric("Viajes de este MES", len(viajes_mes))

        viajes_pendientes = viajes_hoy[viajes_hoy['Aprobacion'] == "🔴 Pendiente"]
        viajes_en_ruta = viajes_hoy[viajes_hoy['Aprobacion'] == "🟢 Aprobado"]

        st.sidebar.markdown("---")
        st.sidebar.write("🔴 **Pendientes de Aprobación:**")
        if not viajes_pendientes.empty:
            st.sidebar.dataframe(viajes_pendientes[['Chofer', 'Destino']], hide_index=True)
        else:
            st.sidebar.write("✅ Todo al día.")

        st.sidebar.markdown("---")
        st.sidebar.write("🚚 **En ruta ahora:**")
        if not viajes_en_ruta.empty:
            st.sidebar.dataframe(viajes_en_ruta[['Chofer', 'Destino']], hide_index=True)
        else:
            st.sidebar.write("✅ No hay vehículos en ruta ahora.")

        if st.session_state["usuario_actual"] == "ADMIN":
            st.sidebar.markdown("---")
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_nube.to_excel(writer, index=False, sheet_name='Viajes_Marbar')

            st.sidebar.download_button(
                label="📥 DESCARGAR BASE DE DATOS",
                data=buffer.getvalue(),
                file_name=f"Reporte_Marbar_{fecha_hoy_str.replace('/','-')}.xlsx",
                mime="application/vnd.ms-excel"
            )
    else:
        st.sidebar.info("Aún no hay viajes en la base de datos.")
except Exception as e:
    st.sidebar.error(f"Error al conectar con la nube: {e}")

# --- BANDEJA DE APROBACIONES ---
if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia"]:
    st.markdown("---")
    st.title("📥 Bandeja de Aprobaciones")
    try:
        viajes_ref = db.collection("viajes").stream()
        lista_viajes = [doc.to_dict() for doc in viajes_ref]
        df_viajes = pd.DataFrame(lista_viajes)

        viajes_pendientes = df_viajes[df_viajes["Aprobacion"] == "🔴 Pendiente"]
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

        if mis_pendientes.empty:
            st.info("✅ No tienes viajes pendientes en tu nivel/sector.")
        else:
            st.warning(f"⚠️ Tienes {len(mis_pendientes)} viaje(s) esperando.")
            for index, viaje in mis_pendientes.iterrows():
                with st.expander(f"🚨 ID: {viaje['ID']} | {viaje['Chofer']}"):
                    st.write(f"**Ruta:** {viaje['Origen']} -> {viaje['Destino']}")
                    if st.button(f"✅ Sellar Aprobación {viaje['ID']}", key=f"btn_aprob_{viaje['ID']}"):
                        db.collection("viajes").document(str(viaje['ID'])).update({"Aprobacion": "🟢 Aprobado"})
                        st.success("Aprobado!")
                        st.rerun()
    except:
        st.info("Buscando viajes...")

# --- 7. OFICINA SECRETA DE ADMINISTRACIÓN ---
if st.session_state["usuario_actual"] == "ADMIN":
    st.markdown("---")
    st.title("🛠️ Oficina de Administración")
    pestaña_usuarios, pestaña_vehiculos = st.tabs(["👥 Usuarios", "🚘 Vehículos"])

    with pestaña_usuarios:
        nuevo_dni = st.text_input("DNI o Usuario:")
        nuevo_nombre = st.text_input("Nombre Completo:")
        nuevo_sector = st.selectbox("Sector:", ["Higiene y Seguridad", "Fluidos", "Control de Sólidos", "Completación", "Administración", "Mantenimiento", "Gerencia"])
        nuevo_rol = st.selectbox("Nivel:", ["Chofer", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia", "ADMIN"])

        if st.button("💾 Guardar Usuario"):
            if nuevo_dni and nuevo_nombre:
                datos_u = {"DNI_Usuario": str(nuevo_dni), "Nombre": nuevo_nombre, "Rol": nuevo_rol, "Sector": nuevo_sector}
                db.collection("usuarios").document(str(nuevo_dni)).set(datos_u)
                st.success("Guardado!")
                st.rerun()
        
        df_u_actual = obtener_usuarios()
        st.subheader("🗑️ Eliminar")
        if not df_u_actual.empty:
            usuario_borrar = st.selectbox("Selecciona DNI:", [""] + df_u_actual["DNI_Usuario"].tolist())
            if st.button("Eliminar"):
                if usuario_borrar:
                    db.collection("usuarios").document(usuario_borrar).delete()
                    st.rerun()
        st.dataframe(df_u_actual, hide_index=True)

    with pestaña_vehiculos:
        nuevo_vehiculo = st.text_input("Patente:")
        if st.button("💾 Guardar"):
            if nuevo_vehiculo:
                db.collection("vehiculos").document(nuevo_vehiculo).set({"Vehiculo": nuevo_vehiculo})
                st.rerun()

        df_v_actual = obtener_vehiculos()
        st.subheader("🗑️ Eliminar")
        if not df_v_actual.empty:
            vehiculo_borrar = st.selectbox("Selecciona Vehículo:", [""] + df_v_actual["Vehiculo"].tolist())
            if st.button("Eliminar Vehículo"):
                if vehiculo_borrar:
                    db.collection("vehiculos").document(vehiculo_borrar).delete()
                    st.rerun()
        st.dataframe(df_v_actual, hide_index=True)
