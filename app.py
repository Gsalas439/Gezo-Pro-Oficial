import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACIÓN ELITE & MÓVIL ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

# Diseño Premium Glassmorphism (Optimizado para iPhone)
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 15px; padding: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(90deg, #00c6ff 0%, #0072ff 100%);
        color: white; font-weight: bold; height: 3.5em; width: 100%; border: none;
    }
    .whatsapp-btn {
        background-color: #25d366; color: white; padding: 15px; text-align: center;
        border-radius: 12px; text-decoration: none; display: block; font-weight: bold; margin-top: 20px;
    }
    .prediction-box {
        background: rgba(255, 165, 0, 0.1); padding: 15px; border-radius: 12px;
        border-left: 5px solid orange; margin: 10px 0;
    }
    .status-tag {
        padding: 4px 10px; border-radius: 15px; font-size: 11px;
        background: rgba(0, 198, 255, 0.2); border: 1px solid #00c6ff; color: #00c6ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS (BASE UNIFICADA) ---
conn = sqlite3.connect('gezo_ultimate_master.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, 
                  plan TEXT DEFAULT 'Prueba', presupuesto REAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo REAL, actual REAL)''')
    
    # Crear Admin Maestro si no existe
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (?,?,?,?,?)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master'))
    conn.commit()

inicializar_db()

# --- 3. VARIABLES DE NEGOCIO ---
WHATSAPP_NUM = "50663712477"
TC_VENTA = 518.00  # Tipo de cambio manual ajustable

# --- 4. CONTROL DE ACCESO ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'ver_montos' not in st.session_state: st.session_state.ver_montos = True

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    st.caption("Versión 2026 - Control Financiero Total")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INGRESAR"):
            c.execute("SELECT id, nombre, rol, presupuesto, plan, expira FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            if res:
                venc = datetime.strptime(res[5], "%Y-%m-%d").date()
                if datetime.now().date() > venc:
                    st.error(f"Suscripción vencida: {res[4]}")
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}?text=Renovación de cuenta: {u}" class="whatsapp-btn">Renovar por WhatsApp</a>', unsafe_allow_html=True)
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[3], "plan":res[4]})
                    st.rerun()
            else: st.error("Acceso denegado")
    st.stop()

# --- 5. FUNCIONES DE INTERFAZ ---
def fmt(n): return f"₡{n:,.0f}" if st.session_state.ver_montos else "₡ *.*"

# --- 6. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    st.markdown(f'<span class="status-tag">{st.session_state.plan}</span>', unsafe_allow_html=True)
    if st.button("👁️ Privacidad"):
        st.session_state.ver_montos = not st.session_state.ver_montos
        st.rerun()
    
    menu = st.radio("Secciones", ["📊 Dashboard IA", "💸 Registrar Movimiento", "💱 Conversor $", "🎯 Metas de Ahorro", "⚙️ Panel Admin"])
    st.markdown("---")
    st.write(f"💵 Dólar: *₡{TC_VENTA}*")
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 7. MÓDULOS ---

# --- DASHBOARD ---
if menu == "📊 Dashboard IA":
    st.header("Análisis de Salud Financiera")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos", fmt(ing))
    col2.metric("Gastos", fmt(gas), delta="-Consumo", delta_color="inverse")
    col3.metric("Saldo", fmt(ing - gas))

    # Inteligencia Predictiva
    if gas > 0:
        dia = datetime.now().day
        proy = (gas / dia) * 30
        st.markdown(f'<div class="prediction-box">🤖 <b>IA GeZo:</b> Al ritmo actual, gastarás <b>{fmt(proy)}</b> este mes. Su presupuesto es de {fmt(st.session_state.pres)}.</div>', unsafe_allow_html=True)

    if not df.empty and gas > 0:
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark", title="¿Hacia dónde va mi dinero?")
        st.plotly_chart(fig, use_container_width=True)

# --- REGISTRO ---
elif menu == "💸 Registrar Movimiento":
    st.header("Registrar Transacción")
    with st.form("registro"):
        desc = st.text_input("Descripción (Ej: Gasolina, Super, Netflix)")
        monto = st.number_input("Monto", min_value=0.0)
        moneda = st.radio("Moneda", ["₡ Colones", "$ Dólares"], horizontal=True)
        cat = st.selectbox("Categoría", [
            "⛽ Gasolina / Transporte", "🛒 Súper / Comida Casa", "🍱 Restaurantes / Salidas", 
            "🏠 Alquiler / Hipoteca", "⚡ Servicios (Luz, Internet)", "📱 SINPE Enviado", 
            "🎬 Suscripciones", "🏥 Salud / Farmacia", "🚗 Marchamo / Seguro Auto", 
            "💡 Gastos Hormiga", "🏦 Deudas / Préstamos", "💰 Ahorro", "💵 Salario", "📦 Otros"
        ])
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        if st.form_submit_button("GUARDAR EN NUBE"):
            m_final = monto if "₡" in moneda else monto * TC_VENTA
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, m_final, tipo, cat))
            conn.commit()
            st.success("¡Sincronizado!")

# --- CONVERSOR ---
elif menu == "💱 Conversor $":
    st.header("Conversor de Moneda")
    val = st.number_input("Monto a convertir", min_value=0.0)
    c1, c2 = st.columns(2)
    c1.metric("Dólares a Colones", f"₡{val * TC_VENTA:,.2f}")
    c2.metric("Colones a Dólares", f"${val / TC_VENTA:,.2f}")

# --- METAS ---
elif menu == "🎯 Metas de Ahorro":
    st.header("Metas de Ahorro")
    with st.expander("Crear Meta"):
        nm = st.text_input("Nombre de meta")
        ob = st.number_input("Objetivo (₡)", min_value=0)
        if st.button("Crear"):
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (?,?,?,?)", (st.session_state.uid, nm, ob, 0))
            conn.commit()
            st.rerun()
    
    metas = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn)
    for i, r in metas.iterrows():
        st.write(f"*{r['nombre']}*")
        p = (r['actual'] / r['objetivo']) if r['objetivo'] > 0 else 0
        st.progress(p)
        st.caption(f"{fmt(r['actual'])} de {fmt(r['objetivo'])} ({p*100:.1f}%)")

# --- ADMIN ---
elif menu == "⚙️ Panel Admin":
    if st.session_state.rol == 'admin':
        st.header("Panel de Administración de Clientes")
        with st.form("admin"):
            un, uc = st.text_input("Usuario"), st.text_input("Contraseña")
            up = st.number_input("Presupuesto Mensual", value=250000)
            planes = {
                "Prueba Gratis (7 días)": 7, "Mensual (₡5,000)": 30, 
                "Semestral (₡25,000)": 180, "Anual (₡45,000)": 365, "Eterno": 36500
            }
            pl = st.selectbox("Plan", list(planes.keys()))
            if st.form_submit_button("ACTIVAR CLIENTE"):
                f_exp = (datetime.now() + timedelta(days=planes[pl])).strftime("%Y-%m-%d")
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, presupuesto) VALUES (?,?,?,?,?,?)", 
                          (un, uc, f_exp, 'usuario', pl, up))
                conn.commit()
                st.success(f"Usuario {un} creado hasta {f_exp}")
        
        st.subheader("Clientes Activos")
        st.table(pd.read_sql("SELECT nombre, plan, expira FROM usuarios WHERE rol!='admin'", conn))
    else:
        st.error("Acceso restringido al Dueño Master.")
