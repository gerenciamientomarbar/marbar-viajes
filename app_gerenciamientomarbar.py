import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta, timezone
import json
import firebase_admin
from firebase_admin import credentials, firestore
import urllib.parse
import io
import os

# --- CONFIGURACIÓN DE ZONA HORARIA (ARGENTINA UTC-3) ---
TZ_AR = timezone(timedelta(hours=-3))

# --- CONFIGURACIÓN DE LA PÁGINA (Pestaña del navegador) ---
st.set_page_config(layout="wide", page_title="MARBAR - Gestión de Viajes", page_icon="🚛")

# --- DISEÑO DE MARCA (COLORES Y ESTILO) ---
primary_color = "#1E3A8A" 
text_color = "#1F2937"    

st.markdown(f"""
<style>
    .stApp {{ background-color: #F3F4F6; }}
    h1, h2, h3, .stSubheader, [data-testid="stHeader"] {{
        color: {primary_color} !important;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }}
    .stButton>button {{
        background-color: {primary_color};
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 20px;
        font-weight: bold;
        transition: all 0.3s ease;
    }}
    .stButton>button:hover {{
        background-color: #111827;
        color: white;
        transform: translateY(-2px);
    }}
    [data-testid="stSidebar"] {{
        background-color: white !important;
        border-right: 1px solid #E5E7EB;
    }}
    input:disabled {{
        background-color: #E5E7EB !important;
        color: {text_color} !important;
    }}
    .streamlit-expanderHeader {{
        background-color: white;
        border-radius: 8px;
        color: {primary_color} !important;
        font-weight: bold;
    }}
</style>
""", unsafe_allow_html=True)

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
    except: 
        return 1

def guardar_en_nube(datos_viaje):
    try:
        db.collection("viajes").document(str(datos_viaje["ID"])).set(datos_viaje)
        return True
    except: 
        return False

# --- LOGIN ---
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = None
if "paso_actual" not in st.session_state:
    st.session_state["paso_actual"] = "Menu"

if st.session_state["usuario_actual"] == None:
    col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
    with col_logo2:
        if os.path.exists("logo.png"):
            st.image("logo.png", use_column_width=True)
        else:
            st.warning("⚠️ Falta archivo logo.png en la carpeta.")
            
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
            else: 
                st.error("\u274C DNI no registrado.")
    st.stop()

# --- INTERFAZ PRINCIPAL ---
st.title("🚛 Gestión Operativa de Viajes")
st.markdown("---")

# --- NAVEGACIÓN POR SECCIONES (WORKFLOW) ---

# 1. MENÚ PRINCIPAL
if st.session_state["paso_actual"] == "Menu":
    st.subheader(f"Bienvenido, {st.session_state['nombre_empleado']}")
    
    # Mostrar viajes activos si es chofer
    if st.session_state["usuario_actual"] != "ADMIN":
        activos = [d.to_dict() for d in db.collection("viajes").where("Chofer", "==", st.session_state["nombre_empleado"]).where("Estado_Viaje", "==", "En viaje").stream()]
        if activos:
            st.info("\U0001F4CD Tienes viajes en curso. No olvides avisar al llegar.")
            for v in activos:
                col1, col2 = st.columns([3, 1])
                col1.write(f"**Viaje ID {v['ID']}** | Destino: {v['Destino']}")
                if col2.button(f"\U0001F3C1 Llegué a destino", key=f"menu_fin_{v['ID']}"):
                    db.collection("viajes").document(str(v['ID'])).update({
                        "Estado_Viaje": "Finalizado",
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
    st.info("Responde con sinceridad. Tu seguridad es la prioridad operativa.")
    
    t1 = st.radio("¿Se siente descansado y en condiciones físicas para conducir?", ["Sí", "No"], index=None)
    t2 = st.radio("¿Ha consumido medicamentos que causen somnolencia?", ["No", "Sí"], index=None)
    t3 = st.radio("¿Se encuentra bajo alguna situación de estrés o distracción?", ["No", "Sí"], index=None)

    col1, col2 = st.columns(2)
    if col1.button("⬅️ Volver al Menú"):
        st.session_state["paso_actual"] = "Menu"
        st.rerun()
    if col2.button("Siguiente Paso ➡️"):
        if t1 is None or t2 is None or t3 is None:
            st.error("⛔ Debes responder todas las preguntas antes de continuar.")
        elif t1 == "Sí" and t2 == "No" and t3 == "No":
            st.session_state["test_chofer"] = "Aprobado"
            st.session_state["paso_actual"] = "Inspeccion_Vehiculo"
            st.rerun()
        else:
            st.error("⚠️ Según tus respuestas, no estás apto para conducir hoy. Contacta a tu supervisor SSA.")

# 3. INSPECCIÓN DEL VEHÍCULO
elif st.session_state["paso_actual"] == "Inspeccion_Vehiculo":
    st.subheader("🚘 Paso 2: Inspección de Vehículo y Documentación")
    st.write("Verifique los siguientes puntos. Responda Sí, No o N/A según corresponda.")

    st.markdown("#### A. Progreso del checklist (Equipamiento)")
    eq_items = [
        "1. Cinturón De Seguridad", 
        "2. Torque En Pernos De Neumáticos", 
        "3. Triángulos Reflectivos x2",
        "4. Neumático De Auxilio, Cric y Llave", 
        "5. Extintor De Incendios", 
        "6. Alarma De Retroceso",
        "7. Botiquín", 
        "8. Neumáticos con cadenas o clavos", 
        "9. Pala, Kit De Supervivencia",
        "10. Verificación 360° del vehículo (ausencia de situaciones de riesgo)"
    ]
    respuestas_eq = {}
    for item in eq_items:
        respuestas_eq[item] = st.radio(item, ["Sí", "No", "N/A"], index=None, horizontal=True)

    st.markdown("---")
    st.markdown("#### B. Progreso de verificación (Documentación)")
    doc_items = [
        "1. Tarjeta De Propiedad (tarjeta verde)", 
        "2. Póliza De Seguro", 
        "3. Revisión Técnica",
        "4. Licencia De Conducir", 
        "5. Manejo Defensivo", 
        "6. Credencial Empresa",
        "7. Autorización De Ingreso A Yacimientos", 
        "8. Permisos Especiales", 
        "9. Curso 4x4"
    ]
    respuestas_doc = {}
    for item in doc_items:
        respuestas_doc[item] = st.radio(item, ["Sí", "No", "N/A"], index=None, horizontal=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    if col1.button("⬅️ Volver al Test"):
        st.session_state["paso_actual"] = "Test_Chofer"
        st.rerun()
    if col2.button("Iniciar Formulario 📝"):
        todas_eq = all(v is not None for v in respuestas_eq.values())
        todas_doc = all(v is not None for v in respuestas_doc.values())
        
        if not (todas_eq and todas_doc):
            st.error("⛔ ALTO: Debes responder todos los puntos de la inspección con Sí, No o N/A para continuar.")
        else:
            hay_negativas = any(v == "No" for v in respuestas_eq.values()) or any(v == "No" for v in respuestas_doc.values())
            if hay_negativas:
                st.error("⛔ Hay puntos críticos marcados con 'No'. El vehículo no está en condiciones de salir.")
            else:
                st.session_state["inspeccion_vehiculo"] = "Completada y Aprobada"
                st.session_state["resp_eq"] = respuestas_eq
                st.session_state["resp_doc"] = respuestas_doc
                st.session_state["paso_actual"] = "Formulario_Viaje"
                st.rerun()

# 4. FORMULARIO DE VIAJE
elif st.session_state["paso_actual"] == "Formulario_Viaje":
    st.subheader("🛡️ Paso 3: Formulario de Despacho Seguro")
    
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
    vehiculo = st.selectbox("Vehículo:", df_v["Vehiculo"].tolist() if not df_v.empty else ["⚠️ Cargar vehículos primero"])

    with st.expander("\U0001F5FA CONSULTAR MAPA DE YACIMIENTOS", expanded=True):
        components.iframe("https://www.google.com/maps/d/u/2/embed?mid=1BPDw99m6vQAC09Kdbw9Onaj5mu-blw4&ehbc=2E312F", height=480)

    col1, col2 = st.columns(2)
    with col1: 
        origen = st.text_input("Origen:")
    with col2: 
        destino_final = st.text_input("Destino:")
        
    duracion = st.text_input("Duración estimada (ej: 2 horas):")
    tipo_salida = st.radio("Salida:", ["Planificada", "Urgencia"], index=None)

    st.markdown("### 2. Evaluación de Riesgos")
    puntaje = 0
    
    dist = st.radio("Distancia:", ["< 50km", "< 100km", "< 200km", "> 200km"], index=None)
    if dist:
        puntaje += {"< 50km":1, "< 100km":2, "< 200km":5, "> 200km":7}.get(dist, 0)
    
    clima = st.selectbox("Clima:", ["Despejado", "Nublado", "Viento", "Lluvia", "Niebla", "Nieve"], index=None)
    if clima:
        puntaje += {"Despejado":0, "Nublado":1, "Viento":2, "Lluvia":4, "Niebla":8, "Nieve":9}.get(clima, 0)
    
    pasajeros = st.radio("Pasajeros:", ["Con pasajeros", "Solo conductor"], index=None)
    nombres_pasajeros = "N/A"
    if pasajeros == "Con pasajeros":
        nombres_pasajeros = st.text_input("👥 Ingrese Nombre y Apellido de los pasajeros:")
    if pasajeros:
        puntaje += 1 if pasajeros == "Con pasajeros" else 5
    
    camino = st.radio("Camino:", ["Pavimento", "Mixto", "Tierra"], index=None)
    if camino:
        puntaje += {"Pavimento":1, "Mixto":2, "Tierra":4}.get(camino, 0)
    
    dormio = st.radio("¿Durmió +8hs?", ["Sí", "No"], index=None)
    hs_tot = st.radio("Horas totales:", ["< 12hs", "< 14hs", "< 16hs"], index=None)
    if dormio and hs_tot:
        p_h = {"< 12hs": (1 if dormio=="Sí" else 2), "< 14hs": (3 if dormio=="Sí" else 5), "< 16hs": (6 if dormio=="Sí" else 8)}
        puntaje += p_h.get(hs_tot, 0)
        
    escolta = st.radio("¿Escolta?", ["No", "Sí"], index=None)
    if escolta:
        puntaje += 1 if escolta == "No" else 5
    
    horario = st.radio("Horario:", ["Diurno", "Nocturno"], index=None)
    if horario:
        puntaje += 5 if horario == "Nocturno" else 1
    
    com = st.radio("Comunicación:", ["Total", "Tramos sin señal", "Sin señal"], index=None)
    if com:
        puntaje += {"Total":1, "Tramos sin señal":3, "Sin señal":5}.get(com, 0)

    # --- CÁLCULO DE NIVEL Y APROBACIÓN ---
    nivel_v = 1 if puntaje <= 15 else (2 if puntaje <= 30 else 3)
    color = "green" if niv_aprob >= nivel_v else ("orange" if nivel_v < 3 else "red")
    estado_v = f"AUTORIZADO (Auto-Aprobado)" if color == "green" else f"PENDIENTE (Nivel {nivel_v})"

    st.markdown("---")
    st.subheader("📋 Resultado del Gerenciamiento")
    if color == "green":
        st.success(f"**{estado_v}** | Riesgo: Nivel {nivel_v} | Puntos: {puntaje}")
    elif color == "orange":
        st.warning(f"**{estado_v}** | Riesgo: Nivel {nivel_v} | Puntos: {puntaje}")
    else:
        st.error(f"**{estado_v}** | Riesgo: Nivel {nivel_v} | Puntos: {puntaje}")
    st.markdown("---")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("⬅️ Volver a Inspección"):
            st.session_state["paso_actual"] = "Inspeccion_Vehiculo"
            st.rerun()
    with col_btn2:
        if st.button("CONFIRMAR Y GUARDAR VIAJE"):
            
            # --- VALIDACIÓN EXTREMA ANTI-VACÍOS ---
            campos_llenos = all([
                origen.strip() != "",
                destino_final.strip() != "",
                duracion.strip() != "",
                vehiculo != "⚠️ Cargar vehículos primero",
                tipo_salida is not None,
                dist is not None,
                clima is not None,
                pasajeros is not None,
                camino is not None,
                dormio is not None,
                hs_tot is not None,
                escolta is not None,
                horario is not None,
                com is not None
            ])

            if not campos_llenos:
                st.error("⛔ ALTO: Faltan datos. Debes escribir Origen, Destino, Duración y responder TODAS las preguntas de opción múltiple antes de guardar.")
            elif pasajeros == "Con pasajeros" and nombres_pasajeros.strip() == "":
                st.error("⚠️ ALTO: Ingrese los nombres y apellidos de los pasajeros antes de continuar.")
            else:
                nid = obtener_siguiente_id()
                hora_actual = datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                
                datos = {
                    "ID": nid, 
                    "Fecha": hora_actual,
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
                    "Fecha_Aprobacion": hora_actual if color == "green" else "Pendiente",
                    "Estado_Viaje": "En viaje" if color == "green" else "En espera", 
                    "Fecha_Fin": "En curso",
                    "Test_Chofer": st.session_state.get("test_chofer", "No registrado"),
                    "Inspeccion_Vehiculo": st.session_state.get("inspeccion_vehiculo", "No registrado"),
                    "Checklist_Eq": st.session_state.get("resp_eq", {}),
                    "Checklist_Doc": st.session_state.get("resp_doc", {}),
                    "R_Distancia": dist, 
                    "R_Clima": clima, 
                    "R_Pasajeros": pasajeros, 
                    "Detalle_Pasajeros": nombres_pasajeros, 
                    "R_Camino": camino, 
                    "R_Sueno": dormio, 
                    "R_Horas": hs_tot, 
                    "R_Escolta": escolta, 
                    "R_Com": com
                }
                
                if guardar_en_nube(datos):
                    st.balloons()
                    
                    if color == "green":
                        cabecera_wa = f"\U0001F7E2 *AVISO DE VIAJE AUTO-APROBADO - ID {nid}* \U0001F7E2"
                        pie_wa = f"👉 *Viaje auto-aprobado por sistema. No requiere acción de aprobación.*"
                    else:
                        cabecera_wa = f"\U0001F534 *NUEVA SOLICITUD DE VIAJE - ID {nid}* \U0001F534"
                        pie_wa = f"👉 *Por favor, ingrese al sistema MARBAR para APROBAR este viaje.*"

                    tkt = (
                        f"{cabecera_wa}\n\n"
                        f"👤 *Chofer:* {chofer}\n"
                        f"🚚 *Vehículo:* {vehiculo}\n"
                        f"📍 *Origen:* {origen}\n"
                        f"🏁 *Destino:* {destino_final}\n"
                        f"⏱️ *Duración:* {duracion}\n"
                        f"⚠️ *Riesgo:* Nivel {nivel_v} ({puntaje} pts)\n"
                        f"📋 *Estado:* {estado_v}\n\n"
                        f"{pie_wa}"
                    )
                    st.markdown(f"### [\U0001F4F2 ENVIAR TICKET A WHATSAPP](https://wa.me/?text={urllib.parse.quote(tkt)})")
                    st.success("Viaje guardado correctamente.")
                    st.session_state["paso_actual"] = "Menu"

# 5. PANTALLA PRINCIPAL DE HISTORIAL
elif st.session_state["paso_actual"] == "Historial":
    st.subheader("📜 Tu Historial Detallado")
    v_ref = db.collection("viajes").stream()
    df_n = pd.DataFrame([doc.to_dict() for doc in v_ref])
    
    if not df_n.empty:
        if st.session_state["usuario_actual"] != "ADMIN":
            df_n = df_n[df_n["Chofer"] == st.session_state["nombre_empleado"]]
            
        if not df_n.empty:
            df_n = df_n.sort_values(by="ID", ascending=False)
            st.dataframe(df_n[['ID', 'Fecha', 'Origen', 'Destino', 'Estado_Viaje']], hide_index=True)
            
            st.markdown("---")
            st.write("#### Descargar Reporte Completo")
            opciones_historial = [""]
            for _, r in df_n.iterrows():
                opciones_historial.append(f"{r['ID']} - {r.get('Chofer','')} - {r.get('Fecha','')[:10]}")
                
            viaje_sel_texto = st.selectbox("Seleccionar viaje:", opciones_historial)
            
            if viaje_sel_texto != "":
                id_sel = viaje_sel_texto.split(" - ")[0]
                v_data = df_n[df_n["ID"].astype(str) == id_sel].iloc[0]
                
                # Desglose de Diccionarios de Inspección
                chk_eq = v_data.get('Checklist_Eq', {})
                chk_doc = v_data.get('Checklist_Doc', {})
                str_eq = "\n".join([f"  - {k}: {v}" for k, v in chk_eq.items()]) if chk_eq else "  (No hay datos de equipamiento)"
                str_doc = "\n".join([f"  - {k}: {v}" for k, v in chk_doc.items()]) if chk_doc else "  (No hay datos de documentación)"

                reporte = f"""
=========================================
      REPORTE INTEGRAL - MARBAR
=========================================
ID VIAJE       : {v_data.get('ID')}
FECHA          : {v_data.get('Fecha')}
CHOFER         : {v_data.get('Chofer')}
SECTOR         : {v_data.get('Sector')}
CARGO          : {v_data.get('Cargo')}
VEHÍCULO       : {v_data.get('Vehiculo')}
-----------------------------------------
1. RUTA Y TIEMPOS
ORIGEN         : {v_data.get('Origen')}
DESTINO        : {v_data.get('Destino')}
DURACIÓN EST.  : {v_data.get('Duracion')}
TIPO SALIDA    : {v_data.get('Salida')}
FECHA CIERRE   : {v_data.get('Fecha_Fin')}
-----------------------------------------
2. PREVENCIÓN PREVIA Y CHECKLIST
TEST FATIGA    : {v_data.get('Test_Chofer', 'N/A')}
INSPECCIÓN V.  : {v_data.get('Inspeccion_Vehiculo', 'N/A')}

>> DETALLE EQUIPAMIENTO:
{str_eq}

>> DETALLE DOCUMENTACIÓN:
{str_doc}
-----------------------------------------
3. EVALUACIÓN DE RIESGOS 
DISTANCIA      : {v_data.get('R_Distancia', 'N/A')}
CLIMA          : {v_data.get('R_Clima', 'N/A')}
PASAJEROS      : {v_data.get('R_Pasajeros', 'N/A')} ({v_data.get('Detalle_Pasajeros', 'N/A')})
CAMINO         : {v_data.get('R_Camino', 'N/A')}
SUEÑO +8HS     : {v_data.get('R_Sueno', 'N/A')}
HS TOTALES     : {v_data.get('R_Horas', 'N/A')}
ESCOLTA        : {v_data.get('R_Escolta', 'N/A')}
COMUNICACIÓN   : {v_data.get('R_Com', 'N/A')}
-----------------------------------------
4. RESULTADO Y APROBACIÓN
PUNTAJE TOTAL  : {v_data.get('Puntaje')}
NIVEL RIESGO   : Nivel {v_data.get('Nivel')}
APROBADO POR   : {v_data.get('Aprobador')}
HORA APROB.    : {v_data.get('Fecha_Aprobacion', 'N/A')}
ESTADO FINAL   : {v_data.get('Estado_Viaje')}
=========================================
                """
                st.download_button("📥 Descargar Ticket Completo (.txt)", reporte, f"Reporte_Viaje_{id_sel}.txt")
        else:
            st.info("No tienes viajes registrados aún.")
    
    if st.button("⬅️ Volver al Menú"):
        st.session_state["paso_actual"] = "Menu"
        st.rerun()

# --- 6. PANEL LATERAL CON LOGO Y AUDITORÍA ---
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_column_width=True)
    else:
        st.write("🚛 **MARBAR**")
    st.markdown("---")
    st.header("\U0001F4CA Gestión SSA")

try:
    v_ref = db.collection("viajes").stream()
    df_n = pd.DataFrame([doc.to_dict() for doc in v_ref])
    
    if not df_n.empty:
        hoy = datetime.now(TZ_AR).strftime("%d/%m/%Y")
        v_hoy = df_n[df_n['Fecha'].str.contains(hoy, na=False)]
        
        st.sidebar.markdown("---")
        st.sidebar.write("\U0001F534 **Pendientes de Aprobación:**")
        pend = v_hoy[v_hoy['Aprobacion'].str.contains("Pendiente", na=False)]
        if not pend.empty: 
            st.sidebar.dataframe(pend[['Chofer','Destino']], hide_index=True)
        else: 
            st.sidebar.write("\u2705 Todo al día.")

        st.sidebar.markdown("---")
        st.sidebar.write("\U0001F699 **En ruta ahora:**")
        ruta = v_hoy[v_hoy['Estado_Viaje'] == "En viaje"]
        if not ruta.empty: 
            st.sidebar.dataframe(ruta[['Chofer','Destino']], hide_index=True)
        else: 
            st.sidebar.write("\u2705 No hay vehículos en ruta.")

        # HISTORIAL DETALLADO (TXT) EN BARRA LATERAL
        st.sidebar.markdown("---")
        st.sidebar.subheader("📜 Descargar Ticket Individual")
        
        opciones_lat = [""]
        df_ord = df_n.sort_values(by="ID", ascending=False)
        for _, r in df_ord.iterrows():
            opciones_lat.append(f"{r['ID']} - {r.get('Chofer','')} - {r.get('Fecha','')[:10]}")
            
        viaje_sel_lat = st.sidebar.selectbox("Seleccionar viaje:", opciones_lat, key="sb_historial")
        
        if viaje_sel_lat != "":
            id_sel_lat = viaje_sel_lat.split(" - ")[0]
            v_data = df_n[df_n["ID"].astype(str) == id_sel_lat].iloc[0]
            
            # Desglose de Diccionarios de Inspección
            chk_eq = v_data.get('Checklist_Eq', {})
            chk_doc = v_data.get('Checklist_Doc', {})
            str_eq = "\n".join([f"  - {k}: {v}" for k, v in chk_eq.items()]) if chk_eq else "  (No hay datos de equipamiento)"
            str_doc = "\n".join([f"  - {k}: {v}" for k, v in chk_doc.items()]) if chk_doc else "  (No hay datos de documentación)"

            reporte = f"""
=========================================
      REPORTE INTEGRAL - MARBAR
=========================================
ID VIAJE       : {v_data.get('ID')}
FECHA          : {v_data.get('Fecha')}
CHOFER         : {v_data.get('Chofer')}
SECTOR         : {v_data.get('Sector')}
CARGO          : {v_data.get('Cargo')}
VEHÍCULO       : {v_data.get('Vehiculo')}
-----------------------------------------
1. RUTA Y TIEMPOS
ORIGEN         : {v_data.get('Origen')}
DESTINO        : {v_data.get('Destino')}
DURACIÓN EST.  : {v_data.get('Duracion')}
TIPO SALIDA    : {v_data.get('Salida')}
FECHA CIERRE   : {v_data.get('Fecha_Fin')}
-----------------------------------------
2. PREVENCIÓN PREVIA Y CHECKLIST
TEST FATIGA    : {v_data.get('Test_Chofer', 'N/A')}
INSPECCIÓN V.  : {v_data.get('Inspeccion_Vehiculo', 'N/A')}

>> DETALLE EQUIPAMIENTO:
{str_eq}

>> DETALLE DOCUMENTACIÓN:
{str_doc}
-----------------------------------------
3. EVALUACIÓN DE RIESGOS 
DISTANCIA      : {v_data.get('R_Distancia', 'N/A')}
CLIMA          : {v_data.get('R_Clima', 'N/A')}
PASAJEROS      : {v_data.get('R_Pasajeros', 'N/A')} ({v_data.get('Detalle_Pasajeros', 'N/A')})
CAMINO         : {v_data.get('R_Camino', 'N/A')}
SUEÑO +8HS     : {v_data.get('R_Sueno', 'N/A')}
HS TOTALES     : {v_data.get('R_Horas', 'N/A')}
ESCOLTA        : {v_data.get('R_Escolta', 'N/A')}
COMUNICACIÓN   : {v_data.get('R_Com', 'N/A')}
-----------------------------------------
4. RESULTADO Y APROBACIÓN
PUNTAJE TOTAL  : {v_data.get('Puntaje')}
NIVEL RIESGO   : Nivel {v_data.get('Nivel')}
APROBADO POR   : {v_data.get('Aprobador')}
HORA APROB.    : {v_data.get('Fecha_Aprobacion', 'N/A')}
ESTADO FINAL   : {v_data.get('Estado_Viaje')}
=========================================
            """
            st.sidebar.download_button("📥 Descargar Ticket Completo (.txt)", reporte, f"Reporte_Viaje_{id_sel_lat}.txt", key="btn_txt_sb")

        if st.session_state["usuario_actual"] == "ADMIN":
            st.sidebar.markdown("---")
            st.sidebar.subheader("📥 Excel de Auditoría")
            orden = [
                'ID', 'Fecha', 'Chofer', 'Sector', 'Cargo', 'Vehiculo', 'Duracion', 
                'Salida', 'Alarma Nocturna', 'Origen', 'Destino', 'Estado', 'Puntaje', 
                'Nivel', 'Aprobacion', 'Aprobador', 'Fecha_Aprobacion', 'Estado_Viaje', 'Fecha_Fin'
            ]
            for c in orden: 
                if c not in df_n.columns: 
                    df_n[c] = "N/A"
                    
            # ORDENAMIENTO DE ID MAYOR A MENOR PARA EL EXCEL
            df_export = df_n[orden].sort_values(by="ID", ascending=False)
            
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as wr: 
                df_export.to_excel(wr, index=False)
                
            st.sidebar.download_button("Descargar Auditoría Maestra", buf.getvalue(), f"Auditoria_Marbar_{hoy.replace('/','-')}.xlsx")

except Exception as e:
    pass

# --- 7. BANDEJA DE APROBACIONES ---
if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia"]:
    st.markdown("---")
    st.title("\U0001F4E5 Bandeja de Aprobaciones")
    try:
        v_ref = db.collection("viajes").where("Aprobacion", "==", "\U0001F534 Pendiente").stream()
        hay_pendientes = False
        
        for doc in v_ref:
            v = doc.to_dict()
            hay_pendientes = True
            with st.expander(f"\U0001F6A8 ID: {v['ID']} | {v['Chofer']}"):
                st.write(f"**Ruta:** {v['Origen']} -> {v['Destino']}")
                if st.button(f"\u2705 Aprobar {v['ID']}", key=f"ap_{v['ID']}"):
                    db.collection("viajes").document(str(v['ID'])).update({
                        "Aprobacion": "\U0001F7E2 Aprobado", 
                        "Aprobador": st.session_state["nombre_empleado"], 
                        "Fecha_Aprobacion": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S"), 
                        "Estado_Viaje": "En viaje"
                    })
                    st.rerun()
                    
        if not hay_pendientes:
            st.info("\u2705 No tienes pendientes de tu sector.")
            
    except Exception as e: 
        pass

# --- 8. ADMINISTRACIÓN ---
if st.session_state["usuario_actual"] == "ADMIN":
    st.markdown("---")
    st.title("\U0001F6E0 Base de Datos")
    t1, t2 = st.tabs(["👥 Usuarios", "🚘 Flota"])
    
    with t1:
        d = st.text_input("DNI:", key="a_d")
        n = st.text_input("Nombre:", key="a_n")
        s = st.selectbox("Sector:", ["Higiene y Seguridad", "Logistica", "Fluidos", "Control de solidos", "Mantenimiento", "Gerencia"], key="a_s")
        r = st.selectbox("Rol:", ["Chofer", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia", "ADMIN"], key="a_r")
        
        if st.button("💾 Guardar Usuario", key="btn_guardar_u"):
            if d.strip() and n.strip(): 
                db.collection("usuarios").document(d).set({"DNI_Usuario":d,"Nombre":n,"Rol":r,"Sector":s})
                st.success("Usuario Guardado")
                st.rerun()
            else:
                st.error("⚠️ Ingrese DNI y Nombre")
                
        st.dataframe(obtener_usuarios(), hide_index=True)
        
        u_list = obtener_usuarios()
        elim = st.selectbox("Borrar Usuario:", [""] + u_list["DNI_Usuario"].tolist(), key="del_u")
        if st.button("Eliminar Usuario", key="btn_elim_u"):
            if elim.strip():
                db.collection("usuarios").document(elim).delete()
                st.rerun()
                
    with t2:
        p = st.text_input("Equipo:", key="a_p")
        if st.button("💾 Agregar Equipo", key="btn_guardar_v"):
            if p.strip(): 
                db.collection("vehiculos").document(p).set({"Vehiculo": p})
                st.success("Vehículo Guardado")
                st.rerun()
            else:
                st.error("⚠️ Ingrese una patente")
                
        v_list = obtener_vehiculos()
        st.dataframe(v_list, hide_index=True)
        
        el_v = st.selectbox("Borrar Vehículo:", [""] + v_list["Vehiculo"].tolist(), key="del_v")
        if st.button("Eliminar Vehículo", key="btn_elim_v"):
            if el_v.strip():
                db.collection("vehiculos").document(el_v).delete()
                st.rerun()