import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta, timezone
import json
import firebase_admin
from firebase_admin import credentials, firestore, auth
import urllib.parse
import io
import os
import requests

# --- CONFIGURACIÓN DE SEGURIDAD DEL IDP ---
# Coloca aquí la Clave de API web que obtendrás al registrar la app web en Firebase
API_KEY_FIREBASE = "AIzaSyAHE35ma-FT5xy1uvacwX2g_CtLbmyCWrs" 

# --- CONFIGURACIÓN DE ZONA HORARIA (ARGENTINA UTC-3) ---
TZ_AR = timezone(timedelta(hours=-3))

# --- CONFIGURACIÓN DE LA PÁGINA (Pestaña del navegador) ---
st.set_page_config(
    layout="wide", 
    page_title="MARBAR - Gestión de Viajes", 
    page_icon="🚛"
)

# --- DISEÑO DE MARCA (COLORES Y ESTILO CORPORATIVO CSS) ---
primary_color = "#1E3A8A" 
text_color = "#1F2937"    

st.markdown(f"""
<style>
    /* Fondo general de la plataforma */
    .stApp {{ 
        background-color: #F3F4F6; 
    }}
    
    /* Estilo de Títulos y Subtítulos principales */
    h1, h2, h3, .stSubheader, [data-testid="stHeader"] {{
        color: {primary_color} !important;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }}
    
    /* Estilo de los Botones del Sistema */
    .stButton>button {{
        background-color: {primary_color};
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 20px;
        font-weight: bold;
        transition: all 0.3s ease;
    }}
    
    /* Efecto al pasar el mouse por encima del botón */
    .stButton>button:hover {{
        background-color: #111827;
        color: white;
        transform: translateY(-2px);
    }}
    
    /* Panel Lateral (Sidebar) */
    [data-testid="stSidebar"] {{
        background-color: white !important;
        border-right: 1px solid #E5E7EB;
    }}
    
    /* Estilo para los campos deshabilitados */
    input:disabled {{
        background-color: #E5E7EB !important;
        color: {text_color} !important;
    }}
    
    /* Estilo para los encabezados de los Expanders */
    .streamlit-expanderHeader {{
        background-color: white;
        border-radius: 8px;
        color: {primary_color} !important;
        font-weight: bold;
    }}
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN A LA NUBE (FIREBASE) ---
if not firebase_admin._apps:
    try:
        llave_secreta = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(llave_secreta)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Error crítico al conectar con la llave secreta de Firebase: {e}")

db = firestore.client()

# --- FUNCIONES DE COMUNICACIÓN CON EL IDP Y BASE DE DATOS ---

def login_usuario(email, password):
    """Autentica las credenciales de correo contra el servidor seguro de Firebase Auth"""
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY_FIREBASE}"
    payload = {
        "email": email, 
        "password": password, 
        "returnSecureToken": True
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def obtener_usuarios():
    """Recupera la lista completa de perfiles registrados en Firestore"""
    usuarios_ref = db.collection("usuarios").stream()
    lista_usuarios = []
    for doc in usuarios_ref:
        lista_usuarios.append(doc.to_dict())
    return pd.DataFrame(lista_usuarios)

def obtener_vehiculos():
    """Recupera la flota activa de vehículos"""
    vehiculos_ref = db.collection("vehiculos").stream()
    lista_vehiculos = []
    for doc in vehiculos_ref:
        lista_vehiculos.append(doc.to_dict())
    if lista_vehiculos:
        return pd.DataFrame(lista_vehiculos)
    else:
        return pd.DataFrame(columns=["Vehiculo"])

def obtener_siguiente_id():
    """Calcula el consecutivo numérico exacto para el ID de viaje"""
    try:
        viajes_ref = db.collection("viajes").order_by("ID", direction=firestore.Query.DESCENDING).limit(1).get()
        if viajes_ref:
            ultimo_id = viajes_ref[0].to_dict().get("ID", 0)
            return ultimo_id + 1
        else:
            return 1
    except Exception: 
        return 1

def guardar_en_nube(datos_viaje):
    """Inserta el documento completo del viaje en Cloud Firestore"""
    try:
        db.collection("viajes").document(str(datos_viaje["ID"])).set(datos_viaje)
        return True
    except Exception: 
        return False

# --- GESTOR DE SESIÓN OPERATIVA ---
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = None
if "paso_actual" not in st.session_state:
    st.session_state["paso_actual"] = "Menu"

# --- PANTALLA DE ACCESO CONTROLADO (LOGIN) ---
if st.session_state["usuario_actual"] is None:
    col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
    with col_logo2:
        if os.path.exists("logo.png"): 
            st.image("logo.png", use_column_width=True)
        else: 
            st.warning("⚠️ El archivo 'logo.png' no se encuentra en el repositorio de GitHub.")
            
    st.title("🔒 Acceso Seguro - Sistema MARBAR")
    st.info("Por favor, ingrese utilizando su correo electrónico asignado y contraseña.")
    
    e_ing = st.text_input("Correo Electrónico (Gmail, Hotmail, Yahoo, Corporativo):")
    c_ing = st.text_input("Contraseña:", type="password")
    
    if st.button("Iniciar Sesión"):
        if e_ing == "admin@marbar.com" and c_ing == "Marbar2026":
            st.session_state.update({
                "usuario_actual": "ADMIN", 
                "nombre_empleado": "Administrador", 
                "sector_empleado": "Gerencia", 
                "email_empleado": e_ing
            })
            st.rerun()
        else:
            login_data = login_usuario(e_ing, c_ing)
            if login_data:
                usuarios_ref = db.collection("usuarios").where("Email", "==", e_ing).limit(1).get()
                if usuarios_ref:
                    perfil = usuarios_ref[0].to_dict()
                    st.session_state.update({
                        "usuario_actual": perfil["Rol"], 
                        "nombre_empleado": perfil["Nombre"], 
                        "sector_empleado": perfil["Sector"],
                        "email_empleado": e_ing
                    })
                    st.rerun()
                else:
                    st.error("❌ El correo está autenticado pero no posee un perfil en la base de datos de MARBAR. Contacte al Administrador.")
            else:
                st.error("❌ Credenciales incorrectas. Verifique el correo o la contraseña.")
    st.stop()

# --- CONTROL DEL WORKFLOW DE VIAJES ---

# 1. PANTALLA: MENÚ PRINCIPAL
if st.session_state["paso_actual"] == "Menu":
    st.subheader(f"Panel Operativo - Bienvenido, {st.session_state['nombre_empleado']}")
    
    # Monitoreo de viajes en curso del chofer logueado
    if st.session_state["usuario_actual"] != "ADMIN":
        viajes_activos = db.collection("viajes").where("Chofer", "==", st.session_state["nombre_empleado"]).where("Estado_Viaje", "==", "En viaje").stream()
        lista_activos = []
        for d in viajes_activos:
            lista_activos.append(d.to_dict())
            
        if lista_activos:
            st.info("📍 Tiene un viaje abierto en curso. Al arribar a la locación, presione el botón de cierre para finalizar el estado.")
            for v in lista_activos:
                col_info, col_accion = st.columns([3, 1])
                col_info.write(f"**Viaje ID {v['ID']}** | Destino: {v['Destino']} | Iniciado: {v['Fecha']}")
                if col_accion.button(f"🏁 Llegué a destino", key=f"menu_fin_{v['ID']}"):
                    db.collection("viajes").document(str(v['ID'])).update({
                        "Estado_Viaje": "Finalizado",
                        "Fecha_Fin": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                    })
                    st.success("Viaje cerrado correctamente como Finalizado.")
                    st.rerun()

    st.markdown("---")
    col_menu1, col_menu2 = st.columns(2)
    with col_menu1:
        if st.button("🚀 NUEVO GERENCIAMIENTO DE VIAJE", use_container_width=True):
            st.session_state["paso_actual"] = "Test_Chofer"
            st.rerun()
    with col_menu2:
        if st.button("📜 VER MI HISTORIAL DE DESPACHOS", use_container_width=True):
            st.session_state["paso_actual"] = "Historial"
            st.rerun()

# 2. PANTALLA: TEST DE APTITUD DEL CHOFER
elif st.session_state["paso_actual"] == "Test_Chofer":
    st.subheader("🛡️ Paso 1: Control de Fatiga y Aptitud Física")
    st.write("Declaración jurada obligatoria de condiciones psicofísicas antes de tomar el servicio.")
    
    t1 = st.radio("¿Se siente descansado, lúcido y en condiciones óptimas para conducir?", ["Sí", "No"], index=None)
    t2 = st.radio("¿Ha consumido en las últimas 12 horas medicamentos que puedan alterar sus reflejos o causar somnolencia?", ["No", "Sí"], index=None)
    t3 = st.radio("¿Se encuentra atravesando alguna situación de alta distracción, fatiga extrema o estrés corporativo?", ["No", "Sí"], index=None)

    col_btn_t1, col_btn_t2 = st.columns(2)
    if col_btn_t1.button("⬅️ Cancelar y Volver"):
        st.session_state["paso_actual"] = "Menu"
        st.rerun()
        
    if col_btn_t2.button("Siguiente Paso ➡️"):
        if t1 is None or t2 is None or t3 is None:
            st.error("⛔ Operación Bloqueada: Debe responder todas las preguntas del test de aptitud obligatoriamente.")
        elif t1 == "Sí" and t2 == "No" and t3 == "No":
            st.session_state["test_chofer"] = "Aprobado sin novedades"
            st.session_state["paso_actual"] = "Inspeccion_Vehiculo"
            st.rerun()
        else:
            st.error("⚠️ ALERTA: Según su declaración, usted no se encuentra en condiciones de conducir hoy. El sistema ha bloqueado el despacho. Tome contacto inmediato con su Supervisor o personal de Higiene y Seguridad (SSA).")

# 3. PANTALLA: INSPECCIÓN DEL VEHÍCULO DE FLOTA
elif st.session_state["paso_actual"] == "Inspeccion_Vehiculo":
    st.subheader("🚘 Paso 2: Check-list Preventivo del Vehículo y Documentación")
    st.write("Inspección visual de seguridad obligatoria antes de iniciar la marcha.")

    st.markdown("#### A. Elementos de Emergencia y Equipamiento Técnico")
    items_equipamiento = [
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
    respuestas_equipamiento = {}
    for item in items_equipamiento:
        respuestas_equipamiento[item] = st.radio(item, ["Sí", "No", "N/A"], index=None, horizontal=True)

    st.markdown("---")
    st.markdown("#### B. Verificación de Documentación Legal y de Yacimiento")
    items_documentacion = [
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
    respuestas_documentacion = {}
    for item in items_documentacion:
        respuestas_documentacion[item] = st.radio(item, ["Sí", "No", "N/A"], index=None, horizontal=True)

    st.markdown("---")
    col_insp1, col_insp2 = st.columns(2)
    if col_insp1.button("⬅️ Regresar al Test"):
        st.session_state["paso_actual"] = "Test_Chofer"
        st.rerun()
        
    if col_insp2.button("Iniciar Formulario de Ruta 📝"):
        todos_respondidos_eq = all(v is not None for v in respuestas_equipamiento.values())
        todos_respondidos_doc = all(v is not None for v in respuestas_documentacion.values())
        
        if not (todos_respondidos_eq and todos_respondidos_doc):
            st.error("⛔ ALTO: Control de auditoría fallido. Debe marcar obligatoriamente 'Sí', 'No' o 'N/A' en cada uno de los ítems del vehículo.")
        else:
            posee_fallas = any(v == "No" for v in respuestas_equipamiento.values()) or any(v == "No" for v in respuestas_documentacion.values())
            if posee_fallas:
                st.error("⛔ DESPACHO RECHAZADO: Se han detectado elementos de seguridad o documentación en estado crítico ('No'). Corrija la novedad antes de intentar realizar el gerenciamiento del viaje o marque N/A si el ítem no aplica a la unidad.")
            else:
                st.session_state["inspeccion_vehiculo"] = "Completada y Validada"
                st.session_state["resp_eq"] = respuestas_equipamiento
                st.session_state["resp_doc"] = respuestas_documentacion
                st.session_state["paso_actual"] = "Formulario_Viaje"
                st.rerun()

# 4. PANTALLA: FORMULARIO DE RUTA Y EVALUACIÓN DE RIESGO
elif st.session_state["paso_actual"] == "Formulario_Viaje":
    st.subheader("🛡️ Paso 3: Planificación de Ruta y Análisis de Riesgo Dinámico")
    
    ORGANIZACION = {
        "Higiene y Seguridad": {"Coordinador SSA": 1, "Jefe SSA": 2},
        "Logistica": {"Chofer": 0, "Coordinador de Logistica": 1, "Jefe de Logistica": 2},
        "Fluidos": {"Supervisor de SFP": 1, "Jefe de SFP": 2},
        "Control de solidos": {"Supervisor de CDS": 1, "Jefe de CDS": 2},
        "Mantenimiento": {"Mecanico / Electrico": 1, "Jefe de Mantenimiento": 2},
        "Gerencia": {"Gerente General": 3}
    }

    st.markdown("### 1. Información General del Despacho")
    sector_sel = st.selectbox("Sector Operativo:", list(ORGANIZACION.keys()))
    cargo_sel = st.selectbox("Cargo del Solicitante:", list(ORGANIZACION[sector_sel].keys()))
    nivel_aprobacion_usuario = ORGANIZACION[sector_sel][cargo_sel]
    
    chofer_nombre = st.text_input("Chofer:", value=st.session_state["nombre_empleado"], disabled=(st.session_state["usuario_actual"] != "ADMIN"))
    
    df_flota = obtener_vehiculos()
    if not df_flota.empty:
        opciones_flota = df_flota["Vehiculo"].tolist()
    else:
        opciones_flota = ["⚠️ Cargar vehículos primero en panel de administración"]
        
    vehiculo_sel = st.selectbox("Unidad de Flota Asignada:", opciones_flota)

    with st.expander("\U0001F5FA CONSULTA DE HOJA DE RUTA Y MAPA DE YACIMIENTOS", expanded=True):
        components.iframe("https://www.google.com/maps/d/u/2/embed?mid=1BPDw99m6vQAC09Kdbw9Onaj5mu-blw4&ehbc=2E312F", height=480)

    col_r1, col_r2 = st.columns(2)
    with col_r1: 
        origen_txt = st.text_input("Punto de Origen:")
    with col_r2: 
        destino_txt = st.text_input("Punto de Destino Final / Yacimiento:")
        
    duracion_txt = st.text_input("Duración Estimada del Trayecto (ej: 2.5 horas):")
    salida_tipo = st.radio("Tipo de Salida Operativa:", ["Planificada", "Urgencia"], index=None)

    st.markdown("### 2. Parámetros del Análisis de Riesgo")
    puntos_totales = 0
    
    v_distancia = st.radio("Distancia de la Ruta:", ["< 50km", "< 100km", "< 200km", "> 200km"], index=None)
    if v_distancia:
        puntos_totales += {"< 50km": 1, "< 100km": 2, "< 200km": 5, "> 200km": 7}.get(v_distancia, 0)
    
    # Inclusión del Clima Nublado con peso de 1 punto
    v_clima = st.selectbox("Condiciones Climáticas en Ruta:", ["Despejado", "Nublado", "Viento", "Lluvia", "Niebla", "Nieve"], index=None)
    if v_clima:
        puntos_totales += {"Despejado": 0, "Nublado": 1, "Viento": 2, "Lluvia": 4, "Niebla": 8, "Nieve": 9}.get(v_clima, 0)
    
    v_pasajeros = st.radio("Acompañantes / Pasajeros:", ["Con pasajeros", "Solo conductor"], index=None)
    pasajeros_detalle = "N/A"
    if v_pasajeros == "Con pasajeros":
        pasajeros_detalle = st.text_input("👥 Especifique Nombre, Apellido y Empresa de los Pasajeros:")
    if v_pasajeros:
        puntos_totales += 1 if v_pasajeros == "Con pasajeros" else 5
    
    v_camino = st.radio("Tipo de Superficie Predominante:", ["Pavimento", "Mixto", "Tierra"], index=None)
    if v_camino:
        puntos_totales += {"Pavimento": 1, "Mixto": 2, "Tierra": 4}.get(v_camino, 0)
    
    v_sueno = st.radio("¿Cumplió con el descanso adecuado de más de 8 horas continuas?", ["Sí", "No"], index=None)
    v_horas_servicio = st.radio("Horas Totales de Servicio Acumuladas:", ["< 12hs", "< 14hs", "< 16hs"], index=None)
    if v_sueno and v_horas_servicio:
        if v_horas_servicio == "< 12hs":
            puntos_totales += 1 if v_sueno == "Sí" else 2
        elif v_horas_servicio == "< 14hs":
            puntos_totales += 3 if v_sueno == "Sí" else 5
        elif v_horas_servicio == "< 16hs":
            puntos_totales += 6 if v_sueno == "Sí" else 8
        
    v_escolta = st.radio("¿Requiere Vehículo Escolta o Apoyo Logístico?", ["No", "Sí"], index=None)
    if v_escolta:
        puntos_totales += 1 if v_escolta == "No" else 5
    
    v_horario = st.radio("Franja Horaria de Conducción:", ["Diurno", "Nocturno"], index=None)
    if v_horario:
        puntos_totales += 5 if v_horario == "Nocturno" else 1
    
    v_comunicacion = st.radio("Nivel de Cobertura de Señal en la Ruta:", ["Total", "Tramos sin señal", "Sin señal"], index=None)
    if v_comunicacion:
        puntos_totales += {"Total": 1, "Tramos sin señal": 3, "Sin señal": 5}.get(v_comunicacion, 0)

    # Evaluación matemática de la matriz de riesgo
    nivel_riesgo_calculado = 1 if puntos_totales <= 15 else (2 if puntos_totales <= 30 else 3)
    
    # Lógica de semaforización de aprobación
    if nivel_aprobacion_usuario >= nivel_riesgo_calculado:
        color_semaforo = "green"
        aprobacion_estado_inicial = "AUTORIZADO (Auto-Aprobado)"
    else:
        if nivel_riesgo_calculado < 3:
            color_semaforo = "orange"
        else:
            color_semaforo = "red"
        aprobacion_estado_inicial = f"PENDIENTE DE APROBACIÓN (Nivel {nivel_riesgo_calculado})"

    # --- BLOQUE VISUAL DINÁMICO EN TIEMPO REAL ---
    st.markdown("---")
    st.subheader("📋 Matriz de Riesgo Calculada")
    if color_semaforo == "green":
        st.success(f"**{aprobacion_estado_inicial}** | Nivel de Riesgo: {nivel_riesgo_calculado} | Puntaje Acumulado: {puntos_totales} puntos")
    elif color_semaforo == "orange":
        st.warning(f"**{aprobacion_estado_inicial}** | Nivel de Riesgo: {nivel_riesgo_calculado} | Puntaje Acumulado: {puntos_totales} puntos")
    else:
        st.error(f"**{aprobacion_estado_inicial}** | Nivel de Riesgo: {nivel_riesgo_calculado} | Puntaje Acumulado: {puntos_totales} puntos")
    st.markdown("---")

    col_final1, col_final2 = st.columns(2)
    with col_final1:
        if st.button("⬅️ Volver a la Inspección"):
            st.session_state["paso_actual"] = "Inspeccion_Vehiculo"
            st.rerun()
            
    with col_final2:
        if st.button("CONFIRMAR Y GUARDAR REGISTRO DE VIAJE"):
            
            # --- CERROJO ABSOLUTO DE VALIDACIÓN ANTI-VACÍOS ---
            formulario_completado_ok = all([
                origen_txt.strip() != "",
                destino_txt.strip() != "",
                duracion_txt.strip() != "",
                vehiculo_sel != "⚠️ Cargar vehículos primero en panel de administración",
                salida_tipo is not None,
                v_distancia is not None,
                v_clima is not None,
                v_pasajeros is not None,
                v_camino is not None,
                v_sueno is not None,
                v_horas_servicio is not None,
                v_escolta is not None,
                v_horario is not None,
                v_comunicacion is not None
            ])

            if not formulario_completado_ok:
                st.error("⛔ ERROR DE CONTROL: No se puede guardar el viaje. Se detectaron campos de texto vacíos o preguntas de la evaluación de riesgo sin responder.")
            elif v_pasajeros == "Con pasajeros" and pasajeros_detalle.strip() == "":
                st.error("⚠️ REGISTRO INCOMPLETO: Determinó que viaja con acompañantes, por ende es obligatorio ingresar Nombre y Apellido de los pasajeros.")
            else:
                siguiente_id_viaje = obtener_siguiente_id()
                timestamp_registro = datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                
                # Armado estructurado del documento para la nube
                documento_viaje = {
                    "ID": siguiente_id_viaje,
                    "Fecha": timestamp_registro,
                    "Chofer": chofer_nombre,
                    "Sector": sector_sel,
                    "Cargo": cargo_sel,
                    "Vehiculo": vehiculo_sel,
                    "Duracion": duracion_txt,
                    "Salida": salida_tipo,
                    "Alarma Nocturna": "encendida" if v_horario == "Nocturno" else "apagada",
                    "Origen": origen_txt,
                    "Destino": destino_txt,
                    "Estado": aprobacion_estado_inicial,
                    "Puntaje": puntos_totales,
                    "Nivel": nivel_riesgo_calculado,
                    "Aprobacion": "🟢 Aprobado" if color_semaforo == "green" else "🔴 Pendiente",
                    "Aprobador": st.session_state["nombre_empleado"] if color_semaforo == "green" else "Pendiente",
                    "Fecha_Aprobacion": timestamp_registro if color_semaforo == "green" else "Pendiente",
                    "Estado_Viaje": "En viaje" if color_semaforo == "green" else "En espera",
                    "Fecha_Fin": "En curso",
                    "Test_Chofer": st.session_state.get("test_chofer", "Aprobado"),
                    "Inspeccion_Vehiculo": st.session_state.get("inspeccion_vehiculo", "Aprobada"),
                    "Checklist_Eq": st.session_state.get("resp_eq", {}),
                    "Checklist_Doc": st.session_state.get("resp_doc", {}),
                    "R_Distancia": v_distancia,
                    "R_Clima": v_clima,
                    "R_Pasajeros": v_pasajeros,
                    "Detalle_Pasajeros": pasajeros_detalle,
                    "R_Camino": v_camino,
                    "R_Sueno": v_sueno,
                    "R_Horas": v_horas_servicio,
                    "R_Escolta": v_escolta,
                    "R_Com": v_comunicacion
                }
                
                if guardar_en_nube(documento_viaje):
                    st.balloons()
                    
                    # Estructuración de la plantilla de WhatsApp Dinámica
                    if color_semaforo == "green":
                        cabecera_mensaje = f"🟢 *AVISO DE VIAJE AUTO-APROBADO - ID {siguiente_id_viaje}* 🟢"
                        pie_mensaje = f"👉 *Viaje autorizado automáticamente por matriz de riesgo. No requiere acción de aprobación.*"
                    else:
                        cabecera_mensaje = f"🔴 *NUEVA SOLICITUD DE VIAJE PENDIENTE - ID {siguiente_id_viaje}* 🔴"
                        pie_mensaje = f"👉 *Atención Supervisor: Ingrese al sistema MARBAR para validar y APROBAR el despacho.*"

                    texto_whatsapp = (
                        f"{cabecera_mensaje}\n\n"
                        f"👤 *Conductor:* {chofer_nombre}\n"
                        f"🚚 *Unidad:* {vehiculo_sel}\n"
                        f"📍 *Origen:* {origen_txt}\n"
                        f"🏁 *Destino:* {destino_txt}\n"
                        f"⏱️ *Duración:* {duracion_txt}\n"
                        f"⚠️ *Riesgo:* Nivel {nivel_riesgo_calculado} ({puntos_totales} pts)\n"
                        f"📋 *Condición:* {aprobacion_estado_inicial}\n\n"
                        f"{pie_mensaje}"
                    )
                    
                    st.markdown(f"### [📱 ENVIAR TICKET DE CONTROL POR WHATSAPP](https://wa.me/?text={urllib.parse.quote(texto_whatsapp)})")
                    st.success("El viaje ha sido registrado exitosamente en la base de datos central.")
                    st.session_state["paso_actual"] = "Menu"

# 5. PANTALLA: HISTORIAL INDIVIDUAL DE VIAJES
elif st.session_state["paso_actual"] == "Historial":
    st.subheader("📜 Historial de Despachos Registrados")
    
    viajes_stream = db.collection("viajes").stream()
    registros_totales = []
    for doc in viajes_stream:
        registros_totales.append(doc.to_dict())
        
    df_historial = pd.DataFrame(registros_totales)
    
    if not df_historial.empty:
        # Filtro de seguridad: Los choferes normales solo ven sus propios despachos
        if st.session_state["usuario_actual"] != "ADMIN":
            df_historial = df_historial[df_historial["Chofer"] == st.session_state["nombre_empleado"]]
            
        if not df_historial.empty:
            # Ordenamiento cronológico forzado de mayor a menor por ID
            df_historial = df_historial.sort_values(by="ID", ascending=False)
            
            st.dataframe(
                df_historial[['ID', 'Fecha', 'Origen', 'Destino', 'Estado_Viaje']], 
                hide_index=True, 
                use_container_width=True
            )
            
            st.markdown("---")
            st.write("#### 📥 Auditoría de Ticket Individual Externo")
            
            opciones_dropdown = [""]
            for _, fila in df_historial.iterrows():
                opciones_dropdown.append(f"{fila['ID']} - {fila.get('Chofer','')} - {fila.get('Fecha','')[:10]}")
                
            viaje_seleccionado_txt = st.selectbox("Seleccione el viaje para extraer el reporte texturizado:", opciones_dropdown)
            
            if viaje_seleccionado_txt != "":
                id_extrayendo = viaje_seleccionado_txt.split(" - ")[0]
                datos_v = df_historial[df_historial["ID"].astype(str) == id_extrayendo].iloc[0]
                
                # Reconstrucción textual completa de las respuestas del checklist de inspección
                mapa_eq = datos_v.get('Checklist_Eq', {})
                mapa_doc = datos_v.get('Checklist_Doc', {})
                
                txt_equipamiento = ""
                if mapa_eq:
                    for k, v in mapa_eq.items():
                        txt_equipamiento += f"  - {k}: {v}\n"
                else:
                    txt_equipamiento = "  (No se registran datos estructurados de equipamiento)\n"
                    
                txt_documentacion = ""
                if mapa_doc:
                    for k, v in mapa_doc.items():
                        txt_documentacion += f"  - {k}: {v}\n"
                else:
                    txt_documentacion = "  (No se registran datos estructurados de documentación)\n"

                reporte_estructurado = f"""
===================================================================
                  REPORTE COMPLETO DE AUDITORÍA - MARBAR
===================================================================
ID DEL VIAJE       : {datos_v.get('ID')}
FECHA Y HORA       : {datos_v.get('Fecha')}
CONDUCTOR          : {datos_v.get('Chofer')}
SECTOR             : {datos_v.get('Sector')}
CARGO              : {datos_v.get('Cargo')}
UNIDAD DE FLOTA    : {datos_v.get('Vehiculo')}
-------------------------------------------------------------------
1. LOGÍSTICA DE RUTA Y SEGUIMIENTO
PUNTO DE ORIGEN    : {datos_v.get('Origen')}
PUNTO DE DESTINO   : {datos_v.get('Destino')}
DURACIÓN ESTIMADA  : {datos_v.get('Duracion')}
MODALIDAD DE SALIDA: {datos_v.get('Salida')}
FECHA/HORA CIERRE  : {datos_v.get('Fecha_Fin')}
-------------------------------------------------------------------
2. CONTROLES OPERATIVOS PREVENTIVOS (CHECKLIST)
DECLARACIÓN FATIGA : {datos_v.get('Test_Chofer')}
ESTADO INSPECCIÓN  : {datos_v.get('Inspeccion_Vehiculo')}

>> DESGLOSE CONTROL DE EQUIPAMIENTO:
{txt_equipamiento}
>> DESGLOSE CONTROL DE DOCUMENTACIÓN:
{txt_documentacion}
-------------------------------------------------------------------
3. ANÁLISIS DE LA MATRIZ DE RIESGOS INDIVIDUAL
DISTANCIA ASIGNADA : {datos_v.get('R_Distancia')}
CLIMA DECLARADO    : {datos_v.get('R_Clima')}
ACOMPAÑANTES       : {datos_v.get('R_Pasajeros')} ({datos_v.get('Detalle_Pasajeros')})
ESTADO DEL CAMINO  : {datos_v.get('R_Camino')}
DESCANSO ADECUADO  : {datos_v.get('R_Sueno')}
HORAS DE JORNADA   : {datos_v.get('R_Horas')}
VEHÍCULO ESCOLTA   : {datos_v.get('R_Escolta')}
COBERTURA SEÑAL    : {datos_v.get('R_Com')}
-------------------------------------------------------------------
4. CONTROL DE VALIDACIÓN Y FIRMA DIGITAL
PUNTAJE OBTENIDO   : {datos_v.get('Puntaje')} puntos
NIVEL DE RIESGO    : Nivel {datos_v.get('Nivel')}
APROBADO POR       : {datos_v.get('Aprobador')}
ESTAMPA DE TIEMPO  : {datos_v.get('Fecha_Aprobacion')}
ESTADO LOGÍSTICO   : {datos_v.get('Estado_Viaje')}
===================================================================
                """
                st.download_button(
                    label="📥 Descargar Reporte Integral Completo (.txt)", 
                    data=reporte_estructurado, 
                    file_name=f"Auditoria_Viaje_MARBAR_{id_extrayendo}.txt"
                )
        else:
            st.info("No posee registros de viaje cargados en su cuenta.")
            
    if st.button("⬅️ Volver al Menú Principal"):
        st.session_state["paso_actual"] = "Menu"
        st.rerun()

# --- 6. DISEÑO DEL PANEL LATERAL CENTRALIZADO (SIDEBAR) ---
with st.sidebar:
    if os.path.exists("logo.png"): 
        st.image("logo.png", use_column_width=True)
    else: 
        st.subheader("🚛 MARBAR SRL")
    st.markdown("---")
    st.header("📊 Monitoreo SSA & Logística")
    
    if st.session_state["usuario_actual"] is not None:
        if st.button("🚪 Cerrar Sesión Segura"):
            st.session_state.clear()
            st.rerun()

try:
    viajes_sidebar_stream = db.collection("viajes").stream()
    registros_sidebar = []
    for d in viajes_sidebar_stream:
        registros_sidebar.append(d.to_dict())
        
    df_sb = pd.DataFrame(registros_sidebar)
    
    if not df_sb.empty:
        fecha_hoy_ar = datetime.now(TZ_AR).strftime("%d/%m/%Y")
        df_hoy = df_sb[df_sb['Fecha'].str.contains(fecha_hoy_ar, na=False)]
        
        st.sidebar.markdown("---")
        st.sidebar.write("⚠️ **Pendientes de Validación Operativa (Hoy):**")
        df_pendientes_hoy = df_hoy[df_hoy['Aprobacion'].str.contains("Pendiente", na=False)]
        if not df_pendientes_hoy.empty:
            st.sidebar.dataframe(df_pendientes_hoy[['Chofer', 'Destino']], hide_index=True)
        else:
            st.sidebar.write("✅ Cero demoras. Sin solicitudes pendientes.")
            
        st.sidebar.markdown("---")
        st.sidebar.write("🚚 **Unidades en Ruta Activas:**")
        df_en_ruta = df_sb[df_sb['Estado_Viaje'] == "En viaje"]
        if not df_en_ruta.empty:
            st.sidebar.dataframe(df_en_ruta[['Chofer', 'Destino']], hide_index=True)
        else:
            st.sidebar.write("✅ Flota resguardada. No hay unidades en ruta.")

        st.sidebar.markdown("---")
        st.sidebar.subheader("📜 Extracción de Auditoría Rápida")
        
        df_sb_ordenado = df_sb.sort_values(by="ID", ascending=False)
        opciones_sidebar = [""]
        for _, r_sb in df_sb_ordenado.iterrows():
            opciones_sidebar.append(f"{r_sb['ID']} - {r_sb.get('Chofer','')} - {r_sb.get('Fecha','')[:10]}")
            
        viaje_sel_sidebar = st.sidebar.selectbox("Buscar ID de despacho:", opciones_sidebar, key="sb_desplegable_aud")
        
        if viaje_sel_sidebar != "":
            id_sb_ext = viaje_sel_sidebar.split(" - ")[0]
            datos_sb_v = df_sb[df_sb["ID"].astype(str) == id_sb_ext].iloc[0]
            
            mapa_eq_sb = datos_sb_v.get('Checklist_Eq', {})
            mapa_doc_sb = datos_sb_v.get('Checklist_Doc', {})
            
            txt_eq_sb = "\n".join([f" - {k}: {v}" for k, v in mapa_eq_sb.items()]) if mapa_eq_sb else " - No data"
            txt_doc_sb = "\n".join([f" - {k}: {v}" for k, v in mapa_doc_sb.items()]) if mapa_doc_sb else " - No data"
            
            reporte_sb_txt = f"MARBAR TRIP ID {id_sb_ext}\nConductor: {datos_sb_v.get('Chofer')}\nUnidad: {datos_sb_v.get('Vehiculo')}\n\nEQUIPAMIENTO:\n{txt_eq_sb}\n\nDOCUMENTACIÓN:\n{txt_doc_sb}"
            st.sidebar.download_button(
                label="📥 Descargar Ficha Rápida", 
                data=reporte_sb_txt, 
                file_name=f"Ficha_Inspeccion_{id_sb_ext}.txt", 
                key="btn_descarga_sidebar_txt"
            )

        # SECCIÓN DE EXCEL: EXCLUSIVO PARA ROL ADMINISTRADOR
        if st.session_state["usuario_actual"] == "ADMIN":
            st.sidebar.markdown("---")
            st.sidebar.subheader("📊 Consola de Cierre Trimestral")
            
            columnas_maestras_orden = [
                'ID', 'Fecha', 'Chofer', 'Sector', 'Cargo', 'Vehiculo', 'Duracion', 
                'Salida', 'Alarma Nocturna', 'Origen', 'Destino', 'Estado', 'Puntaje', 
                'Nivel', 'Aprobacion', 'Aprobador', 'Fecha_Aprobacion', 'Estado_Viaje', 'Fecha_Fin'
            ]
            for col_m in columnas_maestras_orden:
                if col_m not in df_sb.columns:
                    df_sb[col_m] = "N/A"
                    
            # ORDENAMIENTO FORZADO CRÍTICO DE MAYOR A MENOR PARA EL EXCEL GENERAL
            df_exportacion_final = df_sb[columnas_maestras_orden].sort_values(by="ID", ascending=False)
            
            stream_bytes_excel = io.BytesIO()
            with pd.ExcelWriter(stream_bytes_excel, engine='openpyxl') as excel_writer:
                df_exportacion_final.to_excel(excel_writer, index=False)
                
            st.sidebar.download_button(
                label="📥 Descargar Auditoría Maestra (Excel)", 
                data=stream_bytes_excel.getvalue(), 
                file_name=f"Auditoria_General_MARBAR_{fecha_hoy_ar.replace('/','-')}.xlsx",
                key="btn_descarga_excel_maestro"
            )
except Exception as err_sb:
    pass

# --- 7. BANDEJA CENTRALIZADA DE APROBACIONES (VISTA DE SUPERVISIÓN) ---
if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia"]:
    st.markdown("---")
    st.title("📥 Bandeja Central de Validaciones")
    
    try:
        solicitudes_pendientes_stream = db.collection("viajes").where("Aprobacion", "==", "🔴 Pendiente").stream()
        perfiles_pendientes_lista = []
        for doc_p in solicitudes_pendientes_stream:
            perfiles_pendientes_lista.append(doc_p.to_dict())
            
        if perfiles_pendientes_lista:
            for viaje_p in perfiles_pendientes_lista:
                with st.expander(f"🚨 ID: {viaje_p['ID']} | Conductor: {viaje_p['Chofer']} | Riesgo: Nivel {viaje_p['Nivel']}"):
                    st.write(f"**Trayecto Logístico:** {viaje_p['Origen']} e rumbos hacia {viaje_p['Destino']}")
                    st.write(f"**Puntaje total de riesgo:** {viaje_p['Puntaje']} puntos acumulados.")
                    
                    if st.button(f"✍️ Sellar Aprobación Oficial {viaje_p['ID']}", key=f"btn_sellar_aprob_{viaje_p['ID']}"):
                        db.collection("viajes").document(str(viaje_p['ID'])).update({
                            "Aprobacion": "🟢 Aprobado",
                            "Aprobador": st.session_state["nombre_empleado"],
                            "Fecha_Aprobacion": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S"),
                            "Estado_Viaje": "En viaje"
                        })
                        st.success(f"Viaje {viaje_p['ID']} aprobado con firma digital autorizada.")
                        st.rerun()
        else:
            st.info("✅ Bandeja limpia. No existen solicitudes de despacho pendientes en su área de control.")
    except Exception:
        pass

# --- 8. MÓDULO DE ADMINISTRACIÓN AVANZADA (EDICIÓN BASE DE DATOS E IDP) ---
if st.session_state["usuario_actual"] == "ADMIN":
    st.markdown("---")
    st.title("⚙️ Consola de Configuración de Infraestructura")
    tab_usuarios, tab_flota = st.tabs(["👥 Control de Usuarios e Identidades (IDP)", "🚘 Gestión de Flota Pesada/Liviana"])
    
    with tab_usuarios:
        st.write("### Alta Homologada de Personal")
        st.caption("Al guardar, el sistema creará de forma simultánea el perfil en la base de datos y la identidad criptográfica en el IDP de Firebase Auth.")
        
        adm_email = st.text_input("Correo de Acceso del Empleado (Yahoo, Hotmail, Gmail):", key="input_adm_email")
        adm_password = st.text_input("Contraseña Inicial de Seguridad:", type="password", key="input_adm_password")
        adm_nombre = st.text_input("Nombre y Apellido Completo (Razón Social Personal):", key="input_adm_nombre")
        adm_dni = st.text_input("Número de Documento (DNI):", key="input_adm_dni")
        adm_sector = st.selectbox("Sector de Encuadre:", ["Higiene y Seguridad", "Logistica", "Fluidos", "Control de solidos", "Mantenimiento", "Gerencia"], key="input_adm_sector")
        adm_rol = st.selectbox("Rol Jerárquico de Aplicación:", ["Chofer", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia", "ADMIN"], key="input_adm_rol")
        
        if st.button("💾 Registrar y Sincronizar Usuario", key="btn_ejecutar_alta_usuario"):
            if adm_email.strip() != "" and adm_password.strip() != "" and adm_nombre.strip() != "" and adm_dni.strip() != "":
                try:
                    # Registro en la bóveda de Firebase Authentication
                    usuario_creado_auth = auth.create_user(
                        email=adm_email,
                        password=adm_password
                    )
                    
                    # Registro en la colección estructural de Firestore
                    db.collection("usuarios").document(adm_dni).set({
                        "DNI_Usuario": adm_dni,
                        "Nombre": adm_nombre,
                        "Email": adm_email,
                        "Rol": adm_rol,
                        "Sector": adm_sector
                    })
                    st.success(f"Éxito: La identidad de {adm_nombre} se ha sincronizado correctamente con el IDP.")
                    st.rerun()
                except Exception as error_idp:
                    st.error(f"Falla de Infraestructura al crear el usuario: {error_idp}")
            else:
                st.error("⚠️ Validación bloqueada: Complete todos los campos de texto requeridos para el alta.")
                
        st.markdown("---")
        st.write("### Nómina de Usuarios en Base de Datos")
        df_usuarios_consola = obtener_usuarios()
        if not df_usuarios_consola.empty:
            st.dataframe(df_usuarios_consola, hide_index=True, use_container_width=True)
            
            user_eliminar_sel = st.selectbox("Seleccione el DNI del usuario a dar de baja de la plataforma:", [""] + df_usuarios_consola["DNI_Usuario"].tolist(), key="select_adm_delete_user")
            if st.button("❌ Dar de Baja Usuario", key="btn_eliminar_usuario_final"):
                if user_eliminar_sel.strip() != "":
                    db.collection("usuarios").document(user_eliminar_sel).delete()
                    st.success("Perfil de usuario eliminado de los registros de almacenamiento de datos.")
                    st.rerun()
        else:
            st.info("Sin usuarios cargados.")

    with tab_flota:
        st.write("### Incorporación de Patentes a la Flota")
        adm_patente = st.text_input("Identificación de la Unidad / Patente Interna:", key="input_adm_patente")
        
        if st.button("Documentar Nueva Unidad 💾", key="btn_guardar_unidad_flota"):
            if adm_patente.strip() != "":
                db.collection("vehiculos").document(adm_patente).set({
                    "Vehiculo": adm_patente
                })
                st.success(f"La unidad {adm_patente} se integró a los activos vehiculares de la compañía.")
                st.rerun()
            else:
                st.error("⚠️ Ingrese una patente válida.")
                
        st.markdown("---")
        st.write("### Unidades Habilitadas")
        df_flota_consola = obtener_vehiculos()
        if not df_flota_consola.empty:
            st.dataframe(df_flota_consola, hide_index=True, use_container_width=True)
            
            vehiculo_eliminar_sel = st.selectbox("Seleccione la unidad a retirar de servicio de la empresa:", [""] + df_flota_consola["Vehiculo"].tolist(), key="select_adm_delete_vehiculo")
            if st.button("❌ Retirar Unidad de Flota", key="btn_eliminar_vehiculo_final"):
                if vehiculo_eliminar_sel.strip() != "":
                    db.collection("vehiculos").document(vehiculo_eliminar_sel).delete()
                    st.success("Unidad removida del inventario de despacho.")
                    st.rerun()