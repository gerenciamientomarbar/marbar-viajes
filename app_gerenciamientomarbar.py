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

# --- FUNCIONES DE DATOS ---
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

# --- LOGIN ---
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
                st.session_state.update({"usuario_actual": user.iloc[0]["Rol"], "nombre_empleado": user.iloc[0]["Nombre"], "sector_empleado": user.iloc[0]["Sector"]})
                st.rerun()
            else: st.error("\u274C DNI no registrado.")
    st.stop()

# --- INTERFAZ PRINCIPAL ---
st.title("Gestión de Viajes - MARBAR")

# --- BOTÓN DE LLEGADA (CIERRE DE VIAJE) ---
if st.session_state["usuario_actual"] != "ADMIN":
    activos = [d.to_dict() for d in db.collection("viajes").where("Chofer", "==", st.session_state["nombre_empleado"]).where("Estado_Viaje", "==", "En viaje").stream()]
    if activos:
        st.info("\U0001F4CD Tienes viajes en curso. Avisa al llegar.")
        for v in activos:
            c1, c2 = st.columns([3, 1])
            c1.write(f"**Viaje ID {v['ID']}** | Destino: {v['Destino']}")
            if c2.button(f"\U0001F3C1 Llegué", key=f"llegar_{v['ID']}"):
                # ACTUALIZAMOS COLUMNAS 17 Y 18
                db.collection("viajes").document(str(v['ID'])).update({
                    "Aprobacion": "\U0001F3C1 Finalizado",
                    "Estado_Viaje": "Finalizado",
                    "Fecha_Fin": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                })
                st.session_state[f"fin_{v['ID']}"] = True
                st.rerun()
            if st.session_state.get(f"fin_{v['ID']}", False):
                msj = f"\u2705 *REPORTE DE LLEGADA*\nEl viaje ID {v['ID']} con destino {v['Destino']} ha sido FINALIZADO correctamente en la plataforma."
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

# --- 1. DATOS SOLICITANTE ---
st.markdown("### 1. Datos del Solicitante")
sec_elegido = st.selectbox("Selecciona tu Sector:", list(AUTORIDADES.keys()))
car_elegido = st.selectbox("Selecciona tu Cargo:", list(AUTORIDADES[sec_elegido].keys()))
niv_aprob = AUTORIDADES[sec_elegido][car_elegido]

# --- 2. DATOS VIAJE ---
st.markdown("### 2. Datos del Viaje")
chofer = st.text_input("Chofer:", value=st.session_state["nombre_empleado"], disabled=(st.session_state["usuario_actual"] != "ADMIN"))
df_v = obtener_vehiculos()
vehiculo = st.selectbox("Vehículo:", df_v["Vehiculo"].tolist() if not df_v.empty else ["⚠️ Cargar vehículos"])

with st.expander("\U0001F5FA CONSULTAR MAPA DE EQUIPOS", expanded=True):
    components.iframe("https://www.google.com/maps/d/u/2/embed?mid=1BPDw99m6vQAC09Kdbw9Onaj5mu-blw4&ehbc=2E312F", height=480)

col1, col2 = st.columns(2)
with col1: origen = st.text_input("Origen (Tu ubicación actual):")
with col2: destino_final = st.text_input("Destino (Pega aquí el equipo del mapa):")

duracion = st.text_input("Duración estimada (ej: 2 horas):")
tipo_salida = st.radio("Tipo de Salida:", ["Planificada", "Urgencia"], index=None)

# --- 3. RIESGOS ---
st.markdown("### 3. Evaluación de Riesgos")
puntaje = 0
dist = st.radio("A. Distancia:", ["< 50km", "< 100km", "< 200km", "> 200km"], index=None)
puntaje += {"< 50km":1, "< 100km":2, "< 200km":5, "> 200km":7}.get(dist, 0)

clima = st.selectbox("B. Clima:", ["Despejado", "Viento", "Lluvia", "Niebla", "Nieve"], index=None)
puntaje += {"Despejado":0, "Viento":2, "Lluvia":4, "Niebla":8, "Nieve":9}.get(clima, 0)

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

# --- 5. GUARDADO ---
if st.button("CONFIRMAR Y GUARDAR VIAJE"):
    if not (origen and destino_final and tipo_salida and dist):
        st.error("\u26D4 Completa los campos obligatorios.")
    else:
        nid = obtener_siguiente_id()
        # CREAMOS EL REGISTRO CON LAS 18 COLUMNAS DISPONIBLES
        datos = {
            "ID": nid, 
            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "Chofer": chofer, 
            "Sector": sec_elegido, 
            "Cargo": car_elegido, 
            "Vehiculo": vehiculo,
            "Duracion": duracion, 
            "Salida": tipo_salida,
            "Alarma Nocturna": "encendida" if horario == "Nocturno" else "apagada",
            "Origen": origen, 
            "Destino": destino_final, 
            "Estado": estado_v,
            "Puntaje": puntaje, 
            "Nivel": nivel_v, 
            "Aprobacion": "\U0001F7E2 Aprobado" if color == "green" else "\U0001F534 Pendiente",
            "Aprobador": st.session_state["nombre_empleado"] if color == "green" else "Pendiente",
            "Estado_Viaje": "En viaje" if color == "green" else "En espera",
            "Fecha_Fin": "En curso"
        }
        if guardar_en_nube(datos):
            st.balloons()
            # TICKET WHATSAPP (Emojis Irrompibles)
            tkt = (
                f"\U0001F534 *NUEVA SOLICITUD ID {nid}* \U0001F534\n\n"
                f"\U0001F464 *Chofer:* {chofer}\n"
                f"\U0001F69A *Vehículo:* {vehiculo}\n"
                f"\U0001F4CD *Origen:* {origen}\n"
                f"\U0001F3C1 *Destino:* {destino_final}\n"
                f"\u23F3 *Duración:* {duracion}\n"
                f"\u26A0\uFE0F *Riesgo:* Nivel {nivel_v}\n\n"
                f"\U0001F449 Por favor, apruebe en la plataforma MARBAR."
            )
            st.markdown(f"### [\U0001F4F2 ENVIAR TICKET POR WHATSAPP](https://wa.me/?text={urllib.parse.quote(tkt)})")

# --- 6. PANEL LATERAL (HISTORIAL Y EXCEL DE 18 COLUMNAS) ---
st.sidebar.header("\U0001F4CA Gestión y Auditoría")
try:
    v_ref = db.collection("viajes").stream()
    df_n = pd.DataFrame([doc.to_dict() for doc in v_ref])
    if not df_n.empty:
        # --- HISTORIAL INDIVIDUAL ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("📜 Historial de Viajes")
        lista_ids = df_n["ID"].astype(str).tolist()
        viaje_sel = st.sidebar.selectbox("Ver detalle (ID):", [""] + sorted(lista_ids, key=int, reverse=True))
        if viaje_sel:
            v_data = df_n[df_n["ID"].astype(str) == viaje_sel].iloc[0]
            st.sidebar.info(f"**Chofer:** {v_data.get('Chofer')}\n\n**Estado:** {v_data.get('Estado_Viaje')}")
            # Reporte rápido en texto
            reporte = f"VIAJE ID {viaje_sel}\nFecha: {v_data.get('Fecha')}\nRuta: {v_data.get('Origen')} -> {v_data.get('Destino')}\nCierre: {v_data.get('Fecha_Fin')}"
            st.sidebar.download_button("📄 Bajar Ficha (.txt)", reporte, f"Viaje_{viaje_sel}.txt")

        # --- EXCEL GLOBAL CON EL ORDEN DE 18 COLUMNAS ---
        if st.session_state["usuario_actual"] == "ADMIN":
            st.sidebar.markdown("---")
            st.sidebar.subheader("📥 Reporte Maestro")
            orden_18 = [
                'ID', 'Fecha', 'Chofer', 'Sector', 'Cargo', 'Vehiculo', 
                'Duracion', 'Salida', 'Alarma Nocturna', 'Origen', 'Destino', 
                'Estado', 'Puntaje', 'Nivel', 'Aprobacion', 'Aprobador', 
                'Estado_Viaje', 'Fecha_Fin'
            ]
            for col in orden_18: 
                if col not in df_n.columns: df_n[col] = "N/A"
            df_export = df_n[orden_18]
            
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as wr: df_export.to_excel(wr, index=False)
            st.sidebar.download_button("Descargar Excel de 18 Columnas", buf.getvalue(), f"Auditoria_Marbar_{datetime.now().strftime('%d-%m')}.xlsx")
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

            if not mis_p.empty:
                for idx, viaje in mis_p.iterrows():
                    with st.expander(f"\U0001F6A8 ID: {viaje['ID']} | {viaje['Chofer']}"):
                        st.write(f"**Ruta:** {viaje['Origen']} -> {viaje['Destino']}")
                        if st.button(f"\u2705 Sellar Aprobación {viaje['ID']}", key=f"ap_{viaje['ID']}"):
                            db.collection("viajes").document(str(viaje['ID'])).update({
                                "Aprobacion": "\U0001F7E2 Aprobado",
                                "Aprobador": st.session_state["nombre_empleado"],
                                "Estado_Viaje": "En viaje"
                            })
                            st.rerun()
            else: st.info("\u2705 Sin pendientes.")
    except: pass

# --- ADMINISTRACIÓN ---
if st.session_state["usuario_actual"] == "ADMIN":
    st.markdown("---")
    st.title("\U0001F6E0 Configuración")
    t1, t2 = st.tabs(["👥 Usuarios", "🚘 Flota"])
    with t1:
        d = st.text_input("DNI:")
        n = st.text_input("Nombre:")
        s = st.selectbox("Sector:", ["Higiene y Seguridad", "Logistica", "Fluidos", "Control de solidos", "Mantenimiento", "Gerencia"])
        r = st.selectbox("Rol:", ["Chofer", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia", "ADMIN"])
        if st.button("\U0001F4BE Guardar Usuario"):
            db.collection("usuarios").document(d).set({"DNI_Usuario":d,"Nombre":n,"Rol":r,"Sector":s})
            st.rerun()
        u_list = obtener_usuarios()
        st.dataframe(u_list, hide_index=True)
        elim = st.selectbox("Borrar:", [""] + u_list["DNI_Usuario"].tolist())
        if st.button("Eliminar"): db.collection("usuarios").document(elim).delete(); st.rerun()
    with t2:
        pat = st.text_input("Equipo:")
        if st.button("\U0001F4BE Agregar"):
            db.collection("vehiculos").document(pat).set({"Vehiculo": pat})
            st.rerun()
        v_list = obtener_vehiculos()
        st.dataframe(v_list, hide_index=True)
        el_v = st.selectbox("Borrar Equipo:", [""] + v_list["Vehiculo"].tolist())
        if st.button("Borrar"): db.collection("vehiculos").document(el_v).delete(); st.rerun()