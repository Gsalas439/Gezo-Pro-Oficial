import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px

# --- 1. CONFIGURACIÓN DE INTERFAZ ELITE ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer, .stDeployButton {display: none !important;}
    .block-container {padding-top: 1.5rem !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    .balance-card { background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%); border-radius: 15px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.85em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    .bac-card { background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%); border-radius: 12px; padding: 12px; text-align: center; border: 1px solid #ff4b4b; color: white; font-weight: bold; }
    .ia-box { background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; padding: 20px; border-radius: 15px; border-left: 8px solid #00f2fe; margin-top: 10px; }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; border: 1px solid #222; border-left: 5px solid #00f2fe; margin-bottom: 10px; }
    .btn-banco { background-color: #00f2fe; color: #000 !important; padding: 15px; border-radius: 10px; text-decoration: none; font-weight: 900; text-align: center; display: block; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES DE BASE DE DATOS ---
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close(); conn.close()

# --- 3. LOGIN & SEGURIDAD (URL CLEANER) ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    token_url = st.query_params.get("session_token")
    if token_url:
        conn = get_connection(); c = conn.cursor()
        c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE id=%s", (token_url,))
        res = c.fetchone()
        if res and date.today() <= res[4]:
            st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
            st.query_params.clear(); st.rerun()
        c.close(); conn.close()

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #00f2fe;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login"):
            u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
            if st.form_submit_button("INGRESAR", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone(); c.close(); conn.close()
                if res:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    st.query_params["session_token"] = str(res[0]); st.rerun()
                else: st.error("Acceso denegado")
    st.stop()

# --- 4. NAVEGACIÓN ---
t1, t2, t3, t4, t5, t6, t7 = st.tabs(["📊 DASHBOARD", "💸 REGISTRO", "🎯 METAS", "🏦 CUENTAS", "📱 SINPE", "📜 HISTORIAL", "⚙️ AJUSTES"])

# --- DASHBOARD ---
with t1:
    c_bac1, c_bac2, c_bac3 = st.columns([1,1,2])
    c_bac1.markdown('<div class="bac-card"><small>BAC COMPRA</small><br>₡512.00</div>', unsafe_allow_html=True)
    c_bac2.markdown('<div class="bac-card"><small>BAC VENTA</small><br>₡524.00</div>', unsafe_allow_html=True)
    
    conn = get_connection()
    df = pd.read_sql(f"SELECT monto, tipo, cat FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{date.today() - timedelta(days=30)}'", conn)
    df_d = pd.read_sql(f"SELECT id FROM deudas WHERE usuario_id={st.session_state.uid} AND pagado < monto_total", conn)
    conn.close()
    
    ing = float(df[df['tipo']=='Ingreso']['monto'].sum()) if not df.empty else 0
    gas = float(df[df['tipo']=='Gasto']['monto'].sum()) if not df.empty else 0
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="balance-card"><p class="metric-label">Gastos</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
    col3.markdown(f'<div class="balance-card"><p class="metric-label">Neto</p><p class="metric-value" style="color:#2ecc71;">₡{(ing-gas):,.0f}</p></div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="ia-box">#### 🤖 GeZo Advisor<br>Tienes {len(df_d)} deudas pendientes. Ahorro sugerido: ₡{(ing-gas)*0.2 if ing>gas else 0:,.0f}</div>', unsafe_allow_html=True)

# --- REGISTRO ---
with t2:
    tipo = st.radio("Tipo", ["Gasto", "Ingreso"], horizontal=True)
    with st.form("f_reg"):
        m = st.number_input("Monto", min_value=0.0)
        c = st.selectbox("Categoría", ["Comida", "Servicios", "Salario", "Ocio", "Otros"])
        d = st.text_input("Nota")
        if st.form_submit_button("GUARDAR"):
            reg_mov(m, tipo, c, d); st.success("Registrado"); st.rerun()

# --- METAS ---
with t3:
    with st.expander("➕ Nueva Meta"):
        with st.form("f_m"):
            n = st.text_input("Meta"); o = st.number_input("Objetivo", min_value=1.0)
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); conn.close(); st.rerun()
    
    conn = get_connection(); df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn); conn.close()
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b> (₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f})</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        m_a = st.number_input("Abonar", min_value=0.0, key=f"m_{r['id']}")
        if st.button("DEPOSITAR", key=f"b_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close(); conn.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}"); st.rerun()

# --- CUENTAS (DEUDAS/COBROS) ---
with t4:
    def render_x(t_r):
        with st.expander(f"Nuevo {t_r}"):
            with st.form(f"f_{t_r}"):
                nom = st.text_input("Nombre"); mon = st.number_input("Monto"); ven = st.date_input("Vence")
                if st.form_submit_button("OK"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,%s,%s)", (st.session_state.uid, nom, mon, t_r, ven)); conn.commit(); c.close(); conn.close(); st.rerun()
        conn = get_connection(); df_x = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='{t_r}'", conn); conn.close()
        for _, r in df_x.iterrows():
            p = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card"><b>{r["nombre"]}</b> | Pendiente: ₡{p:,.0f}</div>', unsafe_allow_html=True)
            if p > 0:
                am = st.number_input("Abono", min_value=0.0, max_value=p, key=f"ax_{r['id']}")
                if st.button("PAGAR", key=f"bx_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (am, r['id'])); conn.commit(); c.close(); conn.close()
                    reg_mov(am, "Gasto" if t_r=='DEUDA' else "Ingreso", f"🏦 {t_r}", r['nombre']); st.rerun()
    c1, c2 = st.tabs(["🔴 DEUDAS", "🟢 COBROS"])
    with c1: render_x('DEUDA')
    with c2: render_x('COBRO')

# --- SINPE CON AGENDA ---
with t5:
    conn = get_connection()
    c = conn.cursor(); c.execute("CREATE TABLE IF NOT EXISTS contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)"); conn.commit()
    df_c = pd.read_sql(f"SELECT * FROM contactos WHERE usuario_id={st.session_state.uid}", conn); conn.close()
    
    st.subheader("📱 SINPE Móvil")
    sel = st.selectbox("Contacto:", ["Manual"] + [f"{r['nombre']} ({r['telefono']})" for _, r in df_c.iterrows()])
    with st.form("f_s"):
        num = st.text_input("Teléfono", value="" if sel=="Manual" else sel.split("(")[1][:-1])
        mon = st.number_input("Monto (₡)")
        if st.form_submit_button("REGISTRAR Y BANCO"):
            reg_mov(mon, "Gasto", "📱 SINPE", f"A: {num}"); st.markdown('<a href="https://www.google.com" target="_blank" class="btn-banco">🏦 IR AL BANCO</a>', unsafe_allow_html=True)
    
    with st.expander("👥 Agenda"):
        with st.form("f_ac"):
            nc = st.text_input("Nombre"); tc = st.text_input("Tel")
            if st.form_submit_button("GUARDAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO contactos (usuario_id, nombre, telefono) VALUES (%s,%s,%s)", (st.session_state.uid, nc, tc)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- HISTORIAL (CORREGIDO) ---
with t6:
    st.subheader("📜 Historial")
    conn = get_connection()
    # Usamos nombres de columna en minúsculas para evitar el KeyError
    df_h = pd.read_sql(f"SELECT fecha, tipo, cat, monto, descrip FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    if not df_h.empty:
        # Formateamos usando el nombre de columna exacto que devuelve SQL (minúsculas)
        df_h['monto'] = df_h['monto'].apply(lambda x: f"₡{float(x):,.0f}")
        st.dataframe(df_h, use_container_width=True, hide_index=True)

# --- AJUSTES ---
with t7:
    if st.button("🚪 CERRAR SESIÓN", use_container_width=True):
        st.session_state.autenticado = False; st.query_params.clear(); st.rerun()
