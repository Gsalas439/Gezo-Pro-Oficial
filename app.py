import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io
import time

# --- 1. CONFIGURACIÓN ESTÉTICA ELITE PRO ---
st.set_page_config(
    page_title="GeZo Elite Pro",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.08);
        border-radius: 20px; padding: 25px; border: 1px solid #00c6ff;
        box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15); border-left: 10px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 15px; background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        color: #000 !important; font-weight: 800; width: 100%; border: none; height: 4.2em;
        transition: 0.4s all ease; text-transform: uppercase; letter-spacing: 1.5px;
    }
    .stButton>button:hover { transform: translateY(-4px); box-shadow: 0px 10px 30px #00c6ff; color: #fff !important; }
    .user-card { background: rgba(255, 255, 255, 0.05); padding: 30px; border-radius: 20px; border: 1px solid #333; margin-bottom: 20px; border-left: 8px solid #00f2fe; }
    .bank-btn { background-color: #1a1d24; border: 2px solid #00c6ff; color: #00c6ff !important; padding: 20px; border-radius: 15px; text-align: center; display: block; text-decoration: none; font-weight: bold; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS ---
@st.cache_resource
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e:
        st.error(f"Error de conexión: {e}"); st.stop()

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT, precio TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0)")
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS vence DATE")
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precio TEXT")
    except: conn.rollback()
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", ('admin', 'admin123', '2099-12-31', 'admin', 'Master', '0'))
    conn.commit(); c.close()

inicializar_db()

# --- 3. SERVICIOS PDF ---
def limpiar_texto(texto):
    if not texto: return ""
    acentos = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC ","Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ñ":"N"}
    for k, v in acentos.items(): texto = str(texto).replace(k, v)
    return texto.encode('latin-1', 'ignore').decode('latin-1')

def generar_pdf_venda(nombre, plan, monto, vence):
    pdf = FPDF(); pdf.add_page(); pdf.set_fill_color(11, 14, 20); pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(0, 242, 254); pdf.set_font("Arial", 'B', 32)
    pdf.cell(200, 60, limpiar_texto("GEZO ELITE PRO 💎"), ln=True, align='C')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "COMPROBANTE OFICIAL", ln=True, align='C')
    pdf.ln(20); pdf.set_font("Arial", '', 14)
    pdf.cell(200, 12, f"TITULAR: {limpiar_texto(nombre.upper())}", ln=True)
    pdf.cell(200, 12, f"PLAN: {limpiar_texto(plan)}", ln=True)
    pdf.cell(200, 12, f"INVERSION: CRC {monto}", ln=True)
    pdf.cell(200, 12, f"VENCIMIENTO: {vence}", ln=True)
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. ACCESO ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro Access")
    with st.form("login"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.form_submit_button("ACCEDER"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[4]: st.error("Suscripción vencida.")
                else: st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]}); st.rerun()
            else: st.error("Error de acceso.")
            c.close()
    st.stop()

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.markdown(f"## 👑 {st.session_state.uname}"); st.divider()
    menu = st.radio("MÓDULOS", ["📊 Dashboard", "💸 Registrar Cuentas", "🎯 Metas", "🏦 Deudas", "📱 SINPE Rápido", "💱 Conversor", "⚙️ Admin"])
    if st.button("🔒 SALIR"): st.session_state.autenticado = False; st.rerun()

# --- 6. MÓDULO REGISTRO (CORRECCIÓN FINAL DE LISTAS SEPARADAS) ---
if menu == "💸 Registrar Cuentas":
    st.header("Gestión de Entradas y Salidas")
    
    # 1. Definimos las listas claramente
    lista_gastos = [
        "⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", 
        "🏠 Alquiler/Hipoteca", "🛒 Súper/Comida", "📱 Plan Celular/Net", 
        "🏦 Cuota Préstamo", "🚗 Gasolina/Transporte", "📦 Otros Gastos"
    ]
    
    lista_ingresos = [
        "💵 Salario Mensual", "💰 Aguinaldo", "📱 SINPE Recibido", 
        "📈 Ventas/Negocio", "🧧 Comisiones", "🚜 Freelance/Servicios", 
        "🏢 Rentas/Alquileres", "🎁 Regalos", "💸 Cobros", "📦 Otros Ingresos"
    ]
    
    with st.form("registro_mov"):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.radio("Tipo de Movimiento:", ["Gasto", "Ingreso"], horizontal=True)
            monto = st.number_input("Monto (₡)", min_value=0.0, step=1000.0)
        
        with col2:
            # AQUÍ ESTÁ LA CORRECCIÓN: Filtrado dinámico real
            if tipo == "Ingreso":
                categoria = st.selectbox("Seleccione el Ingreso:", lista_ingresos)
            else:
                categoria = st.selectbox("Seleccione el Gasto:", lista_gastos)
                
            fecha_validez = st.date_input("Fecha Correspondiente:", datetime.now())
        
        detalle = st.text_input("Comentario:")
        
        if st.form_submit_button("GUARDAR REGISTRO"):
            conn = get_connection(); c = conn.cursor()
            c.execute("""INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) 
                         VALUES (%s,%s,%s,%s,%s,%s,%s)""", 
                      (st.session_state.uid, datetime.now().date(), f"{categoria}: {detalle}", monto, tipo, categoria, fecha_validez))
            conn.commit(); c.close(); st.success("✅ Guardado correctamente."); time.sleep(1); st.rerun()

# --- 7. DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("Estado Financiero")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    if not df.empty:
        i = float(df[df['tipo']=='Ingreso']['monto'].sum())
        g = float(df[df['tipo']=='Gasto']['monto'].sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("INGRESOS", f"₡{i:,.0f}"); c2.metric("GASTOS", f"₡{g:,.0f}", delta_color="inverse"); c3.metric("SALDO", f"₡{(i-g):,.0f}")
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=0.6, template="plotly_dark"), use_container_width=True)
    else: st.info("Sin datos.")

# --- 8. METAS ---
elif menu == "🎯 Metas":
    st.header("Objetivos de Ahorro")
    with st.form("f_meta"):
        n = st.text_input("Nombre de la Meta"); o = st.number_input("Monto Objetivo", min_value=0.0)
        if st.form_submit_button("CREAR META"):
            conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); st.rerun()
    st.table(pd.read_sql(f"SELECT nombre, objetivo FROM metas WHERE usuario_id={st.session_state.uid}", get_connection()))

# --- 9. DEUDAS ---
elif menu == "🏦 Deudas":
    st.header("Control de Préstamos")
    with st.form("f_deuda"):
        n = st.text_input("Acreedor"); o = st.number_input("Deuda Total", min_value=0.0)
        if st.form_submit_button("REGISTRAR DEUDA"):
            conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); st.rerun()
    st.table(pd.read_sql(f"SELECT nombre, monto_total FROM deudas WHERE usuario_id={st.session_state.uid}", get_connection()))

# --- 10. SINPE RÁPIDO ---
elif menu == "📱 SINPE Rápido":
    st.header("Atajo SINPE Móvil")
    st.text_input("Teléfono"); st.number_input("Monto")
    st.markdown('<a href="https://www.google.com" target="_blank" class="bank-btn">🚀 ABRIR APP BANCO</a>', unsafe_allow_html=True)

# --- 11. CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Calculadora de Divisas")
    m = st.number_input("Monto Colones:", min_value=0.0)
    st.metric("Dólares ($)", f"${(m/515):,.2f}")

# --- 12. ADMIN ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Gestión de Clientes")
    with st.form("f_admin"):
        un = st.text_input("User"); uk = st.text_input("Pass"); up = st.selectbox("Plan", ["Mensual", "Anual"]); um = st.text_input("Precio", "5000")
        if st.form_submit_button("ACTIVAR"):
            vf = (datetime.now() + timedelta(days=30 if up=="Mensual" else 365)).date()
            conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (un, uk, vf, 'usuario', up, um)); conn.commit(); c.close(); st.rerun()
    
    u_list = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for _, r in u_list.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card"><strong>{r["nombre"]}</strong> | Plan: {r["plan"]}</div>', unsafe_allow_html=True)
            pdf = generar_pdf_venda(r['nombre'], r['plan'], r['precio'], str(r['expira']))
            st.download_button(f"📄 Recibo {r['nombre']}", pdf, f"Recibo_{r['nombre']}.pdf", key=f"p_{r['id']}")
            if st.button(f"🗑️ Eliminar {r['nombre']}", key=f"d_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM usuarios WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()
