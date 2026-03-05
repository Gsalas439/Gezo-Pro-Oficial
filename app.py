import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io
import time

# --- 1. INTERFAZ Y ESTÉTICA ELITE ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.08); border-radius: 20px; padding: 25px; 
        border: 1px solid #00c6ff; box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15); border-left: 10px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 15px; background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        color: black; font-weight: 800; width: 100%; border: none; height: 3.5em; transition: 0.4s all;
    }
    .stButton>button:hover { transform: translateY(-3px); box-shadow: 0px 10px 30px #00c6ff; color: white; }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 20px; border-radius: 15px; border: 1px solid #333; margin-bottom: 15px; border-left: 5px solid #00f2fe; }
    .bank-btn { background-color: #1a1d24; border: 1px solid #00c6ff; color: #00c6ff !important; padding: 15px; border-radius: 12px; text-align: center; display: block; text-decoration: none; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN Y BASE DE DATOS ---
@st.cache_resource
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e:
        st.error(f"Error de base de datos: {e}"); st.stop()

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT, precio TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0)")
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS vence DATE")
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precio TEXT")
    except: pass
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", ('admin', 'admin123', '2099-12-31', 'admin', 'Master', '0'))
    conn.commit(); c.close()

inicializar_db()

# --- 3. UTILIDADES (PDF Y TEXTO) ---
def limpiar_t(t):
    acentos = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC "}
    for k, v in acentos.items(): t = str(t).replace(k, v)
    return t.encode('latin-1', 'ignore').decode('latin-1')

def generar_recibo(n, p, m, v):
    pdf = FPDF(); pdf.add_page(); pdf.set_fill_color(11, 14, 20); pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 25)
    pdf.cell(190, 40, limpiar_t("GEZO ELITE PRO 💎"), ln=True, align='C')
    pdf.set_font("Arial", '', 14); pdf.ln(10)
    pdf.cell(190, 10, f"CLIENTE: {limpiar_t(n)}", ln=True)
    pdf.cell(190, 10, f"PLAN: {limpiar_t(p)}", ln=True)
    pdf.cell(190, 10, f"MONTO: {m}", ln=True)
    pdf.cell(190, 10, f"EXPIRA: {v}", ln=True)
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. ACCESO Y SEGURIDAD ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login"):
        u = st.text_input("Usuario"); k = st.text_input("Clave", type="password")
        if st.form_submit_button("ENTRAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, k))
            res = c.fetchone()
            if res:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                st.rerun()
            else: st.error("❌ Acceso denegado.")
            c.close()
    st.stop()

# --- 5. MENÚ LATERAL ---
with st.sidebar:
    st.markdown(f"### Hola, {st.session_state.uname} 👑")
    menu = st.radio("MENÚ", ["📊 Dashboard", "💸 Registrar Cuentas", "🤝 Metas y Deudas", "📱 SINPE Rápido", "⚙️ Admin"])
    if st.button("Cerrar Sesión"): st.session_state.autenticado = False; st.rerun()

# --- 6. MÓDULO: REGISTRO (CON CAMBIOS DE INGRESOS/EGRESOS Y FECHA) ---
if menu == "💸 Registrar Cuentas":
    st.header("Entradas y Salidas")
    cat_g = ["⚖️ Pensión Alimentaria", "⚡ Recibo Luz", "💧 Recibo Agua", "🏠 Alquiler", "🛒 Súper", "📱 Plan Celular", "🏦 Préstamo", "🚗 Gasolina", "📦 Otros Gastos"]
    cat_i = ["💵 Salario", "💰 Aguinaldo", "📱 SINPE Recibido", "📈 Ventas/Negocio", "🧧 Comisiones", "🚜 Freelance", "🏢 Rentas", "🎁 Regalos", "💸 Cobros", "📦 Otros Ingresos"]
    with st.form("mov_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            tipo = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
            monto = st.number_input("Monto (₡)", min_value=0.0, step=1000.0)
        with col_b:
            categoria = st.selectbox("Categoría:", cat_i if tipo == "Ingreso" else cat_g)
            fecha_pago = st.date_input("Fecha de Pago Correspondiente:", datetime.now())
        nota = st.text_input("Detalle adicional:")
        if st.form_submit_button("GUARDAR EN BITÁCORA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", (st.session_state.uid, datetime.now().date(), f"{categoria}: {nota}", monto, tipo, categoria, fecha_pago))
            conn.commit(); c.close(); st.success("✅ Registro exitoso."); time.sleep(1); st.rerun()

# --- 7. DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("Análisis de Capital")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum()); gas = float(df[df['tipo']=='Gasto']['monto'].sum()); bal = ing - gas
        c1, c2, c3 = st.columns(3)
        c1.metric("INGRESOS", f"₡{ing:,.0f}"); c2.metric("GASTOS", f"₡{gas:,.0f}", delta_color="inverse"); c3.metric("DISPONIBLE", f"₡{bal:,.0f}")
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.5, template="plotly_dark"))
    else: st.info("No hay datos registrados aún.")

# --- 8. METAS Y DEUDAS ---
elif menu == "🤝 Metas y Deudas":
    st.header("Visión Financiera")
    t1, t2 = st.tabs(["🎯 Mis Metas de Ahorro", "🏦 Control de Deudas"])
    with t1:
        with st.form("meta_f"):
            n_m = st.text_input("Objetivo (Ej: Carro)"); o_m = st.number_input("Monto Objetivo", min_value=0.0)
            if st.form_submit_button("AÑADIR META"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n_m, o_m)); conn.commit(); c.close(); st.rerun()
        st.dataframe(pd.read_sql(f"SELECT nombre, objetivo FROM metas WHERE usuario_id={st.session_state.uid}", get_connection()), use_container_width=True)
    with t2:
        with st.form("deuda_f"):
            n_d = st.text_input("Acreedor (Ej: Banco)"); o_d = st.number_input("Monto Deuda", min_value=0.0)
            if st.form_submit_button("AÑADIR DEUDA"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total) VALUES (%s,%s,%s)", (st.session_state.uid, n_d, o_d)); conn.commit(); c.close(); st.rerun()
        st.dataframe(pd.read_sql(f"SELECT nombre, monto_total FROM deudas WHERE usuario_id={st.session_state.uid}", get_connection()), use_container_width=True)

# --- 9. SINPE RÁPIDO ---
elif menu == "📱 SINPE Rápido":
    st.header("Atajo Bancario"); st.text_input("Número de Teléfono"); st.number_input("Monto a enviar")
    st.markdown('<a href="https://www.google.com" target="_blank" class="bank-btn">🚀 ABRIR APLICACIÓN DEL BANCO</a>', unsafe_allow_html=True)

# --- 10. ADMIN (SISTEMA DE RECIBOS Y USUARIOS) ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Panel Master de Clientes")
    with st.expander("➕ REGISTRAR NUEVO CLIENTE"):
        with st.form("admin_form"):
            un = st.text_input("Usuario"); uk = st.text_input("Clave"); up = st.selectbox("Plan", ["Mensual", "Anual"])
            if st.form_submit_button("DAR DE ALTA"):
                vf = (datetime.now() + timedelta(days=30 if up=="Mensual" else 365)).date()
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (un, uk, vf, 'usuario', up, "5000" if up=="Mensual" else "50000")); conn.commit(); c.close(); st.success("Cliente creado."); st.rerun()
    u_list = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for _, r in u_list.iterrows():
        st.markdown(f'<div class="user-card">👤 {r["nombre"]} | {r["plan"]} | Expira: {r["expira"]}</div>', unsafe_allow_html=True)
        rec_pdf = generar_recibo(r['nombre'], r['plan'], r['precio'], str(r['expira']))
        st.download_button(f"📄 Descargar Recibo {r['nombre']}", rec_pdf, f"Recibo_{r['nombre']}.pdf", key=f"pdf_{r['id']}")
        if st.button(f"🗑️ Eliminar a {r['nombre']}", key=f"del_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM usuarios WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()
