import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACIÓN ELITE ---
st.set_page_config(page_title="GeZo Elite Pro v4", page_icon="💎", layout="wide")

# Estilo Profesional
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee; }
    .stButton>button { border-radius: 8px; font-weight: bold; background-color: #004a99; color: white; transition: 0.3s; }
    .stButton>button:hover { background-color: #0066cc; transform: translateY(-2px); }
    .anuncio-card { background-color: #e3f2fd; padding: 20px; border-radius: 15px; border-left: 5px solid #2196f3; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS ---
conn = sqlite3.connect('gezo_pro_v4.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, presupuesto REAL DEFAULT 200000)')
    c.execute('CREATE TABLE IF NOT EXISTS movimientos (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY, usuario_id INTEGER, concepto TEXT, monto_total REAL, pagado REAL, tipo TEXT)')
    conn.commit()

init_db()

# Admin por defecto
c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
if not c.fetchone():
    c.execute("INSERT INTO usuarios (nombre, clave, expira, rol) VALUES ('admin', 'admin123', '2099-12-31', 'admin')")
    conn.commit()

# --- 3. LÓGICA DE ANUNCIOS AUTOMÁTICOS ---
def mostrar_anuncio_auto(uid, presupuesto, total_gastado):
    hoy = datetime.now()
    mes_actual = hoy.month
    dia_actual = hoy.day
    
    mensaje = ""
    icono = "📢"

    # Lógica por Fecha (Costa Rica)
    if mes_actual == 12:
        mensaje = "¡Llegó el aguinaldo! 🎄 Recuerda provisionar para el marchamo y los gastos de entrada a clases."
        icono = "🎁"
    elif mes_actual == 1:
        mensaje = "Enero: Mes de metas. 📅 Intenta ahorrar al menos un 10% de tus ingresos este mes."
    elif dia_actual in [14, 15, 29, 30, 31]:
        mensaje = "¡Día de Pago! 💰 No olvides registrar primero tus ahorros y deudas antes de los gastos."
    
    # Lógica por Salud Financiera
    porcentaje = (total_gastado / presupuesto) if presupuesto > 0 else 0
    if porcentaje >= 0.9:
        mensaje = f"⚠️ ALERTA: Has consumido el {porcentaje*100:.0f}% de tu presupuesto. ¡Hora de frenar gastos!"
        icono = "🚨"
    
    if mensaje:
        st.markdown(f"""
        <div class="anuncio-card">
            <h4>{icono} Mensaje del Sistema GeZo</h4>
            <p style='font-size: 16px;'>{mensaje}</p>
        </div>
        """, unsafe_allow_html=True)

# --- 4. SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1,1.5,1])
    with col2:
        st.title("🚀 GeZo Elite Pro")
        with st.form("login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("ACCEDER"):
                c.execute("SELECT id, nombre, rol, expira, presupuesto FROM usuarios WHERE nombre=? AND clave=?", (u, p))
                res = c.fetchone()
                if res:
                    exp = datetime.strptime(res[3], "%Y-%m-%d").date()
                    if datetime.now().date() <= exp:
                        st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[4]})
                        st.rerun()
                    else: st.error("Suscripción vencida 🛑")
                else: st.error("Credenciales incorrectas")
    st.stop()

# --- 5. INTERFAZ PRINCIPAL ---
with st.sidebar:
    st.header(f"Hola, {st.session_state.uname}")
    menu = st.radio("Menú Principal", ["📊 Dashboard", "💸 Mis Movimientos", "🤝 Deudas y Cobros", "⚙️ Admin"])
    if st.button("Salir"):
        st.session_state.autenticado = False
        st.rerun()

# --- MÓDULO DASHBOARD ---
if menu == "📊 Dashboard":
    st.header("Resumen de Salud Financiera 🇨🇷")
    
    # Cargar Datos
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    
    # MOSTRAR ANUNCIO AUTOMÁTICO
    mostrar_anuncio_auto(st.session_state.uid, st.session_state.pres, gas)
    
    # Métricas Principales
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos Reales", f"₡{ing:,.0f}")
    c2.metric("Gastos Totales", f"₡{gas:,.0f}", delta=f"{-(gas/ing*100 if ing>0 else 0):.1f}%", delta_color="inverse")
    c3.metric("Balance", f"₡{(ing-gas):,.0f}")
    
    # Radar de Presupuesto
    st.subheader("Radar de Presupuesto Mensual")
    porc = min((gas / st.session_state.pres if st.session_state.pres > 0 else 0), 1.0)
    st.progress(porc)
    st.write(f"Has gastado ₡{gas:,.0f} de tu límite de ₡{st.session_state.pres:,.0f}")

    if not df.empty:
        col_a, col_b = st.columns(2)
        with col_a:
            fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, title="Gastos por Categoría")
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df_hist = df.groupby('fecha')['monto'].sum().reset_index()
            fig2 = px.area(df_hist, x='fecha', y='monto', title="Flujo de Caja")
            st.plotly_chart(fig2, use_container_width=True)

# --- MÓDULO MOVIMIENTOS ---
elif menu == "💸 Mis Movimientos":
    st.header("Registro de Gastos e Ingresos")
    with st.expander("Registrar Nueva Transacción", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            desc = st.text_input("Descripción")
            monto = st.number_input("Monto (₡)", min_value=0)
        with c2:
            tipo = st.selectbox("Tipo", ["Ingreso", "Gasto"])
            cat = st.selectbox("Categoría", ["Salario", "Ventas", "Comida", "Casa", "Diversión", "Transporte", "Ahorro"])
        if st.button("GUARDAR REGISTRO"):
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, monto, tipo, cat))
            conn.commit()
            st.success("¡Movimiento guardado!")
            st.rerun()

# --- MÓDULO DEUDAS ---
elif menu == "🤝 Deudas y Cobros":
    st.header("Gestión de Préstamos")
    # Lógica de deudas similar a v3 (Simplificada)
    pers = st.text_input("Nombre de la Persona")
    m_t = st.number_input("Monto ₡", min_value=0)
    t_d = st.radio("Tipo", ["Me deben (Cobro)", "Yo debo (Deuda)"], horizontal=True)
    if st.button("Crear Registro"):
        tipo_db = 'me_deben' if "Me deben" in t_d else 'debo'
        c.execute("INSERT INTO deudas (usuario_id, concepto, monto_total, pagado, tipo) VALUES (?,?,?,?,?)",
                  (st.session_state.uid, pers, m_t, 0, tipo_db))
        conn.commit()
        st.rerun()

# --- MÓDULO ADMIN ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Panel de Administración de Usuarios")
    with st.form("crear_u"):
        nu = st.text_input("Nuevo Usuario")
        np = st.text_input("Clave")
        pres_u = st.number_input("Presupuesto Sugerido (₡)", value=200000)
        planes = {"Semanal":7, "Mensual":30, "Trimestral":90, "Semestral":180, "Anual":365, "Eterno":36500}
        sel_plan = st.selectbox("Plan", list(planes.keys()))
        if st.form_submit_button("REGISTRAR Y ACTIVAR"):
            fv = (datetime.now() + timedelta(days=planes[sel_plan])).strftime("%Y-%m-%d")
            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, presupuesto) VALUES (?,?,?,?,?)", 
                      (nu, np, fv, 'usuario', pres_u))
            conn.commit()
            st.success(f"Usuario {nu} activado hasta {fv}")
