import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta, timezone
import json
import firebase_admin
from firebase_admin import credentials, firestore
import urllib.parse
import io

# --- CONFIGURACIÓN DE ZONA HORARIA (ARGENTINA UTC-3) ---
TZ_AR = timezone(timedelta(hours=-3))

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
if "paso_actual" not in st.session_state:
    st.session_state["paso_actual"] = "Menu"

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

# --- NAVEGACIÓN POR SECCIONES ---

# 1. MENÚ PRINCIPAL
if st.session_state["paso_actual"] == "Menu":
    st.subheader(f"Bienvenido, {st.session_state['nombre_empleado']}")
    
    # Mostrar viajes activos si es chofer
    if st.session_state["usuario_actual"] != "ADMIN":
        activos = [d.to_dict() for d in db.collection("viajes").where("Chofer", "==", st.session_state["nombre_empleado"]).where("Estado_Viaje", "==", "En viaje").stream()]
        if activos:
            st.info("\U0001F4CD Tienes viajes en curso.")
            for v in activos:
                col1, col2 = st.columns([3, 1])
                col1.write(f"**Viaje ID {v['ID']}** | Destino: {v['Destino']}")
                if col2.button(f"\U0001F3C1 Finalizar", key=f"menu_fin_{v['ID']}"):
                    db.collection("viajes").document(str(v['ID'])).update({
                        "Aprobacion": "\U0001F3C1 Finalizado", "Estado_Viaje": "Finalizado",
                        "Fecha_Fin": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                    })
                    st.success("Viaje finalizado.")
                    st.rerun()

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🚀 NUEVO GERENCIAMIENTO", use_container_width=True):
            st.session_state["paso_actual"] = "Test_Chofer"
            st.rerun()
    with col_b:
        if st.button("📜 VER MI HISTORIAL", use_container_width=True):
            st.session_state["paso_actual"] = "Historial"
            st.rerun()

# 2. TEST DE CONDICIÓN DEL CHOFER
elif st.session_state["paso_actual"] == "Test_Chofer":
    st.subheader("🛡️ Paso 1: Test de Aptitud del Conductor")
    st.info("Responde con sinceridad. Tu seguridad es la prioridad de MARBAR.")
    
    t1 = st.radio("¿Se siente descansado y en condiciones físicas para conducir?", ["Sí", "No"], index=None)
    t2 = st.radio("¿Ha consumido medicamentos que causen somnolencia?", ["No", "Sí"], index=None)
    t3 = st.radio("¿Se encuentra bajo alguna situación de estrés o distracción?", ["No", "Sí"], index=None)

    col1, col2 = st.columns(2)
    if col1.button("⬅️ Volver al Menú"):
        st.session_state["paso_actual"] = "Menu"
        st.rerun()
    if col2.button("Siguiente Paso ➡️"):
        if t1 == "Sí" and t2 == "No" and t3 == "No":
            st.session_state["test_chofer"] = "Aprobado"
            st.session_state["paso_actual"] = "Inspeccion_Vehiculo"
            st.rerun()
        else:
            st.error("⚠️ Según tus respuestas, no estás apto para conducir hoy. Contacta a tu supervisor SSA.")

# 3. INSPECCIÓN DEL VEHÍCULO
elif st.session_state["paso_actual"] == "Inspeccion_Vehiculo":
    st.subheader("🚘 Paso 2: Check-list Rápido del Vehículo")
    
    c1 = st.checkbox("Niveles de fluidos (Aceite, refrigerante, frenos) OK")
    c2 = st.checkbox("Neumáticos (Presión y dibujo visible) OK")
    c3 = st.checkbox("Luces, frenos y cinturones de seguridad OK")
    c4 = st.checkbox("Documentación y Kit de Emergencia completo OK")

    col1, col2 = st.columns(2)
    if col1.button("⬅️ Volver al Test"):
        st.session_state["paso_actual"] = "Test_Chofer"
        st.rerun()
    if col2.button("Iniciar Formulario 📝"):
        if c1 and c2 and c3 and c4:
            st.session_state["inspeccion_vehiculo"] = "Aprobada"
            st.session_state["paso_actual"] = "Formulario_Viaje"
            st.rerun()
        else:
            st.warning("⚠️ Debes verificar todos los puntos del vehículo.")

# 4. FORMULARIO DE VIAJE (RIESGOS)
elif st.session_state["paso_actual"] == "Formulario_Viaje":
    st.subheader("Formulario de Despacho Seguro (Evaluación de Riesgos)")
    
    AUTORIDADES = {
        "Higiene y Seguridad": {"Coordinador SSA": 1, "Jefe SSA": 2},
        "Logistica": {"Chofer": 0, "Coordinador de Logistica": 1, "Jefe de Logistica": 2},
        "Fluidos": {"Supervisor de SFP": 1, "Jefe de SFP": 2},
        "Control de solidos": {"Supervisor de CDS": 1, "Jefe de CDS": 2},
        "Mantenimiento": {"Mecanico / Electrico": 1, "Jefe de Mantenimiento": 2},
        "Gerencia": {"Gerente General": 3}
    }

    st.markdown("### 1. Datos Generales")
    sec_elegido = st.selectbox("Sector:", list(AUTORIDADES.keys()))
    car_elegido = st.selectbox("Cargo:", list(AUTORIDADES[sec_elegido].keys()))
    niv_aprob = AUTORIDADES[sec_elegido][car_elegido]
    
    chofer = st.text_input("Chofer:", value=st.session_state["nombre_empleado"], disabled=(st.session_state["usuario_actual"] != "ADMIN"))
    df_v = obtener_vehiculos()
    vehiculo = st.selectbox("Vehículo:", df_v["Vehiculo"].tolist() if not df_v.empty else ["⚠️ Cargar"])

    with st.expander("\U0001F5FA CONSULTAR MAPA", expanded=True):
        components.iframe("https://www.google.com/maps/d/u/2/embed?mid=1BPDw99m6vQAC09Kdbw9Onaj5mu-blw4&ehbc=2E312F", height=480)

    col1, col2 = st.columns(2)
    with col1: origen = st.text_input("Origen:")
    with col2: destino_final = st.text_input("Destino:")
    duracion = st.text_input("Duración estimada:")
    tipo_salida = st.radio("Salida:", ["Planificada", "Urgencia"], index=None)

    st.markdown("### 2. Evaluación de Riesgos")
    puntaje = 0
    dist = st.radio("Distancia:", ["< 50km", "< 100km", "< 200km", "> 200km"], index=None)
    puntaje += {"< 50km":1, "< 100km":2, "< 200km":5, "> 200km":7}.get(dist, 0)
    clima = st.selectbox("Clima:", ["Despejado", "Viento", "Lluvia", "Niebla", "Nieve"], index=None)
    puntaje += {"Despejado":0, "Viento":2, "Lluvia":4, "Niebla":8, "Nieve":9}.get(clima, 0)
    pasajeros = st.radio("Pasajeros:", ["Con pasajeros", "Solo conductor"], index=None)
    puntaje += 1 if pasajeros == "Con pasajeros" else 5
    camino = st.radio("Camino:", ["Pavimento", "Mixto", "Tierra"], index=None)
    puntaje += {"Pavimento":1, "Mixto":2, "Tierra":4}.get(camino, 0)
    dormio = st.radio("¿Durmió +8hs?", ["Sí", "No"], index=None)
    hs_tot = st.radio("Horas totales:", ["< 12hs", "< 14hs", "< 16hs"], index=None)
    p_h = {"< 12hs": (1 if dormio=="Sí" else 2), "< 14hs": (3 if dormio=="Sí" else 5), "< 16hs": (6 if dormio=="Sí" else 8)}
    puntaje += p_h.get(hs_tot, 0)
    escolta = st.radio("¿Escolta?", ["No", "Sí"], index=None)
    puntaje += 1 if escolta == "No" else 5
    horario = st.radio("Horario:", ["Diurno", "Nocturno"], index=None)
    puntaje += 5 if horario == "Nocturno" else 1
    com = st.radio("Comunicación:", ["Total", "Tramos sin señal", "Sin señal"], index=None)
    puntaje += {"Total":1, "Tramos sin señal":3, "Sin señal":5}.get(com, 0)

    nivel_v = 1 if puntaje <= 15 else (2 if puntaje <= 30 else 3)
    color = "green" if niv_aprob >= nivel_v else ("orange" if nivel_v < 3 else "red")
    estado_v = f"AUTORIZADO" if color == "green" else f"PENDIENTE"

    if st.button("CONFIRMAR Y GUARDAR VIAJE"):
        if not (origen and destino_final and tipo_salida and dist):
            st.error("\u26D4 Completa los datos.")
        else:
            nid = obtener_siguiente_id()
            # SE GUARDA EL VIAJE CON HORA ARGENTINA
            datos = {
                "ID": nid, "Fecha": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S"),
                "Chofer": chofer, "Sector": sec_elegido, "Cargo": car_elegido, "Vehiculo": vehiculo,
                "Duracion": duracion, "Salida": tipo_salida, "Alarma Nocturna": "encendida" if horario == "Nocturno" else "apagada",
                "Origen": origen, "Destino": destino_final, "Estado": estado_v, "Puntaje": puntaje, "Nivel": nivel_v, 
                "Aprobacion": "\U0001F7E2 Aprobado" if color == "green" else "\U0001F534 Pendiente",
                "Aprobador": st.session_state["nombre_empleado"] if color == "green" else "Pendiente",
                "Estado_Viaje": "En viaje" if color == "green" else "En espera", "Fecha_Fin": "En curso",
                "Test_Chofer": st.session_state.get("test_chofer"),
                "Inspeccion_Vehiculo": st.session_state.get("inspeccion_vehiculo")
            }
            if guardar_en_nube(datos):
                st.balloons()
                tkt = (f"\U0001F534 *NUEVA SOLICITUD ID {nid}* \U0001F534\n\nChofer: {chofer}\nVehículo: {vehiculo}\nRuta: {origen} -> {destino_final}\n\nFavor revisar sistema MARBAR.")
                st.markdown(f"### [\U0001F4F2 ENVIAR TICKET](https://wa.me/?text={urllib.parse.quote(tkt)})")
                st.session_state["paso_actual"] = "Menu"

# 5. SECCIÓN DE HISTORIAL
elif st.session_state["paso_actual"] == "Historial":
    st.subheader("📜 Historial Detallado de Viajes")
    v_ref = db.collection("viajes").stream()
    df_n = pd.DataFrame([doc.to_dict() for doc in v_ref])
    
    if not df_n.empty:
        lista_ids = df_n["ID"].astype(str).tolist()
        viaje_sel = st.selectbox("Seleccionar viaje por ID:", [""] + sorted(lista_ids, key=int, reverse=True))
        if viaje_sel:
            v = df_n[df_n["ID"].astype(str) == viaje_sel].iloc[0]
            st.info(f"**Chofer:** {v.get('Chofer')} | **Estado:** {v.get('Estado_Viaje')}")
            rep = f"VIAJE ID {viaje_sel}\nFecha: {v.get('Fecha')}\nChofer: {v.get('Chofer')}\nVehiculo: {v.get('Vehiculo')}\nRuta: {v.get('Origen')} -> {v.get('Destino')}\nTest Chofer: {v.get('Test_Chofer')}\nInspeccion: {v.get('Inspeccion_Vehiculo')}\nAprobador: {v.get('Aprobador')}\nFin: {v.get('Fecha_Fin')}"
            st.download_button("📥 Descargar Ticket", rep, f"Viaje_{viaje_sel}.txt")
    
    if st.button("⬅️ Volver al Menú"):
        st.session_state["paso_actual"] = "Menu"
        st.rerun()

# --- PANEL LATERAL (AUDITORÍA Y ADMIN) ---
st.sidebar.header("\U0001F4CA Gestión SSA")
if st.session_state["usuario_actual"] == "ADMIN":
    # Descarga Excel 18 columnas
    v_ref = db.collection("viajes").stream()
    df_n = pd.DataFrame([doc.to_dict() for doc in v_ref])
    if not df_n.empty:
        orden = ['ID', 'Fecha', 'Chofer', 'Sector', 'Cargo', 'Vehiculo', 'Duracion', 'Salida', 'Alarma Nocturna', 'Origen', 'Destino', 'Estado', 'Puntaje', 'Nivel', 'Aprobacion', 'Aprobador', 'Estado_Viaje', 'Fecha_Fin']
        for c in orden: 
            if c not in df_n.columns: df_n[c] = "N/A"
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as wr: df_n[orden].to_excel(wr, index=False)
        st.sidebar.download_button("📥 Excel Auditoría", buf.getvalue(), f"Audit_Marbar_{datetime.now(TZ_AR).strftime('%d-%m')}.xlsx")

# --- BANDEJA DE APROBACIONES ---
if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia"]:
    st.markdown("---")
    st.title("\U0001F4E5 Bandeja de Aprobaciones")
    try:
        v_ref = db.collection("viajes").where("Aprobacion", "==", "\U0001F534 Pendiente").stream()
        for doc in v_ref:
            viaje = doc.to_dict()
            with st.expander(f"\U0001F6A8 ID: {viaje['ID']} | {viaje['Chofer']}"):
                st.write(f"Ruta: {viaje['Origen']} -> {viaje['Destino']}")
                if st.button(f"\u2705 Aprobar {viaje['ID']}", key=f"ap_{viaje['ID']}"):
                    db.collection("viajes").document(str(viaje['ID'])).update({
                        "Aprobacion": "\U0001F7E2 Aprobado", "Aprobador": st.session_state["nombre_empleado"], "Estado_Viaje": "En viaje"
                    })
                    st.rerun()
    except: pass

# --- ADMINISTRACIÓN ---
if st.session_state["usuario_actual"] == "ADMIN":
    st.markdown("---")
    st.title("\U0001F6E0 Configuración")
    t1, t2 = st.tabs(["👥 Usuarios", "🚘 Flota"])
    with t1:
        d = st.text_input("DNI:"); n = st.text_input("Nombre:")
        s = st.selectbox("Sector:", ["Higiene y Seguridad", "Logistica", "Fluidos", "Control de solidos", "Mantenimiento", "Gerencia"])
        r = st.selectbox("Rol:", ["Chofer", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia", "ADMIN"])
        if st.button("\U0001F4BE Guardar Usuario"):
            db.collection("usuarios").document(d).set({"DNI_Usuario":d,"Nombre":n,"Rol":r,"Sector":s})
            st.rerun()
        u_list = obtener_usuarios()
        st.dataframe(u_list, hide_index=True)
    with t2:
        pat = st.text_input("Equipo:")
        if st.button("\U0001F4BE Agregar"):
            db.collection("vehiculos").document(pat).set({"Vehiculo": pat})
            st.rerun()
        st.dataframe(obtener_vehiculos(), hide_index=True)