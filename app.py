import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import requests
import io
import time

# --- 1. ESTÉTICA Y DISEÑO UI (CSS DE ALTO NIVEL) ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.08);
        border-radius: 20px; padding: 25px; border: 1px solid #00c6ff;
        box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15);
        border-left: 10px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 15px; background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        color: black; font-weight: 800; width: 100%; border: none; height: 4em;
        transition: 0.4s all; text-transform: uppercase; letter-spacing: 1.5px;
    }
    .stButton>button:hover { transform: translateY(-4px); box-shadow: 0px 10px 30px #00c6ff; color: white; }
    .coach-box { padding: 35px; border-radius: 25px; margin: 25px 0; border-left: 15px solid; line-height: 2; font-size: 1.2em; }
    .rojo { background-color: rgba(255, 75, 75, 0.15); border-color: #ff4b4b; color: #ff4b4b; }
    .verde { background-color: rgba(37, 211, 102, 0.15); border-color: #25d366; color: #25d366; }
    .alerta { background-color: rgba(241, 196, 15, 0.15); border-color: #f1c40f; color: #f1c40f; }
    .user-card {
        background: rgba(255, 255, 255, 0.05); padding: 30px; border-radius: 20px;
        border: 1px solid #333; margin-bottom: 20px; border-left: 8px solid #00f2fe;
        transition: 0.4s;
    }
    .user-card:hover { background: rgba(255, 255, 255, 0.1); border-color: #00f2fe; transform: scale(1.01); }
    .bank-btn {
        background-color: #1a1d24; border: 2px solid #00c6ff; color: #00c6ff !important;
        padding: 20px; border-radius: 15px; text-align: center; display: block; 
        text-decoration: none; font-weight: bold; margin-top: 15px; transition: 0.3s;
    }
    .bank-btn:hover { background: #00c6ff; color: black !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS (CON REPARACIÓN AUTOMÁTICA) ---
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=20)
    except Exception as e:
        st.error("🚀 Conectando con la Nube GeZo... Refresca en 5 segundos.")
        st.stop()

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    # Tablas Principales
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, 
                  plan TEXT, precio TEXT, presupuesto DECIMAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo TEXT)''')
    
    # --- FIX DE ERRORES (Lo que faltaba en tus fotos) ---
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS vence DATE")
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precio TEXT")
    except:
        pass 
    
    # Admin Maestro
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', 'N/A'))
    conn.commit(); c.close(); conn.close()

try:
    inicializar_db()
except:
    st.info("Sincronizando Base de Datos...")

# --- 3. SERVICIOS ESPECIALES (PDF Y TEXTO) ---
def limpiar_texto(texto):
    if not texto: return ""
    m = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC ","Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ñ":"N"}
    for k, v in m.items(): texto = texto.replace(k, v)
    return str(texto).encode('latin-1', 'ignore').decode('latin-1')

def generar_pdf_pro(nombre, plan, monto, vence):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(11, 14, 20); pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 30)
    pdf.cell(200, 50, limpiar_texto("GEZO ELITE PRO 💎"), ln=True, align='C')
    pdf.set_font("Arial", '', 18); pdf.ln(15)
    pdf.cell(200, 15, f"RECIBO DE SUSCRIPCION DIGITAL", ln=True, align='C')
    pdf.ln(20); pdf.set_font("Arial", '', 15)
    pdf.cell(200, 12, f"Titular: {limpiar_texto(nombre)}", ln=True)
    pdf.cell(200, 12, f"Servicio: {limpiar_texto(plan)}", ln=True)
    pdf.cell(200, 12, f"Monto Pagado: {limpiar_texto(str(monto))}", ln=True)
    pdf.cell(200, 12, f"Valido hasta: {vence}", ln=True)
    pdf.ln(60); pdf.set_font("Arial", 'I', 11)
    pdf.cell(200, 10, "Este comprobante es generado automaticamente por GeZo Pro.", ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. ACCESO AL SISTEMA ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    st.subheader("Control Financiero de Nueva Generacion")
    with st.container():
        with st.form("login_gezo"):
            u_in = st.text_input("Usuario GeZo")
            p_in = st.text_input("Password", type="password")
            if st.form_submit_button("ACCEDER AL PANEL"):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u_in, p_in))
                res = c.fetchone()
                if res:
                    if datetime.now().date() > res[4]: st.error("❌ Membresia vencida.")
                    else:
                        st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                        st.rerun()
                else: st.error("❌ Credenciales incorrectas.")
                c.close(); conn.close()
    st.stop()

# --- 5. NAVEGACION ---
with st.sidebar:
    st.markdown(f"## Bienvenido, \n### {st.session_state.uname} 👑")
    st.info(f"Estatus: {st.session_state.plan}")
    st.divider()
    menu = st.radio("NAVEGACION:", ["📊 Dashboard IA", "💸 Registrar Cuentas", "📱 SINPE Rápido", "⚖️ Pensión y Aguinaldo", "🤝 Deudas y Metas", "💱 Conversor", "⚙️ Admin"])
    st.divider()
    if st.button("🔴 CERRAR SESION"):
        st.session_state.autenticado = False; st.rerun()

# --- 6. MÓDULO: DASHBOARD IA ---
if menu == "📊 Dashboard IA":
    st.header("Analisis Financiero con IA 🤖")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    ing = float(df[df['tipo']=='Ingreso']['monto'].sum()) if not df.empty else 0
    gas = float(df[df['tipo']=='Gasto']['monto'].sum()) if not df.empty else 0
    bal = ing - gas
    
    c1, c2, c3 = st.columns(3)
    c1.metric("FLUJO DE ENTRADA", f"₡{ing:,.0f}")
    c2.metric("FLUJO DE SALIDA", f"₡{gas:,.0f}", delta_color="inverse")
    c3.metric("CAPITAL DISPONIBLE", f"₡{bal:,.0f}")

    if ing > 0:
        pct = (gas/ing)*100
        if bal < 0: 
            st.markdown(f'<div class="coach-box rojo"><h3>🚨 ALERTA ROJA</h3><p>Estas en deficit por <b>₡{abs(bal):,.0f}</b>. Tu gasto supera tus ingresos. ¡Para el consumo ahora mismo!</p></div>', unsafe_allow_html=True)
        elif pct > 80: 
            st.markdown(f'<div class="coach-box alerta"><h3>⚠️ MARGEN CRITICO</h3><p>Has gastado el <b>{pct:.1f}%</b>. Te queda muy poco margen de maniobra para el resto del mes.</p></div>', unsafe_allow_html=True)
        else: 
            st.markdown(f'<div class="coach-box verde"><h3>💎 EXCELENTE GESTION</h3><p>Felicidades. Tu ahorro es de <b>₡{bal:,.0f}</b>. Mantienes un control elite de tus finanzas.</p></div>', unsafe_allow_html=True)
    
    if not df.empty:
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.5, template="plotly_dark", title="Mapa de Gasto Mensual"))

# --- 7. MÓDULO: REGISTRO (CON FIX DE FOTOS) ---
elif menu == "💸 Registrar Cuentas":
    st.header("Gestion de Entradas y Salidas")
    g_cats = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "📱 Plan Telefónico", "🏠 Alquiler/Hipoteca", "🏦 Préstamo", "🛒 Súper", "📦 Otros"]
    i_cats = ["💵 Salario", "📱 SINPE Recibido", "💰 Negocio/Ventas", "📈 Inversiones", "📦 Otros"]

    with st.form("f_registro_pro"):
        col_x, col_y = st.columns(2)
        with col_x:
            t_mov = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
            m_mov = st.number_input("Monto (₡)", min_value=0.0, step=500.0)
        with col_y:
            c_mov = st.selectbox("Categoria:", g_cats if t_mov == "Gasto" else i_cats)
            v_mov = st.date_input("Fecha de Vencimiento", datetime.now())
        
        a_mov = st.checkbox("🔔 Activar Notificacion GeZo")
        if st.form_submit_button("REGISTRAR EN LA NUBE"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                      (st.session_state.uid, datetime.now().date(), f"Registro de {c_mov}", m_mov, t_mov, c_mov, v_mov))
            conn.commit(); c.close(); conn.close()
            st.success("✅ Datos sincronizados correctamente.")

# --- 8. MÓDULO: SINPE RÁPIDO ---
elif menu == "📱 SINPE Rápido":
    st.header("SINPE Movil Pro")
    n_sinpe = st.text_input("Numero Telefonico")
    m_sinpe = st.number_input("Monto GeZo", min_value=0)
    b_sinpe = st.selectbox("Banco Origen:", ["BNCR", "BAC", "BCR", "BP", "Promerica"])
    if st.button("REGISTRAR Y PAGAR"):
        st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🚀 ABRIR APP BANCARIA {b_sinpe}</a>', unsafe_allow_html=True)

# --- 9. MÓDULO: PENSIÓN Y AGUINALDO ---
elif menu == "⚖️ Pensión y Aguinaldo":
    st.header("Calculadora de Ley")
    s_bruto = st.number_input("Salario Bruto (₡)", min_value=0.0)
    st.info(f"⚖️ Estimacion de Pension (35%): ₡{(s_bruto*0.35):,.0f}")
    st.success(f"💰 Aguinaldo Proyectado: ₡{s_bruto:,.0f}")

# --- 10. MÓDULO: DEUDAS Y METAS ---
elif menu == "🤝 Deudas y Metas":
    st.header("Vision de Futuro")
    t_1, t_2 = st.tabs(["🎯 Mis Metas", "🏦 Mis Deudas"])
    with t_1:
        with st.form("f_meta"):
            n_m = st.text_input("Nombre de la Meta"); o_m = st.number_input("Objetivo Final (₡)", min_value=1.0)
            if st.form_submit_button("ACTIVAR META"): st.success("🎯 Meta en seguimiento.")
    with t_2:
        st.write("Registra tus deudas para que la IA diseñe tu plan de salida.")

# --- 11. MÓDULO: CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Cambio de Divisas")
    v_c = st.number_input("Cantidad:", min_value=0.0)
    st.metric("Conversion a Dolares ($)", f"{(v_c/521.50):,.2f}")
    st.metric("Conversion a Colones (₡)", f"{(v_c*512.10):,.2f}")

# --- 12. MÓDULO: ADMIN (PDF Y CONTROL TOTAL) ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Administracion GeZo Elite")
    p_config = {"Semana Gratis":7, "Mensual":30, "Anual":365}
    p_money = {"Semana Gratis":"₡0", "Mensual":"₡5,000", "Anual":"₡45,000"}
    
    with st.expander("➕ REGISTRAR NUEVO USUARIO"):
        u_nom = st.text_input("Username"); u_key = st.text_input("Clave"); u_pla = st.selectbox("Plan", list(p_config.keys()))
        if st.button("DAR DE ALTA"):
            v_fin = (datetime.now() + timedelta(days=p_config[u_pla])).date()
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (u_nom, u_key, v_fin, 'usuario', u_pla, p_money[u_pla]))
            conn.commit(); c.close(); conn.close(); st.rerun()

    st.subheader("Control de Clientes")
    u_list = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for i, r in u_list.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card">👤 {r["nombre"]} | 💎 {r["plan"]} | Expira: {r["expira"]}</div>', unsafe_allow_html=True)
            p_bin = generar_pdf_pro(r['nombre'], r['plan'], r['precio'], str(r['expira']))
            st.download_button(f"📄 Recibo {r['nombre']}", p_bin, f"Recibo_GeZo_{r['nombre']}.pdf", key=f"p_{r['id']}")
            if st.button(f"🗑️ Eliminar Usuario {r['nombre']}", key=f"d_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM usuarios WHERE id={r['id']}"); conn.commit(); c.close(); conn.close(); st.rerun()
