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

# Estilos CSS de Alta Gama
st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.08);
        border-radius: 20px;
        padding: 25px;
        border: 1px solid #00c6ff;
        box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15);
        border-left: 10px solid #00c6ff;
    }
    
    .stButton>button {
        border-radius: 15px;
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        color: #000 !important;
        font-weight: 800;
        width: 100%;
        border: none;
        height: 4.2em;
        transition: 0.4s all ease;
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }
    
    .stButton>button:hover {
        transform: translateY(-4px);
        box-shadow: 0px 10px 30px rgba(0, 198, 255, 0.4);
        color: #fff !important;
    }

    .user-card {
        background: rgba(255, 255, 255, 0.05);
        padding: 30px;
        border-radius: 20px;
        border: 1px solid #333;
        margin-bottom: 20px;
        border-left: 8px solid #00f2fe;
    }
    
    .bank-btn {
        background-color: #1a1d24;
        border: 2px solid #00c6ff;
        color: #00c6ff !important;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        display: block;
        text-decoration: none;
        font-weight: bold;
        margin-top: 15px;
        transition: 0.3s;
    }
    .bank-btn:hover { background-color: #00c6ff; color: #000 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS (POSTGRESQL) ---
@st.cache_resource(show_spinner="Sincronizando con Servidor Seguro...")
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

def inicializar_db():
    conn = get_connection()
    c = conn.cursor()
    # Tablas Robustas
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT, precio TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0)''')
    
    # Parches de seguridad para columnas nuevas
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS vence DATE")
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precio TEXT")
    except:
        conn.rollback()
    
    # Usuario Admin por defecto
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', '0'))
    
    conn.commit()
    c.close()

inicializar_db()

# --- 3. UTILIDADES: GENERADOR DE RECIBOS PDF ---
def limpiar_texto(texto):
    if not texto: return ""
    reemplazos = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC ","Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ñ":"N"}
    for k, v in reemplazos.items():
        texto = str(texto).replace(k, v)
    return texto.encode('latin-1', 'ignore').decode('latin-1')

def generar_pdf_venda(nombre, plan, monto, vence):
    pdf = FPDF()
    pdf.add_page()
    # Diseño de Recibo
    pdf.set_fill_color(11, 14, 20)
    pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(0, 242, 254)
    pdf.set_font("Arial", 'B', 32)
    pdf.cell(200, 60, limpiar_texto("GEZO ELITE PRO 💎"), ln=True, align='C')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "COMPROBANTE OFICIAL DE SUSCRIPCION", ln=True, align='C')
    pdf.ln(20)
    
    pdf.set_font("Arial", '', 14)
    pdf.set_draw_color(0, 242, 254)
    pdf.line(20, 100, 190, 100)
    
    pdf.ln(10)
    pdf.cell(200, 12, f"TITULAR: {limpiar_texto(nombre.upper())}", ln=True)
    pdf.cell(200, 12, f"PLAN ACTIVO: {limpiar_texto(plan)}", ln=True)
    pdf.cell(200, 12, f"INVERSION: CRC {monto}", ln=True)
    pdf.cell(200, 12, f"FECHA VENCIMIENTO: {vence}", ln=True)
    
    pdf.ln(40)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, "Este documento sirve como comprobante legal de activacion.", ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro Access")
    with st.form("login_form"):
        u_user = st.text_input("Usuario GeZo")
        u_pass = st.text_input("Contraseña", type="password")
        if st.form_submit_button("ACCEDER AL SISTEMA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u_user, u_pass))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[4]:
                    st.error("❌ Tu suscripción ha vencido. Contacta al administrador.")
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    st.success("Bienvenido al Élite")
                    time.sleep(0.5); st.rerun()
            else:
                st.error("Credenciales incorrectas.")
            c.close()
    st.stop()

# --- 5. SIDEBAR DE NAVEGACIÓN ---
with st.sidebar:
    st.markdown(f"## 👑 {st.session_state.uname}")
    st.markdown(f"**Membresía:** {st.session_state.plan}")
    st.divider()
    menu = st.radio("MÓDULOS DISPONIBLES", 
                    ["📊 Dashboard Real", "💸 Registrar Movimiento", "🎯 Mis Metas", "🏦 Control Deudas", "📱 SINPE Rápido", "💱 Conversor", "⚙️ Panel Maestro"])
    st.divider()
    if st.button("🔒 SALIR"):
        st.session_state.autenticado = False
        st.rerun()

# --- 6. MÓDULO REGISTRO (CON CAMBIOS DE INGRESOS/EGRESOS Y FECHA) ---
if menu == "💸 Registrar Movimiento":
    st.header("Gestión de Entradas y Salidas")
    
    # Categorías Corregidas y Ampliadas
    egresos = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "🏠 Alquiler/Hipoteca", "🛒 Supermercado", "📱 Plan Celular/Net", "🏦 Préstamo", "🚗 Gasolina/Bus", "📦 Otros Gastos"]
    ingresos = ["💵 Salario", "💰 Aguinaldo", "📱 SINPE Recibido", "📈 Ventas/Negocio", "🧧 Comisiones", "🚜 Freelance", "🏢 Rentas", "🎁 Regalos", "💸 Cobros", "📦 Otros Ingresos"]
    
    with st.form("movimiento_form"):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.radio("Acción:", ["Gasto", "Ingreso"], horizontal=True)
            monto = st.number_input("Cantidad (₡)", min_value=0.0, step=1000.0)
        with col2:
            categoria = st.selectbox("Categoría:", ingresos if tipo == "Ingreso" else egresos)
            fecha_manual = st.date_input("Fecha del movimiento:", datetime.now())
        
        detalle = st.text_input("Nota adicional:")
        
        if st.form_submit_button("REGISTRAR AHORA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("""INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
                      (st.session_state.uid, datetime.now().date(), f"{categoria}: {detalle}", monto, tipo, categoria, fecha_manual))
            conn.commit(); c.close()
            st.success("✅ Datos guardados en la nube.")
            time.sleep(1); st.rerun()

# --- 7. MÓDULO DASHBOARD ---
elif menu == "📊 Dashboard Real":
    st.header("Análisis Financiero")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    
    if not df.empty:
        i_t = float(df[df['tipo']=='Ingreso']['monto'].sum())
        g_t = float(df[df['tipo']=='Gasto']['monto'].sum())
        bal = i_t - g_t
        
        c1, c2, c3 = st.columns(3)
        c1.metric("INGRESOS", f"₡{i_t:,.0f}")
        c2.metric("GASTOS", f"₡{g_t:,.0f}", delta=f"-{g_t:,.0f}", delta_color="inverse")
        c3.metric("DISPONIBLE", f"₡{bal:,.0f}")
        
        st.divider()
        st.subheader("Distribución de Gastos")
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=0.6, template="plotly_dark"), use_container_width=True)
    else:
        st.info("No hay registros para mostrar gráficas.")

# --- 8. MÓDULO METAS ---
elif menu == "🎯 Mis Metas":
    st.header("Objetivos de Ahorro")
    with st.form("meta_form"):
        n_m = st.text_input("¿Qué quieres lograr?")
        o_m = st.number_input("Monto Objetivo (₡)", min_value=0.0)
        if st.form_submit_button("FIJAR META"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n_m, o_m))
            conn.commit(); c.close(); st.rerun()
    
    m_df = pd.read_sql(f"SELECT nombre, objetivo FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    if not m_df.empty: st.table(m_df)

# --- 9. MÓDULO DEUDAS ---
elif menu == "🏦 Control Deudas":
    st.header("Gestión de Compromisos")
    with st.form("deuda_form"):
        n_d = st.text_input("Acreedor")
        m_d = st.number_input("Monto Total", min_value=0.0)
        if st.form_submit_button("REGISTRAR DEUDA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total) VALUES (%s,%s,%s)", (st.session_state.uid, n_d, m_d))
            conn.commit(); c.close(); st.rerun()
    
    d_df = pd.read_sql(f"SELECT nombre, monto_total FROM deudas WHERE usuario_id={st.session_state.uid}", get_connection())
    if not d_df.empty: st.table(d_df)

# --- 10. SINPE RÁPIDO ---
elif menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil Elite")
    st.text_input("Número de Teléfono")
    st.number_input("Monto", min_value=0)
    st.markdown('<br><a href="https://www.google.com" target="_blank" class="bank-btn">🚀 ABRIR APP BANCARIA</a>', unsafe_allow_html=True)

# --- 11. CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Conversor de Moneda")
    m_c = st.number_input("Monto en Colones:", min_value=0.0)
    t_c = st.number_input("Tipo de cambio:", value=515.0)
    st.metric("Equivalente en Dólares", f"${(m_c/t_c):,.2f}")

# --- 12. PANEL MAESTRO (ADMIN) ---
elif menu == "⚙️ Panel Maestro" and st.session_state.rol == 'admin':
    st.header("Control Maestro de Usuarios")
    
    with st.expander("👤 CREAR NUEVO CLIENTE"):
        with st.form("admin_create"):
            u_n = st.text_input("Usuario")
            u_k = st.text_input("Clave")
            u_p = st.selectbox("Plan", ["Mensual", "Anual"])
            u_m = st.text_input("Monto Cobrado (₡)", value="5000")
            if st.form_submit_button("ACTIVAR CLIENTE"):
                v_f = (datetime.now() + timedelta(days=30 if u_p=="Mensual" else 365)).date()
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                          (u_n, u_k, v_f, 'usuario', u_p, u_m))
                conn.commit(); c.close(); st.success("Cliente Activado"); st.rerun()
    
    u_list = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin' ORDER BY id DESC", get_connection())
    for _, r in u_list.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card"><strong>{r["nombre"]}</strong> | Plan: {r["plan"]} | Vence: {r["expira"]}</div>', unsafe_allow_html=True)
            col_x, col_y = st.columns(2)
            with col_x:
                pdf = generar_pdf_venda(r['nombre'], r['plan'], r['precio'], str(r['expira']))
                st.download_button(f"📄 Recibo {r['nombre']}", pdf, f"Recibo_{r['nombre']}.pdf", "application/pdf", key=f"pdf_{r['id']}")
            with col_y:
                if st.button(f"🗑️ Eliminar Acceso {r['nombre']}", key=f"del_{r['id']}"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute(f"DELETE FROM usuarios WHERE id={r['id']}")
                    conn.commit(); c.close(); st.rerun()
