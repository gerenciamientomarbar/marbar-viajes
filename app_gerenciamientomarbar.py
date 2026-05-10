import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
import json
import firebase_admin
from firebase_admin import credentials, firestore
import urllib.parse
import io

# --- CONEXIÓN A LA BÓVEDA EN LA NUBE (FIREBASE) ---
if not firebase_admin._apps:
    try:
        llave_secreta = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(llave_secreta)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Error con la llave secreta: {e}")

db = firestore.client()

# --- FUNCIONES DE CONEXIÓN A DATOS ---
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
    return pd.DataFrame(lista) if lista else pd.DataFrame(columns=["Vehiculo"])

def obtener_siguiente_id():
    try:
        viajes_ref = db.collection("viajes").order_by("ID", direction=firestore.Query.DESCENDING).limit(1).get()
        return viajes_ref[0].to_dict().get("ID", 0) + 1 if viajes_ref else 1
    except: return 1

def guardar_en_nube(datos_viaje):
    try:
        db.collection("viajes").document(str(datos_viaje["ID"])).set(datos_viaje)
        return True
    except: return False

# --- SISTEMA DE INGRESO (LOGIN) ---
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = None

if st.session_state["usuario_actual"] == None:
    st.title("\U0001F512 Ingreso Privado - MARBAR")
    u_ing = st.text_input("Usuario o DNI:")
    c_ing = st.text_input("Contraseña:", type="password")
    if st.button("Entrar al Sistema"):
        if u_ing == "ADMIN" and c_ing == "Marbar2026":
            st.session_state.update({"usuario_actual": "ADMIN", "nombre_empleado": "Administrador", "sector_empleado": "Gerencia"})
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
            else: st.error("\u274C DNI no registrado.")
    st.stop()

# --- INTERFAZ PRINCIPAL ---
st.title("Gestión de Viajes - MARBAR")

# --- MIS VIAJES EN CURSO (Botón de llegada) ---
if st.session_state["usuario_actual"] != "ADMIN":
    viajes_ref = db.collection("viajes").stream()
    mis_activos = [d.to_dict() for d in viajes_ref if d.to_dict().get("Chofer") == st.session_state["nombre_empleado"] and d.to_dict().get("Aprobacion") == "\U0001F7E2 Aprobado"]
    if mis_activos:
        st.info("\U0001F4CD Tienes viajes en curso. Avisa al llegar.")
        for v in mis_activos:
            c1, c2 = st.columns([3, 1])
            c1.write(f"**ID {v['ID']}** | Destino: {v['Destino']}")
            if c2.button(f"\U0001F3C1 Llegué", key=f"llegar_{v['ID']}"):
                db.collection("viajes").document(str(v['ID'])).update({"Aprobacion": "\U0001F3C1 Finalizado"})
                st.session_state[f"fin_{v['ID']}"] = True
                st.rerun()
            if st.session_state.get(f"fin_{v['ID']}", False):
                msj = f"\u2705 *REPORTE DE LLEGADA*\nEl viaje ID {v['ID']} con destino {v['Destino']} ha sido FINALIZADO correctamente."
                st.markdown(f"### [\U0001F4F2 INFORMAR POR WHATSAPP](https://wa.me/?text={urllib.parse.quote(msj)})")
        st.markdown("---")

st.subheader("Formulario de Despacho Seguro")

AUTORIDADES = {
    "Higiene y Seguridad": {"Coordinador SSA": 1, "Jefe SSA": 2},
    "Logistica": {"Chofer": 0, "Coordinador de Logistica": 1, "Jefe de Logistica": 2},
    "Fluidos": {"Supervisor de SFP": 1, "Jefe de SFP": 2},
    "Control de solidos": {"Supervisor de CDS": 1, "Jefe de CDS": 2},
    "Mantenimiento": {"Mecanico / Electrico": 1, "Jefe de Mantenimiento": 2},
    "Gerencia": {"Gerente General": 3}
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
vehiculo = st.selectbox("Vehículo:", df_v["Vehiculo"].tolist() if not df_v.empty else ["⚠️ Cargar vehículos"])

with st.expander("\U0001F5FA ABRIR MAPA DE YACIMIENTOS Y EQUIPOS", expanded=True):
    st.write("Identifica tu equipo. Usa la **flecha roja** del mapa para ruta y distancia.")
    components.iframe("https://www.google.com/maps/d/u/2/embed?mid=1BPDw99m6vQAC09Kdbw9Onaj5mu-blw4&ehbc=2E312F", height=480)

col1, col2 = st.columns(2)
with col1: origen = st.text_input("Origen (Tu ubicación actual):")
with col2: destino_final = st.text_input("Destino (Equipo del mapa):")

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

clima = st.selectbox("B. Clima:", ["Despejado", "Nublado", "Viento", "Lluvia", "Niebla", "Nieve"], index=None)
puntaje += {"Despejado":0, "Nublado":1, "Viento":2, "Lluvia":4, "Niebla":8, "Nieve":9}.get(clima, 0)

pasajeros = st.radio("C. Pasajeros:", ["Con pasajeros", "Solo conductor"], index=None)
puntaje += 1 if pasajeros == "Con pasajeros" else 5

camino = st.radio("D. Camino:", ["Pavimento", "Mixto", "Tierra"], index=None)
puntaje += {"Pavimento":1, "Mixto":2, "Tierra":4}.get(camino, 0)

dormio = st.radio("E1. ¿Durmió +8hs?", ["Sí", "No"], index=None)
hs_tot = st.radio("E2. Horas totales:", ["< 12hs", "< 14hs", "< 16hs"], index=None)
p_h = {"< 12hs": (1 if dormio=="Sí" else 2), "< 14hs": (3 if dormio=="Sí" else 5), "< 16hs": (6 if dormio=="Sí" else 8)}
puntaje += p_h.get(hs_tot, 0)

escolta = st.radio("F. ¿Escolta?", ["No", "Sí"], index=None)
puntaje += 1 if escolta == "No" else 5

horario = st.radio("G. Horario:", ["Diurno", "Nocturno"], index=None)
puntaje += 5 if horario == "Nocturno" else 1

com = st.radio("H. Comunicación:", ["Total", "Tramos sin señal", "Sin señal"], index=None)
puntaje += {"Total":1, "Tramos sin señal":3, "Sin señal":5}.get(com, 0)

nivel_v = 1 if puntaje <= 15 else (2 if puntaje <= 30 else 3)
color = "green" if niv_aprob >= nivel_v else ("orange" if nivel_v < 3 else "red")
estado_v = f"AUTORIZADO" if color == "green" else f"PENDIENTE (Nivel {nivel_v})"

st.markdown("---")
if color == "green": st.success(f"**{estado_v}** | Riesgo: {nivel_v} | Puntos: {puntaje}")
elif color == "orange": st.warning(f"**{estado_v}** | Riesgo: {nivel_v} | Puntos: {puntaje}")
else: st.error(f"**{estado_v}** | Riesgo: {nivel_v} | Puntos: {puntaje}")

# --- 5. GUARDADO Y TICKET ---
if st.button("CONFIRMAR Y GUARDAR VIAJE"):
    if not (origen and destino_final and tipo_salida and dist):
        st.error("\u26D4 Completa todos los campos.")
    else:
        nid = obtener_siguiente_id()
        datos = {
            "ID": nid, "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "Chofer": chofer, "Sector": sec_elegido, "Cargo": car_elegido, "Vehiculo": vehiculo,
            "Origen": origen, "Destino": destino_final, "Duracion": duracion, "Salida": tipo_salida,
            "Puntaje": puntaje, "Nivel": nivel_v, "Estado": estado_v,
            "Aprobacion": "\U0001F7E2 Aprobado" if color == "green" else "\U0001F534 Pendiente"
        }
        if guardar_en_nube(datos):
            st.balloons()
            tkt = (
                f"\U0001F534 *SOLICITUD DE VIAJE - ID {nid}* \U0001F534\n\n"
                f"\U0001F464 *Chofer:* {chofer}\n\n"
                f"\U0001F69A *Vehículo:* {vehiculo}\n\n"
                f"\U0001F4CD *Origen:* {origen}\n\n"
                f"\U0001F3C1 *Destino:* {destino_final}\n\n"
                f"\u23F3 *Duración:* {duracion}\n\n"
                f"\u26A0\uFE0F *Riesgo:* Nivel {nivel_v} ({puntaje} pts)\n\n"
                f"\U0001F4CB *Estado:* {estado_v}\n\n"
                f"\U0001F449 Por favor, apruebe en el sistema MARBAR."
            )
            st.markdown(f"### [\U0001F4F2 ENVIAR TICKET POR WHATSAPP](https://wa.me/?text={urllib.parse.quote(tkt)})")

# --- 6. PANEL LATERAL ---
st.sidebar.header("\U0001F4CA Gestión")
try:
    v_ref = db.collection("viajes").stream()
    df_n = pd.DataFrame([doc.to_dict() for doc in v_ref])
    if not df_n.empty:
        hoy = datetime.now().strftime("%d/%m/%Y")
        v_hoy = df_n[df_n['Fecha'].str.contains(hoy, na=False)]
        st.sidebar.metric("Viajes HOY", len(v_hoy))
        st.sidebar.write("\U0001F534 **Pendientes:**")
        st.sidebar.dataframe(v_hoy[v_hoy['Aprobacion']=="\U0001F534 Pendiente"][['Chofer','Destino']], hide_index=True)
        st.sidebar.write("\U0001F699 **En ruta:**")
        st.sidebar.dataframe(v_hoy[v_hoy['Aprobacion']=="\U0001F7E2 Aprobado"][['Chofer','Destino']], hide_index=True)
        if st.session_state["usuario_actual"] == "ADMIN":
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as wr: df_n.to_excel(wr, index=False)
            st.sidebar.download_button("\U0001F4E5 Descargar Base", buf.getvalue(), f"Marbar_{hoy}.xlsx")
except: pass

# --- BANDEJA DE APROBACIONES ---
if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia"]:
    st.markdown("---")
    st.title("\U0001F4E5 Bandeja de Aprobaciones")
    try:
        v_ref = db.collection("viajes").stream()
        df_v = pd.DataFrame([doc.to_dict() for doc in v_ref])
        if not df_v.empty:
            pend = df_v[df_v["Aprobacion"] == "\U0001F534 Pendiente"]
            rol = st.session_state["usuario_actual"]
            sec = st.session_state.get("sector_empleado", "")
            if rol == "ADMIN": mis_p = pend
            elif rol == "Gerencia": mis_p = pend[pend["Nivel"] == 3]
            elif rol == "Jefe de Servicio": mis_p = pend[(pend["Nivel"] == 2) & (pend["Sector"] == sec)]
            elif rol == "Supervisor / Coordinador": mis_p = pend[(pend["Nivel"] == 1) & (pend["Sector"] == sec)]
            else: mis_p = pd.DataFrame()

            if mis_p.empty: st.info("\u2705 Sin pendientes.")
            else:
                for idx, viaje in mis_p.iterrows():
                    with st.expander(f"\U0001F6A8 ID: {viaje['ID']} | {viaje['Chofer']}"):
                        st.write(f"**Ruta:** {viaje['Origen']} -> {viaje['Destino']}")
                        if st.button(f"\u2705 Aprobar {viaje['ID']}", key=f"aprob_{viaje['ID']}"):
                            db.collection("viajes").document(str(viaje['ID'])).update({"Aprobacion": "\U0001F7E2 Aprobado"})
                            st.rerun()
    except: pass

# --- 7. ADMINISTRACIÓN ---
if st.session_state["usuario_actual"] == "ADMIN":
    st.markdown("---")
    st.title("\U0001F6E0 Administración")
    t1, t2 = st.tabs(["\U0001F465 Usuarios", "\U0001F699 Vehículos"])
    with t1:
        d = st.text_input("DNI:")
        n = st.text_input("Nombre:")
        s = st.selectbox("Sector:", ["Higiene y Seguridad", "Fluidos", "Control de Sólidos", "Completación", "Administración", "Mantenimiento", "Gerencia"])
        r = st.selectbox("Rol:", ["Chofer", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia", "ADMIN"])
        if st.button("\U0001F4BE Guardar Usuario"):
            db.collection("usuarios").document(d).set({"DNI_Usuario":d,"Nombre":n,"Rol":r,"Sector":s})
            st.rerun()
        u_list = obtener_usuarios()
        st.dataframe(u_list, hide_index=True)
        elim = st.selectbox("Borrar DNI:", [""] + u_list["DNI_Usuario"].tolist())
        if st.button("Eliminar"): db.collection("usuarios").document(elim).delete(); st.rerun()
    with t2:
        pat = st.text_input("Patente/Equipo:")
        if st.button("\U0001F4BE Agregar"):
            db.collection("vehiculos").document(pat).set({"Vehiculo": pat})
            st.rerun()
        v_list = obtener_vehiculos()
        st.dataframe(v_list, hide_index=True)
        el_v = st.selectbox("Borrar Equipo:", [""] + v_list["Vehiculo"].tolist())
        if st.button("Borrar"): db.collection("vehiculos").document(el_v).delete(); st.rerun()