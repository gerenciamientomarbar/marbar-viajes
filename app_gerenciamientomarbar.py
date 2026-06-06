import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import json
import urllib.parse
from PIL import Image
import os
import io
import streamlit.components.v1 as components
import random
import string
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

# --- NUEVAS LIBRERÍAS PARA AUTH0 ---
import requests
import jwt

# -----------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -----------------------------------------
st.set_page_config(
    layout="wide", 
    page_title="MARBAR - Gestión de Viajes",
    page_icon="🚛"
)

# -----------------------------------------
# VARIABLES GLOBALES Y FIREBASE
# -----------------------------------------
import firebase_admin
from firebase_admin import credentials, firestore, auth

# --- CONFIGURACIÓN DE LA BASE DE DATOS CENTRAL ---
COLECCION_VIAJES = "viajes"

# --- CONFIGURACIÓN DE ZONA HORARIA (ARGENTINA UTC-3) ---
TZ_AR = timezone(timedelta(hours=-3))

# --- DISEÑO CORPORATIVO (CSS) ---
primary_color = "#1E3A8A"
text_color = "#1F2937"  

st.markdown(f"""
<style>
    /* Ocultar elementos por defecto de Streamlit para un look corporativo */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    
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
        firebase_secrets = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(firebase_secrets)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Error crítico al conectar con la llave secreta: {e}")

db = firestore.client()

# --- FUNCIONES DE COMUNICACIÓN Y FORMATO ---
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
        viajes_ref = db.collection(COLECCION_VIAJES).order_by("ID", direction=firestore.Query.DESCENDING).limit(1).get()
        if viajes_ref:
            return viajes_ref[0].to_dict().get("ID", 0) + 1
        else:
            return 1
    except Exception:
        return 1

def guardar_en_nube(datos_viaje):
    try:
        db.collection(COLECCION_VIAJES).document(str(datos_viaje["ID"])).set(datos_viaje)
        return True
    except Exception:
        return False

def calcular_duracion_real(fecha_inicio, fecha_fin):
    """Calcula la diferencia exacta de tiempo entre la salida y la llegada"""
    if fecha_fin in ["En curso", "Pendiente", "N/A", "", None]:
        return "No finalizado"
    
    try:
        formato = "%d/%m/%Y %H:%M:%S"
        inicio = datetime.strptime(fecha_inicio, formato)
        fin = datetime.strptime(fecha_fin, formato)
        diferencia = fin - inicio
        segundos = int(diferencia.total_seconds())
        
        if segundos < 0:
            return "Error de fechas"
            
        horas, resto = divmod(segundos, 3600)
        minutos, _ = divmod(resto, 60)
        return f"{horas:02d}:{minutos:02d} Hs"
    except Exception:
        return "Error de cálculo"

def generar_ficha_html(v_data):
    """Genera la ficha corporativa de auditoría en formato HTML para impresión/PDF"""
    
    # Función para ordenar numéricamente los items
    def ordenar_por_numero(texto):
        try: return int(texto.split(".")[0])
        except: return 99
    
    # Procesamiento del Equipamiento
    eq_html = ""
    chk_eq = v_data.get('Checklist_Eq', {})
    if chk_eq:
        for k in sorted(chk_eq.keys(), key=ordenar_por_numero):
            v = chk_eq[k]
            color = "#16a34a" if v == "Sí" else ("#dc2626" if v == "No" else "#64748b")
            eq_html += f'<tr><td style="padding: 4px; border-bottom: 1px solid #f1f5f9; font-size: 9pt;">{k}</td><td style="text-align: right; font-weight: bold; width: 15%; color: {color};">{str(v).upper()}</td></tr>'
    else: eq_html = "<tr><td colspan='2'>Sin datos</td></tr>"

    # Procesamiento de Documentación
    doc_html = ""
    chk_doc = v_data.get('Checklist_Doc', {})
    if chk_doc:
        for k in sorted(chk_doc.keys(), key=ordenar_por_numero):
            v = chk_doc[k]
            color = "#16a34a" if v == "Sí" else ("#dc2626" if v == "No" else "#64748b")
            doc_html += f'<tr><td style="padding: 4px; border-bottom: 1px solid #f1f5f9; font-size: 9pt;">{k}</td><td style="text-align: right; font-weight: bold; width: 15%; color: {color};">{str(v).upper()}</td></tr>'
    else: doc_html = "<tr><td colspan='2'>Sin datos</td></tr>"

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Ficha MARBAR ID {v_data.get('ID')}</title>
        <style>
            @media print {{
                @page {{ margin: 15mm; }}
                body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            }}
            body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #1e293b; max-width: 800px; margin: 0 auto; padding: 20px; }}
            h2 {{ color: #1e3a8a; font-size: 12pt; background-color: #f1f5f9; padding: 6px 10px; border-left: 4px solid #e65100; margin-top: 15px; }}
            .tbl {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
            .tbl th, .tbl td {{ padding: 6px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
            .tbl th {{ background-color: #f8fafc; width: 30%; }}
            .badge {{ background-color: #fff7ed; border: 1px solid #ffedd5; padding: 10px; text-align: center; border-radius: 5px; margin-top: 15px; }}
            .ddjj {{ font-size: 8pt; color: #64748b; border: 1px dashed #cbd5e1; padding: 10px; background-color: #fafafa; margin-top: 20px; text-align: justify; }}
        </style>
    </head>
    <body onload="window.print()">
        <table style="width: 100%; border-bottom: 3px solid #1e3a8a; margin-bottom: 15px;">
            <tr>
                <td><strong style="color: #1e3a8a; font-size: 16pt;">MARBAR SA</strong><br><span style="color: #475569; font-size: 9pt;">Auditoría de Gerenciamiento de Viaje</span></td>
                <td style="text-align: right;"><strong style="color: #e65100; font-size: 12pt;">ID #{v_data.get('ID')}</strong><br><span style="color: #475569; font-size: 9pt;">Estado: <b>{str(v_data.get('Estado_Viaje')).upper()}</b></span></td>
            </tr>
        </table>

        <h2>1. PERSONAL Y UNIDAD</h2>
        <table class="tbl">
            <tr><th>Conductor</th><td>{v_data.get('Chofer')}</td><th>Unidad</th><td>{v_data.get('Vehiculo')}</td></tr>
            <tr><th>Sector/Cargo</th><td>{v_data.get('Sector')} / {v_data.get('Cargo')}</td><th>Regional</th><td>{v_data.get('Regional')}</td></tr>
        </table>

        <h2>2. RUTA Y TIEMPOS</h2>
        <table class="tbl">
            <tr><th>Origen</th><td>{v_data.get('Origen')}</td><th>Destino</th><td>{v_data.get('Destino')}</td></tr>
            <tr><th>Duración Est.</th><td>{v_data.get('Duracion')}</td><th>Fecha Cierre</th><td>{v_data.get('Fecha_Fin', 'En curso')}</td></tr>
        </table>

        <h2>3. ANÁLISIS DE RIESGOS</h2>
        <table class="tbl">
            <tr><th>Distancia</th><td>{v_data.get('R_Distancia')}</td><th>Clima</th><td>{v_data.get('R_Clima')}</td></tr>
            <tr><th>Pasajeros</th><td>{v_data.get('R_Pasajeros')} ({v_data.get('Detalle_Pasajeros', 'N/A')})</td><th>Camino</th><td>{v_data.get('R_Camino')}</td></tr>
            <tr><th>Sueño +8hs</th><td>{v_data.get('R_Sueno')}</td><th>Horas Servicio</th><td>{v_data.get('R_Horas')}</td></tr>
        </table>

        <h2>4. CHECKLIST TÉCNICO</h2>
        <table style="width: 100%;" class="tbl">
            <tr>
                <td style="width: 50%; vertical-align: top;">
                    <strong style="color: #1e3a8a; font-size: 9pt;">A. Equipamiento</strong>
                    <table style="width: 100%; border-collapse: collapse;">{eq_html}</table>
                </td>
                <td style="width: 50%; vertical-align: top;">
                    <strong style="color: #1e3a8a; font-size: 9pt;">B. Documentación</strong>
                    <table style="width: 100%; border-collapse: collapse;">{doc_html}</table>
                </td>
            </tr>
        </table>

        <div class="badge">
            <strong style="color: #c2410c; font-size: 11pt;">EVALUACIÓN: NIVEL {v_data.get('Nivel')} ({v_data.get('Puntaje')} PTS)</strong><br>
            <span style="font-size: 9pt;">Aprobado por: <b>{v_data.get('Aprobador')}</b> ({v_data.get('Fecha_Aprobacion')})</span>
        </div>

        <div class="ddjj">
            <b>CERTIFICACIÓN LEGAL:</b> Los datos aquí expuestos poseen carácter de Declaración Jurada, registrados por el operador y convalidados por la supervisión de MARBAR SA.
        </div>
    </body>
    </html>
    """
    return html

# --- GESTOR DE SESIÓN ---
if "usuario_actual" not in st.session_state: 
    st.session_state["usuario_actual"] = None
    
if "paso_actual" not in st.session_state: 
    st.session_state["paso_actual"] = "Menu"

# -----------------------------------------
# SISTEMA DE LOGIN CORPORATIVO (AUTH0)
# -----------------------------------------

try:
    AUTH0_DOMAIN = st.secrets["auth0"]["domain"]
    CLIENT_ID = st.secrets["auth0"]["client_id"]
    CLIENT_SECRET = st.secrets["auth0"]["client_secret"]
except KeyError as e:
    st.error(f"Falta configurar las credenciales de Auth0: {e}")
    st.stop()

# IMPORTANTE: URL de redirección oficial.
# Detección automática del entorno (Local vs Nube)
if "localhost" in st.query_params.get("host", "localhost") or "127.0.0.1" in st.query_params.get("host", "127.0.0.1"):
    REDIRECT_URI = "http://localhost:8501/"
else:
    REDIRECT_URI = "https://gerenciamientomarbar-marbar-via-app-gerenciamientomarbar-4ol9rm.streamlit.app/"

AUTHORIZE_URL = "https://" + AUTH0_DOMAIN + "/authorize"
TOKEN_URL = "https://" + AUTH0_DOMAIN + "/oauth/token"
USERINFO_URL = "https://" + AUTH0_DOMAIN + "/userinfo"

if st.session_state["usuario_actual"] is None:
    
    query_params = st.query_params
    
    if "code" not in query_params:
        col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
        with col_logo2:
            if os.path.exists("logo.png"): 
                st.image("logo.png", use_column_width=True)
            else: 
                st.warning("⚠️ Falta 'logo.png'")
        
        st.title("🔒 Acceso Seguro - MARBAR SA")
        st.info("El acceso a esta plataforma está restringido a personal autorizado. Ingrese mediante el portal corporativo de identidad.")
        
        # Generamos la URL de autorización nativa
        uri = f"{AUTHORIZE_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={urllib.parse.quote(REDIRECT_URI)}&scope=openid%20profile%20email"
        
        st.link_button("🔑 INICIAR SESIÓN CORPORATIVA", uri, use_container_width=True)
        st.stop() 
        
    else:
        code = query_params["code"]
        
        try:
            # 1. Pedimos el Token de acceso a Auth0 de manera directa
            payload = {
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI
            }
            token_response = requests.post(TOKEN_URL, json=payload)
            token_data = token_response.json()
            
            # 2. Con ese Token, consultamos la identidad del operador
            access_token = token_data.get("access_token")
            headers = {'Authorization': f'Bearer {access_token}'}
            userinfo_response = requests.get(USERINFO_URL, headers=headers)
            user_info = userinfo_response.json()
            
            correo_auth0 = user_info.get("email", "").lower()
            
            # --- COTEJO CON LA BASE DE DATOS DE LA EMPRESA (FIREBASE) ---
            usuarios_ref = db.collection("usuarios").where("Email", "==", correo_auth0).stream()
            usuario_encontrado = None
            for u in usuarios_ref:
                usuario_encontrado = u.to_dict()
                break
            
            if usuario_encontrado:
                st.session_state.update({
                    "usuario_actual": usuario_encontrado.get("Rol", "Chofer"), 
                    "nombre_empleado": usuario_encontrado.get("Nombre", "Empleado MARBAR"), 
                    "sector_empleado": usuario_encontrado.get("Sector", "Sin Sector"), 
                    "regional_empleado": usuario_encontrado.get("Regional", "No asignada"),
                    "email_empleado": correo_auth0,
                    "paso_actual": "Menu"
                })
                
                st.query_params.clear()
                st.rerun()
                
            elif correo_auth0 == "admin@marbar.com":
                st.session_state.update({
                    "usuario_actual": "ADMIN", 
                    "nombre_empleado": "Administrador", 
                    "sector_empleado": "Gerencia", 
                    "regional_empleado": "Sede Central",
                    "email_empleado": correo_auth0,
                    "paso_actual": "Menu"
                })
                st.query_params.clear()
                st.rerun()
                
            else:
                st.error(f"⛔ El correo **{correo_auth0}** es válido, pero no tiene un perfil operativo asignado en el Sistema de Viajes. Solicite el alta a la supervisión.")
                if st.button("⬅️ Volver al Inicio"):
                    st.query_params.clear()
                    st.rerun()
                st.stop()
                
        except Exception as e:
            st.error(f"Ocurrió un error en la validación corporativa: {e}")
            if st.button("Intentar de nuevo"):
                st.query_params.clear()
                st.rerun()
            st.stop()

# --- WORKFLOW PRINCIPAL ---

# 1. MENÚ PRINCIPAL
if st.session_state["paso_actual"] == "Menu":
    st.subheader(f"Panel Operativo - Bienvenido, {st.session_state['nombre_empleado']}")
    
    # --- AVISO WHATSAPP DE LLEGADA A DESTINO ---
    if "alerta_llegada" in st.session_state:
        v_llegada = st.session_state["alerta_llegada"]
        msg_llegada_wa = f"✅ *AVISO DE LLEGADA MARBAR*\n\n🔹 *Conductor:* {st.session_state['nombre_empleado']}\n🔹 *Viaje ID:* {v_llegada['id']}\n🔹 *Destino:* {v_llegada['destino']}\n\n👉 *Llegué bien a destino sin novedades.*"
        link_llegada_wa = f"https://wa.me/?text={urllib.parse.quote(msg_llegada_wa)}"
        
        st.success("El viaje se cerró correctamente en el sistema operativo.")
        st.markdown(f"### [📱 ENVIAR AVISO DE LLEGADA POR WHATSAPP]({link_llegada_wa})")
        
        if st.button("Ocultar Aviso", key="ocultar_llegada"):
            del st.session_state["alerta_llegada"]
            st.rerun()
        st.markdown("---")
        
    # --- AVISO WHATSAPP DE CANCELACIÓN DE VIAJE ---
    if "alerta_cancelacion" in st.session_state:
        v_canc = st.session_state["alerta_cancelacion"]
        msg_canc_wa = f"❌ *VIAJE CANCELADO - MARBAR*\n\n🔹 *Conductor:* {st.session_state['nombre_empleado']}\n🔹 *Viaje ID:* {v_canc['id']}\n🔹 *Destino:* {v_canc['destino']}\n\n👉 *El viaje ha sido suspendido y cerrado en el sistema.*"
        link_canc_wa = f"https://wa.me/?text={urllib.parse.quote(msg_canc_wa)}"
        
        st.warning("El viaje fue cancelado y retirado de la ruta activa.")
        st.markdown(f"### [📱 ENVIAR AVISO DE CANCELACIÓN POR WHATSAPP]({link_canc_wa})")
        
        if st.button("Ocultar Aviso", key="ocultar_canc"):
            del st.session_state["alerta_cancelacion"]
            st.rerun()
        st.markdown("---")
    
    if st.session_state["usuario_actual"] != "ADMIN":
        viajes_activos = db.collection(COLECCION_VIAJES).where("Chofer", "==", st.session_state["nombre_empleado"]).where("Estado_Viaje", "in", ["En viaje", "En espera"]).stream()
        lista_activos = []
        for d in viajes_activos:
            lista_activos.append(d.to_dict())
            
        if lista_activos:
            st.info("📍 Estado de su viaje actual:")
            for v in lista_activos:
                with st.container(border=True): # <-- IMPLEMENTACIÓN DE TARJETAS VISUALES
                    estado_aprobacion = v.get("Aprobacion", "🔴 Pendiente")
                    
                    if "Aprobado" in estado_aprobacion:
                        st.success(f"🚀 **VIAJE AUTORIZADO (ID {v['ID']})**\n\nEl supervisor ya firmó digitalmente. Está habilitado para iniciar la marcha hacia **{v['Destino']}** de forma segura.")
                    else:
                        st.warning(f"⏳ **ESPERANDO APROBACIÓN (ID {v['ID']})**\n\nSu solicitud de viaje hacia **{v['Destino']}** requiere validación de la supervisión. **No mueva la unidad hasta recibir la autorización en este panel.**")
                    
                    col_info, col_accion, col_canc = st.columns([1, 1, 1])
                    col_info.write(f"**Gestión ID {v['ID']}**")
                    
                    if col_accion.button(f"🏁 Llegar", key=f"menu_fin_{v['ID']}"):
                        db.collection(COLECCION_VIAJES).document(str(v['ID'])).update({
                            "Estado_Viaje": "Finalizado", 
                            "Fecha_Fin": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                        })
                        st.session_state["alerta_llegada"] = {"id": v['ID'], "destino": v['Destino']}
                        st.rerun()
                        
                    if col_canc.button(f"❌ Cancelar", key=f"menu_canc_{v['ID']}"):
                        db.collection(COLECCION_VIAJES).document(str(v['ID'])).update({
                            "Estado_Viaje": "Cancelado", 
                            "Fecha_Fin": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                        })
                        st.session_state["alerta_cancelacion"] = {"id": v['ID'], "destino": v['Destino']}
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
    st.warning("⚖️ **DECLARACIÓN JURADA:** La información ingresada en este gerenciamiento reviste carácter de Declaración Jurada. Cualquier omisión o falsedad sobre su estado o el del vehículo constituye una falta grave a las normativas de seguridad (SSA).")
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
    st.warning("⚖️ **DECLARACIÓN JURADA:** La información ingresada en este gerenciamiento reviste carácter de Declaración Jurada. Cualquier omisión o falsedad sobre su estado o el del vehículo constituye una falta grave a las normativas de seguridad (SSA).")
    st.subheader("🚘 Paso 2: Condiciones del Vehículo")
    
    st.markdown("#### A. Equipamiento y Estado Técnico")
    eq_items = [
        "1. Frenos de Servicio en Correcto Funcionamiento",
        "2. Freno de Estacionamiento en Correcto Funcionamiento",
        "3. Neumáticos en buen estado (mín. 1,6mm, sin daños ni deformaciones)",
        "4. Sistema de Dirección y Suspensión íntegro libre de pérdidas de fluidos",
        "5. Tablero de instrumentos libre de indicadores (luces prendidas)",
        "6. Cinturones de Seguridad Funcional en todas las plazas",
        "7. Apoyacabeza en todas las plazas de la unidad",
        "8. Extintor Vigente, precintado y asegurado correctamente",
        "9. Balizas Portátiles/Triángulos Reflectivos",
        "10. Kit de Herramientas para cambio de neumáticos",
        "11. Rueda de Auxilio Operativa",
        "12. Airbag Operativo (Verificar ausencia de testigo en tablero)",
        "13. Sist. ABS Operativo (Verificar ausencia de testigo en tablero)",
        "14. Microtrack Operativo",
        "15. Kit Invernal",
        "16. ¿Los objetos en la caja de carga o en el habitáculo se encuentran asegurados?",
        "17. ¿Las luces en general del vehículo se encuentran en condiciones?",
        "18. ¿El estado de los cristales del vehículo es correcto?"
    ]
    respuestas_eq = {}
    for item in eq_items:
        respuestas_eq[item] = st.radio(item, ["Sí", "No", "N/A"], index=None, horizontal=True)
        
    st.markdown("---")
    st.markdown("#### B. Documentación Obligatoria")
    doc_items = [
        "1. Licencia de conducir vigente y acorde al vehículo",
        "2. Cédula Verde/Azul",
        "3. RTO Libre de observaciones",
        "4. Seguro del Vehículo",
        "5. Curso conducción Defensiva Chofer"
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
                    st.error("⛔ Elementos marcados con 'No'. Prohibido el viaje.")
                else:
                    st.session_state["inspeccion_vehiculo"] = "Aprobada"
                    st.session_state["resp_eq"] = respuestas_eq
                    st.session_state["resp_doc"] = respuestas_doc
                    st.session_state["paso_actual"] = "Formulario_Viaje"
                    st.rerun()

# 4. FORMULARIO Y RIESGO
elif st.session_state["paso_actual"] == "Formulario_Viaje":
    st.warning("⚖️ **DECLARACIÓN JURADA:** La información ingresada en este gerenciamiento reviste carácter de Declaración Jurada. Cualquier omisión o falsedad sobre su estado o el del vehículo constituye una falta grave a las normativas de seguridad (SSA).")
    st.subheader("🛡️ Paso 3: Análisis de Riesgo")
    
    sector_usuario = st.session_state["sector_empleado"]
    rol_usuario = st.session_state["usuario_actual"]
    nombre_chofer = st.session_state["nombre_empleado"]
    regional_usuario = st.session_state.get("regional_empleado", "No asignada")
    
    mapa_autoridad = {
        "Chofer": 0, 
        "Supervisor / Coordinador / Ingeniero": 1, 
        "Jefe de Servicio": 2, 
        "Gerencia": 3, 
        "ADMIN": 3
    }
    nivel_aprobacion_usuario = mapa_autoridad.get(rol_usuario, 0)
    
    st.markdown("### 1. Datos Generales")
    st.info(f"👤 **Conductor:** {nombre_chofer} | **Regional:** {regional_usuario} | **Sector:** {sector_usuario}")

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
        
    st.write("Duración Estimada del Trayecto:")
    col_dur_h, col_dur_m = st.columns(2)
    
    with col_dur_h:
        dur_horas = st.number_input("Horas (HH):", min_value=0, max_value=72, value=None, step=1)
    with col_dur_m:
        dur_minutos = st.number_input("Minutos (MM):", min_value=0, max_value=59, value=None, step=1)
    
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
            
            duracion_valida = False
            if dur_horas is not None and dur_minutos is not None:
                if dur_horas > 0 or dur_minutos > 0:
                    duracion_valida = True
            
            campos_ok = all([
                origen_txt.strip() != "", 
                destino_txt.strip() != "", 
                duracion_valida,
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
                st.error("⛔ Faltan datos por responder o la duración de viaje no fue completada.")
            elif v_pasajeros == "Con pasajeros" and pasajeros_detalle.strip() == "": 
                st.error("⚠️ Ingrese nombres de pasajeros.")
            else:
                duracion_final_txt = f"{int(dur_horas):02d}:{int(dur_minutos):02d} Hs"
                
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
                    "Regional": regional_usuario,
                    "Fecha": hora_str, 
                    "Chofer": nombre_chofer, 
                    "Sector": sector_usuario, 
                    "Cargo": rol_usuario, 
                    "Vehiculo": vehiculo_sel, 
                    "Duracion": duracion_final_txt, 
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
                        cabecera_wa = f"🟢 *VIAJE AUTO-APROBADO ID {nuevo_id}*"
                        pie_wa = f"👉 *Aprobado automáticamente por sistema.*"
                    else:
                        cabecera_wa = f"🔴 *NUEVA SOLICITUD ID {nuevo_id}*"
                        pie_wa = f"👉 *Por favor, apruebe en la plataforma MARBAR.*"

                    tkt = (
                        f"{cabecera_wa}\n\n"
                        f"🔹 *Chofer:* {nombre_chofer}\n"
                        f"🔹 *Vehículo:* {vehiculo_sel}\n"
                        f"🔹 *Origen:* {origen_txt}\n"
                        f"🔹 *Destino:* {destino_txt}\n"
                        f"🔹 *Duración:* {duracion_final_txt}\n"
                        f"🔹 *Riesgo:* Nivel {nivel_riesgo_calculado}\n\n"
                        f"{pie_wa}"
                    )
                    
                    st.markdown(f"### [📱 ENVIAR TICKET](https://wa.me/?text={urllib.parse.quote(tkt)})")
                    st.success("Guardado Exitoso.")
                    st.session_state["paso_actual"] = "Menu"

# 5. HISTORIAL
elif st.session_state["paso_actual"] == "Historial":
    st.subheader("📜 Historial")
    viajes_historicos = db.collection(COLECCION_VIAJES).stream()
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
            st.write("#### 📥 Extraer Ficha Auditada (PDF/HTML)")
            
            op_dd = [""]
            for _, r in df_h.iterrows():
                op_dd.append(f"{r['ID']} - {r.get('Chofer','')} - {r.get('Fecha','')[:10]}")
                
            v_sel = st.selectbox("Seleccione viaje:", op_dd)
            
            if v_sel != "":
                id_ext = v_sel.split(" - ")[0]
                d_v = df_h[df_h["ID"].astype(str) == id_ext].iloc[0]
                
                reporte_html = generar_ficha_html(d_v)
                st.download_button("📥 Descargar Ficha PDF", reporte_html, f"MARBAR_Auditoria_{id_ext}.html", mime="text/html")
                
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
        
        # --- BOTÓN DE ACTUALIZACIÓN (NO PIERDE LA SESIÓN) ---
        if st.button("🔄 Actualizar Pantalla", use_container_width=True):
            st.rerun()
            
        if st.button("🚪 Cerrar Sesión", use_container_width=True): 
            st.session_state.clear()
            st.query_params.clear()
            # Ordenamos a Auth0 destruir la sesión global y regresar a la app
            url_salida_auth0 = f"https://{AUTH0_DOMAIN}/v2/logout?client_id={CLIENT_ID}&returnTo={urllib.parse.quote(REDIRECT_URI)}"
            st.markdown(f'<meta http-equiv="refresh" content="0; url={url_salida_auth0}">', unsafe_allow_html=True)

try:
    viajes_sidebar = db.collection(COLECCION_VIAJES).stream()
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
        st.sidebar.subheader("📜 Ficha Rápida")
        
        df_sb_ord = df_sb.sort_values(by="ID", ascending=False)
        op_sb = [""]
        for _, r in df_sb_ord.iterrows():
            op_sb.append(f"{r['ID']} - {r.get('Chofer','')}")
            
        v_sb = st.sidebar.selectbox("Buscar ID:", op_sb, key="sb_aud")
        
        if v_sb != "":
            id_sb = v_sb.split(" - ")[0]
            d_sb = df_sb[df_sb["ID"].astype(str) == id_sb].iloc[0]
            
            reporte_sb_html = generar_ficha_html(d_sb)
            st.sidebar.download_button(
                label="📥 Descargar Ficha PDF", 
                data=reporte_sb_html, 
                file_name=f"MARBAR_Auditoria_{id_sb}.html", 
                mime="text/html",
                key="btn_sb_txt"
            )

        if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador / Ingeniero", "Jefe de Servicio", "Gerencia"]:
            st.sidebar.markdown("---")
            st.sidebar.subheader("📊 Consola Excel")
            
            cols = [
                'ID', 'Regional', 'Fecha', 'Chofer', 'Sector', 'Cargo', 'Vehiculo', 'Duracion', 
                'Salida', 'Alarma Nocturna', 'Origen', 'Destino', 'Estado', 'Puntaje', 
                'Nivel', 'Aprobacion', 'Aprobador', 'Fecha_Aprobacion', 'Estado_Viaje', 'Fecha_Fin'
            ]
            
            for c in cols: 
                if c not in df_sb.columns: 
                    df_sb[c] = "N/A"
                    
            df_ex = df_sb[cols].sort_values(by="ID", ascending=False).copy()
            
            # --- CÁLCULO DE DURACIÓN REAL EN EXCEL ---
            df_ex['Duracion_Real_Viaje'] = df_ex.apply(lambda r: calcular_duracion_real(r.get('Fecha', ''), r.get('Fecha_Fin', '')), axis=1)
            
            # --- IMPLEMENTACIÓN DE MÉTRICAS EN LA CONSOLA ADMIN (Solo si es ADMIN para no recargar otras vistas) ---
            if st.session_state["usuario_actual"] == "ADMIN":
                st.sidebar.markdown("---")
                st.sidebar.subheader("📈 Resumen de Operaciones")
                col_met1, col_met2 = st.sidebar.columns(2)
                col_met1.metric("Viajes Hoy", str(len(df_hoy)), delta=f"{len(df_p)} pendientes" if not df_p.empty else "Al día", delta_color="inverse" if not df_p.empty else "normal")
                col_met2.metric("En Ruta", str(len(df_r)))
            
            # --- CREACIÓN DEL EXCEL EN FORMATO TABLA (CON DISEÑO OPENPYXL) ---
            bx = io.BytesIO()
            with pd.ExcelWriter(bx, engine='openpyxl') as wr: 
                df_ex.to_excel(wr, index=False, sheet_name='Auditoria_Viajes')
                worksheet = wr.sheets['Auditoria_Viajes']
                
                filas = worksheet.max_row
                columnas = worksheet.max_column
                
                if filas > 1:
                    letra_final = get_column_letter(columnas)
                    rango_tabla = f"A1:{letra_final}{filas}"
                    
                    tabla = Table(displayName="TablaAuditoria", ref=rango_tabla)
                    estilo = TableStyleInfo(
                        name="TableStyleMedium9", 
                        showFirstColumn=False, 
                        showLastColumn=False, 
                        showRowStripes=True, 
                        showColumnStripes=False
                    )
                    tabla.tableStyleInfo = estilo
                    worksheet.add_table(tabla)
                
            st.sidebar.download_button("📥 Auditoría (Excel)", bx.getvalue(), f"Auditoria_MARBAR_{hoy.replace('/','-')}.xlsx", key="btn_ex")
            
except Exception as e_sidebar: 
    pass

# --- 7. BANDEJA APROBACIONES ---
if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador / Ingeniero", "Jefe de Servicio", "Gerencia"]:
    st.markdown("---")
    st.title("📥 Bandeja de Validaciones")
    
    try:
        solicitudes_pendientes = db.collection(COLECCION_VIAJES).where("Aprobacion", "==", "🔴 Pendiente").stream()
        p_list = []
        for doc in solicitudes_pendientes:
            p_list.append(doc.to_dict())
            
        if p_list:
            for v_p in p_list:
                with st.expander(f"🚨 ID: {v_p['ID']} | Conductor: {v_p['Chofer']}"):
                    st.write(f"**Ruta:** {v_p['Origen']} -> {v_p['Destino']} ({v_p['Puntaje']} pts)")
                    if st.button(f"✍️ Aprobar {v_p['ID']}", key=f"btn_ap_{v_p['ID']}"):
                        db.collection(COLECCION_VIAJES).document(str(v_p['ID'])).update({
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
        st.info("💡 En este panel puedes gestionar los perfiles de los usuarios en Firebase. Recuerda que la contraseña ya no se usa aquí, sino que se gestiona mediante Auth0.")
        adm_email = st.text_input("Correo Electrónico Oficial:").strip().lower()
        adm_nombre = st.text_input("Nombre y Apellido Real:").strip()
        adm_dni = st.text_input("DNI:").strip()
        adm_regional = st.text_input("Regional a la que pertenece (Ej: Neuquén, Río Negro):").strip()
        adm_sector = st.selectbox("Sector:", ["Higiene y Seguridad", "Logistica", "Fluidos", "Control de solidos", "Mantenimiento", "Gerencia", "Completacion"])
        adm_rol = st.selectbox("Rol:", ["Chofer", "Supervisor / Coordinador / Ingeniero", "Jefe de Servicio", "Gerencia", "ADMIN"])
        
        if st.button("💾 Asignar Perfil Operativo"):
            if adm_email != "" and adm_nombre != "" and adm_dni != "" and adm_regional != "":
                
                try:
                    db.collection("usuarios").document(adm_dni).set({
                        "DNI_Usuario": adm_dni, 
                        "Nombre": adm_nombre, 
                        "Email": adm_email, 
                        "Regional": adm_regional,
                        "Rol": adm_rol, 
                        "Sector": adm_sector
                    })
                    
                    st.success(f"✅ ¡Perfil asignado con éxito! Ahora el usuario podrá ingresar a la aplicación usando su cuenta corporativa Auth0 ({adm_email}).")
                    st.rerun()
                except Exception as e: 
                    st.error(f"Error de Firebase: {e}")
            else: 
                st.error("Complete todos los campos de texto, incluyendo la Regional.")
                
        df_u = obtener_usuarios()
        if not df_u.empty:
            st.dataframe(df_u, hide_index=True)
            
            # --- FILTRO DE SEGURIDAD: PROTEGER AL ADMIN DE SER ELIMINADO ---
            lista_borrar_u = [""]
            for index, row in df_u.iterrows():
                if row.get("Rol") != "ADMIN" and row.get("Email") != "admin@marbar.com":
                    lista_borrar_u.append(row["DNI_Usuario"])
                
            elim_u = st.selectbox("Borrar Perfil Operativo (DNI):", lista_borrar_u)
            
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