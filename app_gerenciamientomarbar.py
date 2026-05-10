import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
import os
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import urllib.parse

# --- CONEXIÓN A LA BÓVEDA EN LA NUBE (FIREBASE) ---
if not firebase_admin._apps:
    try:
        llave_secreta = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(llave_secreta)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Error con la llave secreta: {e}")

db = firestore.client()

# --- CONECTORES DE DATOS ---
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
    u_ing = st.text_input("Usuario o DNI:")
    c_ing = st.text_input("Contraseña:", type="password")
    
    if st.button("Entrar al Sistema"):
        if u_ing == "ADMIN" and c_ing == "Marbar2026":
            st.session_state.update({"usuario_actual": "ADMIN", "nombre_empleado": "Administrador"})
            st.rerun()
        else:
            df_u = obtener_usuarios()
            user = df_u[df_u["DNI_Usuario"].astype(str) == str(u_ing)]
            if not user.empty:
                st.session_state.update({
                    "usuario_actual": user.iloc[0]["Rol"],
                    "nombre_empleado": user.iloc[0]["Nombre"],
                    "sector_empleado": user.iloc[0]["Sector"]
                })
                st.rerun()
            else:
                st.error("❌ DNI no registrado.")
    st.stop()

# --- INTERFAZ VISUAL ---
st.title("Gestión de Viajes - MARBAR")

# --- MIS VIAJES EN CURSO (Botón de llegada) ---
if st.session_state["usuario_actual"] != "ADMIN":
    viajes_ref = db.collection("viajes").stream()
    mis_activos = [d.to_dict() for d in viajes_ref if d.to_dict().get("Chofer") == st.session_state["nombre_empleado"] and d.to_dict().get("Aprobacion") == "🟢 Aprobado"]
    
    if len(mis_activos) > 0:
        st.info("📍 Tienes viajes en curso. Avisa al llegar.")
        for v in mis_activos:
            c1, c2 = st.columns([3, 1])
            c1.write(f"**ID {v['ID']}** | Destino: {v['Destino']}")
            if c2.button(f"🏁 Llegué", key=f"llegar_{v['ID']}"):
                db.collection("viajes").document(str(v['ID'])).update({"Aprobacion": "🏁 Finalizado"})
                st.session_state[f"fin_{v['ID']}"] = True
                st.rerun()
            
            if st.session_state.get(f"fin_{v['ID']}", False):
                msj = f"✅ *REPORTE DE LLEGADA*\nEl viaje ID {v['ID']} con destino {v['Destino']} ha sido FINALIZADO correctamente."
                st.markdown(f"### [📲 INFORMAR POR WHATSAPP](https://wa.me/?text={urllib.parse.quote(msj)})")
                if st.button("Limpiar", key=f"clear_{v['ID']}"):
                    st.session_state[f"fin_{v['ID']}"] = False
                    st.rerun()
        st.markdown("---")

st.subheader("Formulario de Despacho Seguro")

AUTORIDADES = {
    "Higiene y Seguridad": {"Coordinador SSA": 1, "Jefe SSA": 2},
    "Logistica": {"Chofer": 0, "Coordinador de Logistica": 1, "Jefe de Logistica": 2},
    "Fluidos": {"Supervisor de SFP": 1, "Jefe de SFP": 2},
    "Control de solidos": {"Supervisor de CDS": 1, "Jefe de CDS": 2},
    "Mantenimiento": {"Mecanico / Electrico / Soldador": 1, "Jefe de Mantenimiento": 2},
    "Gerencia": {"Jefe de Operaciones / Gerente General": 3}
}

# --- 1. DATOS DEL SOLICITANTE ---
st.markdown("### 1. Datos del Solicitante")
sec_elegido = st.selectbox("Selecciona tu Sector:", list(AUTORIDADES.keys()))
car_elegido = st.selectbox("Selecciona tu Cargo:", list(AUTORIDADES[sec_elegido].keys()))
niv_aprob = AUTORIDADES[sec_elegido][car_elegido]

# --- 2. DATOS DEL VIAJE ---
st.markdown("### 2. Datos del Viaje")
chofer = st.text_input("Chofer:", value=st.session_state["nombre_empleado"], disabled=(st.session_state["usuario_actual"] != "ADMIN"))

df_v = obtener_vehiculos()
vehiculos_lista = df_v["Vehiculo"].tolist() if not df_v.empty else ["⚠️ Cargar vehículos"]
vehiculo = st.selectbox("Vehículo o equipo a utilizar:", vehiculos_lista)

# --- MAPA INTERACTIVO (CONSULTA) ---
with st.expander("🗺️ ABRIR MAPA DE YACIMIENTOS Y EQUIPOS", expanded=True):
    st.write("Identifica tu ubicación y el equipo de destino en el mapa.")
    components.iframe("https://www.google.com/maps/d/u/2/embed?mid=1BPDw99m6vQAC09Kdbw9Onaj5mu-blw4&ehbc=2E312F", height=480)

col1, col2 = st.columns(2)
with col1:
    origen = st.text_input("Origen (Tu ubicación en el mapa):")
with col2:
    # Usamos los vehículos cargados como lista de equipos/destinos sugeridos
    destino = st.selectbox("Destino (Selecciona el Equipo del Mapa):", ["Escribir otro..."] + vehiculos_lista)
    if destino == "Escribir otro...":
        destino = st.text_input("Escribe el nombre del Equipo/Pozo/Base:")

if origen and destino:
    link_m = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(origen)}&destination={urllib.parse.quote(destino)}"
    st.info("💡 [Toca aquí para calcular distancia exacta en Google Maps]("+link_m+")")

duracion = st.text_input("Duración estimada (ej: 2 horas):")
tipo_salida = st.radio("Tipo de Salida:", ["Planificada", "Urgencia"], index=None)

# --- 3. RIESGOS ---
st.markdown("### 3. Evaluación de Riesgos")
puntaje = 0
dist = st.radio("A. Distancia:", ["< 50km", "< 100km", "< 200km", "> 200km"], index=None)
if dist == "< 50km": puntaje += 1
elif dist == "< 100km": puntaje += 2
elif dist == "< 200km": puntaje += 5
else: puntaje += 7

clima = st.selectbox("B. Clima:", ["Despejado", "Viento", "Lluvia", "Niebla", "Nieve"], index=None)
puntos_clima = {"Despejado": 0, "Viento": 2, "Lluvia": 4, "Niebla": 8, "Nieve": 9}
puntaje += puntos_clima.get(clima, 0)

pasajeros = st.radio("C. Pasajeros:", ["Con pasajeros", "Solo conductor"], index=None)
puntaje += 1 if pasajeros == "Con pasajeros" else 5

camino = st.radio("D. Camino:", ["Pavimento", "Mixto", "Tierra"], index=None)
puntos_camino = {"Pavimento": 1, "Mixto": 2, "Tierra": 4}
puntaje += puntos_camino.get(camino, 0)

dormio = st.radio("E1. ¿Durmió +8hs?", ["Sí", "No"], index=None)
hs_totales = st.radio("E2. Horas totales (Trabajo+Viaje):", ["< 12hs", "< 14hs", "< 16hs"], index=None)
p_h = {"< 12hs": (1 if dormio=="Sí" else 2), "< 14hs": (3 if dormio=="Sí" else 5), "< 16hs": (6 if dormio=="Sí" else 8)}
puntaje += p_h.get(hs_totales, 0)

escolta = st.radio("F. ¿Necesita escolta?", ["No", "Sí"], index=None)
puntaje += 1 if escolta == "No" else 5

horario = st.radio("G. Condición:", ["Diurno", "Nocturno"], index=None)
alarma_n = "encendida" if horario == "Nocturno" else "apagada"
puntaje += 5 if horario == "Nocturno" else 1

com = st.radio("H. Comunicación:", ["Total", "Tramos sin señal", "Sin señal"], index=None)
puntaje += {"Total": 1, "Tramos sin señal": 3, "Sin señal": 5}.get(com, 0)

# --- 4. RESULTADO ---
nivel_v = 1 if puntaje <= 15 else (2 if puntaje <= 30 else 3)
if niv_aprob >= nivel_v:
    estado_v = f"AUTORIZADO (Auto-aprobado por {car_elegido})"
    color = "green"
else:
    estado_v = f"PENDIENTE (Nivel {nivel_v})"
    color = "orange" if nivel_v < 3 else "red"

st.markdown("---")
if color == "green": st.success(f"**{estado_v}** | Riesgo: {nivel_v} | Puntos: {puntaje}")
elif color == "orange": st.warning(f"**{estado_v}** | Riesgo: {nivel_v} | Puntos: {puntaje}")
else: st.error(f"**{estado_v}** | Riesgo: {nivel_v} | Puntos: {puntaje}")

# --- 5. GUARDADO Y TICKET ---
if st.button("CONFIRMAR Y GUARDAR VIAJE"):
    if not (origen and destino and tipo_salida and dist and clima):
        st.error("⛔ Por favor responde todas las preguntas.")
    else:
        nid = obtener_siguiente_id()
        datos = {
            "ID": nid, "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "Chofer": chofer, "Sector": sec_elegido, "Cargo": car_elegido,
            "Vehiculo": vehiculo, "Origen": origen, "Destino": destino,
            "Duracion": duracion, "Salida": tipo_salida, "Puntaje": puntaje,
            "Nivel": nivel_v, "Alarma Nocturna": alarma_n, "Estado": estado_v,
            "Aprobacion": "🟢 Aprobado" if color == "green" else "🔴 Pendiente"
        }
        if guardar_en_nube(datos):
            st.balloons()
            # TICKET DETALLADO DE WHATSAPP
            tkt = (
                f"🚨 *NUEVA SOLICITUD DE VIAJE - ID {nid}* 🚨\n\n"
                f"👤 *Chofer:* {chofer}\n"
                f"🚙 *Vehículo:* {vehiculo}\n"
                f"📍 *Origen:* {origen}\n"
                f"🏁 *Destino:* {destino}\n"
                f"⏱️ *Duración:* {duracion}\n"
                f"⚠️ *Riesgo:* Nivel {nivel_v} ({puntaje} pts)\n"
                f"📢 *Estado:* {estado_v}\n\n"
                f"👉 Por favor, apruebe en el sistema MARBAR."
            )
            link_w = f"https://wa.me/?text={urllib.parse.quote(tkt)}"
            st.markdown(f"### [📲 ENVIAR TICKET DE DESPACHO]({link_w})")

# --- 6. PANEL LATERAL ---
st.sidebar.header("📊 Gestión")
try:
    v_ref = db.collection("viajes").stream()
    df_n = pd.DataFrame([doc.to_dict() for doc in v_ref])
    if not df_n.empty:
        hoy = datetime.now().strftime("%d/%m/%Y")
        v_hoy = df_n[df_n['Fecha'].str.contains(hoy, na=False)]
        st.sidebar.metric("Viajes HOY", len(v_hoy))
        
        st.sidebar.write("🔴 **Pendientes:**")
        st.sidebar.dataframe(v_hoy[v_hoy['Aprobacion']=="🔴 Pendiente"][['Chofer','Destino']], hide_index=True)
        
        st.sidebar.write("🚚 **En ruta:**")
        st.sidebar.dataframe(v_hoy[v_hoy['Aprobacion']=="🟢 Aprobado"][['Chofer','Destino']], hide_index=True)

        if st.session_state["usuario_actual"] == "ADMIN":
            import io
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as wr:
                df_n.to_excel(wr, index=False)
            st.sidebar.download_button("📥 Descargar Base", buf.getvalue(), f"Marbar_{hoy}.xlsx")
except: pass

# --- 7. ADMINISTRACIÓN ---
if st.session_state["usuario_actual"] == "ADMIN":
    st.markdown("---")
    st.title("🛠️ Administración")
    t1, t2 = st.tabs(["👥 Usuarios", "🚘 Vehículos"])
    with t1:
        d = st.text_input("DNI:")
        n = st.text_input("Nombre:")
        s = st.selectbox("Sector:", ["Higiene y Seguridad", "Fluidos", "Control de Sólidos", "Completación", "Administración", "Mantenimiento", "Gerencia"])
        r = st.selectbox("Rol:", ["Chofer", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia", "ADMIN"])
        if st.button("💾 Guardar"):
            db.collection("usuarios").document(d).set({"DNI_Usuario":d,"Nombre":n,"Rol":r,"Sector":s})
            st.rerun()
        u_list = obtener_usuarios()
        st.dataframe(u_list, hide_index=True)
        elim = st.selectbox("Borrar DNI:", [""] + u_list["DNI_Usuario"].tolist())
        if st.button("Eliminar Usuario"):
            db.collection("usuarios").document(elim).delete()
            st.rerun()
    with t2:
        pat = st.text_input("Patente/Equipo:")
        if st.button("💾 Agregar"):
            db.collection("vehiculos").document(pat).set({"Vehiculo": pat})
            st.rerun()
        v_list = obtener_vehiculos()
        st.dataframe(v_list, hide_index=True)
        elim_v = st.selectbox("Borrar Equipo:", [""] + v_list["Vehiculo"].tolist())
        if st.button("Eliminar Vehículo"):
            db.collection("vehiculos").document(elim_v).delete()
            st.rerun()