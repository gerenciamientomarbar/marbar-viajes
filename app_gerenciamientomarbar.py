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
# Coloca aquí la Clave de API web que obtuviste de Firebase
API_KEY_FIREBASE = "AIzaSyAHE35ma-FT5xy1uvacwX2g_CtLbmyCWrsv" 

# --- CONFIGURACIÓN DE ZONA HORARIA (ARGENTINA UTC-3) ---
TZ_AR = timezone(timedelta(hours=-3))

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    layout="wide", 
    page_title="MARBAR - Gestión de Viajes", 
    page_icon="🚛"
)

# --- DISEÑO CORPORATIVO (CSS) ---
primary_color = "#1E3A8A" 
text_color = "#1F2937"    

st.markdown(f"""
<style>
    .stApp {{ 
        background-color: #F3F4F6; 
    }}
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

# --- CONEXIÓN A LA NUBE (FIREBASE) ---
if not firebase_admin._apps:
    try:
        llave_secreta = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(llave_secreta)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Error crítico al conectar con la llave secreta: {e}")

db = firestore.client()

# --- FUNCIONES DE COMUNICACIÓN Y FORMATO ---
def login_usuario(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY_FIREBASE}"
    payload = {
        "email": email, 
        "password": password, 
        "returnSecureToken": True
    }
    res = requests.post(url, json=payload)
    if res.status_code == 200:
        return res.json()
    else:
        return None

def enviar_correo_recuperacion(email):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={API_KEY_FIREBASE}"
    payload = {
        "requestType": "PASSWORD_RESET", 
        "email": email
    }
    res = requests.post(url, json=payload)
    if res.status_code == 200:
        return True
    else:
        return False

def obtener_usuarios():
    usuarios_ref = db.collection("usuarios").stream()
    lista_usuarios = []
    for doc in usuarios_ref:
        lista_usuarios.append(doc.to_dict())
    return pd.DataFrame(lista_usuarios)

def obtener_vehiculos():
    vehiculos_ref = db.collection("vehiculos").stream()
    lista_vehiculos = []
    for doc in vehiculos_ref:
        lista_vehiculos.append(doc.to_dict())
    
    if lista_vehiculos:
        return pd.DataFrame(lista_vehiculos)
    else:
        return pd.DataFrame(columns=["Vehiculo"])

def obtener_siguiente_id():
    try:
        viajes_ref = db.collection("viajes").order_by("ID", direction=firestore.Query.DESCENDING).limit(1).get()
        if viajes_ref:
            return viajes_ref[0].to_dict().get("ID", 0) + 1
        else:
            return 1
    except Exception:
        return 1

def guardar_en_nube(datos_viaje):
    try:
        db.collection("viajes").document(str(datos_viaje["ID"])).set(datos_viaje)
        return True
    except Exception:
        return False

def generar_ticket_txt(v_data):
    """Genera el reporte TXT con el formato profesional corporativo"""
    chk_eq = v_data.get('Checklist_Eq', {})
    chk_doc = v_data.get('Checklist_Doc', {})
    
    str_eq = ""
    if chk_eq:
        for k, v in chk_eq.items():
            str_eq += f"  - {k}: {v}\n"
    else:
        str_eq = "  (Sin datos de equipamiento)\n"
        
    str_doc = ""
    if chk_doc:
        for k, v in chk_doc.items():
            str_doc += f"  - {k}: {v}\n"
    else:
        str_doc = "  (Sin datos de documentación)\n"

    reporte = f"""MARBAR TRIP ID {v_data.get('ID')}
Conductor: {v_data.get('Chofer')}
Unidad: {v_data.get('Vehiculo')}

EQUIPAMIENTO:
{str_eq}
DOCUMENTACIÓN:
{str_doc}
=========================================
      REPORTE INTEGRAL DE RUTA
=========================================
SECTOR         : {v_data.get('Sector', 'N/A')}
CARGO          : {v_data.get('Cargo', 'N/A')}
FECHA          : {v_data.get('Fecha')}
-----------------------------------------
1. RUTA Y TIEMPOS
ORIGEN         : {v_data.get('Origen')}
DESTINO        : {v_data.get('Destino')}
DURACIÓN EST.  : {v_data.get('Duracion')}
TIPO SALIDA    : {v_data.get('Salida', 'N/A')}
FECHA CIERRE   : {v_data.get('Fecha_Fin', 'N/A')}
-----------------------------------------
2. PREVENCIÓN PREVIA 
TEST FATIGA    : {v_data.get('Test_Chofer', 'N/A')}
INSPECCIÓN V.  : {v_data.get('Inspeccion_Vehiculo', 'N/A')}
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
APROBADO POR   : {v_data.get('Aprobador', 'N/A')}
HORA APROB.    : {v_data.get('Fecha_Aprobacion', 'N/A')}
ESTADO FINAL   : {v_data.get('Estado_Viaje', 'N/A')}
========================================="""
    return reporte

# --- GESTOR DE SESIÓN ---
if "usuario_actual" not in st.session_state: 
    st.session_state["usuario_actual"] = None
    
if "paso_actual" not in st.session_state: 
    st.session_state["paso_actual"] = "Menu"

# --- PANTALLA DE ACCESO (LOGIN) ---
if st.session_state["usuario_actual"] is None:
    col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
    with col_logo2:
        if os.path.exists("logo.png"): 
            st.image("logo.png", use_column_width=True)
        else: 
            st.warning("⚠️ Falta 'logo.png'")
            
    st.title("🔒 Acceso Seguro - MARBAR")
    e_ing = st.text_input("Correo Electrónico:").strip()
    c_ing = st.text_input("Contraseña:", type="password")
    
    col_log1, col_log2 = st.columns(2)
    
    with col_log1:
        if st.button("Iniciar Sesión", use_container_width=True):
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
                        p = usuarios_ref[0].to_dict()
                        st.session_state.update({
                            "usuario_actual": p["Rol"], 
                            "nombre_empleado": p["Nombre"], 
                            "sector_empleado": p["Sector"], 
                            "email_empleado": e_ing
                        })
                        st.rerun()
                    else: 
                        st.error("❌ Correo sin perfil en la base MARBAR.")
                else: 
                    st.error("❌ Credenciales incorrectas.")
                
    with col_log2:
        if st.button("¿Olvidaste tu contraseña?", use_container_width=True):
            if e_ing == "":
                st.warning("⚠️ Por favor, escribe tu correo arriba y vuelve a presionar este botón.")
            else:
                if enviar_correo_recuperacion(e_ing):
                    st.success(f"✅ Se ha enviado un enlace seguro a {e_ing} para restablecer tu contraseña.")
                else:
                    st.error("❌ No se pudo enviar el correo. Verifica que la dirección esté bien escrita y registrada.")
    st.stop()

# --- WORKFLOW PRINCIPAL ---

# 1. MENÚ PRINCIPAL
if st.session_state["paso_actual"] == "Menu":
    st.subheader(f"Panel Operativo - Bienvenido, {st.session_state['nombre_empleado']}")
    
    if st.session_state["usuario_actual"] != "ADMIN":
        viajes_activos = db.collection("viajes").where("Chofer", "==", st.session_state["nombre_empleado"]).where("Estado_Viaje", "==", "En viaje").stream()
        lista_activos = []
        for d in viajes_activos:
            lista_activos.append(d.to_dict())
            
        if lista_activos:
            st.info("📍 Tiene un viaje abierto en curso.")
            for v in lista_activos:
                col_info, col_accion = st.columns([3, 1])
                col_info.write(f"**ID {v['ID']}** | Destino: {v['Destino']}")
                if col_accion.button(f"🏁 Llegué a destino", key=f"menu_fin_{v['ID']}"):
                    db.collection("viajes").document(str(v['ID'])).update({
                        "Estado_Viaje": "Finalizado", 
                        "Fecha_Fin": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                    })
                    st.success("Viaje cerrado.")
                    st.rerun()

    st.markdown("---")
    col_menu1, col_menu2 = st.columns(2)
    with col_menu1:
        if st.button("🚀 NUEVO GERENCIAMIENTO DE VIAJE", use_container_width=True): 
            st.session_state["paso_actual"] = "Test_Chofer"
            st.rerun()
            
    with col_menu2:
        if st.button("📜 VER MI HISTORIAL", use_container_width=True): 
            st.session_state["paso_actual"] = "Historial"
            st.rerun()

# 2. TEST DE FATIGA
elif st.session_state["paso_actual"] == "Test_Chofer":
    st.subheader("🛡️ Paso 1: Control de Fatiga")
    
    t1 = st.radio("¿Se siente descansado y en condiciones?", ["Sí", "No"], index=None)
    t2 = st.radio("¿Ha consumido medicamentos que causen somnolencia?", ["No", "Sí"], index=None)
    t3 = st.radio("¿Se encuentra bajo estrés o distracción?", ["No", "Sí"], index=None)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Cancelar"): 
            st.session_state["paso_actual"] = "Menu"
            st.rerun()
            
    with col2:
        if st.button("Siguiente ➡️"):
            if t1 is None or t2 is None or t3 is None: 
                st.error("⛔ Responda todas las preguntas.")
            elif t1 == "Sí" and t2 == "No" and t3 == "No":
                st.session_state["test_chofer"] = "Aprobado"
                st.session_state["paso_actual"] = "Inspeccion_Vehiculo"
                st.rerun()
            else: 
                st.error("⚠️ No está en condiciones de conducir.")

# 3. INSPECCIÓN VEHÍCULO
elif st.session_state["paso_actual"] == "Inspeccion_Vehiculo":
    st.subheader("🚘 Paso 2: Check-list Preventivo")
    
    st.markdown("#### A. Equipamiento")
    eq_items = [
        "1. Cinturón De Seguridad", 
        "2. Torque En Pernos", 
        "3. Triángulos x2", 
        "4. Neumático Auxilio/Cric", 
        "5. Extintor", 
        "6. Alarma Retroceso", 
        "7. Botiquín", 
        "8. Cadenas/Clavos", 
        "9. Pala/Supervivencia", 
        "10. Verificación 360°"
    ]
    respuestas_eq = {}
    for item in eq_items:
        respuestas_eq[item] = st.radio(item, ["Sí", "No", "N/A"], index=None, horizontal=True)
        
    st.markdown("---")
    st.markdown("#### B. Documentación")
    doc_items = [
        "1. Tarjeta Propiedad", 
        "2. Póliza Seguro", 
        "3. Revisión Técnica", 
        "4. Licencia", 
        "5. Manejo Defensivo", 
        "6. Credencial", 
        "7. Ingreso Yacimientos", 
        "8. Permisos Especiales", 
        "9. Curso 4x4"
    ]
    respuestas_doc = {}
    for item in doc_items:
        respuestas_doc[item] = st.radio(item, ["Sí", "No", "N/A"], index=None, horizontal=True)
        
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Regresar"): 
            st.session_state["paso_actual"] = "Test_Chofer"
            st.rerun()
            
    with col2:
        if st.button("Siguiente 📝"):
            todas_eq = all(v is not None for v in respuestas_eq.values())
            todas_doc = all(v is not None for v in respuestas_doc.values())
            
            if not (todas_eq and todas_doc):
                st.error("⛔ Debe responder 'Sí', 'No' o 'N/A' en todos los ítems.")
            else:
                hay_negativas = any(v == "No" for v in respuestas_eq.values()) or any(v == "No" for v in respuestas_doc.values())
                if hay_negativas:
                    st.error("⛔ Elementos marcados con 'No'. Prohibido el despacho.")
                else:
                    st.session_state["inspeccion_vehiculo"] = "Aprobada"
                    st.session_state["resp_eq"] = respuestas_eq
                    st.session_state["resp_doc"] = respuestas_doc
                    st.session_state["paso_actual"] = "Formulario_Viaje"
                    st.rerun()

# 4. FORMULARIO Y RIESGO
elif st.session_state["paso_actual"] == "Formulario_Viaje":
    st.subheader("🛡️ Paso 3: Análisis de Riesgo")
    
    sector_usuario = st.session_state["sector_empleado"]
    rol_usuario = st.session_state["usuario_actual"]
    nombre_chofer = st.session_state["nombre_empleado"]
    
    mapa_autoridad = {
        "Chofer": 0, 
        "Supervisor / Coordinador": 1, 
        "Jefe de Servicio": 2, 
        "Gerencia": 3, 
        "ADMIN": 3
    }
    nivel_aprobacion_usuario = mapa_autoridad.get(rol_usuario, 0)
    
    st.markdown("### 1. Datos Generales")
    st.info(f"👤 **Conductor:** {nombre_chofer} | **Sector:** {sector_usuario} | **Perfil:** {rol_usuario}")

    df_flota = obtener_vehiculos()
    if not df_flota.empty:
        opciones_flota = df_flota["Vehiculo"].tolist()
    else:
        opciones_flota = ["⚠️ Cargar flota en Admin"]
        
    vehiculo_sel = st.selectbox("Unidad:", opciones_flota)

    with st.expander("\U0001F5FA CONSULTA MAPA DE YACIMIENTOS", expanded=True):
        components.iframe("https://www.google.com/maps/d/u/2/embed?mid=1BPDw99m6vQAC09Kdbw9Onaj5mu-blw4&ehbc=2E312F", height=480)

    col1, col2 = st.columns(2)
    with col1: 
        origen_txt = st.text_input("Origen:")
    with col2: 
        destino_txt = st.text_input("Destino:")
        
    duracion_txt = st.text_input("Duración Estimada:")
    salida_tipo = st.radio("Salida:", ["Planificada", "Urgencia"], index=None)

    st.markdown("### 2. Parámetros de Riesgo")
    puntos_totales = 0
    
    v_distancia = st.radio("Distancia:", ["< 50km", "< 100km", "< 200km", "> 200km"], index=None)
    if v_distancia: 
        if v_distancia == "< 50km": puntos_totales += 1
        elif v_distancia == "< 100km": puntos_totales += 2
        elif v_distancia == "< 200km": puntos_totales += 5
        elif v_distancia == "> 200km": puntos_totales += 7
    
    v_clima = st.selectbox("Clima:", ["Despejado", "Nublado", "Viento", "Lluvia", "Niebla", "Nieve"], index=None)
    if v_clima: 
        if v_clima == "Despejado": puntos_totales += 0
        elif v_clima == "Nublado": puntos_totales += 1
        elif v_clima == "Viento": puntos_totales += 2
        elif v_clima == "Lluvia": puntos_totales += 4
        elif v_clima == "Niebla": puntos_totales += 8
        elif v_clima == "Nieve": puntos_totales += 9
    
    v_pasajeros = st.radio("Acompañantes:", ["Con pasajeros", "Solo conductor"], index=None)
    pasajeros_detalle = "N/A"
    if v_pasajeros == "Con pasajeros":
        pasajeros_detalle = st.text_input("👥 Nombres:")
        
    if v_pasajeros: 
        if v_pasajeros == "Con pasajeros":
            puntos_totales += 1 
        else:
            puntos_totales += 5
    
    v_camino = st.radio("Superficie:", ["Pavimento", "Mixto", "Tierra"], index=None)
    if v_camino: 
        if v_camino == "Pavimento": puntos_totales += 1
        elif v_camino == "Mixto": puntos_totales += 2
        elif v_camino == "Tierra": puntos_totales += 4
    
    v_sueno = st.radio("¿Descansó +8hs?", ["Sí", "No"], index=None)
    v_horas_servicio = st.radio("Horas Totales:", ["< 12hs", "< 14hs", "< 16hs"], index=None)
    
    if v_sueno and v_horas_servicio:
        if v_horas_servicio == "< 12hs": 
            if v_sueno == "Sí": puntos_totales += 1 
            else: puntos_totales += 2
        elif v_horas_servicio == "< 14hs": 
            if v_sueno == "Sí": puntos_totales += 3 
            else: puntos_totales += 5
        elif v_horas_servicio == "< 16hs": 
            if v_sueno == "Sí": puntos_totales += 6 
            else: puntos_totales += 8
        
    v_escolta = st.radio("¿Vehículo Escolta?", ["No", "Sí"], index=None)
    if v_escolta: 
        if v_escolta == "No": puntos_totales += 1 
        else: puntos_totales += 5
    
    v_horario = st.radio("Horario:", ["Diurno", "Nocturno"], index=None)
    if v_horario: 
        if v_horario == "Nocturno": puntos_totales += 5 
        else: puntos_totales += 1
    
    v_comunicacion = st.radio("Cobertura Señal:", ["Total", "Tramos sin señal", "Sin señal"], index=None)
    if v_comunicacion: 
        if v_comunicacion == "Total": puntos_totales += 1
        elif v_comunicacion == "Tramos sin señal": puntos_totales += 3
        elif v_comunicacion == "Sin señal": puntos_totales += 5

    # Evaluación y Auto-Aprobación
    nivel_riesgo_calculado = 1
    if puntos_totales > 15 and puntos_totales <= 30:
        nivel_riesgo_calculado = 2
    elif puntos_totales > 30:
        nivel_riesgo_calculado = 3
    
    if nivel_aprobacion_usuario >= nivel_riesgo_calculado:
        color_semaforo = "green"
        aprobacion_estado = "AUTORIZADO (Auto-Aprobado)"
    else:
        if nivel_riesgo_calculado < 3:
            color_semaforo = "orange"
        else:
            color_semaforo = "red"
        aprobacion_estado = f"PENDIENTE (Requiere Nivel {nivel_riesgo_calculado})"

    st.markdown("---")
    st.subheader("📋 Resultado")
    if color_semaforo == "green": 
        st.success(f"**{aprobacion_estado}** | Riesgo Nivel {nivel_riesgo_calculado} | {puntos_totales} pts")
    elif color_semaforo == "orange": 
        st.warning(f"**{aprobacion_estado}** | Riesgo Nivel {nivel_riesgo_calculado} | {puntos_totales} pts")
    else: 
        st.error(f"**{aprobacion_estado}** | Riesgo Nivel {nivel_riesgo_calculado} | {puntos_totales} pts")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("⬅️ Volver"): 
            st.session_state["paso_actual"] = "Inspeccion_Vehiculo"
            st.rerun()
            
    with col_btn2:
        if st.button("CONFIRMAR VIAJE"):
            campos_ok = all([
                origen_txt.strip() != "", 
                destino_txt.strip() != "", 
                duracion_txt.strip() != "", 
                vehiculo_sel != "⚠️ Cargar flota en Admin", 
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
            
            if not campos_ok: 
                st.error("⛔ Faltan datos por responder.")
            elif v_pasajeros == "Con pasajeros" and pasajeros_detalle.strip() == "": 
                st.error("⚠️ Ingrese nombres de pasajeros.")
            else:
                nuevo_id = obtener_siguiente_id()
                hora_str = datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                
                alarma_noche = "apagada"
                if v_horario == "Nocturno":
                    alarma_noche = "encendida"
                    
                aprobacion_db = "🔴 Pendiente"
                aprobador_db = "Pendiente"
                fecha_aprobacion_db = "Pendiente"
                estado_viaje_db = "En espera"
                
                if color_semaforo == "green":
                    aprobacion_db = "🟢 Aprobado"
                    aprobador_db = nombre_chofer
                    fecha_aprobacion_db = hora_str
                    estado_viaje_db = "En viaje"
                
                datos = {
                    "ID": nuevo_id, 
                    "Fecha": hora_str, 
                    "Chofer": nombre_chofer, 
                    "Sector": sector_usuario, 
                    "Cargo": rol_usuario, 
                    "Vehiculo": vehiculo_sel, 
                    "Duracion": duracion_txt, 
                    "Salida": salida_tipo, 
                    "Alarma Nocturna": alarma_noche, 
                    "Origen": origen_txt, 
                    "Destino": destino_txt, 
                    "Estado": aprobacion_estado, 
                    "Puntaje": puntos_totales, 
                    "Nivel": nivel_riesgo_calculado, 
                    "Aprobacion": aprobacion_db, 
                    "Aprobador": aprobador_db, 
                    "Fecha_Aprobacion": fecha_aprobacion_db, 
                    "Estado_Viaje": estado_viaje_db, 
                    "Fecha_Fin": "En curso", 
                    "Test_Chofer": st.session_state.get("test_chofer"), 
                    "Inspeccion_Vehiculo": st.session_state.get("inspeccion_vehiculo"), 
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
                
                if guardar_en_nube(datos):
                    st.balloons()
                    
                    if color_semaforo == "green":
                        cabecera_wa = f"💠 VIAJE AUTO-APROBADO ID {nuevo_id} 💠"
                        pie_wa = f"👉 Aprobado automáticamente por sistema."
                    else:
                        cabecera_wa = f"💠 NUEVA SOLICITUD ID {nuevo_id} 💠"
                        pie_wa = f"👉 Por favor, apruebe en la plataforma MARBAR."

                    tkt = (
                        f"{cabecera_wa}\n\n"
                        f"🔹 Chofer: {nombre_chofer}\n"
                        f"🔹 Vehículo: {vehiculo_sel}\n"
                        f"🔹 Origen: {origen_txt}\n"
                        f"🔹 Destino: {destino_txt}\n"
                        f"🔹 Duración: {duracion_txt}\n"
                        f"🔹 Riesgo: Nivel {nivel_riesgo_calculado}\n\n"
                        f"{pie_wa}"
                    )
                    
                    st.markdown(f"### [📱 ENVIAR TICKET](https://wa.me/?text={urllib.parse.quote(tkt)})")
                    st.success("Guardado Exitoso.")
                    st.session_state["paso_actual"] = "Menu"

# 5. HISTORIAL
elif st.session_state["paso_actual"] == "Historial":
    st.subheader("📜 Historial")
    viajes_historicos = db.collection("viajes").stream()
    lista_historica = []
    for doc in viajes_historicos:
        lista_historica.append(doc.to_dict())
        
    df_h = pd.DataFrame(lista_historica)
    
    if not df_h.empty:
        if st.session_state["usuario_actual"] != "ADMIN": 
            df_h = df_h[df_h["Chofer"] == st.session_state["nombre_empleado"]]
            
        if not df_h.empty:
            df_h = df_h.sort_values(by="ID", ascending=False)
            st.dataframe(df_h[['ID', 'Fecha', 'Origen', 'Destino', 'Estado_Viaje']], hide_index=True, use_container_width=True)
            
            st.markdown("---")
            st.write("#### 📥 Extraer Ticket TXT")
            
            op_dd = [""]
            for _, r in df_h.iterrows():
                op_dd.append(f"{r['ID']} - {r.get('Chofer','')} - {r.get('Fecha','')[:10]}")
                
            v_sel = st.selectbox("Seleccione viaje:", op_dd)
            
            if v_sel != "":
                id_ext = v_sel.split(" - ")[0]
                d_v = df_h[df_h["ID"].astype(str) == id_ext].iloc[0]
                
                # --- USO DE LA FUNCIÓN DE TICKET PROFESIONAL ---
                reporte_estructurado = generar_ticket_txt(d_v)
                st.download_button("📥 Descargar TXT", reporte_estructurado, f"MARBAR_Viaje_{id_ext}.txt")
                
        else:
            st.info("No hay viajes en el historial.")
            
    if st.button("⬅️ Menú"): 
        st.session_state["paso_actual"] = "Menu"
        st.rerun()

# --- 6. SIDEBAR ---
with st.sidebar:
    if os.path.exists("logo.png"): 
        st.image("logo.png", use_column_width=True)
        
    st.header("📊 SSA & Logística")
    
    if st.session_state["usuario_actual"]:
        if st.button("🚪 Cerrar Sesión"): 
            st.session_state.clear()
            st.rerun()

try:
    viajes_sidebar = db.collection("viajes").stream()
    lista_sidebar = []
    for d in viajes_sidebar:
        lista_sidebar.append(d.to_dict())
        
    df_sb = pd.DataFrame(lista_sidebar)
    
    if not df_sb.empty:
        hoy = datetime.now(TZ_AR).strftime("%d/%m/%Y")
        df_hoy = df_sb[df_sb['Fecha'].str.contains(hoy, na=False)]
        
        st.sidebar.markdown("---")
        st.sidebar.write("⚠️ **Pendientes (Hoy):**")
        df_p = df_hoy[df_hoy['Aprobacion'].str.contains("Pendiente", na=False)]
        
        if not df_p.empty:
            st.sidebar.dataframe(df_p[['Chofer', 'Destino']], hide_index=True)
        else:
            st.sidebar.write("✅ Al día.")
            
        st.sidebar.markdown("---")
        st.sidebar.write("🚚 **En Ruta:**")
        df_r = df_sb[df_sb['Estado_Viaje'] == "En viaje"]
        
        if not df_r.empty:
            st.sidebar.dataframe(df_r[['Chofer', 'Destino']], hide_index=True)
        else:
            st.sidebar.write("✅ Ninguna.")

        st.sidebar.markdown("---")
        st.sidebar.subheader("📜 TXT Rápido")
        
        df_sb_ord = df_sb.sort_values(by="ID", ascending=False)
        op_sb = [""]
        for _, r in df_sb_ord.iterrows():
            op_sb.append(f"{r['ID']} - {r.get('Chofer','')}")
            
        v_sb = st.sidebar.selectbox("Buscar ID:", op_sb, key="sb_aud")
        
        if v_sb != "":
            id_sb = v_sb.split(" - ")[0]
            d_sb = df_sb[df_sb["ID"].astype(str) == id_sb].iloc[0]
            
            # --- USO DE LA FUNCIÓN DE TICKET PROFESIONAL ---
            reporte_sb_txt = generar_ticket_txt(d_sb)
            st.sidebar.download_button("📥 Descargar Ficha", reporte_sb_txt, f"Ficha_{id_sb}.txt", key="btn_sb_txt")

        if st.session_state["usuario_actual"] == "ADMIN":
            st.sidebar.markdown("---")
            st.sidebar.subheader("📊 Consola Excel")
            
            cols = [
                'ID', 'Fecha', 'Chofer', 'Sector', 'Cargo', 'Vehiculo', 'Duracion', 
                'Salida', 'Alarma Nocturna', 'Origen', 'Destino', 'Estado', 'Puntaje', 
                'Nivel', 'Aprobacion', 'Aprobador', 'Fecha_Aprobacion', 'Estado_Viaje', 'Fecha_Fin'
            ]
            
            for c in cols: 
                if c not in df_sb.columns: 
                    df_sb[c] = "N/A"
                    
            df_ex = df_sb[cols].sort_values(by="ID", ascending=False)
            
            bx = io.BytesIO()
            with pd.ExcelWriter(bx, engine='openpyxl') as wr: 
                df_ex.to_excel(wr, index=False)
                
            st.sidebar.download_button("📥 Auditoría (Excel)", bx.getvalue(), f"Auditoria_MARBAR_{hoy.replace('/','-')}.xlsx", key="btn_ex")
            
except Exception as e_sidebar: 
    pass

# --- 7. BANDEJA APROBACIONES ---
if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia"]:
    st.markdown("---")
    st.title("📥 Bandeja de Validaciones")
    
    try:
        solicitudes_pendientes = db.collection("viajes").where("Aprobacion", "==", "🔴 Pendiente").stream()
        p_list = []
        for doc in solicitudes_pendientes:
            p_list.append(doc.to_dict())
            
        if p_list:
            for v_p in p_list:
                with st.expander(f"🚨 ID: {v_p['ID']} | Conductor: {v_p['Chofer']}"):
                    st.write(f"**Ruta:** {v_p['Origen']} -> {v_p['Destino']} ({v_p['Puntaje']} pts)")
                    if st.button(f"✍️ Aprobar {v_p['ID']}", key=f"btn_ap_{v_p['ID']}"):
                        db.collection("viajes").document(str(v_p['ID'])).update({
                            "Aprobacion": "🟢 Aprobado", 
                            "Aprobador": st.session_state["nombre_empleado"], 
                            "Fecha_Aprobacion": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S"), 
                            "Estado_Viaje": "En viaje"
                        })
                        st.rerun()
        else: 
            st.info("✅ Bandeja limpia.")
            
    except Exception as e_bandeja: 
        pass

# --- 8. ADMIN ---
if st.session_state["usuario_actual"] == "ADMIN":
    st.markdown("---")
    st.title("⚙️ Consola Admin")
    t1, t2 = st.tabs(["👥 Usuarios", "🚘 Flota"])
    
    with t1:
        adm_email = st.text_input("Correo Electrónico:").strip()
        adm_password = st.text_input("Contraseña:", type="password").strip()
        st.caption("🔴 Firebase exige mínimo 6 caracteres para crear contraseñas.")
        adm_nombre = st.text_input("Nombre y Apellido Real:").strip()
        adm_dni = st.text_input("DNI:").strip()
        adm_sector = st.selectbox("Sector:", ["Higiene y Seguridad", "Logistica", "Fluidos", "Control de solidos", "Mantenimiento", "Gerencia"])
        adm_rol = st.selectbox("Rol:", ["Chofer", "Supervisor / Coordinador", "Jefe de Servicio", "Gerencia", "ADMIN"])
        
        if st.button("💾 Crear Usuario"):
            if adm_email != "" and adm_password != "" and adm_nombre != "" and adm_dni != "":
                if len(adm_password) < 6:
                    st.error("⚠️ La contraseña debe tener al menos 6 caracteres.")
                else:
                    try:
                        auth.create_user(email=adm_email, password=adm_password)
                        db.collection("usuarios").document(adm_dni).set({
                            "DNI_Usuario": adm_dni, 
                            "Nombre": adm_nombre, 
                            "Email": adm_email, 
                            "Rol": adm_rol, 
                            "Sector": adm_sector
                        })
                        st.success("Usuario creado con éxito.")
                        st.rerun()
                    except Exception as e: 
                        st.error(f"Error de Firebase: {e}")
            else: 
                st.error("Complete todos los campos de texto.")
                
        df_u = obtener_usuarios()
        if not df_u.empty:
            st.dataframe(df_u, hide_index=True)
            
            lista_borrar_u = [""]
            for dni in df_u["DNI_Usuario"].tolist():
                lista_borrar_u.append(dni)
                
            elim_u = st.selectbox("Borrar Perfil (DNI):", lista_borrar_u)
            
            if st.button("❌ Dar de Baja"): 
                if elim_u.strip() != "": 
                    db.collection("usuarios").document(elim_u.strip()).delete()
                    st.rerun()

    with t2:
        adm_pat = st.text_input("Patente:").strip()
        
        if st.button("💾 Agregar Equipo"):
            if adm_pat != "": 
                db.collection("vehiculos").document(adm_pat).set({"Vehiculo": adm_pat})
                st.rerun()
                
        df_v = obtener_vehiculos()
        if not df_v.empty:
            st.dataframe(df_v, hide_index=True)
            
            lista_borrar_v = [""]
            for vh in df_v["Vehiculo"].tolist():
                lista_borrar_v.append(vh)
                
            elim_v = st.selectbox("Borrar Equipo:", lista_borrar_v)
            
            if st.button("❌ Retirar Unidad"): 
                if elim_v.strip() != "": 
                    db.collection("vehiculos").document(elim_v.strip()).delete()
                    st.rerun()