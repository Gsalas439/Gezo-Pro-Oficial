import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACIÓN DE ALTO NIVEL ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

# Diseño Premium "Glassmorphism" optimizado para iPhone
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 15px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }
    .stButton>button {
        border-radius: 12px;
        background: linear-gradient(90deg, #00c6ff 0%, #0072ff 100%);
        color: white; font-weight: bold; border: none; height: 3.5em;
        width: 100%;
    }
    .prediction-box {
        background: rgba(255, 165, 0, 0.1);
        padding: 15px; border-radius: 12px; border-left: 5px solid orange; margin: 10px 0;
    }
    .stTextInput>div>div>input { color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS & AUTO-ADMIN ---
conn = sqlite3.connect('gezo_ultimate_v2.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, presupuesto REAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo REAL, actual REAL)''')
    
    # Crear admin por defecto si la base es nueva
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol) VALUES (?,?,?,?)", 
                  ('admin', 'admin123', '2099-12-31', 'admin'))
    conn.commit()

inicializar_db()

# --- 3. LÓGICA DE SESIÓN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'ver_montos' not in st.session_state:
    st.session_state.ver_montos = True

# --- 4. PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    st.subheader("Bienvenido al control total de tus finanzas")
    
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        btn = st.form_submit_button("INICIAR SESIÓN")
        
        if btn:
            c.execute("SELECT id, nombre, rol, presupuesto FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            if res:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[3]})
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- 5. PANEL PRINCIPAL (SIDEBAR) ---
tc_venta = 518.00 # Dólar BCCR aproximado

with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    if st.button("👁️ Privacidad (Ocultar/Ver)"):
        st.session_state.ver_montos = not st.session_state.ver_montos
        st.rerun()
    
    menu = st.radio("Menú", ["📊 Dashboard IA", "💸 Registrar", "🎯 Metas", "⚙️ Admin"])
    st.markdown(f"--- \n *Tipo de Cambio:* ₡{tc_venta}")
    
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 6. MÓDULOS DE LA APP ---

# --- DASHBOARD IA ---
if menu == "📊 Dashboard IA":
    st.header("Análisis Inteligente")
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    bal = ing - gas
    
    # Formato de privacidad
    def fmt(n): return f"₡{n:,.0f}" if st.session_state.ver_montos else "₡ *.*"

    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt(ing))
    c2.metric("Gastos", fmt(gas), delta="-Consumo", delta_color="inverse")
    c3.metric("Saldo Real", fmt(bal))

    # Predicción automática
    if gas > 0:
        dia_actual = datetime.now().day
        proyeccion = (gas / dia_actual) * 30
        st.markdown(f'<div class="prediction-box">🤖 <b>Proyección GeZo:</b> Al ritmo actual, cerrarás el mes con un gasto de <b>{fmt(proyeccion)}</b>.</div>', unsafe_allow_html=True)

    if not df.empty and gas > 0:
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark", title="¿En qué se va el dinero?")
        st.plotly_chart(fig, use_container_width=True)

# --- REGISTRAR ---
elif menu == "💸 Registrar":
    st.header("Nuevo Movimiento")
    with st.form("reg"):
        desc = st.text_input("Detalle (Ej: Supermercado)")
        monto = st.number_input("Monto", min_value=0.0)
        moneda = st.radio("Moneda", ["CRC (₡)", "USD ($)"], horizontal=True)
        cat = st.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Sinpe", "Ocio", "Salario", "Otros"])
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        
        if st.form_submit_button("GUARDAR EN NUBE"):
            monto_final = monto if "CRC" in moneda else monto * tc_venta
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, monto_final, tipo, cat))
            conn.commit()
            st.success("¡Registrado exitosamente!")

# --- METAS ---
elif menu == "🎯 Metas":
    st.header("Metas de Ahorro")
    with st.expander("Crear Nueva Meta"):
        n_meta = st.text_input("Nombre de la meta")
        obj_meta = st.number_input("Monto Objetivo", min_value=0)
        if st.button("Añadir"):
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (?,?,?,?)", (st.session_state.uid, n_meta, obj_meta, 0))
            conn.commit()
            st.rerun()
    
    metas_df = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn)
    for i, r in metas_df.iterrows():
        st.write(f"*{r['nombre']}*")
        prog = (r['actual'] / r['objetivo']) if r['objetivo'] > 0 else 0
        st.progress(prog)
        st.caption(f"{fmt(r['actual'])} de {fmt(r['objetivo'])}")

# --- ADMIN ---
elif menu == "⚙️ Admin":
    if st.session_state.rol == 'admin':
        st.header("Panel de Control")
        with st.form("nuevo_u"):
            nu = st.text_input("Usuario Nuevo")
            np = st.text_input("Clave")
            if st.form_submit_button("Crear Usuario"):
                fv = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol) VALUES (?,?,?,?)", (nu, np, fv, 'usuario'))
                conn.commit()
                st.success(f"Usuario {nu} creado.")
    else:
        st.error("Acceso denegado.")
