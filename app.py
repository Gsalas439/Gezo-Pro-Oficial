import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="🚀", layout="wide")

# Estilo CSS Personalizado para que sea "Super Atractiva"
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #007bff; color: white; }
    .stMetric { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS ---
conn = sqlite3.connect('gezo_finanzas_v2.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo REAL, ahorro REAL)''')
    conn.commit()

init_db()

# Crear Admin por defecto si no existe
c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
if not c.fetchone():
    c.execute("INSERT INTO usuarios (nombre, clave, expira, rol) VALUES (?,?,?,?)", 
              ('admin', 'admin123', '2099-12-31', 'admin'))
    conn.commit()

# --- 3. LÓGICA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🚀 GeZo Elite Pro")
    st.subheader("Tu Centro de Control Financiero")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar al Sistema"):
            c.execute("SELECT id, nombre, rol, expira FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            if res:
                hoy = datetime.now().date()
                expira_date = datetime.strptime(res[3], "%Y-%m-%d").date()
                if hoy <= expira_date:
                    st.session_state.autenticado = True
                    st.session_state.user_id = res[0]
                    st.session_state.user_name = res[1]
                    st.session_state.rol = res[2]
                    st.rerun()
                else: st.error("❌ Tu suscripción ha expirado. Contacta al soporte.")
            else: st.error("❌ Usuario o clave incorrectos")
    st.stop()

# --- 4. MENÚ LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
    st.title(f"Hola, {st.session_state.user_name}")
    opciones = ["🏠 Dashboard", "💰 Ingresos/Gastos", "🎯 Metas de Ahorro", "🤝 Me Deben / Debo"]
    if st.session_state.rol == 'admin':
        opciones.append("⚙️ PANEL ADMIN")
    menu = st.radio("Ir a:", opciones)
    
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 5. FUNCIONES DE LA APP ---

if menu == "🏠 Dashboard":
    st.header("📊 Resumen General")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.user_id}", conn)
    
    col1, col2, col3 = st.columns(3)
    if not df.empty:
        ingresos = df[df['tipo'] == 'Ingreso']['monto'].sum()
        gastos = df[df['tipo'] == 'Gasto']['monto'].sum()
        balance = ingresos - gastos
        col1.metric("Ingresos Totales", f"₡{ingresos:,.2f}")
        col2.metric("Gastos Totales", f"₡{gastos:,.2f}", delta_color="inverse")
        col3.metric("Balance Neto", f"₡{balance:,.2f}")
        
        fig = px.pie(df, values='monto', names='cat', title='Distribución por Categoría')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aún no tienes movimientos registrados. ¡Empieza hoy!")

elif menu == "💰 Ingresos/Gastos":
    st.header("💵 Registro de Movimientos")
    with st.form("mov"):
        f = st.date_input("Fecha", datetime.now())
        d = st.text_input("Descripción (ej. Salario, Supermercado)")
        m = st.number_input("Monto (₡)", min_value=0.0)
        t = st.selectbox("Tipo", ["Ingreso", "Gasto"])
        c_cat = st.selectbox("Categoría", ["Salario", "Alimentación", "Transporte", "Servicios", "Ocio", "Otros"])
        if st.form_submit_button("Guardar Registro"):
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.user_id, f, d, m, t, c_cat))
            conn.commit()
            st.success("¡Movimiento guardado!")

elif menu == "⚙️ PANEL ADMIN":
    st.header("🛠️ Gestión de Usuarios y Planes")
    with st.expander("Crear Nuevo Usuario / Renovación"):
        nuevo_u = st.text_input("Nombre de Usuario")
        nuevo_p = st.text_input("Clave de Acceso")
        
        # AJUSTE DE PLANES SOLICITADO
        dict_planes = {
            "Semanal": 7,
            "Mensual": 30,
            "Trimestral": 90,
            "Semestral": 180,
            "Anual": 365,
            "Pago Único (Eterno)": 36500
        }
        plan_nombre = st.selectbox("Seleccione el Plan de Suscripción", list(dict_planes.keys()))
        dias = dict_planes[plan_nombre]
        
        if st.button("Registrar Usuario"):
            fecha_v = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol) VALUES (?,?,?,?)",
                      (nuevo_u, nuevo_p, fecha_v, 'usuario'))
            conn.commit()
            st.success(f"Usuario {nuevo_u} creado. Expira el {fecha_v}")

    st.subheader("Usuarios Actuales")
    usuarios_df = pd.read_sql("SELECT nombre, expira, rol FROM usuarios", conn)
    st.table(usuarios_df)
