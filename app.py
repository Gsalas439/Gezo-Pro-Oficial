import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
import io

# --- 1. ESTÉTICA DE ALTO CONTRASTE ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(0, 198, 255, 0.1) 0%, rgba(0, 114, 255, 0.1) 100%);
        border-radius: 15px; padding: 20px; border: 1px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        color: black; font-weight: bold; height: 3.5em; width: 100%; border: none;
    }
    .coach-box {
        background: rgba(255, 255, 255, 0.03); padding: 20px; border-radius: 15px;
        border: 1px dashed #00f2fe; margin: 20px 0;
    }
    .emergencia-box {
        background: linear-gradient(90deg, #333333 0%, #222222 100%);
        padding: 15px; border-radius: 12px; border-left: 5px solid #ff007f; margin-bottom: 20px;
    }
    .status-tag {
        padding: 4px 10px; border-radius: 15px; font-size: 11px;
        background: rgba(0, 198, 255, 0.2); border: 1px solid #00c6ff; color: #00c6ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS (POSTGRESQL) ---
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT, clave TEXT, expira DATE, rol TEXT, 
                  plan TEXT, presupuesto DECIMAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo TEXT)''')
    
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (%s, %s, %s, %s, %s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master'))
    conn.commit()
    c.close()
    conn.close()

# Ejecutar inicialización al arranque
try:
    inicializar_db()
except Exception as e:
    st.error(f"Error de conexión a la base de datos: {e}")
    st.stop()

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
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT id, nombre, rol, presupuesto, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                venc = res[5]
                if datetime.now().date() > venc:
                    st.error("Suscripción vencida.")
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}" target="_blank" class="whatsapp-btn">📲 Contactar para Renovar</a>', unsafe_allow_html=True)
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[3], "plan":res[4]})
                    st.rerun()
            else: st.error("Credenciales incorrectas.")
            c.close()
            conn.close()
    st.stop()

def fmt(n): return f"₡{float(n):,.0f}" if st.session_state.ver_montos else "₡ *.*"

# --- 4. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    st.markdown(f'<span class="status-tag">{st.session_state.plan}</span>', unsafe_allow_html=True)
    if st.button("👁️ Privacidad"):
        st.session_state.ver_montos = not st.session_state.ver_montos
        st.rerun()
    menu = st.radio("Secciones", ["📊 Dashboard IA", "📱 SINPE Rápido", "💸 Registrar", "🤝 Deudas y Cobros", "💱 Conversor", "🎯 Metas", "⚙️ Admin"])
    st.markdown("---")
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 5. MÓDULOS ---

if menu == "📊 Dashboard IA":
    st.header("Análisis GeZo IA")
    st.markdown('<div class="emergencia-box">🛡️ RETO: Fondo de Emergencia ₡500,000</div>', unsafe_allow_html=True)
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    balance = float(ing) - float(gas)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt(ing))
    c2.metric("Gastos", fmt(gas), delta_color="inverse")
    c3.metric("Saldo Real", fmt(balance))

    st.markdown('<div class="coach-box">', unsafe_allow_html=True)
    st.subheader("🤖 Recomendaciones")
    if balance < 0:
        st.error(f"⚠️ Revisa tus gastos en '⚖️ Pensión' o '📱 SINPE'. Estás en números rojos.")
    else:
        st.success("💎 Balance saludable. ¡No olvides abonar a tus metas!")
    st.markdown('</div>', unsafe_allow_html=True)

    if not df.empty:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Excel (CSV)", csv, "Reporte_GeZo.csv", "text/csv")
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

elif menu == "📱 SINPE Rápido":
    st.header("Envío y Registro SINPE")
    with st.form("sinpe_f"):
        num = st.text_input("Número (8 dígitos)")
        mon = st.number_input("Monto (₡)", min_value=0)
        det = st.text_input("Detalle")
        ban = st.selectbox("Abrir Banco:", ["BNCR", "BAC", "BCR", "BP"])
        if st.form_submit_button("REGISTRAR Y ABRIR APP"):
            if len(num) == 8:
                conn = get_connection()
                c = conn.cursor()
                c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)",
                          (st.session_state.uid, datetime.now().date(), f"SINPE a {num}: {det}", mon, "Gasto", "📱 SINPE"))
                conn.commit()
                c.close()
                conn.close()
                links = {"BNCR": "https://www.bnmovil.fi.cr/", "BAC": "https://www.baccredomatic.com/", "BCR": "https://www.bancobcr.com/", "BP": "https://www.bancopopular.fi.cr/"}
                st.markdown(f'<a href="{links.get(ban)}" target="_blank" class="whatsapp-btn">🚀 Ir a {ban}</a>', unsafe_allow_html=True)

elif menu == "💸 Registrar":
    st.header("Registro Manual")
    with st.form("reg_m"):
        desc = st.text_input("Descripción")
        monto = st.number_input("Monto", min_value=0.0)
        cat = st.selectbox("Categoría", ["⚖️ Pensión", "⛽ Gasolina", "🛒 Súper", "🏠 Casa", "⚡ Servicios", "📱 SINPE", "🎬 Suscripciones", "💡 Gastos Hormiga", "🏦 Deudas", "💰 Ahorro", "💵 Salario", "📦 Otros"])
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        if st.form_submit_button("GUARDAR"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)",
                      (st.session_state.uid, datetime.now().date(), desc, monto, tipo, cat))
            conn.commit()
            c.close()
            conn.close()
            st.success("¡Registro exitoso!")

elif menu == "🤝 Deudas y Cobros":
    st.header("Préstamos")
    t1, t2 = st.tabs(["➕ Nueva", "📋 Gestión"])
    with t1:
        with st.form("d_n"):
            p_n = st.text_input("Nombre")
            p_m = st.number_input("Monto Total", min_value=0.0)
            p_t = st.selectbox("Tipo", ["Me deben", "Yo debo"])
            if st.form_submit_button("CREAR"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo) VALUES (%s,%s,%s,%s,%s)", (st.session_state.uid, p_n, p_m, 0, p_t))
                conn.commit()
                c.close()
                conn.close()
                st.rerun()
    with t2:
        deudas = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid}", get_connection())
        for i, r in deudas.iterrows():
            falta = float(r['monto_total']) - float(r['pagado'])
            st.write(f"*{r['nombre']}* | Resta: {fmt(falta)}")
            if falta > 0:
                with st.expander("Abonar"):
                    ab = st.number_input("Monto Abono", min_value=0.0, key=f"ab_{r['id']}")
                    if st.button("Confirmar Abono", key=f"bt_{r['id']}"):
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("UPDATE deudas SET pagado = pagado + %s WHERE id = %s", (ab, r['id']))
                        t_mov = "Ingreso" if r['tipo'] == "Me deben" else "Gasto"
                        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)",
                                  (st.session_state.uid, datetime.now().date(), f"Abono {r['nombre']}", ab, t_mov, "🤝 Deudas/Cobros"))
                        conn.commit()
                        c.close()
                        conn.close()
                        st.rerun()

elif menu == "💱 Conversor":
    st.header("Calculadora ₡/$")
    v = st.number_input("Monto", min_value=0.0)
    st.write(f"En colones: *₡{v * TC_DOLAR:,.2f}* | En dólares: *${v / TC_DOLAR:,.2f}*")

elif menu == "🎯 Metas":
    st.header("Ahorros")
    metas = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for i, r in metas.iterrows():
        st.write(f"*{r['nombre']}*")
        st.progress(float(r['actual'])/float(r['objetivo']) if float(r['objetivo']) > 0 else 0)

elif menu == "⚙️ Admin":
    if st.session_state.rol == 'admin':
        st.header("Control Maestro")
        with st.form("adm"):
            nu, nc = st.text_input("Usuario"), st.text_input("Clave")
            np = st.selectbox("Plan", ["Prueba", "Mensual", "Anual"])
            dias = 7 if "Prueba" in np else 30 if "Mensual" in np else 365
            if st.form_submit_button("CREAR USUARIO"):
                vf = (datetime.now() + timedelta(days=dias)).date()
                conn = get_connection()
                c = conn.cursor()
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (%s,%s,%s,%s,%s)", (nu, nc, vf, 'usuario', np))
                conn.commit()
                c.close()
                conn.close()
                st.success(f"Usuario {nu} creado.")
        st.table(pd.read_sql("SELECT nombre, plan, expira FROM usuarios WHERE rol!='admin'", get_connection()))
