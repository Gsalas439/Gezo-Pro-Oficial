import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACIÓN Y ESTÉTICA "ULTRA-PREMIUM" ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

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
    .card-deuda {
        background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px;
        margin-bottom: 10px; border-left: 5px solid #ff4b4b;
    }
    .card-cobro {
        background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px;
        margin-bottom: 10px; border-left: 5px solid #00c6ff;
    }
    .prediction-box {
        background: rgba(255, 165, 0, 0.1); padding: 15px; border-radius: 12px;
        border-left: 5px solid orange; margin: 15px 0;
    }
    .status-tag {
        padding: 4px 10px; border-radius: 15px; font-size: 11px;
        background: rgba(0, 198, 255, 0.2); border: 1px solid #00c6ff; color: #00c6ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS (REVISIÓN DE TABLAS) ---
conn = sqlite3.connect('gezo_master_total.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    # Tabla de Usuarios con Plan y Presupuesto
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, 
                  plan TEXT, presupuesto REAL DEFAULT 250000)''')
    # Tabla de Movimientos (Gastos e Ingresos)
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)''')
    # Tabla de Metas de Ahorro
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo REAL, actual REAL)''')
    # Tabla de Deudas y Cobros
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total REAL, pagado REAL DEFAULT 0, tipo TEXT)''')
    
    # Usuario Administrador por defecto
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (?,?,?,?,?)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master'))
    conn.commit()

inicializar_db()

# --- 3. LÓGICA DE SESIÓN Y SEGURIDAD ---
WHATSAPP_NUM = "50663712477"
TC_DOLAR = 518.00 # Tipo de Cambio Actualizable

if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'ver_montos' not in st.session_state: st.session_state.ver_montos = True

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INGRESAR"):
            c.execute("SELECT id, nombre, rol, presupuesto, plan, expira FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            if res:
                venc = datetime.strptime(res[5], "%Y-%m-%d").date()
                if datetime.now().date() > venc:
                    st.error(f"Suscripción '{res[4]}' vencida.")
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}?text=Deseo renovar mi cuenta GeZo: {u}" class="whatsapp-btn">📲 Tocar aquí para renovar</a>', unsafe_allow_html=True)
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[3], "plan":res[4]})
                    st.rerun()
            else: st.error("Usuario o clave incorrectos.")
    st.stop()

def fmt(n): return f"₡{n:,.0f}" if st.session_state.ver_montos else "₡ *.*"

# --- 4. BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    st.markdown(f'<span class="status-tag">{st.session_state.plan}</span>', unsafe_allow_html=True)
    if st.button("👁️ Privacidad"):
        st.session_state.ver_montos = not st.session_state.ver_montos
        st.rerun()
    
    menu = st.radio("Secciones", ["📊 Dashboard IA", "💸 Registrar", "🤝 Deudas y Cobros", "💱 Conversor", "🎯 Metas", "⚙️ Admin"])
    st.markdown("---")
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 5. MÓDULOS DEL SISTEMA ---

# --- DASHBOARD IA ---
if menu == "📊 Dashboard IA":
    st.header("Salud Financiera")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt(ing))
    c2.metric("Gastos", fmt(gas), delta_color="inverse")
    c3.metric("Saldo Real", fmt(ing - gas))

    if gas > 0:
        dia_act = datetime.now().day
        proy = (gas / dia_act) * 30
        st.markdown(f'<div class="prediction-box">🤖 <b>IA GeZo:</b> Al ritmo actual, gastarás <b>{fmt(proy)}</b> este mes. Tu límite es {fmt(st.session_state.pres)}.</div>', unsafe_allow_html=True)

    if not df.empty and gas > 0:
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark", title="Distribución de Gastos")
        st.plotly_chart(fig, use_container_width=True)

# --- REGISTRO DE MOVIMIENTOS ---
elif menu == "💸 Registrar":
    st.header("Nueva Transacción")
    with st.form("reg"):
        desc = st.text_input("Detalle (Ej: Almuerzo, Gasolina)")
        monto = st.number_input("Monto", min_value=0.0)
        moneda = st.radio("Moneda", ["CRC (₡)", "USD ($)"], horizontal=True)
        cat = st.selectbox("Categoría", [
            "⛽ Gasolina", "🛒 Súper", "🍱 Restaurantes", "🏠 Casa", "⚡ Servicios", 
            "📱 SINPE", "🎬 Suscripciones", "🏥 Salud", "🚗 Marchamo", "💡 Gastos Hormiga", 
            "🏦 Deudas", "💰 Ahorro", "💵 Salario", "📦 Otros"
        ])
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        if st.form_submit_button("GUARDAR REGISTRO"):
            m_final = monto if "CRC" in moneda else monto * TC_DOLAR
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, m_final, tipo, cat))
            conn.commit()
            st.success("Guardado en la nube ☁️")

# --- DEUDAS Y COBROS (LÓGICA DE ABONO VINCULADO) ---
elif menu == "🤝 Deudas y Cobros":
    st.header("Préstamos y Cobros")
    tab1, tab2 = st.tabs(["➕ Crear", "📋 Gestionar"])
    
    with tab1:
        with st.form("d_new"):
            persona = st.text_input("Persona / Entidad")
            m_total = st.number_input("Monto Total", min_value=0.0)
            tipo_d = st.selectbox("Tipo", ["Me deben (Cobro)", "Yo debo (Deuda)"])
            if st.form_submit_button("REGISTRAR PRÉSTAMO"):
                c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo) VALUES (?,?,?,?,?)",
                          (st.session_state.uid, persona, m_total, 0, tipo_d))
                conn.commit()
                st.rerun()

    with tab2:
        deudas = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid}", conn)
        for i, r in deudas.iterrows():
            falta = r['monto_total'] - r['pagado']
            clase = "card-cobro" if "Me deben" in r['tipo'] else "card-deuda"
            st.markdown(f"<div class='{clase}'><b>{r['nombre']}</b><br>{r['tipo']}<br>"
                        f"Saldo: {fmt(falta)} / Total: {fmt(r['monto_total'])}</div>", unsafe_allow_html=True)
            
            if falta > 0:
                with st.expander(f"Abonar a {r['nombre']}"):
                    abono = st.number_input("Monto del abono", min_value=0.0, key=f"ab_{r['id']}")
                    if st.button("Procesar Abono", key=f"btn_{r['id']}"):
                        # 1. Actualizar saldo de deuda
                        c.execute("UPDATE deudas SET pagado = pagado + ? WHERE id = ?", (abono, r['id']))
                        # 2. VINCULACIÓN AUTOMÁTICA A MOVIMIENTOS
                        t_mov = "Ingreso" if "Me deben" in r['tipo'] else "Gasto"
                        d_mov = f"Abono deuda: {r['nombre']}"
                        c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                                  (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), d_mov, abono, t_mov, "🤝 Deudas/Cobros"))
                        conn.commit()
                        st.success("Abono procesado e historial actualizado.")
                        st.rerun()

# --- CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Conversor $ / ₡")
    v = st.number_input("Monto", min_value=0.0)
    st.write(f"En colones: *₡{v * TC_DOLAR:,.2f}*")
    st.write(f"En dólares: *${v / TC_DOLAR:,.2f}*")

# --- METAS ---
elif menu == "🎯 Metas":
    st.header("Metas de Ahorro")
    with st.expander("Nueva Meta"):
        nm = st.text_input("Nombre meta")
        ob = st.number_input("Objetivo (₡)", min_value=0)
        if st.button("Crear Meta"):
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (?,?,?,?)", (st.session_state.uid, nm, ob, 0))
            conn.commit()
            st.rerun()
    metas = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn)
    for i, r in metas.iterrows():
        p = (r['actual'] / r['objetivo']) if r['objetivo'] > 0 else 0
        st.write(f"*{r['nombre']}* ({p*100:.1f}%)")
        st.progress(p)

# --- ADMIN ---
elif menu == "⚙️ Admin":
    if st.session_state.rol == 'admin':
        st.header("Panel de Administración")
        with st.form("admin_u"):
            un, uc = st.text_input("Usuario"), st.text_input("Clave")
            up = st.number_input("Presupuesto", value=250000)
            planes = {"Prueba (7d)": 7, "Mes (5k)": 30, "Año (45k)": 365, "Eterno": 36500}
            pl = st.selectbox("Plan", list(planes.keys()))
            if st.form_submit_button("CREAR CLIENTE"):
                f_v = (datetime.now() + timedelta(days=planes[pl])).strftime("%Y-%m-%d")
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, presupuesto) VALUES (?,?,?,?,?,?)", 
                          (un, uc, f_v, 'usuario', pl, up))
                conn.commit()
                st.success(f"Creado: {un} hasta {f_v}")
        st.table(pd.read_sql("SELECT nombre, plan, expira FROM usuarios WHERE rol!='admin'", conn))
