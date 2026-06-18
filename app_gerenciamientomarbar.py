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
    #MainMenu {{visibility: hidden;}}
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
    if fecha_fin in ["En curso", "Pendiente", "N/A", "", None]:
        return "No finalizado"
    
    try:
        formato = "%d/%m/%Y %H:%M:%S"
        inicio = datetime.strptime(fecha_inicio, formato)
        fin = datetime.strptime(fecha_fin, formato)
        diferencia = fin - inicio
        segundos = int(diferencia.total_seconds())
        
        if segundos < 0: return "Error de fechas"
            
        horas, resto = divmod(segundos, 3600)
        minutos, _ = divmod(resto, 60)
        return f"{horas:02d}:{minutos:02d} Hs"
    except Exception:
        return "Error de cálculo"

def generar_ficha_html(v_data):
    def ordenar_por_numero(texto):
        try: return int(texto.split(".")[0])
        except: return 99
    
    eq_html = ""
    chk_eq = v_data.get('Checklist_Eq', {})
    if chk_eq:
        for k in sorted(chk_eq.keys(), key=ordenar_por_numero):
            v = chk_eq[k]
            color = "#16a34a" if v == "Sí" else ("#dc2626" if v == "No" else "#64748b")
            eq_html += f'<tr><td style="padding: 4px; border-bottom: 1px solid #f1f5f9; font-size: 9pt;">{k}</td><td style="text-align: right; font-weight: bold; width: 15%; color: {color};">{str(v).upper()}</td></tr>'
    else: eq_html = "<tr><td colspan='2'>Sin datos</td></tr>"

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
            <tr><th>Conductor</th><td>{v_data.get('Conductor')}</td><th>Unidad</th><td>{v_data.get('Vehiculo')}</td></tr>
            <tr><th>Sector/Cargo</th><td>{v_data.get('Sector')} / {v_data.get('Cargo')}</td><th>Regional</th><td>{v_data.get('Regional')}</td></tr>
            <tr><th>Fecha Confección</th><td colspan="3">{v_data.get('Fecha')}</td></tr>
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
        st.info("Ingrese sus credenciales de Firebase para acceder a la plataforma operativa.")
        with st.form("form_login"):
            correo_login = st.text_input("Correo Electrónico:").strip().lower()
            pass_login = st.text_input("Contraseña:", type="password")
            btn_ingresar = st.form_submit_button("Ingresar al Sistema")
            
        if btn_ingresar:
            if not correo_login or not pass_login:
                st.error("⛔ Ingrese correo y contraseña.")
            else:
                url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
                payload = {"email": correo_login, "password": pass_login, "returnSecureToken": True}
                respuesta = requests.post(url, json=payload)
                
                if respuesta.status_code == 200:
                    usuarios_ref = db.collection("usuarios").where("Email", "==", correo_login).stream()
                    usuario_encontrado = None
                    for u in usuarios_ref:
                        usuario_encontrado = u.to_dict()
                        break
                    
                    if usuario_encontrado:
                        st.session_state.update({
                            "usuario_actual": usuario_encontrado.get("Rol", "Conductor"), 
                            "nombre_empleado": usuario_encontrado.get("Nombre", "Empleado MARBAR"), 
                            "sector_empleado": usuario_encontrado.get("Sector", "Sin Sector"), 
                            "regional_empleado": usuario_encontrado.get("Regional", "No asignada"),
                            "base_empleado": usuario_encontrado.get("Base", "No asignada"), # <--- NUEVO
                            "venc_licencia": usuario_encontrado.get("Venc_Licencia", "N/A"),
                            "venc_defensiva": usuario_encontrado.get("Venc_Defensiva", "N/A"),
                            "venc_def_chile": usuario_encontrado.get("Venc_Def_Chile", "N/A"),
                            "email_empleado": correo_login,
                            "paso_actual": "Menu"
                        })
                        st.rerun()
                        
                    elif correo_login == "admin@marbar.com":
                        st.session_state.update({
                            "usuario_actual": "ADMIN", 
                            "nombre_empleado": "Administrador", 
                            "sector_empleado": "Gerencia", 
                            "regional_empleado": "Sede Central",
                            "base_empleado": "Sede Central", # <--- NUEVO
                            "venc_licencia": "N/A",
                            "venc_defensiva": "N/A",
                            "venc_def_chile": "N/A",
                            "email_empleado": correo_login,
                            "paso_actual": "Menu"
                        })
                        st.rerun()
                    else:
                        st.error(f"⛔ El correo **{correo_login}** no tiene un perfil operativo asignado. Contacte al administrador.")
                else:
                    st.error("⛔ Correo o contraseña incorrectos. Verifique sus datos.")

    with tab_recupero:
        st.write("Si es su primer ingreso o ha olvidado su clave, ingrese su correo corporativo. Le enviaremos un enlace oficial para configurar su nueva contraseña.")
        correo_configurar = st.text_input("Correo Registrado:", key="txt_correo_config").strip().lower()
        if st.button("📧 Enviar Enlace de Configuración", use_container_width=True):
            if correo_configurar != "":
                
                # --- NUEVA LÓGICA INTELIGENTE: CREACIÓN BAJO DEMANDA ---
                # 1. Verificamos si el usuario EXISTE en nuestra base de datos (Firestore)
                usuarios_ref = db.collection("usuarios").where("Email", "==", correo_configurar).stream()
                usuario_db = None
                for u in usuarios_ref:
                    usuario_db = u.to_dict()
                    break
                
                # Si el usuario está en la base de datos (o es el admin) avanzamos
                if usuario_db or correo_configurar == "admin@marbar.com":
                    
                    # 2. Forzamos la creación de la bóveda de Auth (por si Firebase lo bloqueó en la carga masiva)
                    try:
                        pass_temporal = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
                        auth.create_user(email=correo_configurar, password=pass_temporal)
                    except Exception:
                        pass # Si ya existía, simplemente lo ignora de forma silenciosa
                        
                    # 3. Ahora sí, enviamos el correo oficial de configuración
                    url_reset = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
                    payload_reset = {"requestType": "PASSWORD_RESET", "email": correo_configurar}
                    res_reset = requests.post(url_reset, json=payload_reset)
                    
                    if res_reset.status_code == 200:
                        st.success("📩 ¡Enlace enviado con éxito! Revise su bandeja de entrada (o la carpeta Spam) para establecer la contraseña.")
                    else:
                        st.error("⛔ Hubo un error de conexión con los servidores de Google al intentar enviar el correo.")
                else:
                    st.error("⛔ El correo ingresado NO figura en la base de datos de empleados de MARBAR. Comuníquese con la gerencia.")
            else:
                st.error("Por favor, escriba un correo electrónico válido.") 

# --- WORKFLOW PRINCIPAL ---

# 1. MENÚ PRINCIPAL
if st.session_state["paso_actual"] == "Menu":
    st.subheader(f"Panel Operativo - Bienvenido, {st.session_state['nombre_empleado']}")
    
    # --- SISTEMA DE ALERTA PROACTIVA DE VENCIMIENTOS DOCUMENTALES ---
    if st.session_state["usuario_actual"] != "ADMIN":
        v_lic = st.session_state.get("venc_licencia", "N/A")
        v_def = st.session_state.get("venc_defensiva", "N/A")
        v_def_chile = st.session_state.get("venc_def_chile", "N/A")
        reg_emp = st.session_state.get("regional_empleado", "N/A").strip().lower()
        hoy_dt = datetime.now(TZ_AR).date()
        
        docs_a_revisar = [("Carnet de Manejo", v_lic), ("Curso de Conducción Defensiva", v_def)]
        
        if reg_emp == "chile":
            docs_a_revisar.append(("Manejo Defensivo (Chile)", v_def_chile))
            
        for tipo_doc, fecha_str in docs_a_revisar:
            if fecha_str and fecha_str != "N/A":
                try:
                    fecha_venc = datetime.strptime(fecha_str, "%d/%m/%Y").date()
                    dias_restantes = (fecha_venc - hoy_dt).days
                    
                    if dias_restantes < 0:
                        st.error(f"🚨 **VENCIMIENTO CRÍTICO:** Su **{tipo_doc}** caducó hace {abs(dias_restantes)} días ({fecha_str}). Gestione la renovación de forma urgente.")
                    elif dias_restantes <= 30:
                        st.warning(f"⚠️ **AVISO DE VENCIMIENTO:** Su **{tipo_doc}** vencerá en {dias_restantes} días ({fecha_str}).")
                except Exception:
                    pass
    
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
        viajes_activos = db.collection(COLECCION_VIAJES).where("Conductor", "==", st.session_state["nombre_empleado"]).where("Estado_Viaje", "in", ["En viaje", "En espera"]).stream()
        lista_activos = []
        for d in viajes_activos:
            lista_activos.append(d.to_dict())
            
        if lista_activos:
            st.info("📍 Estado de su viaje actual:")
            for v in lista_activos:
                with st.container(border=True):
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
            documentacion_vencida = False
            if st.session_state["usuario_actual"] != "ADMIN":
                v_lic = st.session_state.get("venc_licencia", "N/A")
                v_def = st.session_state.get("venc_defensiva", "N/A")
                v_def_chile = st.session_state.get("venc_def_chile", "N/A")
                reg_emp = st.session_state.get("regional_empleado", "N/A").strip().lower()
                hoy_dt = datetime.now(TZ_AR).date()
                
                fechas_check = [v_lic, v_def]
                if reg_emp == "chile":
                    fechas_check.append(v_def_chile)
                
                for fecha_str in fechas_check:
                    if fecha_str and fecha_str != "N/A":
                        try:
                            fecha_venc = datetime.strptime(fecha_str, "%d/%m/%Y").date()
                            if (fecha_venc - hoy_dt).days < 0:
                                documentacion_vencida = True
                                break
                        except Exception:
                            pass
                            
            if documentacion_vencida:
                st.error("⛔ **ACCESO DENEGADO:** Tiene documentación habilitante (Nacional o Internacional) vencida. Por normativas de seguridad, el sistema bloqueó la creación de nuevos viajes.")
            else:
                st.session_state["paso_actual"] = "Test_Conductor"
                st.rerun()
            
    with col_menu2:
        if st.button("📜 VER MI HISTORIAL", use_container_width=True): 
            st.session_state["paso_actual"] = "Historial"
            st.rerun()

# 2. TEST DE FATIGA
elif st.session_state["paso_actual"] == "Test_Conductor":
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
                st.session_state["test_conductor"] = "Aprobado"
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
        "5. Curso conducción Defensiva Conductor"
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
    nombre_conductor = st.session_state["nombre_empleado"]
    regional_usuario = st.session_state.get("regional_empleado", "No asignada")
    base_usuario = st.session_state.get("base_empleado", "No asignada") # <--- NUEVO
    
    mapa_autoridad = {
        "Conductor": 0, "Supervisor / Coordinador / Ingeniero": 1, 
        "Jefe de Servicio": 2, "Gerencia": 3, "ADMIN": 3
    }
    nivel_aprobacion_usuario = mapa_autoridad.get(rol_usuario, 0)
    
    st.markdown("### 1. Datos Generales")
    st.info(f"👤 **Conductor:** {nombre_conductor} | **Regional:** {regional_usuario} | **Base:** {base_usuario} | **Sector:** {sector_usuario}") # <--- ACTUALIZADO

    df_flota = obtener_vehiculos()
    if not df_flota.empty: opciones_flota = df_flota["Vehiculo"].tolist()
    else: opciones_flota = ["⚠️ Cargar flota en Admin"]
        
    vehiculo_sel = st.selectbox("Unidad:", opciones_flota)

    # --- VALIDACIÓN DE DOCUMENTACIÓN DEL VEHÍCULO ---
    vehiculo_inhabilitado = False
    if vehiculo_sel != "⚠️ Cargar flota en Admin" and not df_flota.empty:
        datos_vehiculo = df_flota[df_flota["Vehiculo"] == vehiculo_sel].iloc[0]
        v_vtv = datos_vehiculo.get("Venc_VTV", "N/A")
        v_seg = datos_vehiculo.get("Venc_Seguro", "N/A")
        hoy_dt = datetime.now(TZ_AR).date()
        
        for doc_name, doc_date in [("VTV", v_vtv), ("Seguro", v_seg)]:
            if doc_date and doc_date != "N/A":
                try:
                    fecha_v = datetime.strptime(doc_date, "%d/%m/%Y").date()
                    if (fecha_v - hoy_dt).days < 0:
                        vehiculo_inhabilitado = True
                        st.error(f"🚨 **UNIDAD INHABILITADA:** El vehículo seleccionado tiene el **{doc_name}** vencido desde el {doc_date}. Por normativas de seguridad, no puede iniciar la marcha con este equipo.")
                        break
                except Exception: pass

    with st.expander("\U0001F5FA CONSULTA MAPA DE YACIMIENTOS", expanded=True):
        components.iframe("https://www.google.com/maps/d/u/2/embed?mid=1BPDw99m6vQAC09Kdbw9Onaj5mu-blw4&ehbc=2E312F", height=480)

    col1, col2 = st.columns(2)
    with col1: origen_txt = st.text_input("Origen:")
    with col2: destino_txt = st.text_input("Destino:")
        
    st.write("Duración Estimada del Trayecto:")
    col_dur_h, col_dur_m = st.columns(2)
    
    with col_dur_h: dur_horas = st.number_input("Horas (HH):", min_value=0, max_value=72, value=None, step=1)
    with col_dur_m: dur_minutos = st.number_input("Minutos (MM):", min_value=0, max_value=59, value=None, step=1)
    
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
    if v_pasajeros == "Con pasajeros": pasajeros_detalle = st.text_input("👥 Nombres:")
        
    if v_pasajeros: 
        if v_pasajeros == "Con pasajeros": puntos_totales += 1 
        else: puntos_totales += 5
    
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
    if puntos_totales > 15 and puntos_totales <= 30: nivel_riesgo_calculado = 2
    elif puntos_totales > 30: nivel_riesgo_calculado = 3
        
    if salida_tipo == "Urgencia" and v_horario == "Nocturno": nivel_riesgo_calculado = 3
    
    if nivel_aprobacion_usuario >= nivel_riesgo_calculado:
        color_semaforo = "green"
        aprobacion_estado = "AUTORIZADO (Auto-Aprobado)"
    else:
        if nivel_riesgo_calculado < 3: color_semaforo = "orange"
        else: color_semaforo = "red"
        aprobacion_estado = f"PENDIENTE (Requiere Nivel {nivel_riesgo_calculado})"

    st.markdown("---")
    st.subheader("📋 Resultado")
    if color_semaforo == "green": st.success(f"**{aprobacion_estado}** | Riesgo Nivel {nivel_riesgo_calculado} | {puntos_totales} pts")
    elif color_semaforo == "orange": st.warning(f"**{aprobacion_estado}** | Riesgo Nivel {nivel_riesgo_calculado} | {puntos_totales} pts")
    else: st.error(f"**{aprobacion_estado}** | Riesgo Nivel {nivel_riesgo_calculado} | {puntos_totales} pts")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("⬅️ Volver"): 
            st.session_state["paso_actual"] = "Inspeccion_Vehiculo"
            st.rerun()
            
    with col_btn2:
        if st.button("CONFIRMAR VIAJE"):
            duracion_valida = False
            if dur_horas is not None and dur_minutos is not None:
                if dur_horas > 0 or dur_minutos > 0: duracion_valida = True
            
            campos_ok = all([
                origen_txt.strip() != "", destino_txt.strip() != "", duracion_valida,
                vehiculo_sel != "⚠️ Cargar flota en Admin", not vehiculo_inhabilitado,
                salida_tipo is not None, v_distancia is not None, v_clima is not None, 
                v_pasajeros is not None, v_camino is not None, v_sueno is not None, 
                v_horas_servicio is not None, v_escolta is not None, v_horario is not None, 
                v_comunicacion is not None
            ])
            
            if not campos_ok: st.error("⛔ Faltan datos por responder o la duración de viaje no fue completada.")
            elif v_pasajeros == "Con pasajeros" and pasajeros_detalle.strip() == "": st.error("⚠️ Ingrese nombres de pasajeros.")
            else:
                duracion_final_txt = f"{int(dur_horas):02d}:{int(dur_minutos):02d} Hs"
                nuevo_id = obtener_siguiente_id()
                hora_str = datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S")
                
                alarma_noche = "encendida" if v_horario == "Nocturno" else "apagada"
                aprobacion_db, aprobador_db, fecha_aprobacion_db, estado_viaje_db = "🔴 Pendiente", "Pendiente", "Pendiente", "En espera"
                
                if color_semaforo == "green":
                    aprobacion_db, aprobador_db, fecha_aprobacion_db, estado_viaje_db = "🟢 Aprobado", nombre_conductor, hora_str, "En viaje"
                
                datos = {
                    "ID": nuevo_id, "Regional": regional_usuario, "Base": base_usuario, "Fecha": hora_str, # <--- NUEVO
                    "Conductor": nombre_conductor, "Sector": sector_usuario, "Cargo": rol_usuario, 
                    "Vehiculo": vehiculo_sel, "Duracion": duracion_final_txt, "Salida": salida_tipo, 
                    "Alarma Nocturna": alarma_noche, "Origen": origen_txt, "Destino": destino_txt, 
                    "Estado": aprobacion_estado, "Puntaje": puntos_totales, "Nivel": nivel_riesgo_calculado, 
                    "Aprobacion": aprobacion_db, "Aprobador": aprobador_db, "Fecha_Aprobacion": fecha_aprobacion_db, 
                    "Estado_Viaje": estado_viaje_db, "Fecha_Fin": "En curso", 
                    "Test_Conductor": st.session_state.get("test_conductor"), 
                    "Inspeccion_Vehiculo": st.session_state.get("inspeccion_vehiculo"), 
                    "Checklist_Eq": st.session_state.get("resp_eq", {}), 
                    "Checklist_Doc": st.session_state.get("resp_doc", {}), 
                    "R_Distancia": v_distancia, "R_Clima": v_clima, "R_Pasajeros": v_pasajeros, 
                    "Detalle_Pasajeros": pasajeros_detalle, "R_Camino": v_camino, "R_Sueno": v_sueno, 
                    "R_Horas": v_horas_servicio, "R_Escolta": v_escolta, "R_Com": v_comunicacion
                }
                
                if guardar_en_nube(datos):
                    st.balloons()
                    cabecera_wa = f"🟢 *VIAJE AUTO-APROBADO ID {nuevo_id}*" if color_semaforo == "green" else f"🔴 *NUEVA SOLICITUD ID {nuevo_id}*"
                    pie_wa = f"👉 *Aprobado automáticamente por sistema.*" if color_semaforo == "green" else f"👉 *Por favor, apruebe en la plataforma MARBAR.*"
                    tkt = f"{cabecera_wa}\n\n🔹 *Conductor:* {nombre_conductor}\n🔹 *Vehículo:* {vehiculo_sel}\n🔹 *Origen:* {origen_txt}\n🔹 *Destino:* {destino_txt}\n🔹 *Duración:* {duracion_final_txt}\n🔹 *Riesgo:* Nivel {nivel_riesgo_calculado}\n\n{pie_wa}"
                    
                    st.markdown(f"### [📱 ENVIAR TICKET](https://wa.me/?text={urllib.parse.quote(tkt)})")
                    st.success("Guardado Exitoso.")
                    st.session_state["paso_actual"] = "Menu"

# 5. HISTORIAL
elif st.session_state["paso_actual"] == "Historial":
    st.subheader("📜 Historial")
    viajes_historicos = db.collection(COLECCION_VIAJES).stream()
    lista_historica = []
    for doc in viajes_historicos: lista_historica.append(doc.to_dict())
        
    df_h = pd.DataFrame(lista_historica)
    if not df_h.empty:
        if st.session_state["usuario_actual"] != "ADMIN": df_h = df_h[df_h["Conductor"] == st.session_state["nombre_empleado"]]
        if not df_h.empty:
            df_h = df_h.sort_values(by="ID", ascending=False)
            st.dataframe(df_h[['ID', 'Fecha', 'Origen', 'Destino', 'Estado_Viaje']], hide_index=True, use_container_width=True)
            st.markdown("---")
            st.write("#### 📥 Extraer Ficha Auditada (PDF/HTML)")
            
            op_dd = [""]
            for _, r in df_h.iterrows(): op_dd.append(f"{r['ID']} - {r.get('Conductor','')} - {r.get('Fecha','')[:10]}")
            v_sel = st.selectbox("Seleccione viaje:", op_dd)
            
            if v_sel != "":
                id_ext = v_sel.split(" - ")[0]
                d_v = df_h[df_h["ID"].astype(str) == id_ext].iloc[0]
                st.download_button("📥 Descargar Ficha PDF", generar_ficha_html(d_v), f"MARBAR_Auditoria_{id_ext}.html", mime="text/html")
        else: st.info("No hay viajes en el historial.")
            
    if st.button("⬅️ Menú"): 
        st.session_state["paso_actual"] = "Menu"
        st.rerun()

# --- 6. SIDEBAR ---
if st.session_state["usuario_actual"]:
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png", use_column_width=True)
        st.header("📊 SSA & Logística")
        
        if st.button("🔄 Actualizar Pantalla", use_container_width=True): st.rerun()
        if st.button("🚪 Cerrar Sesión", use_container_width=True): 
            st.session_state.clear()
            st.rerun()

    try:
        viajes_sidebar = db.collection(COLECCION_VIAJES).stream()
        lista_sidebar = []
        for d in viajes_sidebar: lista_sidebar.append(d.to_dict())
        df_sb = pd.DataFrame(lista_sidebar)
        
        if not df_sb.empty:
            hoy = datetime.now(TZ_AR).strftime("%d/%m/%Y")
            mes_actual = datetime.now(TZ_AR).strftime("/%m/%Y")
            df_hoy = df_sb[df_sb['Fecha'].str.contains(hoy, na=False)]
            df_mes = df_sb[df_sb['Fecha'].str.contains(mes_actual, na=False)]
            df_p = df_hoy[df_hoy['Aprobacion'].str.contains("Pendiente", na=False)]
            df_r = df_sb[df_sb['Estado_Viaje'] == "En viaje"]

            with st.sidebar:
                st.markdown("---")
                st.subheader("📈 Resumen de Operaciones")
                col_met1, col_met2 = st.columns(2)
                col_met1.metric("Viajes Hoy", str(len(df_hoy)), delta=f"{len(df_p)} pend." if not df_p.empty else "Al día", delta_color="inverse" if not df_p.empty else "normal")
                col_met2.metric("En Ruta", str(len(df_r)))
                col_met3, col_met4 = st.columns(2)
                col_met3.metric("Este Mes", str(len(df_mes)))
                col_met4.metric("Histórico", str(len(df_sb)))
            
            with st.sidebar:
                st.markdown("---")
                st.write("⚠️ **Pendientes (Hoy):**")
            if not df_p.empty: st.sidebar.dataframe(df_p[['Conductor', 'Destino']], hide_index=True)
            else: st.sidebar.write("✅ Al día.")
                
            with st.sidebar:
                st.markdown("---")
                st.write("🚚 **En Ruta:**")
            if not df_r.empty: st.sidebar.dataframe(df_r[['Conductor', 'Destino']], hide_index=True)
            else: st.sidebar.write("✅ Ninguna.")

            with st.sidebar:
                st.markdown("---")
                st.subheader("📜 Ficha Rápida")
            df_sb_ord = df_sb.sort_values(by="ID", ascending=False)
            op_sb = [""]
            for _, r in df_sb_ord.iterrows(): op_sb.append(f"{r['ID']} - {r.get('Conductor','')}")
            with st.sidebar: v_sb = st.selectbox("Buscar ID:", op_sb, key="sb_aud")
            
            if v_sb != "":
                id_sb = v_sb.split(" - ")[0]
                d_sb = df_sb[df_sb["ID"].astype(str) == id_sb].iloc[0]
                with st.sidebar:
                    st.download_button(label="📥 Descargar Ficha PDF", data=generar_ficha_html(d_sb), file_name=f"MARBAR_Auditoria_{id_sb}.html", mime="text/html", key="btn_sb_txt")

            if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador / Ingeniero", "Jefe de Servicio", "Gerencia"]:
                with st.sidebar:
                    st.markdown("---")
                    st.subheader("📊 Consola Excel")
                cols = ['ID', 'Regional', 'Fecha', 'Conductor', 'Sector', 'Cargo', 'Vehiculo', 'Duracion', 'Salida', 'Alarma Nocturna', 'Origen', 'Destino', 'Estado', 'Puntaje', 'Nivel', 'Aprobacion', 'Aprobador', 'Fecha_Aprobacion', 'Estado_Viaje', 'Fecha_Fin']
                for c in cols: 
                    if c not in df_sb.columns: df_sb[c] = "N/A"
                df_ex = df_sb[cols].sort_values(by="ID", ascending=False).copy()
                df_ex['Duracion_Real_Viaje'] = df_ex.apply(lambda r: calcular_duracion_real(r.get('Fecha', ''), r.get('Fecha_Fin', '')), axis=1)
                
                bx = io.BytesIO()
                with pd.ExcelWriter(bx, engine='openpyxl') as wr: 
                    df_ex.to_excel(wr, index=False, sheet_name='Auditoria_Viajes')
                    worksheet = wr.sheets['Auditoria_Viajes']
                    filas = worksheet.max_row
                    columnas = worksheet.max_column
                    if filas > 1:
                        tabla = Table(displayName="TablaAuditoria", ref=f"A1:{get_column_letter(columnas)}{filas}")
                        tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
                        worksheet.add_table(tabla)
                with st.sidebar: st.download_button("📥 Auditoría (Excel)", bx.getvalue(), f"Auditoria_MARBAR_{hoy.replace('/','-')}.xlsx", key="btn_ex")
    except Exception as e_sidebar: pass

# --- 7. BANDEJA APROBACIONES ---
if st.session_state["usuario_actual"] in ["ADMIN", "Supervisor / Coordinador / Ingeniero", "Jefe de Servicio", "Gerencia"]:
    st.markdown("---")
    st.title("📥 Bandeja de Validaciones")
    
    mapa_autoridad = {
        "Conductor": 0, "Supervisor / Coordinador / Ingeniero": 1, 
        "Jefe de Servicio": 2, "Gerencia": 3, "ADMIN": 3
    }
    mi_nivel = mapa_autoridad.get(st.session_state["usuario_actual"], 0)
    
    # Estandarizamos la regional del usuario actual a minúsculas para evitar errores de tipeo
    mi_regional = st.session_state.get("regional_empleado", "").strip().lower()
    
    try:
        solicitudes_pendientes = db.collection(COLECCION_VIAJES).where("Aprobacion", "==", "🔴 Pendiente").stream()
        p_list = []
        
        for doc in solicitudes_pendientes: 
            viaje_data = doc.to_dict()
            viaje_regional = viaje_data.get("Regional", "").strip().lower()
            
            # --- FILTRO REGIONAL ESTRICTO ---
            # ADMIN y Gerencia ven todo. Los demás solo ven los viajes de su propia regional.
            if st.session_state["usuario_actual"] in ["ADMIN", "Gerencia"] or viaje_regional == mi_regional:
                p_list.append(viaje_data)
            
        if p_list:
            for v_p in p_list:
                nivel_viaje = v_p.get("Nivel", 1)
                
                # Agregamos la Regional a la tarjeta visual para mayor claridad
                with st.expander(f"🚨 ID: {v_p['ID']} | Conductor: {v_p['Conductor']} | Base: {v_p.get('Regional', 'N/A')} | Riesgo Nivel {nivel_viaje}"):
                    st.write(f"**Ruta:** {v_p['Origen']} -> {v_p['Destino']} ({v_p['Puntaje']} pts)")
                    
                    if mi_nivel >= nivel_viaje:
                        if st.button(f"✍️ Aprobar {v_p['ID']}", key=f"btn_ap_{v_p['ID']}"):
                            db.collection(COLECCION_VIAJES).document(str(v_p['ID'])).update({
                                "Aprobacion": "🟢 Aprobado", "Aprobador": st.session_state["nombre_empleado"], 
                                "Fecha_Aprobacion": datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M:%S"), "Estado_Viaje": "En viaje"
                            })
                            st.rerun()
                    else: 
                        st.error(f"🔒 Usted es {st.session_state['usuario_actual']} (Nivel {mi_nivel}). Este gerenciamiento exige firma de Nivel {nivel_viaje}.")
        else: 
            st.info("✅ Bandeja limpia para su alcance operativo.")
            
    except Exception as e_bandeja: 
        pass

# --- 8. ADMIN ---
if st.session_state["usuario_actual"] == "ADMIN":
    st.markdown("---")
    st.title("⚙️ Consola Admin")
    t1, t2, t3 = st.tabs(["👥 Usuarios", "🚘 Flota", "⚡ Carga Masiva"])
    
    with t1:
        st.info("💡 Creación manual de perfiles operativos. El sistema enviará un correo automático de configuración al empleado.")
        adm_email = st.text_input("Correo Electrónico Oficial:").strip().lower()
        adm_nombre = st.text_input("Nombre y Apellido Real:").strip()
        adm_dni = st.text_input("DNI:").strip()
        col_reg_base = st.columns(2)
        with col_reg_base[0]: adm_regional = st.text_input("Regional (Ej: Neuquén, Chile):").strip()
        with col_reg_base[1]: adm_base = st.text_input("Base Operativa (Ej: Base Cipolletti):").strip()
        adm_sector = st.selectbox("Sector:", ["Higiene y Seguridad", "Logistica", "Fluidos", "Control de solidos", "Mantenimiento", "Gerencia", "Completacion"])
        adm_rol = st.selectbox("Rol:", ["Conductor", "Supervisor / Coordinador / Ingeniero", "Jefe de Servicio", "Gerencia", "ADMIN"])
        
        col_v1, col_v2, col_v3 = st.columns(3)
        with col_v1: adm_venc_lic = st.date_input("Venc. Carnet Manejo:", value=datetime.now(TZ_AR).date(), format="DD/MM/YYYY")
        with col_v2: adm_venc_def = st.date_input("Venc. Defensiva:", value=datetime.now(TZ_AR).date(), format="DD/MM/YYYY")
        with col_v3: adm_venc_def_chile = st.date_input("Venc. Defensiva Chile:", value=datetime.now(TZ_AR).date(), format="DD/MM/YYYY")
        
        if st.button("💾 Asignar Perfil Operativo"):
            if adm_email != "" and adm_nombre != "" and adm_dni != "" and adm_regional != "" and adm_base != "":
                try:
                    try:
                        pass_temporal = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
                        auth.create_user(email=adm_email, password=pass_temporal)
                        url_reset = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
                        requests.post(url_reset, json={"requestType": "PASSWORD_RESET", "email": adm_email}) # <--- CORREGIDO: Usando dos puntos
                    except Exception: pass
                    
                    db.collection("usuarios").document(adm_dni).set({
                        "DNI_Usuario": adm_dni, "Nombre": adm_nombre, "Email": adm_email, "Regional": adm_regional, "Base": adm_base,
                        "Rol": adm_rol, "Sector": adm_sector, 
                        "Venc_Licencia": adm_venc_lic.strftime("%d/%m/%Y"),
                        "Venc_Defensiva": adm_venc_def.strftime("%d/%m/%Y"),
                        "Venc_Def_Chile": adm_venc_def_chile.strftime("%d/%m/%Y")
                    })
                    st.success(f"✅ ¡Perfil asignado con éxito! Se ha enviado un correo a {adm_email} para configurar la clave.")
                    st.rerun()
                except Exception as e: st.error(f"Error de Firebase: {e}")
            else: st.error("Complete todos los campos de texto, incluyendo la Regional y la Base.")
                
        st.markdown("---")
        st.subheader("👥 Perfiles Operativos Registrados")
        df_u = obtener_usuarios()
        if not df_u.empty:
            st.dataframe(df_u, hide_index=True, use_container_width=True)
        else:
            st.info("ℹ️ No se detectan perfiles operativos registrados en la colección de Firestore.")
            
        lista_borrar_u = [""]
        if not df_u.empty and "DNI_Usuario" in df_u.columns:
            for index, row in df_u.iterrows():
                if row.get("Rol") != "ADMIN" and row.get("Email") != "admin@marbar.com": 
                    lista_borrar_u.append(str(row["DNI_Usuario"]))
        elim_u = st.selectbox("Borrar Perfil Operativo (DNI):", lista_borrar_u)
        if st.button("❌ Dar de Baja"): 
            if elim_u.strip() != "": 
                db.collection("usuarios").document(elim_u.strip()).delete()
                st.rerun()

    with t2:
        st.info("💡 Agregue las unidades de la flota y su documentación. El sistema bloqueará automáticamente los viajes si la VTV o el Seguro están vencidos.")
        adm_pat = st.text_input("Patente / Interno:").strip()
        col_vtv, col_seg = st.columns(2)
        with col_vtv: adm_venc_vtv = st.date_input("Vencimiento VTV:", value=datetime.now(TZ_AR).date(), format="DD/MM/YYYY")
        with col_seg: adm_venc_seguro = st.date_input("Vencimiento Seguro:", value=datetime.now(TZ_AR).date(), format="DD/MM/YYYY")
        
        if st.button("💾 Agregar Equipo"):
            if adm_pat != "": 
                db.collection("vehiculos").document(adm_pat).set({"Vehiculo": adm_pat, "Venc_VTV": adm_venc_vtv.strftime("%d/%m/%Y"), "Venc_Seguro": adm_venc_seguro.strftime("%d/%m/%Y")})
                st.success(f"Unidad {adm_pat} guardada correctamente.")
                st.rerun()
                
        df_v = obtener_vehiculos()
        if not df_v.empty:
            st.dataframe(df_v, hide_index=True)
            lista_borrar_v = [""]
            for vh in df_v["Vehiculo"].tolist(): lista_borrar_v.append(vh)
            elim_v = st.selectbox("Borrar Equipo:", lista_borrar_v)
            if st.button("❌ Retirar Unidad"): 
                if elim_v.strip() != "": 
                    db.collection("vehiculos").document(elim_v.strip()).delete()
                    st.rerun()

    with t3:
        st.subheader("⚡ Carga Masiva de Datos")
        
        # Muestra mensajes de éxito diferidos despues del rerun
        if "msg_masivo_u" in st.session_state:
            st.success(st.session_state["msg_masivo_u"])
            del st.session_state["msg_masivo_u"]
            
        # Muestra la lista de errores si Firestore rechazó alguna fila
        if "err_masivo_u" in st.session_state:
            st.error("❌ Alerta: Los siguientes registros arrojaron errores en la base de datos:")
            for err in st.session_state["err_masivo_u"]:
                st.write(err)
            del st.session_state["err_masivo_u"]
        
        if "msg_masivo_v" in st.session_state:
            st.success(st.session_state["msg_masivo_v"])
            del st.session_state["msg_masivo_v"]
        
        def limpiar_fecha(val):
            v_str = str(val).strip()
            if v_str.lower() in ["nan", "nat", "n/a", "none", "null", ""]:
                return "N/A"
            try:
                return pd.to_datetime(val).strftime("%d/%m/%Y")
            except:
                return "N/A"
                
        st.markdown("#### 👥 1. Carga de Usuarios")
        st.info("Columnas necesarias: DNI_USUARIO, NOMBRE, EMAIL, REGIONAL, BASE, ROL, SECTOR, VENC_LICENCIA, VENC_DEFENSIVA, VENC_DEF_CHILE")
        
        archivo_usuarios = st.file_uploader("Subir planilla (.xlsx o .csv)", type=["xlsx", "csv"], key="up_usu")
        
        if archivo_usuarios is not None:
            try:
                if archivo_usuarios.name.endswith('.csv'):
                    df_masivo_u = pd.read_csv(archivo_usuarios, dtype=str) # <-- Forzamos lectura como string desde el inicio
                else:
                    df_masivo_u = pd.read_excel(archivo_usuarios, dtype=str) # <-- Forzamos lectura como string desde el inicio
                    
                df_masivo_u.columns = df_masivo_u.columns.str.strip().str.upper()
                
                # Reemplazamos todos los valores NaN/nulos por strings vacíos para evitar que Firebase reciba floats
                df_masivo_u = df_masivo_u.fillna("")
                
                for col in df_masivo_u.columns:
                    if "VENC" in col: 
                        df_masivo_u[col] = df_masivo_u[col].apply(limpiar_fecha)
                        
                st.dataframe(df_masivo_u.head())
                
                if st.button("🚀 Procesar Usuarios en Firebase"):
                    barra_u = st.progress(0)
                    tot_u = len(df_masivo_u)
                    procesados_reales = 0
                    lista_errores = []
                    
                    url_reset = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
                    
                    for i, row in df_masivo_u.iterrows():
                        dni_bruto = row.get("DNI_USUARIO", row.get("DNI", ""))
                        # Limpiamos decimales fantasmas que Python agrega (.0)
                        if isinstance(dni_bruto, str) and dni_bruto.endswith(".0"):
                            dni_bruto = dni_bruto[:-2]
                            
                        dni_str = str(dni_bruto).strip()
                        
                        if dni_str and dni_str.lower() not in ["nan", "nat", "n/a", "none", "null", ""]:
                            email_str = str(row.get("EMAIL", "")).strip().lower()
                            es_correo_real = True
                            if email_str in ["nan", "nat", "n/a", "none", "null", ""]:
                                email_str = f"{dni_str}@marbar.com"
                                es_correo_real = False
                                
                            rol_excel = str(row.get("ROL", "")).strip().upper()
                            rol_oficial = "Conductor"
                            if any(x in rol_excel for x in ["SUPERVISOR", "COORDINADOR", "INGENIERO"]): rol_oficial = "Supervisor / Coordinador / Ingeniero"
                            elif "JEFE" in rol_excel: rol_oficial = "Jefe de Servicio"
                            elif "GERENCIA" in rol_excel: rol_oficial = "Gerencia"
                            elif "ADMIN" in rol_excel: rol_oficial = "ADMIN"

                            try:
                                pass_temporal = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
                                auth.create_user(email=email_str, password=pass_temporal)
                            except Exception: 
                                pass 
                            
                            if es_correo_real:
                                try:
                                    requests.post(url_reset, json={"requestType": "PASSWORD_RESET", "email": email_str})
                                except Exception:
                                    pass
                                
                            try:
                                db.collection("usuarios").document(dni_str).set({
                                    "DNI_Usuario": str(dni_str), 
                                    "Nombre": str(row.get("NOMBRE", "")).strip() or "Sin Nombre", 
                                    "Email": str(email_str), 
                                    "Regional": str(row.get("REGIONAL", "")).strip() or "N/A", 
                                    "Base": str(row.get("BASE", "")).strip() or "N/A", 
                                    "Rol": str(rol_oficial), 
                                    "Sector": str(row.get("SECTOR", "")).strip() or "N/A",
                                    "Venc_Licencia": str(row.get("VENC_LICENCIA", "N/A")),
                                    "Venc_Defensiva": str(row.get("VENC_DEFENSIVA", "N/A")),
                                    "Venc_Def_Chile": str(row.get("VENC_DEF_CHILE", "N/A"))
                                })
                                procesados_reales += 1
                            except Exception as e_db: 
                                lista_errores.append(f"Fila {i+2} (DNI {dni_str}): {str(e_db)}")
                                
                        barra_u.progress((i + 1) / tot_u)
                        
                    st.session_state["msg_masivo_u"] = f"✅ ¡Se procesaron {tot_u} filas del archivo y se asentaron {procesados_reales} perfiles en la base de datos!"
                    if lista_errores:
                        st.session_state["err_masivo_u"] = lista_errores
                        
                    st.rerun()
                    
            except Exception as e_read:
                st.error(f"Error al leer el archivo: {e_read}")

        st.markdown("---")
        st.markdown("#### 🚘 2. Carga de Vehículos")
        archivo_vehiculos = st.file_uploader("Subir planilla de flota (.xlsx o .csv)", type=["xlsx", "csv"], key="up_veh")
        
        if archivo_vehiculos is not None:
            try:
                if archivo_vehiculos.name.endswith('.csv'):
                    df_masivo_v = pd.read_csv(archivo_vehiculos, dtype=str) # <-- Forzamos lectura como string desde el inicio
                else:
                    df_masivo_v = pd.read_excel(archivo_vehiculos, dtype=str) # <-- Forzamos lectura como string desde el inicio
                    
                df_masivo_v.columns = df_masivo_v.columns.str.strip().str.upper()
                df_masivo_v = df_masivo_v.fillna("")
                
                for col in df_masivo_v.columns:
                    if "VENC" in col: 
                        df_masivo_v[col] = df_masivo_v[col].apply(limpiar_fecha)
                        
                st.dataframe(df_masivo_v.head())
                
                if st.button("🚀 Procesar Vehículos en Firebase"):
                    barra_v = st.progress(0)
                    tot_v = len(df_masivo_v)
                    v_procesados = 0
                    
                    for i, row in df_masivo_v.iterrows():
                        veh_str = str(row.get("VEHICULO", "")).strip()
                        if veh_str and veh_str.lower() not in ["nan", "nat", "n/a", "none", "null", ""]:
                            try:
                                db.collection("vehiculos").document(veh_str).set({
                                    "Vehiculo": str(veh_str), 
                                    "Venc_VTV": str(row.get("VENC_VTV", "N/A")),
                                    "Venc_SEGURO": str(row.get("VENC_SEGURO", "N/A"))
                                })
                                v_procesados += 1
                            except Exception: pass
                        barra_v.progress((i + 1) / tot_v)
                        
                    st.session_state["msg_masivo_v"] = f"✅ ¡Se leyeron {tot_v} filas y se guardaron {v_procesados} vehículos!"
                    st.rerun()
            except Exception as e_read_v:
                st.error(f"Error al leer el archivo de flota: {e_read_v}")
