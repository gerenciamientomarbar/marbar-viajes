import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import json
import urllib.parse
import os
import io
import streamlit.components.v1 as components
import random
import string
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
import requests

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
    footer {{visibility: hidden;}}
    
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

# -----------------------------------------
# FUNCIONES DE COMUNICACIÓN OPTIMIZADAS (CACHÉ DE RECURSOS)
# -----------------------------------------

@st.cache_resource(ttl=300) # Se cambió a cache_resource para evitar que Arrow rompa los diccionarios internos
def obtener_usuarios_cached():
    try:
        usuarios_ref = db.collection("usuarios").stream()
        lista_usuarios = []
        for doc in usuarios_ref:
            lista_usuarios.append(doc.to_dict())
        return pd.DataFrame(lista_usuarios)
    except Exception as e:
        print(f"Error usuarios: {e}")
        return pd.DataFrame()

@st.cache_resource(ttl=300)
def obtener_vehiculos_cached():
    try:
        vehiculos_ref = db.collection("vehiculos").stream()
        lista_vehiculos = []
        for doc in vehiculos_ref:
            lista_vehiculos.append(doc.to_dict())
        
        if lista_vehiculos:
            return pd.DataFrame(lista_vehiculos)
        else:
            return pd.DataFrame(columns=["Vehiculo"])
    except Exception as e:
        print(f"Error vehiculos: {e}")
        return pd.DataFrame(columns=["Vehiculo"])

@st.cache_resource(ttl=300)
def obtener_viajes_cached():
    try:
        viajes_ref = db.collection(COLECCION_VIAJES).stream()
        lista_viajes = []
        for doc in viajes_ref:
            lista_viajes.append(doc.to_dict())
        return pd.DataFrame(lista_viajes)
    except Exception as e:
        print(f"Error viajes: {e}")
        return pd.DataFrame()

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
        db.collection(COLECCION_VIAJES).document(str(datos_viaje.get("ID", 0))).set(datos_viaje)
        # Limpiamos la caché para que el nuevo viaje aparezca de inmediato
        st.cache_resource.clear()
        return True
    except Exception:
        return False

def calcular_duracion_real(fecha_inicio, fecha_fin):
    if str(fecha_fin) in ["En curso", "Pendiente", "N/A", "", "None"]:
        return "No finalizado"
    try:
        formato = "%d/%m/%Y %H:%M:%S"
        inicio = datetime.strptime(str(fecha_inicio), formato)
        fin = datetime.strptime(str(fecha_fin), formato)
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
    def ordenar_por_numero(texto):
        try:
            return int(str(texto).split(".")[0])
        except Exception:
            return 99
    
    eq_html = ""
    chk_eq = v_data.get('Checklist_Eq', {})
    if chk_eq and isinstance(chk_eq, dict):
        for k in sorted(chk_eq.keys(), key=ordenar_por_numero):
            v = chk_eq[k]
            color = "#16a34a" if str(v) == "Sí" else ("#dc2626" if str(v) == "No" else "#64748b")
            eq_html += f'<tr><td style="padding: 4px; border-bottom: 1px solid #f1f5f9; font-size: 9pt;">{k}</td><td style="text-align: right; font-weight: bold; width: 15%; color: {color};">{str(v).upper()}</td></tr>'
    else:
        eq_html = "<tr><td colspan='2'>Sin datos</td></tr>"

    doc_html = ""
    chk_doc = v_data.get('Checklist_Doc', {})
    if chk_doc and isinstance(chk_doc, dict):
        for k in sorted(chk_doc.keys(), key=ordenar_por_numero):
            v = chk_doc[k]
            color = "#16a34a" if str(v) == "Sí" else ("#dc2626" if str(v) == "No" else "#64748b")
            doc_html += f'<tr><td style="padding: 4px; border-bottom: 1px solid #f1f5f9; font-size: 9pt;">{k}</td><td style="text-align: right; font-weight: bold; width: 15%; color: {color};">{str(v).upper()}</td></tr>'
    else:
        doc_html = "<tr><td colspan='2'>Sin datos</td></tr>"

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Ficha MARBAR ID {v_data.get('ID', 'N/A')}</title>
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
                <td style="text-align: right;"><strong style="color: #e65100; font-size: 12pt;">ID #{v_data.get('ID', 'N/A')}</strong><br><span style="color: #475569; font-size: 9pt;">Estado: <b>{str(v_data.get('Estado_Viaje', 'N/A')).upper()}</b></span></td>
            </tr>
        </table>

        <h2>1. PERSONAL Y UNIDAD</h2>
        <table class="tbl">
            <tr><th>Conductor</th><td>{v_data.get('Conductor', 'N/A')}</td><th>Unidad</th><td>{v_data.get('Vehiculo', 'N/A')}</td></tr>
            <tr><th>Sector/Cargo</th><td>{v_data.get('Sector', 'N/A')} / {v_data.get('Cargo', 'N/A')}</td><th>Regional</th><td>{v_data.get('Regional', 'N/A')}</td></tr>
            <tr><th>Base Operativa</th><td>{v_data.get('Base', 'N/A')}</td><th>Fecha Confección</th><td>{v_data.get('Fecha', 'N/A')}</td></tr>
        </table>

        <h2>2. RUTA Y TIEMPOS</h2>
        <table class="tbl">
            <tr><th>Origen</th><td>{v_data.get('Origen', 'N/A')}</td><th>Destino</th><td>{v_data.get('Destino', 'N/A')}</td></tr>
            <tr><th>Duración Est.</th><td>{v_data.get('Duracion', 'N/A')}</td><th>Fecha Cierre</th><td>{v_data.get('Fecha_Fin', 'En curso')}</td></tr>
        </table>

        <h2>3. ANÁLISIS DE RIESGOS</h2>
        <table class="tbl">
            <tr><th>Distancia</th><td>{v_data.get('R_Distancia', 'N/A')}</td><th>Clima</th><td>{v_data.get('R_Clima', 'N/A')}</td></tr>
            <tr><th>Pasajeros</th><td>{v_data.get('R_Pasajeros', 'N/A')} ({v_data.get('Detalle_Pasajeros', 'N/A')})</td><th>Camino</th><td>{v_data.get('R_Camino', 'N/A')}</td></tr>
            <tr><th>Sueño +8hs</th><td>{v_data.get('R_Sueno', 'N/A')}</td><th>Horas Servicio</th><td>{v_data.get('R_Horas', 'N/A')}</td></tr>
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
            <strong style="color: #c2410c; font-size: 11pt;">EVALUACIÓN: NIVEL {v_data.get('Nivel', 'N/A')} ({v_data.get('Puntaje', 0)} PTS)</strong><br>
            <span style="font-size: 9pt;">Aprobado por: <b>{v_data.get('Aprobador', 'N/A')}</b> ({v_data.get('Fecha_Aprobacion', 'N/A')})</span>
        </div>

        <div class="ddjj">
            <b>CERTIFICACIÓN LEGAL:</b> Los datos aquí expuestos poseen carácter de Declaración Jurada, registrados por el operador y convalidados por la supervisión de MARBAR SA bajo el carácter de declaración jurada, quedando prohibida cualquier alteración o edición posterior a su almacenamiento en la base central del sistema.
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
# SISTEMA DE LOGIN (FIREBASE AUTH)
# -----------------------------------------

try:
    FIREBASE_API_KEY = st.secrets["firebase_api_key"]
except KeyError:
    st.error("⚠️ Falta configurar 'firebase_api_key' en los secretos de la nube.")
    st.stop()

if st.session_state["usuario_actual"] is None:
    col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
    with col_logo2:
        if os.path.exists("logo.png"): 
            st.image("logo.png", use_column_width=True)
        else:
            st.warning("⚠️ Falta 'logo.png'")
    
    st.title("🔒 Acceso Seguro - MARBAR SA")
    
    tab_login, tab_recupero = st.tabs(["🔑 Iniciar Sesión", "✉️ Configurar o Recuperar Contraseña"])
    
    with tab_login:
        st.info("Ingrese sus credenciales para acceder a la plataforma operativa.")
        with st.form("form_login"):
            correo_input = st.text_input("Correo Electrónico:")
            pass_login = st.text_input("Contraseña:", type="password")
            btn_ingresar = st.form_submit_button("Ingresar al Sistema")
            
        if btn_ingresar:
            correo_login = str(correo_input).strip().lower()
            if not correo_login or not pass_login:
                st.error("⛔ Ingrese correo y contraseña.")
            else:
                url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY.strip()}"
                respuesta = requests.post(url, json={"email": correo_login, "password": pass_login, "returnSecureToken": True})
                
                if respuesta.status_code == 200:
                    if correo_login == "admin@marbar.com":
                        st.session_state.update({
                            "usuario_actual": "ADMIN", 
                            "nombre_empleado": "Administrador", 
                            "sector_empleado": "Gerencia", 
                            "regional_empleado": "Sede Central", 
                            "base_empleado": "Sede Central", 
                            "venc_licencia": "N/A",
                            "venc_defensiva": "N/A", 
                            "venc_def_chile": "N/A", 
                            "email_empleado": correo_login, 
                            "paso_actual": "Menu"
                        })
                        st.rerun()
                    else:
                        df_usuarios = obtener_usuarios_cached()
                        if not df_usuarios.empty and correo_login in df_usuarios['Email'].values:
                            usuario_encontrado = df_usuarios[df_usuarios['Email'] == correo_login].iloc[0].to_dict()
                            st.session_state.update({
                                "usuario_actual": str(usuario_encontrado.get("Rol", "Conductor")), 
                                "nombre_empleado": str(usuario_encontrado.get("Nombre", "Empleado MARBAR")), 
                                "sector_empleado": str(usuario_encontrado.get("Sector", "Sin Sector")), 
                                "regional_empleado": str(usuario_encontrado.get("Regional", "No asignada")),
                                "base_empleado": str(usuario_encontrado.get("Base", "No asignada")),
                                "venc_licencia": str(usuario_encontrado.get("Venc_Licencia", "N/A")),
                                "venc_defensiva": str(usuario_encontrado.get("Venc_Defensiva", "N/A")),
                                "venc_def_chile": str(usuario_encontrado.get("Venc_Def_Chile", "N/A")),
                                "email_empleado": correo_login, 
                                "paso_actual": "Menu"
                            })
                            st.rerun()
                        else: 
                            st.error(f"⛔ El correo **{correo_login}** es válido, pero no figura en la base de datos operativa.")
                else: 
                    st.error("⛔ Correo o contraseña incorrectos.")

    with tab_recupero:
        st.write("Ingrese su correo corporativo. Le enviaremos un enlace oficial para configurar su nueva contraseña.")
        correo_configurar = st.text_input("Correo Registrado:", key="txt_correo_config").strip().lower()
        
        if st.button("📧 Enviar Enlace de Configuración", use_container_width=True):
            if correo_configurar != "":
                # Intentamos forzar la creación de la cuenta en Firebase Auth por si no existe
                try:
                    pass_temporal = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
                    auth.create_user(email=correo_configurar, password=pass_temporal)
                except Exception: 
                    pass # Ignoramos el error si la cuenta ya existía
                    
                url_reset = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY.strip()}"
                try:
                    res_reset = requests.post(url_reset, json={"requestType": "PASSWORD_RESET", "email": correo_configurar})
                    if res_reset.status_code == 200:
                        st.success(f"📩 ¡Enlace enviado con éxito a **{correo_configurar}**! Revise su bandeja de entrada o Spam.")
                    else: 
                        st.error(f"⛔ Firebase rebotó el envío. Respuesta oficial: {res_reset.text}")
                except Exception as e_req: 
                    st.error(f"⛔ Error de red: {e_req}")
            else: 
                st.error("Escriba un correo válido.")
    
    # Detenemos la ejecución si el usuario no ha iniciado sesión
    st.stop() 

# --- WORKFLOW PRINCIPAL ---
if st.session_state["paso_actual"] == "Menu":
    st.subheader(f"Panel Operativo - Bienvenido, {st.session_state.get('nombre_empleado', 'Usuario')}")
    
    # --- Alertas de Vencimiento de Documentación ---
    if st.session_state.get("usuario_actual") not in ["ADMIN", "ADMINISTRADOR"]:
        v_lic = st.session_state.get("venc_licencia", "N/A")
        v_def = st.session_state.get("venc_defensiva", "N/A")
        v_def_chile = st.session_state.get("venc_def_chile", "N/A")
        reg_emp = st.session_state.get("regional_empleado", "N/A").strip().lower()
        hoy_dt = datetime.now(TZ_AR).date()
        
        docs_a_revisar = [("Carnet de Manejo", v_lic), ("Curso de Conducción Defensiva", v_def)]
        if reg_emp == "chile": 
            docs_a_revisar.append(("Manejo Defensivo (Chile)", v_def_chile))
            
        for tipo_doc, fecha_str in docs_a_revisar:
            if fecha_str and str(fecha_str) != "N/A":
                try:
                    fecha_venc = datetime.strptime(str(fecha_str), "%d/%m/%Y").date()
                    dias_restantes = (fecha_venc - hoy_dt).days
                    if dias_restantes < 0: 
                        st.error(f"🚨 **VENCIMIENTO CRÍTICO:** Su **{tipo_doc}** caducó hace {abs(dias_restantes)} días ({fecha_str}).")
                    elif dias_restantes <= 30: 
                        st.warning(f"⚠️ **AVISO DE VENCIMIENTO:** Su **{tipo_doc}** vencerá en {dias_restantes} días ({fecha_str}).")
                except Exception: 
                    pass
    
    # --- SISTEMA DE ALERTAS PERSISTENTES POR WHATSAPP ---
    if "alerta_nuevo_viaje" in st.session_state:
        v_new = st.session_state["alerta_nuevo_viaje"]
        cabecera_wa = f"🟢 *VIAJE AUTO-APROBADO ID {v_new['id']}*" if v_new['color'] == "green" else f"🔴 *NUEVA SOLICITUD ID {v_new['id']}*"
        tkt = f"{cabecera_wa}\n\n🔹 *Conductor:* {v_new['conductor']}\n🔹 *Vehículo:* {v_new['vehiculo']}\n🔹 *Origen:* {v_new['origen']}\n🔹 *Destino:* {v_new['destino']}\n🔹 *Riesgo:* Nivel {v_new['nivel']}"
        link_nuevo_wa = f"https://wa.me/?text={urllib.parse.quote(tkt)}"
        
        st.success(f"✅ ¡Viaje registrado con éxito en el sistema (ID {v_new['id']})!")
        st.markdown(f"### [📱 ENVIAR TICKET DE VIAJE POR WHATSAPP]({link_nuevo_wa})")
        if st.button("Ocultar Alerta de Ticket", key="ocultar_nuevo_viaje"):
            del st.session_state["alerta_nuevo_viaje"]
            st.rerun()
        st.markdown("---")

    if "alerta_llegada" in st.session_state:
        v_llegada = st.session_state["alerta_llegada"]
        msg_llegada_wa = f"✅ *AVISO DE LLEGADA MARBAR*\n\n🔹 *Conductor:* {st.session_state.get('nombre_empleado','')}\n🔹 *Viaje ID:* {v_llegada.get('id','')}\n🔹 *Destino:* {v_llegada.get('destino','')}\n\n👉 *Llegué bien a destino sin novedades.*"
        st.success("El viaje se cerró correctamente en el sistema operativo.")
        st.markdown(f"### [📱 ENVIAR AVISO DE LLEGADA POR WHATSAPP](https://wa.me/?text={urllib.parse.quote(msg_llegada_wa)})")
        if st.button("Ocultar Aviso de Arribo", key="ocultar_llegada"):
            del st.session_state["alerta_llegada"]
            st.rerun()
        st.markdown("---")
        
    if "alerta_cancelacion" in st.session_state:
        v_canc = st.session_state["alerta_cancelacion"]
        msg_canc_wa = f"❌ *VIAJE CANCELADO - MARBAR*\n\n🔹 *Conductor:* {st.session_state.get('nombre_empleado','')}\n🔹 *Viaje ID:* {v_canc.get('id','')}\n🔹 *Destino:* {v_canc.get('destino','')}\n\n👉 *El viaje ha sido suspendido y cerrado.*"
        st.warning("El viaje fue cancelado y retirado de la ruta activa.")
        st.markdown(f"### [📱 ENVIAR AVISO DE CANCELACIÓN POR WHATSAPP](https://wa.me/?text={urllib.parse.quote(msg_canc_wa)})")
        if st.button("Ocultar Aviso de Cancelación", key="ocultar_canc"):
            del st.session_state["alerta_cancelacion"]
            st.rerun()
        st.markdown("---")
    
    # --- Gestión de Viaje en Curso del Conductor ---
    if st.session_state.get("usuario_actual") not in ["ADMIN", "ADMINISTRADOR"]:
        df_viajes_activos = obtener_viajes_cached()
        if not df_viajes_activos.empty:
            activos_conductor = df_viajes_activos[
                (df_viajes_activos["Conductor"] == st.session_state.get("nombre_empleado")) & 
                (df_viajes_activos["Estado_Viaje"].isin(["En viaje", "En espera"]))
            ]
            
            if not activos_conductor.empty:
                st.info("📍 Estado de su viaje actual:")
                for index, v in activos_conductor.iterrows():
                    with st.container(border=True):
                        estado_aprobacion = str(v.get("Aprobacion", "🔴 Pendiente"))
                        v_id = str(v.get("ID", "0"))
                        v_dest = str(v.get("Destino", "N/A"))
                        v_orig = str(v.get("Origen", "N/A"))
                        v_veh = str(v.get("Vehiculo", "N/A"))
                        v_niv = str(v.get("Nivel", "1"))
                        
                        # Mostramos el estado y generamos el Link de WhatsApp permanente
                        if "Aprobado" in estado_aprobacion: 
                            st.success(f"🚀 **VIAJE AUTORIZADO (ID {v_id})**\n\nEl supervisor ya firmó digitalmente. Está habilitado hacia **{v_dest}**.")
                            tkt_wa = f"🟢 *VIAJE EN CURSO ID {v_id}*\n\n🔹 *Conductor:* {st.session_state.get('nombre_empleado')}\n🔹 *Vehículo:* {v_veh}\n🔹 *Origen:* {v_orig}\n🔹 *Destino:* {v_dest}\n🔹 *Estado:* Autorizado"
                            st.markdown(f"#### [📱 COMPARTIR TICKET POR WHATSAPP](https://wa.me/?text={urllib.parse.quote(tkt_wa)})")
                        else: 
                            st.warning(f"⏳ **ESPERANDO APROBACIÓN (ID {v_id})**\n\nSu solicitud requiere validación. **No mueva la unidad.**")
                            tkt_req = f"🔴 *SOLICITUD DE APROBACIÓN ID {v_id}*\n\n🔹 *Conductor:* {st.session_state.get('nombre_empleado')}\n🔹 *Vehículo:* {v_veh}\n🔹 *Origen:* {v_orig}\n🔹 *Destino:* {v_dest}\n🔹 *Riesgo:* Nivel {v_niv}\n\n👉 *Solicito autorización en el sistema MARBAR para iniciar marcha.*"
                            st.markdown(f"#### [📱 NOTIFICAR A SUPERVISOR POR WHATSAPP](https://wa.me/?text={urllib.parse.quote(tkt_req)})")
                        
                        st.write("---")
                        col_accion, col_canc = st.columns(2)
                        
                        if col_accion.button(f"🏁 Informar Llegada", key=f"menu_fin_{v_id}", use_container_width=True):
                            db.collection(COLECCION_VIAJES).document(v_id).update({
                                "Estado_Viaje": "Finalizado", 
                                "Fecha_Fin": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                            })
                            st.cache_resource.clear() 
                            st.session_state["alerta_llegada"] = {"id": v_id, "destino": v_dest}
                            st.rerun()
                            
                        if col_canc.button(f"❌ Cancelar Viaje", key=f"menu_canc_{v_id}", use_container_width=True):
                            db.collection(COLECCION_VIAJES).document(v_id).update({
                                "Estado_Viaje": "Cancelado", 
                                "Fecha_Fin": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                            })
                            st.cache_resource.clear() 
                            st.session_state["alerta_cancelacion"] = {"id": v_id, "destino": v_dest}
                            st.rerun()
                            
    # --- Botones del Menú Principal ---
    st.markdown("---")
    col_menu1, col_menu2 = st.columns(2)
    with col_menu1:
        if st.button("🚀 NUEVO GERENCIAMIENTO DE VIAJE", use_container_width=True): 
            documentacion_vencida = False
            if st.session_state.get("usuario_actual") not in ["ADMIN", "ADMINISTRADOR"]:
                hoy_dt = datetime.now(TZ_AR).date()
                fechas_a_evaluar = [
                    st.session_state.get("venc_licencia"), 
                    st.session_state.get("venc_defensiva"), 
                    st.session_state.get("venc_def_chile")
                ]
                for fecha_str in fechas_a_evaluar:
                    if fecha_str and str(fecha_str) != "N/A":
                        try:
                            if (datetime.strptime(str(fecha_str), "%d/%m/%Y").date() - hoy_dt).days < 0: 
                                documentacion_vencida = True
                        except Exception: 
                            pass
                            
            if documentacion_vencida: 
                st.error("⛔ **ACCESO DENEGADO:** Tiene documentación habilitante vencida. Regularice su situación.")
            else:
                st.session_state["paso_actual"] = "Test_Conductor"
                st.rerun()
                
    with col_menu2:
        if st.button("📜 VER MI HISTORIAL", use_container_width=True): 
            st.session_state["paso_actual"] = "Historial"
            st.rerun()

elif st.session_state["paso_actual"] == "Test_Conductor":
    st.warning("⚖️ **DECLARACIÓN JURADA:** La información ingresada reviste carácter de Declaración Jurada.")
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
            if None in [t1, t2, t3]: 
                st.error("⛔ Responda todas las preguntas.")
            elif t1 == "Sí" and t2 == "No" and t3 == "No":
                st.session_state["test_conductor"] = "Aprobado"
                st.session_state["paso_actual"] = "Inspeccion_Vehiculo"
                st.rerun()
            else: 
                st.error("⚠️ No está en condiciones de conducir. Repórtese con su supervisor.")

elif st.session_state["paso_actual"] == "Inspeccion_Vehiculo":
    st.warning("⚖️ **DECLARACIÓN JURADA:** La información ingresada reviste carácter de Declaración Jurada.")
    st.subheader("🚘 Paso 2: Condiciones del Vehículo")
    
    st.markdown("#### A. Equipamiento y Estado Técnico")
    eq_items = [
        "1. Frenos de Servicio", 
        "2. Freno Estacionamiento", 
        "3. Neumáticos buen estado", 
        "4. Sistema de Dirección libre de pérdidas", 
        "5. Tablero libre de luces", 
        "6. Cinturones funcionales", 
        "7. Apoyacabeza", 
        "8. Extintor Vigente", 
        "9. Balizas/Triángulos", 
        "10. Kit de Herramientas", 
        "11. Rueda de Auxilio", 
        "12. Airbag Operativo", 
        "13. ABS Operativo", 
        "14. MVI Operativo", 
        "15. Kit Invernal"
    ]
    respuestas_eq = {}
    for item in eq_items:
        respuestas_eq[item] = st.radio(item, ["Sí", "No", "N/A"], index=None, horizontal=True)
        
    st.markdown("#### B. Documentación Obligatoria")
    doc_items = [
        "1. Licencia vigente", 
        "2. Cédula Verde/Azul", 
        "3. RTO Vigente", 
        "4. Seguro del Vehículo", 
        "5. Conducción Defensiva"
    ]
    respuestas_doc = {}
    for item in doc_items:
        respuestas_doc[item] = st.radio(item, ["Sí", "No", "N/A"], index=None, horizontal=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Regresar"): 
            st.session_state["paso_actual"] = "Test_Conductor"
            st.rerun()
    with col2:
        if st.button("Siguiente 📝"):
            if not (all(v is not None for v in respuestas_eq.values()) and all(v is not None for v in respuestas_doc.values())): 
                st.error("⛔ Responda todos los ítems.")
            elif any(v == "No" for v in respuestas_eq.values()) or any(v == "No" for v in respuestas_doc.values()): 
                st.error("⛔ Elementos marcados con 'No'. Prohibido el viaje.")
            else:
                st.session_state["inspeccion_vehiculo"] = "Aprobada"
                st.session_state["resp_eq"] = respuestas_eq
                st.session_state["resp_doc"] = respuestas_doc
                st.session_state["paso_actual"] = "Formulario_Viaje"
                st.rerun()

elif st.session_state["paso_actual"] == "Formulario_Viaje":
    st.subheader("🛡️ Paso 3: Análisis de Riesgo")
    
    sector_usuario = str(st.session_state.get("sector_empleado", "N/A"))
    rol_usuario = str(st.session_state.get("usuario_actual", "N/A")).strip().upper()
    nombre_conductor = str(st.session_state.get("nombre_empleado", "N/A"))
    regional_usuario = str(st.session_state.get("regional_empleado", "No asignada"))
    base_usuario = str(st.session_state.get("base_empleado", "No asignada"))
    
    mapa_autoridad = {"CONDUCTOR": 0, "SUPERVISOR / COORDINADOR / INGENIERO": 1, "JEFE DE SERVICIO": 2, "GERENCIA": 3, "ADMIN": 3, "ADMINISTRADOR": 3}
    nivel_aprobacion_usuario = mapa_autoridad.get(rol_usuario, 0)
    
    df_flota = obtener_vehiculos_cached()
    if not df_flota.empty:
        opciones_flota = [""] + df_flota.get("Vehiculo", pd.Series(["⚠️ Cargar flota en Admin"])).tolist()
    else:
        opciones_flota = ["", "⚠️ Cargar flota en Admin"]
        
    vehiculo_sel = st.selectbox("Unidad / Vehículo a utilizar:", opciones_flota, index=0)
    
    if vehiculo_sel == "":
        st.warning("⚠️ OBLIGATORIO: Seleccione la patente/interno asignado antes de confirmar el viaje.")

    vehiculo_inhabilitado = False
    if vehiculo_sel not in ["", "⚠️ Cargar flota en Admin"] and not df_flota.empty:
        try:
            datos_vehiculo = df_flota[df_flota["Vehiculo"] == vehiculo_sel].iloc[0]
            hoy_dt = datetime.now(TZ_AR).date()
            
            fechas_vehiculo = [
                ("VTV", str(datos_vehiculo.get("Venc_VTV", "N/A"))), 
                ("Seguro", str(datos_vehiculo.get("Venc_Seguro", "N/A")))
            ]
            
            for doc_name, doc_date in fechas_vehiculo:
                if doc_date and doc_date != "N/A":
                    try:
                        if (datetime.strptime(doc_date, "%d/%m/%Y").date() - hoy_dt).days < 0:
                            vehiculo_inhabilitado = True
                            st.error(f"🚨 **UNIDAD INHABILITADA:** {doc_name} vencido.")
                    except: 
                        pass
        except Exception: 
            pass

    with st.expander("\U0001F5FA MAPA DE YACIMIENTOS", expanded=True): 
        components.iframe("https://www.google.com/maps/d/u/2/embed?mid=1BPDw99m6vQAC09Kdbw9Onaj5mu-blw4&ehbc=2E312F", height=480)

    col1, col2 = st.columns(2)
    with col1: origen_txt = st.text_input("Origen:")
    with col2: destino_txt = st.text_input("Destino:")
    
    col_dur_h, col_dur_m = st.columns(2)
    with col_dur_h: dur_horas = st.number_input("Horas (HH):", min_value=0, max_value=72, value=0, step=1)
    with col_dur_m: dur_minutos = st.number_input("Minutos (MM):", min_value=0, max_value=59, value=0, step=1)
    
    salida_tipo = st.radio("Salida:", ["Planificada", "Urgencia"], index=None)
    v_distancia = st.radio("Distancia:", ["< 50km", "< 100km", "< 200km", "> 200km"], index=None)
    v_clima = st.selectbox("Clima:", ["Despejado", "Nublado", "Viento", "Lluvia", "Niebla", "Nieve"], index=None)
    v_pasajeros = st.radio("Acompañantes:", ["Con pasajeros", "Solo conductor"], index=None)
    pasajeros_detalle = st.text_input("👥 Nombres:") if v_pasajeros == "Con pasajeros" else "N/A"
    v_camino = st.radio("Superficie:", ["Pavimento", "Mixto", "Tierra"], index=None)
    v_sueno = st.radio("¿Descansó +8hs?", ["Sí", "No"], index=None)
    v_horas_servicio = st.radio("Horas Totales:", ["< 12hs", "< 14hs", "< 16hs"], index=None)
    v_escolta = st.radio("¿Vehículo Escolta?", ["No", "Sí"], index=None)
    v_horario = st.radio("Horario:", ["Diurno", "Nocturno"], index=None)
    v_comunicacion = st.radio("Cobertura Señal:", ["Total", "Tramos sin señal", "Sin señal"], index=None)

    puntos_totales = 0
    if v_distancia: puntos_totales += {"< 50km":1, "< 100km":2, "< 200km":5, "> 200km":7}.get(v_distancia, 0)
    if v_clima: puntos_totales += {"Despejado":0, "Nublado":1, "Viento":2, "Lluvia":4, "Niebla":8, "Nieve":9}.get(v_clima, 0)
    if v_pasajeros: puntos_totales += 1 if v_pasajeros == "Con pasajeros" else 5
    if v_camino: puntos_totales += {"Pavimento":1, "Mixto":2, "Tierra":4}.get(v_camino, 0)
    if v_sueno and v_horas_servicio:
        if v_horas_servicio == "< 12hs": puntos_totales += 1 if v_sueno == "Sí" else 2
        elif v_horas_servicio == "< 14hs": puntos_totales += 3 if v_sueno == "Sí" else 5
        elif v_horas_servicio == "< 16hs": puntos_totales += 6 if v_sueno == "Sí" else 8
    if v_escolta: puntos_totales += 1 if v_escolta == "No" else 5
    if v_horario: puntos_totales += 5 if v_horario == "Nocturno" else 1
    if v_comunicacion: puntos_totales += {"Total":1, "Tramos sin señal":3, "Sin señal":5}.get(v_comunicacion, 0)

    nivel_riesgo_calculado = 1
    if puntos_totales > 15 and puntos_totales <= 30: nivel_riesgo_calculado = 2
    elif puntos_totales > 30: nivel_riesgo_calculado = 3
    if salida_tipo == "Urgencia" and v_horario == "Nocturno": nivel_riesgo_calculado = 3
    
    if nivel_aprobacion_usuario >= nivel_riesgo_calculado:
        color_semaforo = "green"
    else:
        if nivel_riesgo_calculado < 3:
            color_semaforo = "orange"
        else:
            color_semaforo = "red"
            
    aprobacion_estado = "AUTORIZADO (Auto-Aprobado)" if color_semaforo == "green" else f"PENDIENTE (Requiere Nivel {nivel_riesgo_calculado})"

    st.subheader("📋 Resultado")
    if color_semaforo == "green": 
        st.success(f"**{aprobacion_estado}** | {puntos_totales} pts")
    else: 
        st.warning(f"**{aprobacion_estado}** | {puntos_totales} pts")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("⬅️ Volver"): 
            st.session_state["paso_actual"] = "Inspeccion_Vehiculo"
            st.rerun()
    with col_btn2:
        if st.button("CONFIRMAR VIAJE"):
            duracion_es_cero = (dur_horas == 0 and dur_minutos == 0)
            
            campos_ok = all([
                origen_txt.strip(), 
                destino_txt.strip(), 
                not duracion_es_cero, 
                vehiculo_sel != "", 
                vehiculo_sel != "⚠️ Cargar flota en Admin", 
                not vehiculo_inhabilitado, 
                salida_tipo, 
                v_distancia, 
                v_clima, 
                v_pasajeros, 
                v_camino, 
                v_sueno, 
                v_horas_servicio, 
                v_escolta, 
                v_horario, 
                v_comunicacion
            ])
            
            if not campos_ok: 
                if duracion_es_cero:
                    st.error("⛔ Ingrese la duración estimada del trayecto.")
                else:
                    st.error("⛔ Faltan datos obligatorios. Verifique haber seleccionado una Unidad/Vehículo en la sección superior.")
            elif v_pasajeros == "Con pasajeros" and not pasajeros_detalle.strip(): 
                st.error("⚠️ Ingrese el nombre de los pasajeros.")
            else:
                nuevo_id = obtener_siguiente_id()
                hora_str = datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                
                if color_semaforo == "green":
                    aprob_db = "🟢 Aprobado"
                    aprobador_db = nombre_conductor
                    fecha_aprob_db = hora_str
                    est_v_db = "En viaje"
                else:
                    aprob_db = "🔴 Pendiente"
                    aprobador_db = "Pendiente"
                    fecha_aprob_db = "Pendiente"
                    est_v_db = "En espera"
                
                datos = {
                    "ID": nuevo_id, 
                    "Regional": regional_usuario, 
                    "Base": base_usuario, 
                    "Fecha": hora_str, 
                    "Conductor": nombre_conductor, 
                    "Sector": sector_usuario, 
                    "Cargo": rol_usuario, 
                    "Vehiculo": vehiculo_sel, 
                    "Duracion": f"{int(dur_horas):02d}:{int(dur_minutos):02d} Hs", 
                    "Salida": salida_tipo, 
                    "Alarma Nocturna": "encendida" if v_horario == "Nocturno" else "apagada", 
                    "Origen": origen_txt, 
                    "Destino": destino_txt, 
                    "Estado": aprobacion_estado, 
                    "Puntaje": puntos_totales, 
                    "Nivel": nivel_riesgo_calculado, 
                    "Aprobacion": aprob_db, 
                    "Aprobador": aprobador_db, 
                    "Fecha_Aprobacion": fecha_aprob_db, 
                    "Estado_Viaje": est_v_db, 
                    "Fecha_Fin": "En curso", 
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
                    st.session_state["alerta_nuevo_viaje"] = {
                        "id": nuevo_id,
                        "conductor": nombre_conductor,
                        "vehiculo": vehiculo_sel,
                        "origen": origen_txt,
                        "destino": destino_txt,
                        "nivel": nivel_riesgo_calculado,
                        "color": color_semaforo
                    }
                    st.session_state["paso_actual"] = "Menu"
                    st.rerun()

elif st.session_state["paso_actual"] == "Historial":
    st.subheader("📜 Historial de Registros")
    df_h = obtener_viajes_cached()
    
    if not df_h.empty:
        if st.session_state.get("usuario_actual") not in ["ADMIN", "ADMINISTRADOR"]: 
            df_h = df_h[df_h["Conductor"] == st.session_state.get("nombre_empleado")]
            
        if not df_h.empty:
            df_h = df_h.sort_values(by="ID", ascending=False)
            st.dataframe(df_h[['ID', 'Fecha', 'Origen', 'Destino', 'Estado_Viaje']], hide_index=True)
            
            op_dd = [""] + [f"{r.get('ID','')} - {r.get('Conductor','')} - {str(r.get('Fecha',''))[:10]}" for _, r in df_h.iterrows()]
            v_sel = st.selectbox("Seleccione viaje:", op_dd)
            
            if v_sel != "":
                id_ext = str(v_sel.split(" - ")[0])
                d_v = df_h[df_h["ID"].astype(str) == id_ext].iloc[0]
                st.download_button("📥 Descargar Ficha PDF", generar_ficha_html(d_v), f"Auditoria_{id_ext}.html", mime="text/html")
    
    if st.button("⬅️ Menú"): 
        st.session_state["paso_actual"] = "Menu"
        st.rerun()

# --- 6. SIDEBAR (PANEL LATERAL) ---
if st.session_state.get("usuario_actual"):
    with st.sidebar:
        if os.path.exists("logo.png"): 
            st.image("logo.png", use_column_width=True)
        st.header("📊 SSA & Logística")
        
        if st.button("🔄 Actualizar", use_container_width=True): 
            st.cache_resource.clear()
            st.rerun()
            
        if st.button("🚪 Cerrar Sesión", use_container_width=True): 
            st.session_state.clear()
            st.rerun()

    try:
        df_sb = obtener_viajes_cached()
        
        if not df_sb.empty:
            hoy = datetime.now(TZ_AR).strftime("%d/%m/%Y")
            mes_actual = datetime.now(TZ_AR).strftime("/%m/%Y")
            
            # --- BLINDAJE DE MÉTRICAS (EXCLUYE CANCELADOS) ---
            df_activos_reales = df_sb[df_sb.get('Estado_Viaje', pd.Series()) != "Cancelado"]
            
            if 'Fecha' in df_activos_reales.columns:
                df_hoy = df_activos_reales[df_activos_reales['Fecha'].astype(str).str.contains(hoy, na=False)]
                df_mes = df_activos_reales[df_activos_reales['Fecha'].astype(str).str.contains(mes_actual, na=False)]
            else:
                df_hoy = pd.DataFrame()
                df_mes = pd.DataFrame()

            # PENDIENTES REALES
            if 'Aprobacion' in df_hoy.columns and 'Estado_Viaje' in df_hoy.columns:
                df_p = df_hoy[
                    (df_hoy['Aprobacion'].astype(str).str.contains("Pendiente", na=False)) & 
                    (df_hoy['Estado_Viaje'] == "En espera")
                ]
            else:
                df_p = pd.DataFrame()

            # EN RUTA REALES
            if 'Estado_Viaje' in df_sb.columns:
                df_r = df_sb[df_sb['Estado_Viaje'] == "En viaje"]
            else:
                df_r = pd.DataFrame()

            with st.sidebar:
                st.markdown("---")
                st.subheader("📈 Resumen Global Operativo")
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Viajes Hoy", str(len(df_hoy)), delta=f"{len(df_p)} pend." if not df_p.empty else "Al día", delta_color="inverse" if not df_p.empty else "normal")
                col_m2.metric("En Ruta", str(len(df_r)))
                
                col_m3, col_m4 = st.columns(2)
                col_m3.metric("Este Mes", str(len(df_mes)))
                col_m4.metric("Histórico", str(len(df_sb)))
                
                st.markdown("---")
                st.write("⚠️ **Pendientes (Hoy):**")
                if not df_p.empty: 
                    st.dataframe(df_p[['Conductor', 'Destino']], hide_index=True)
                else: 
                    st.write("✅ Al día.")
                
                st.markdown("---")
                st.write("🚚 **En Ruta:**")
                if not df_r.empty: 
                    st.dataframe(df_r[['Conductor', 'Destino']], hide_index=True)
                else: 
                    st.write("✅ Ninguna.")

                st.markdown("---")
                st.subheader("📜 Ficha Rápida")
                if "ID" in df_sb.columns and "Conductor" in df_sb.columns:
                    df_sb_ord = df_sb.sort_values(by="ID", ascending=False)
                    op_sb = [""] + [f"{r.get('ID','')} - {r.get('Conductor','')}" for _, r in df_sb_ord.iterrows()]
                    v_sb = st.selectbox("Buscar ID:", op_sb)
                    
                    if v_sb != "":
                        id_sb = str(v_sb.split(" - ")[0])
                        d_sb = df_sb[df_sb["ID"].astype(str) == id_sb].iloc[0]
                        st.download_button("📥 Descargar Ficha", generar_ficha_html(d_sb), f"Auditoria_{id_sb}.html", mime="text/html")

            if st.session_state.get("usuario_actual") in ["ADMIN", "ADMINISTRADOR", "Supervisor / Coordinador / Ingeniero", "Jefe de Servicio", "Gerencia"]:
                with st.sidebar:
                    st.markdown("---")
                    st.subheader("📊 Consola Excel")
                    
                    cols = ['ID', 'Regional', 'Fecha', 'Conductor', 'Sector', 'Cargo', 'Vehiculo', 'Duracion', 'Salida', 'Alarma Nocturna', 'Origen', 'Destino', 'Estado', 'Puntaje', 'Nivel', 'Aprobacion', 'Aprobador', 'Fecha_Aprobacion', 'Estado_Viaje', 'Fecha_Fin']
                    for c in cols: 
                        if c not in df_sb.columns: 
                            df_sb[c] = "N/A"
                            
                    df_ex = df_sb[cols].sort_values(by="ID", ascending=False).copy()
                    df_ex['Duracion_Real_Viaje'] = df_ex.apply(lambda r: calcular_duracion_real(r.get('Fecha', ''), r.get('Fecha_Fin', '')), axis=1)
                    
                    bx = io.BytesIO()
                    with pd.ExcelWriter(bx, engine='openpyxl') as wr: 
                        df_ex.to_excel(wr, index=False, sheet_name='Auditoria_Viajes')
                        
                    st.download_button("📥 Auditoría (Excel)", bx.getvalue(), f"Auditoria_{hoy.replace('/','-')}.xlsx")
    except Exception as error_sidebar: 
        print(f"Error en sidebar: {error_sidebar}")

# --- 7. BANDEJA APROBACIONES (SUPERVISIÓN) ---
rol_bdj = str(st.session_state.get("usuario_actual", "N/A")).strip().upper()

if rol_bdj in ["ADMIN", "ADMINISTRADOR", "SUPERVISOR / COORDINADOR / INGENIERO", "JEFE DE SERVICIO", "GERENCIA"]:
    st.markdown("---")
    st.title("📥 Bandeja de Validaciones")
    
    mapa_autoridad_bdj = {"SUPERVISOR / COORDINADOR / INGENIERO": 1, "JEFE DE SERVICIO": 2, "GERENCIA": 3, "ADMIN": 3, "ADMINISTRADOR": 3}
    mi_nivel = mapa_autoridad_bdj.get(rol_bdj, 0)
    
    mi_reg = str(st.session_state.get("regional_empleado", "")).strip().lower()
    mi_sec = str(st.session_state.get("sector_empleado", "")).strip().lower()
    es_jefe_global = rol_bdj in ["ADMIN", "ADMINISTRADOR", "GERENCIA"]
    
    try:
        df_tod = obtener_viajes_cached()
        if not df_tod.empty:
            df_pen = df_tod[
                (df_tod.get('Aprobacion', pd.Series()).astype(str).str.contains("Pendiente", na=False)) & 
                (df_tod.get('Estado_Viaje', pd.Series()) == "En espera")
            ]
            
            p_list = []
            for _, v_data in df_pen.iterrows():
                v_dict = v_data.to_dict()
                v_reg = str(v_dict.get("Regional", "")).strip().lower()
                v_sec = str(v_dict.get("Sector", "")).strip().lower()
                
                # Filtro estricto
                if es_jefe_global or (v_reg == mi_reg and v_sec == mi_sec): 
                    p_list.append(v_dict)
            
            if p_list:
                for v_p in p_list:
                    n_v = int(v_p.get("Nivel", 1))
                    v_id = str(v_p.get("ID", "0"))
                    
                    with st.expander(f"🚨 ID: {v_id} | Conductor: {v_p.get('Conductor', 'N/A')} | Sector: {v_p.get('Sector', 'N/A')} | Nivel {n_v}"):
                        st.write(f"**Ruta:** {v_p.get('Origen', '')} -> {v_p.get('Destino', '')} ({v_p.get('Puntaje', 0)} pts)")
                        
                        if mi_nivel >= n_v:
                            if st.button(f"✍️ Aprobar {v_id}", key=f"ap_{v_id}"):
                                db.collection(COLECCION_VIAJES).document(v_id).update({
                                    "Aprobacion": "🟢 Aprobado", 
                                    "Aprobador": st.session_state.get("nombre_empleado"), 
                                    "Fecha_Aprobacion": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S"), 
                                    "Estado_Viaje": "En viaje"
                                })
                                st.cache_resource.clear()
                                st.rerun()
                        else: 
                            st.error(f"🔒 Nivel {mi_nivel} insuficiente. Exige Nivel {n_v}.")
            else: 
                st.info("✅ Bandeja limpia. No hay solicitudes pendientes para su sector.")
    except Exception: 
        pass

# --- 8. ADMIN ---
if rol_bdj in ["ADMIN", "ADMINISTRADOR"]:
    st.markdown("---")
    st.title("⚙️ Consola Admin")
    t1, t2, t3 = st.tabs(["👥 Usuarios", "🚘 Flota", "⚡ Carga Masiva"])
    
    with t1:
        st.info("💡 Creación manual de perfiles.")
        adm_email = st.text_input("Correo Electrónico Oficial:").strip().lower()
        adm_nombre = st.text_input("Nombre y Apellido Real:").strip()
        adm_dni = st.text_input("DNI:").strip()
        
        col_r, col_b = st.columns(2)
        with col_r: 
            adm_regional = st.text_input("Regional:").strip()
        with col_b: 
            adm_base = st.text_input("Base Operativa:").strip()
            
        adm_sector = st.selectbox("Sector:", ["Higiene y Seguridad", "Logistica", "Fluidos", "Control de solidos", "Mantenimiento", "Gerencia", "Completacion"])
        adm_rol = st.selectbox("Rol:", ["Conductor", "Supervisor / Coordinador / Ingeniero", "Jefe de Servicio", "Gerencia", "ADMIN"])
        
        c_v1, c_v2, c_v3 = st.columns(3)
        with c_v1: 
            adm_venc_lic = st.date_input("Venc. Carnet Manejo:", value=datetime.now(TZ_AR).date(), format="DD/MM/YYYY")
        with c_v2: 
            adm_venc_def = st.date_input("Venc. Defensiva:", value=datetime.now(TZ_AR).date(), format="DD/MM/YYYY")
        with c_v3: 
            adm_venc_def_chile = st.date_input("Venc. Def Chile:", value=datetime.now(TZ_AR).date(), format="DD/MM/YYYY")
        
        if st.button("💾 Asignar Perfil Operativo"):
            if adm_email and adm_nombre and adm_dni and adm_regional and adm_base:
                try:
                    pass_temp = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
                    auth.create_user(email=adm_email, password=pass_temp)
                except Exception: 
                    pass
                    
                try:
                    res = requests.post(f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY.strip()}", json={"requestType": "PASSWORD_RESET", "email": adm_email})
                    if res.status_code != 200: 
                        st.error(f"Fallo envío correo: {res.text}")
                except Exception: 
                    pass
                    
                db.collection("usuarios").document(adm_dni).set({
                    "DNI_Usuario": adm_dni, 
                    "Nombre": adm_nombre, 
                    "Email": adm_email, 
                    "Regional": adm_regional, 
                    "Base": adm_base, 
                    "Rol": adm_rol, 
                    "Sector": adm_sector, 
                    "Venc_Licencia": adm_venc_lic.strftime("%d/%m/%Y"), 
                    "Venc_Defensiva": adm_venc_def.strftime("%d/%m/%Y"), 
                    "Venc_Def_Chile": adm_venc_def_chile.strftime("%d/%m/%Y")
                })
                st.cache_resource.clear()
                st.success("✅ Guardado en base de datos operativa.")
                st.rerun()
            else: 
                st.error("Complete todos los campos.")
                
        df_u = obtener_usuarios_cached()
        if not df_u.empty:
            st.dataframe(df_u, hide_index=True)
            lista_b = [""] + [str(r.get("DNI_Usuario", "")) for _, r in df_u.iterrows() if str(r.get("Rol", "")) not in ["ADMIN", "ADMINISTRADOR"]]
            elim_u = st.selectbox("Borrar Perfil (DNI):", lista_b)
            
            if st.button("❌ Dar de Baja") and elim_u: 
                db.collection("usuarios").document(elim_u).delete()
                st.cache_resource.clear()
                st.rerun()

    with t2:
        adm_pat = st.text_input("Patente:").strip()
        c_vtv, c_seg = st.columns(2)
        with c_vtv: 
            adm_venc_vtv = st.date_input("Vencimiento VTV:", value=datetime.now(TZ_AR).date(), format="DD/MM/YYYY")
        with c_seg: 
            adm_venc_seguro = st.date_input("Vencimiento Seguro:", value=datetime.now(TZ_AR).date(), format="DD/MM/YYYY")
            
        if st.button("💾 Agregar Equipo") and adm_pat:
            db.collection("vehiculos").document(adm_pat).set({
                "Vehiculo": adm_pat, 
                "Venc_VTV": adm_venc_vtv.strftime("%d/%m/%Y"), 
                "Venc_Seguro": adm_venc_seguro.strftime("%d/%m/%Y")
            })
            st.cache_resource.clear()
            st.rerun()
            
        df_v = obtener_vehiculos_cached()
        if not df_v.empty:
            st.dataframe(df_v, hide_index=True)
            elim_v = st.selectbox("Borrar Equipo:", [""] + df_v.get("Vehiculo", pd.Series()).tolist())
            if st.button("❌ Retirar Unidad") and elim_v: 
                db.collection("vehiculos").document(elim_v).delete()
                st.cache_resource.clear()
                st.rerun()

    with t3:
        st.subheader("⚡ Carga Masiva")
        if "msg_masivo_u" in st.session_state: 
            st.success(st.session_state.pop("msg_masivo_u"))
        if "msg_masivo_v" in st.session_state: 
            st.success(st.session_state.pop("msg_masivo_v"))
            
        def limp_f(val):
            v_s = str(val).strip()
            if v_s.lower() in ["nan", "nat", "n/a", "none", "null", ""]: 
                return "N/A"
            try: 
                return pd.to_datetime(val).strftime("%d/%m/%Y")
            except: 
                return "N/A"
                
        arch_u = st.file_uploader("Subir Usuarios (.xlsx/.csv)", type=["xlsx", "csv"])
        if arch_u:
            try:
                if arch_u.name.endswith('.csv'):
                    df_m = pd.read_csv(arch_u, dtype=str)
                else:
                    df_m = pd.read_excel(arch_u, dtype=str)
                    
                df_m.columns = df_m.columns.str.strip().str.upper()
                df_m = df_m.fillna("")
                
                for col in df_m.columns:
                    if "VENC" in col: 
                        df_m[col] = df_m[col].apply(limp_f)
                        
                st.dataframe(df_m.head())
                
                if st.button("🚀 Procesar Usuarios"):
                    br_u = st.progress(0)
                    t_u, proc_u = len(df_m), 0
                    
                    for i, r in df_m.iterrows():
                        d_str = str(r.get("DNI_USUARIO", r.get("DNI", ""))).replace(".0", "").strip()
                        
                        if d_str and d_str.lower() not in ["nan", "nat", "n/a", "none", "null", ""]:
                            e_str = str(r.get("EMAIL", "")).strip().lower() or f"{d_str}@marbar.com"
                            rol_ex = str(r.get("ROL", "")).strip().upper()
                            r_of = "Conductor"
                            
                            if any(x in rol_ex for x in ["SUPERVISOR", "COORDINADOR", "INGENIERO"]): 
                                r_of = "Supervisor / Coordinador / Ingeniero"
                            elif "JEFE" in rol_ex: 
                                r_of = "Jefe de Servicio"
                            elif "GERENCIA" in rol_ex: 
                                r_of = "Gerencia"
                            elif "ADMIN" in rol_ex: 
                                r_of = "ADMIN"
                                
                            try: 
                                auth.create_user(email=e_str, password=''.join(random.choices(string.ascii_letters + string.digits, k=16)))
                            except Exception: 
                                pass 
                                
                            if "@marbar.com" not in e_str or "admin" in e_str:
                                try: 
                                    requests.post(f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY.strip()}", json={"requestType": "PASSWORD_RESET", "email": e_str})
                                except Exception: 
                                    pass
                                    
                            db.collection("usuarios").document(d_str).set({
                                "DNI_Usuario": d_str, 
                                "Nombre": str(r.get("NOMBRE", "")).strip() or "Sin Nombre", 
                                "Email": e_str, 
                                "Regional": str(r.get("REGIONAL", "")).strip() or "N/A", 
                                "Base": str(r.get("BASE", "")).strip() or "N/A", 
                                "Rol": r_of, 
                                "Sector": str(r.get("SECTOR", "")).strip() or "N/A", 
                                "Venc_Licencia": str(r.get("VENC_LICENCIA", "N/A")), 
                                "Venc_Defensiva": str(r.get("VENC_DEFENSIVA", "N/A")), 
                                "Venc_Def_Chile": str(r.get("VENC_DEF_CHILE", "N/A"))
                            })
                            proc_u += 1
                        br_u.progress((i + 1) / t_u)
                        
                    st.cache_resource.clear()
                    st.session_state["msg_masivo_u"] = f"✅ ¡{proc_u} perfiles operativos guardados de {t_u} filas!"
                    st.rerun()
            except Exception as e_r: 
                st.error(f"Error lectura: {e_r}")

        arch_v = st.file_uploader("Subir Flota (.xlsx/.csv)", type=["xlsx", "csv"])
        if arch_v:
            try:
                if arch_v.name.endswith('.csv'):
                    df_mv = pd.read_csv(arch_v, dtype=str)
                else:
                    df_mv = pd.read_excel(arch_v, dtype=str)
                    
                df_mv.columns = df_mv.columns.str.strip().str.upper()
                df_mv = df_mv.fillna("")
                
                for col in df_mv.columns:
                    if "VENC" in col: 
                        df_mv[col] = df_mv[col].apply(limp_f)
                        
                st.dataframe(df_mv.head())
                
                if st.button("🚀 Procesar Vehículos"):
                    br_v = st.progress(0)
                    t_v, p_v = len(df_mv), 0
                    
                    for i, r in df_mv.iterrows():
                        v_str = str(r.get("VEHICULO", "")).strip()
                        if v_str and v_str.lower() not in ["nan", "nat", "n/a", "none", "null", ""]:
                            db.collection("vehiculos").document(v_str).set({
                                "Vehiculo": v_str, 
                                "Venc_VTV": str(r.get("VENC_VTV", "N/A")), 
                                "Venc_SEGURO": str(r.get("VENC_SEGURO", "N/A"))
                            })
                            p_v += 1
                        br_v.progress((i + 1) / t_v)
                        
                    st.cache_resource.clear()
                    st.session_state["msg_masivo_v"] = f"✅ ¡{p_v} vehículos guardados!"
                    st.rerun()
            except Exception as e_rv: 
                st.error(f"Error lectura: {e_rv}")
