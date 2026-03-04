import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACIÓN Y ESTÉTICA PREMIUM ---
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
    .coach-box {
        background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 15px;
        border: 1px dashed rgba(0, 198, 255, 0.5); margin: 20px 0;
    }
    .status-tag {
        padding: 4px 10px; border-radius: 15px; font-size: 11px;
        background: rgba(0, 198, 255, 0.2); border: 1px solid #00c6ff; color: #00c6ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS ---
conn = sqlite3.connect('gezo_master_total.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, 
                  plan TEXT, presupuesto REAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo REAL, actual REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total REAL, pagado REAL DEFAULT 0, tipo TEXT)''')
    
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (?,?,?,?,?)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master'))
    conn.commit()

inicializar_db()

# --- 3. SEGURIDAD Y SESIÓN ---
WHATSAPP_NUM = "50663712477"
TC_DOLAR = 518.00 

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
                    st.error("Suscripción vencida.")
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}?text=Hola GeZo, renovar mi cuenta: {u}" class="whatsapp-btn">📲 Renovar por WhatsApp</a>', unsafe_allow_html=True)
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[3], "plan":res[4]})
                    st.rerun()
            else: st.error("Acceso incorrecto.")
    st.stop()

def fmt(n): return f"₡{n:,.0f}" if st.session_state.ver_montos else "₡ *.*"

# --- 4. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    st.markdown(f'<span class="status-tag">{st.session_state.plan}</span>', unsafe_allow_html=True)
    if st.button("👁️ Privacidad"):
        st.session_state.ver_montos = not st.session_state.ver_montos
        st.rerun()
    menu = st.radio("Secciones", ["📊 Dashboard IA", "💸 Registrar", "📱 SINPE Rápido", "🤝 Deudas y Cobros", "💱 Conversor", "🎯 Metas", "⚙️ Admin"])
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 5. MÓDULOS ---

# --- DASHBOARD + COACH IA ---
if menu == "📊 Dashboard IA":
    st.header("Análisis GeZo IA")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    balance = ing - gas
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt(ing))
    c2.metric("Gastos", fmt(gas), delta_color="inverse")
    c3.metric("Saldo Real", fmt(balance))

    st.markdown('<div class="coach-box">', unsafe_allow_html=True)
    st.subheader("🤖 Recomendaciones del Coach")
    if balance < 0:
        st.error(f"⚠️ *Balance Crítico:* Estás en números rojos. Revisa la categoría de '⚖️ Pensión' o '🏠 Casa' y recorta 'Gastos Hormiga'.")
    elif balance > 0 and balance < (st.session_state.pres * 0.15):
        st.warning("🧐 *Margen Bajo:* Queda poco saldo libre. Cuidado con los SINPEs de esta semana.")
    else:
        st.success("💎 *Excelente:* Tienes capacidad de ahorro. ¡Sigue así!")
    st.markdown('</div>', unsafe_allow_html=True)

    if not df.empty and gas > 0:
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

# --- SINPE RÁPIDO (INTEGRADO) ---
elif menu == "📱 SINPE Rápido":
    st.header("📱 Envío y Registro SINPE")
    st.info("Registra el gasto aquí y luego abre tu banca en línea.")
    with st.form("sinpe_f"):
        num_s = st.text_input("Número (8 dígitos)")
        mon_s = st.number_input("Monto (₡)", min_value=0)
        det_s = st.text_input("Detalle")
        ban_s = st.selectbox("Abrir App de:", ["BNCR", "BAC", "BCR", "BP", "Promerica"])
        if st.form_submit_button("REGISTRAR Y ABRIR BANCO"):
            if len(num_s) == 8:
                c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                          (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), f"SINPE a {num_s}: {det_s}", mon_s, "Gasto", "📱 SINPE"))
                conn.commit()
                st.success("✅ Gasto registrado.")
                links = {"BNCR": "https://www.bnmovil.fi.cr/", "BAC": "https://www.baccredomatic.com/", "BCR": "https://www.bancobcr.com/", "BP": "https://www.bancopopular.fi.cr/"}
                st.markdown(f'<a href="{links.get(ban_s, "https://google.com")}" target="_blank" class="whatsapp-btn">🚀 Abrir App de {ban_s}</a>', unsafe_allow_html=True)

# --- REGISTRO MANUAL ---
elif menu == "💸 Registrar":
    st.header("Nuevo Registro")
    with st.form("reg"):
        desc = st.text_input("Detalle")
        monto = st.number_input("Monto", min_value=0.0)
        mon = st.radio("Moneda", ["₡ Colones", "$ Dólares"], horizontal=True)
        cat = st.selectbox("Categoría", ["⚖️ Pensión", "⛽ Gasolina", "🛒 Súper", "🍱 Salidas", "🏠 Casa", "⚡ Servicios", "📱 SINPE", "🎬 Suscripciones", "💡 Gastos Hormiga", "🏦 Deudas", "💰 Ahorro", "💵 Salario", "📦 Otros"])
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        if st.form_submit_button("GUARDAR"):
            m_f = monto if "₡" in mon else monto * TC_DOLAR
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, m_f, tipo, cat))
            conn.commit()
            st.success("¡Hecho!")

# --- DEUDAS + ABONO AUTOMÁTICO ---
elif menu == "🤝 Deudas y Cobros":
    st.header("Gestión de Préstamos")
    t1, t2 = st.tabs(["➕ Crear", "📋 Movimientos"])
    with t1:
        with st.form("d"):
            per = st.text_input("Nombre")
            tot = st.number_input("Monto Total", min_value=0.0)
            tip = st.selectbox("Tipo", ["Me deben (Cobro)", "Yo debo (Deuda)"])
            if st.form_submit_button("REGISTRAR"):
                c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo) VALUES (?,?,?,?,?)", (st.session_state.uid, per, tot, 0, tip))
                conn.commit()
                st.rerun()
    with t2:
        deudas = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid}", conn)
        for i, r in deudas.iterrows():
            falta = r['monto_total'] - r['pagado']
            st.markdown(f"*{r['nombre']}* | {'✅ Pagado' if falta <= 0 else f'Faltan {fmt(falta)}'}")
            if falta > 0:
                with st.expander("Abonar"):
                    ab = st.number_input("Monto", min_value=0.0, key=f"a_{r['id']}")
                    if st.button("Confirmar Abono", key=f"b_{r['id']}"):
                        c.execute("UPDATE deudas SET pagado = pagado + ? WHERE id = ?", (ab, r['id']))
                        t_m = "Ingreso" if "Me deben" in r['tipo'] else "Gasto"
                        c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                                  (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), f"Abono: {r['nombre']}", ab, t_m, "🤝 Deudas/Cobros"))
                        conn.commit()
                        st.rerun()

# --- CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Calculadora de Moneda")
    val = st.number_input("Monto", min_value=0.0)
    st.write(f"En colones: *₡{val * TC_DOLAR:,.2f}* | En dólares: *${val / TC_DOLAR:,.2f}*")

# --- METAS ---
elif menu == "🎯 Metas":
    st.header("Metas de Ahorro")
    with st.expander("Nueva Meta"):
        nm = st.text_input("Meta")
        ob = st.number_input("Objetivo", min_value=0.0)
        if st.button("Crear"):
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (?,?,?,?)", (st.session_state.uid, nm, ob, 0))
            conn.commit()
            st.rerun()
    metas = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn)
    for i, r in metas.iterrows():
        st.write(f"*{r['nombre']}*")
        st.progress(r['actual']/r['objetivo'] if r['objetivo'] > 0 else 0)

# --- ADMIN ---
elif menu == "⚙️ Admin":
    if st.session_state.rol == 'admin':
        st.header("Panel de Control")
        with st.form("admin_f"):
            un, uc = st.text_input("Usuario"), st.text_input("Clave")
            pl = st.selectbox("Plan", ["Prueba (7d)", "Mensual", "Anual", "Eterno"])
            dias = 7 if "Prueba" in pl else 30 if "Mensual" in pl else 365 if "Anual" in pl else 36500
            if st.form_submit_button("CREAR"):
                v = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (?,?,?,?,?)", (un, uc, v, 'usuario', pl))
                conn.commit()
                st.success(f"Usuario {un} creado.")
        st.table(pd.read_sql("SELECT nombre, plan, expira FROM usuarios WHERE rol!='admin'", conn))
