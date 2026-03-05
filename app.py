import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io
import time

# --- 1. CONFIGURACIÓN E INTERFAZ DE ALTA GAMA ---
st.set_page_config(
    page_title="GeZo Elite Pro",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS Personalizados
st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.05);
        border-radius: 20px;
        padding: 25px;
        border: 1px solid #00c6ff;
        box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.1);
        border-left: 10px solid #00c6ff;
    }
    
    .stButton>button {
        border-radius: 12px;
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        color: #000 !important;
        font-weight: 800;
        width: 100%;
        border: none;
        height: 3.8em;
        transition: 0.3s all ease;
        text-transform: uppercase;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0px 5px 20px rgba(0, 198, 255, 0.4);
        color: #fff !important;
    }

    .user-card {
        background: rgba(255, 255, 255, 0.02);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #2e3748;
        margin-bottom: 15px;
        border-left: 5px solid #00f2fe;
    }
    
    .bank-btn {
        background: #161b22;
        border: 1px solid #25d366;
        color: #25d366 !important;
        padding: 18px;
        border-radius: 15px;
        text-align: center;
        display: block;
        text-decoration: none;
        font-weight: bold;
        font-size: 1.1em;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS ---
@st.cache_resource
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e:
        st.error(f"Error crítico de conexión: {e}")
        st.stop()

def inicializar_db():
    conn = get_connection()
    c = conn.cursor()
    # Crear tablas principales
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT, precio TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0)")
    
    # Parches de actualización de columnas
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS vence DATE")
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precio TEXT")
    except:
        conn.rollback()
    
    # Usuario Administrador Maestro
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Master Elite', '0'))
    
    conn.commit()
    c.close()

inicializar_db()

# --- 3. FUNCIONES DE APOYO (PDF Y LIMPIEZA) ---
def limpiar_t(t):
    acentos = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC ","Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U"}
    for k, v in acentos.items():
        t = str(t).replace(k, v)
    return t.encode('latin-1', 'ignore').decode('latin-1')

def generar_recibo_pdf(nombre, plan, monto, vencimiento):
    pdf = FPDF()
    pdf.add_page()
    # Fondo Oscuro
    pdf.set_fill_color(11, 14, 20)
    pdf.rect(0, 0, 210, 297, 'F')
    # Logo / Título
    pdf.set_text_color(0, 198, 255)
    pdf.set_font("Arial", 'B', 30)
    pdf.cell(190, 50, limpiar_t("GEZO ELITE PRO 💎"), ln=True, align='C')
    # Datos
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", '', 14)
    pdf.ln(20)
    pdf.cell(190, 12, f"CLIENTE: {limpiar_t(nombre.upper())}", ln=True, align='L')
    pdf.cell(190, 12, f"PLAN ADQUIRIDO: {limpiar_t(plan)}", ln=True, align='L')
    pdf.cell(190, 12, f"INVERSION: {monto}", ln=True, align='L')
    pdf.cell(190, 12, f"FECHA DE VENCIMIENTO: {vencimiento}", ln=True, align='L')
    pdf.ln(30)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(190, 10, limpiar_t("Gracias por confiar en el sistema de gestion elite."), ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. CONTROL DE ACCESO ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro Access")
    with st.form("login_panel"):
        user_in = st.text_input("Nombre de Usuario")
        pass_in = st.text_input("Contraseña de Acceso", type="password")
        if st.form_submit_button("INICIAR SESIÓN ELITE"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (user_in, pass_in))
            res = c.fetchone()
            if res:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                st.success("Acceso Concedido")
                time.sleep(0.5); st.rerun()
            else:
                st.error("Credenciales incorrectas o usuario inexistente.")
            c.close()
    st.stop()

# --- 5. NAVEGACIÓN SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👑 Perfil: {st.session_state.uname}")
    st.markdown(f"**Plan:** {st.session_state.plan}")
    st.divider()
    menu = st.radio("MENÚ DE CONTROL", 
                    ["📊 Dashboard General", "💸 Registrar Movimientos", "🎯 Metas de Ahorro", "🏦 Control de Deudas", "📱 SINPE Rápido", "⚙️ Administración"])
    st.divider()
    if st.button("CERRAR SESIÓN"):
        st.session_state.autenticado = False
        st.rerun()

# --- 6. MÓDULO: REGISTRO DE MOVIMIENTOS (CORREGIDO) ---
if menu == "💸 Registrar Movimientos":
    st.header("Entradas y Salidas de Capital")
    
    # Listas Actualizadas según lo solicitado
    egresos = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "🏠 Alquiler/Hipoteca", "🛒 Supermercado", "📱 Plan Celular", "🏦 Cuota Préstamo", "🚗 Gasolina/Mantenimiento", "📦 Otros Gastos"]
    ingresos = ["💵 Salario Mensual", "💰 Aguinaldo", "📱 SINPE Recibido", "📈 Ventas del Negocio", "🧧 Comisiones Extra", "🚜 Freelance/Trabajos", "🏢 Rentas de Alquiler", "🎁 Regalos/Premios", "💸 Cobro de Préstamos", "📦 Otros Ingresos"]
    
    with st.form("form_movimiento"):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.radio("Tipo de Transacción:", ["Gasto", "Ingreso"], horizontal=True)
            monto = st.number_input("Monto en Colones (₡)", min_value=0.0, step=1000.0)
        with col2:
            categoria = st.selectbox("Categoría Correspondiente:", ingresos if tipo == "Ingreso" else egresos)
            fecha_pago = st.date_input("Fecha de Pago/Vencimiento:", datetime.now())
        
        comentario = st.text_input("Nota o Detalle (Opcional):")
        
        if st.form_submit_button("REGISTRAR EN EL SISTEMA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                      (st.session_state.uid, datetime.now().date(), f"{categoria}: {comentario}", monto, tipo, categoria, fecha_pago))
            conn.commit(); c.close()
            st.success("✅ El movimiento ha sido registrado correctamente.")
            time.sleep(1); st.rerun()

# --- 7. MÓDULO: DASHBOARD ---
elif menu == "📊 Dashboard General":
    st.header("Estado de Situación Financiera")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    
    if not df.empty:
        ing_total = float(df[df['tipo']=='Ingreso']['monto'].sum())
        gas_total = float(df[df['tipo']=='Gasto']['monto'].sum())
        balance = ing_total - gas_total
        
        m1, m2, m3 = st.columns(3)
        m1.metric("TOTAL INGRESOS", f"₡{ing_total:,.0f}")
        m2.metric("TOTAL GASTOS", f"₡{gas_total:,.0f}", delta=f"-₡{gas_total:,.0f}", delta_color="inverse")
        m3.metric("SALDO DISPONIBLE", f"₡{balance:,.0f}")
        
        st.divider()
        st.subheader("Distribución de Gastos")
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=0.5, template="plotly_dark", color_discrete_sequence=px.colors.sequential.Cyan_r)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aún no existen datos registrados para generar el análisis.")

# --- 8. MÓDULO: METAS ---
elif menu == "🎯 Metas de Ahorro":
    st.header("Objetivos de Ahorro")
    with st.form("nueva_meta"):
        n_meta = st.text_input("¿Qué quieres comprar o lograr?")
        o_meta = st.number_input("Monto Objetivo (₡)", min_value=0.0)
        if st.form_submit_button("ESTABLECER META"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n_meta, o_meta))
            conn.commit(); c.close(); st.rerun()
    
    metas_df = pd.read_sql(f"SELECT nombre as 'Meta', objetivo as 'Objetivo' FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    if not metas_df.empty: st.table(metas_df)

# --- 9. MÓDULO: DEUDAS ---
elif menu == "🏦 Control de Deudas":
    st.header("Gestión de Pasivos (Deudas)")
    with st.form("nueva_deuda"):
        n_deuda = st.text_input("Acreedor / Entidad")
        m_deuda = st.number_input("Monto Total de la Deuda (₡)", min_value=0.0)
        if st.form_submit_button("REGISTRAR DEUDA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total) VALUES (%s,%s,%s)", (st.session_state.uid, n_deuda, m_deuda))
            conn.commit(); c.close(); st.rerun()
    
    deudas_df = pd.read_sql(f"SELECT nombre as 'Acreedor', monto_total as 'Monto Total' FROM deudas WHERE usuario_id={st.session_state.uid}", get_connection())
    if not deudas_df.empty: st.table(deudas_df)

# --- 10. MÓDULO: SINPE ---
elif menu == "📱 SINPE Rápido":
    st.header("Preparar Transferencia SINPE")
    st.text_input("Número de Teléfono Destino")
    st.number_input("Monto del Envío (₡)", step=500.0)
    st.markdown('<br><a href="https://www.google.com" target="_blank" class="bank-btn">🚀 ABRIR APLICACIÓN BANCARIA</a>', unsafe_allow_html=True)

# --- 11. MÓDULO: ADMINISTRACIÓN (MAESTRO) ---
elif menu == "⚙️ Administración" and st.session_state.rol == 'admin':
    st.header("Panel de Control Master")
    
    with st.expander("👤 REGISTRAR NUEVO CLIENTE ELITE"):
        with st.form("registro_admin"):
            n_u = st.text_input("Nombre de Usuario")
            c_u = st.text_input("Contraseña Temporal")
            p_u = st.selectbox("Plan de Suscripción", ["Semanal", "Mensual", "Anual"])
            if st.form_submit_button("CREAR ACCESO"):
                dias = {"Semanal":7, "Mensual":30, "Anual":365}
                venc = (datetime.now() + timedelta(days=dias[p_u])).date()
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                          (n_u, c_u, venc, 'usuario', p_u, "5000" if p_u == "Mensual" else "50000"))
                conn.commit(); c.close(); st.success("Cliente Creado"); st.rerun()
    
    st.subheader("Gestión de Usuarios Activos")
    usuarios = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin' ORDER BY id DESC", get_connection())
    
    for _, row in usuarios.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card"><strong>{row["nombre"]}</strong> | Plan: {row["plan"]} | Expira: {row["expira"]}</div>', unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            with col_a:
                pdf_bytes = generar_recibo_pdf(row['nombre'], row['plan'], row['precio'], str(row['expira']))
                st.download_button(f"📄 Descargar Recibo PDF", pdf_bytes, f"Recibo_{row['nombre']}.pdf", "application/pdf", key=f"pdf_{row['id']}")
            with col_b:
                if st.button(f"🗑️ Eliminar Cliente", key=f"del_{row['id']}"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute(f"DELETE FROM usuarios WHERE id={row['id']}")
                    conn.commit(); c.close(); st.rerun()
