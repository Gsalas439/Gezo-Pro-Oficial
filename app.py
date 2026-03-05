import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io
import time

# --- 1. UI & DESIGN MASTER ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")
st.markdown("""<style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] { background: rgba(0, 198, 255, 0.08); border-radius: 20px; padding: 25px; border: 1px solid #00c6ff; box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15); border-left: 10px solid #00c6ff; }
    .stButton>button { border-radius: 15px; background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%); color: black; font-weight: 800; width: 100%; border: none; height: 3.5em; transition: 0.4s all; }
    .stButton>button:hover { transform: translateY(-3px); box-shadow: 0px 10px 30px #00c6ff; color: white; }
    .coach-box { padding: 30px; border-radius: 20px; margin: 20px 0; border-left: 10px solid; line-height: 1.8; }
    .rojo { background-color: rgba(255, 75, 75, 0.1); border-color: #ff4b4b; color: #ff4b4b; }
    .verde { background-color: rgba(37, 211, 102, 0.1); border-color: #25d366; color: #25d366; }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 20px; border-radius: 15px; border: 1px solid #333; margin-bottom: 15px; border-left: 5px solid #00f2fe; }
    .bank-btn { background-color: #1a1d24; border: 1px solid #00c6ff; color: #00c6ff !important; padding: 15px; border-radius: 12px; text-align: center; display: block; text-decoration: none; font-weight: bold; }
</style>""", unsafe_allow_html=True)

# --- 2. DB ENGINE ---
@st.cache_resource
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e: st.error(f"Error: {e}"); st.stop()

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

# --- 3. HELPERS ---
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

# --- 4. AUTH ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro Access")
    with st.form("login"):
        u = st.text_input("Usuario"); k = st.text_input("Contraseña", type="password")
        if st.form_submit_button("ACCEDER"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, k))
            res = c.fetchone()
            if res:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                st.rerun()
            else: st.error("❌ Denegado.")
            c.close()
    st.stop()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown(f"### Bienvenido, \n## {st.session_state.uname} 👑")
    menu = st.radio("MENÚ", ["📊 Dashboard", "💸 Registrar Cuentas", "🤝 Metas y Deudas", "📱 SINPE Rápido", "⚙️ Admin"])
    if st.button("Salir"): st.session_state.autenticado = False; st.rerun()

# --- 6. REGISTRO (CORREGIDO CON NUEVOS INGRESOS Y FECHA) ---
if menu == "💸 Registrar Cuentas":
    st.header("Entradas y Salidas")
    cat_g = ["⚖️ Pensión Alimentaria", "⚡ Recibo Luz", "💧 Recibo Agua", "🏠 Alquiler", "🛒 Súper", "📱 Celular", "🏦 Préstamo", "📦 Otros Gastos"]
    cat_i = ["💵 Salario", "💰 Aguinaldo", "📱 SINPE Recibido", "📈 Ventas", "🧧 Comisiones", "🚜 Freelance", "🏢 Rentas", "🎁 Regalos", "💸 Cobros", "📦 Otros Ingresos"]
    with st.form("mov"):
        c1, c2 = st.columns(2)
        with c1: 
            tipo = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
            monto = st.number_input("Monto (₡)", min_value=0.0)
        with c2: 
            categoria = st.selectbox("Categoría:", cat_i if tipo == "Ingreso" else cat_g)
            fecha_v = st.date_input("Fecha de Pago/Vencimiento:", datetime.now())
        nota = st.text_input("Nota adicional:")
        if st.form_submit_button("GUARDAR EN BITÁCORA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", (st.session_state.uid, datetime.now().date(), f"{categoria}: {nota}", monto, tipo, categoria, fecha_v))
            conn.commit(); c.close(); st.success("✅ Guardado."); time.sleep(1); st.rerun()

# --- 7. DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("Análisis de Capital")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum()); gas = float(df[df['tipo']=='Gasto']['monto'].sum()); bal = ing - gas
        c1, c2, c3 = st.columns(3)
        c1.metric("INGRESOS", f"₡{ing:,.0f}"); c2.metric("GASTOS", f"₡{gas:,.0f}", delta_color="inverse"); c3.metric("DISPONIBLE", f"₡{bal:,.0f}")
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.5, template="plotly_dark"))
    else: st.info("Sin registros.")

# --- 8. METAS Y DEUDAS ---
elif menu == "🤝 Metas y Deudas":
    st.header("Visión Financiera")
    t1, t2 = st.tabs(["🎯 Metas", "🏦 Deudas"])
    with t1:
        with st.form("m"):
            n_m = st.text_input("Meta"); o_m = st.number_input("Monto Meta", min_value=0.0)
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n_m, o_m)); conn.commit(); c.close(); st.rerun()
        st.dataframe(pd.read_sql(f"SELECT nombre, objetivo FROM metas WHERE usuario_id={st.session_state.uid}", get_connection()), use_container_width=True)
    with t2:
        with st.form("d"):
            n_d = st.text_input("Acreedor"); o_d = st.number_input("Deuda Total", min_value=0.0)
            if st.form_submit_button("AÑADIR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total) VALUES (%s,%s,%s)", (st.session_state.uid, n_d, o_d)); conn.commit(); c.close(); st.rerun()
        st.dataframe(pd.read_sql(f"SELECT nombre, monto_total FROM deudas WHERE usuario_id={st.session_state.uid}", get_connection()), use_container_width=True)

# --- 9. SINPE & ADMIN ---
elif menu == "📱 SINPE Rápido":
    st.header("Atajo Bancario"); st.text_input("Número"); st.number_input("Monto")
    st.markdown('<a href="https://www.google.com" target="_blank" class="bank-btn">🚀 ABRIR APP BANCO</a>', unsafe_allow_html=True)

elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Gestión de Clientes")
    with st.expander("➕ NUEVO CLIENTE"):
        with st.form("adm"):
            un = st.text_input("Usuario"); uk = st.text_input("Clave"); up = st.selectbox("Plan", ["Mensual", "Anual"])
            if st.form_submit_button("ALTA"):
                vf = (datetime.now() + timedelta(days=30 if up=="Mensual" else 365)).date()
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (un, uk, vf, 'usuario', up, "5000")); conn.commit(); c.close(); st.success("Creado"); st.rerun()
    u_l = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for i, r in u_l.iterrows():
        st.markdown(f'<div class="user-card">👤 {r["nombre"]} | {r["plan"]} | Vence: {r["expira"]}</div>', unsafe_allow_html=True)
        rec = generar_recibo(r['nombre'], r['plan'], r['precio'], str(r['expira']))
        st.download_button(f"📄 Recibo {r['nombre']}", rec, f"Recibo_{r['id']}.pdf", key=f"p_{r['id']}")
        if st.button(f"🗑️ Eliminar {r['nombre']}", key=f"d_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM usuarios WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()
