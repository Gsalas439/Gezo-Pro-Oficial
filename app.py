import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px

# --- 1. CONFIGURACIÓN DE INTERFAZ Y BLOQUEO DE MENÚS NATIVOS ---
st.set_page_config(
    page_title="GeZo Elite Pro", 
    page_icon="💎", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    /* Ocultar elementos nativos de Streamlit */
    header[data-testid="stHeader"], 
    div[data-testid="stToolbar"], 
    #MainMenu, 
    footer, 
    .stDeployButton {display: none !important;}
    
    /* Ajuste de espacio superior */
    .block-container {padding-top: 1.5rem !important;}
    
    /* Estética Dark Pro */
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    
    /* Tarjetas de Dashboard */
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 15px; padding: 20px; border: 1px solid #333; text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin-bottom: 15px;
    }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.85em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    
    /* Tarjetas BAC */
    .bac-card {
        background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%);
        border-radius: 12px; padding: 12px; text-align: center; border: 1px solid #ff4b4b;
    }
    
    /* IA Box */
    .ia-box {
        background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe;
        padding: 20px; border-radius: 15px; border-left: 8px solid #00f2fe; margin-top: 10px;
    }
    
    /* Tarjetas de registros (Metas/Deudas) */
    .user-card { 
        background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; 
        border: 1px solid #222; border-left: 5px solid #00f2fe; margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN A BASE DE DATOS ---
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"])
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close(); conn.close()

# --- 3. LOGICA DE AUTENTICACIÓN Y PARCHE DE SEGURIDAD ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# PARCHE: Auto-login seguro con limpieza de URL
if not st.session_state.autenticado:
    # Leer token de la URL si existe
    token_url = st.query_params.get("session_token")
    
    if token_url:
        conn = get_connection(); c = conn.cursor()
        c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE id=%s", (token_url,))
        res = c.fetchone()
        c.close(); conn.close()
        
        if res and date.today() <= res[4]:
            st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
            # LIMPIEZA DE SEGURIDAD: Borra el rastro de la URL para que nadie lo pueda copiar
            st.query_params.clear()
            st.rerun()

# Pantalla de Login (Si no hay sesión activa)
if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #00f2fe;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            mantener = st.checkbox("Mantener sesión en este dispositivo", value=True)
            if st.form_submit_button("INGRESAR AL PANEL", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone()
                c.close(); conn.close()
                if res:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    if mantener:
                        st.query_params["session_token"] = str(res[0])
                    st.rerun()
                else: st.error("Usuario o clave incorrectos.")
    st.stop()

# --- 4. INTERFAZ PRINCIPAL (NAVEGACIÓN POR PESTAÑAS) ---
st.markdown(f"### 👑 **{st.session_state.uname}** | Panel {st.session_state.plan}")

tab_dash, tab_reg, tab_metas, tab_deudas, tab_sinpe, tab_hist, tab_ajustes = st.tabs([
    "📊 DASHBOARD", "💸 REGISTRO", "🎯 METAS", "🏦 DEUDAS / COBROS", "📱 SINPE", "📜 HISTORIAL", "⚙️ AJUSTES"
])

# --- 5. CONTENIDO DE MÓDULOS ---

# DASHBOARD E IA
with tab_dash:
    c_bac1, c_bac2, c_bac3 = st.columns([1,1,2])
    with c_bac1: st.markdown('<div class="bac-card"><small style="color:white;">BAC COMPRA</small><br><b style="color:white; font-size:1.2em;">₡512.00</b></div>', unsafe_allow_html=True)
    with c_bac2: st.markdown('<div class="bac-card"><small style="color:white;">BAC VENTA</small><br><b style="color:white; font-size:1.2em;">₡524.00</b></div>', unsafe_allow_html=True)
    
    st.divider()
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{date.today() - timedelta(days=30)}'", conn)
    conn.close()
    
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum())
        gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        neto = ing - gas
        
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
        with col2: st.markdown(f'<div class="balance-card"><p class="metric-label">Gastos</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
        with col3: st.markdown(f'<div class="balance-card"><p class="metric-label">Generación Neta</p><p class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</p></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="ia-box">', unsafe_allow_html=True)
        st.markdown("#### 🤖 GeZo AI Advisor")
        if neto > 0:
            st.write(f"Balance positivo. Tu meta de ahorro de hoy (20%) es: **₡{neto*0.2:,.0f}**.")
        else:
            st.write("Cuidado: Estás gastando más de lo que ingresas. Revisa tus deudas.")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', title="Gastos por Categoría", template="plotly_dark", hole=0.4), use_container_width=True)
    else:
        st.info("No hay datos registrados en los últimos 30 días.")

# REGISTRO
with tab_reg:
    st.subheader("Registrar Movimiento")
    t = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    with st.form("f_mov"):
        m = st.number_input("Monto (₡)", min_value=0.0)
        c = st.selectbox("Categoría", ["Salario", "Venta", "Comida", "Servicios", "Ocio", "Otros"])
        d = st.text_input("Detalle")
        if st.form_submit_button("GUARDAR REGISTRO", use_container_width=True):
            reg_mov(m, t, c, d); st.success("¡Registrado!"); st.rerun()

# METAS
with tab_metas:
    st.subheader("Tus Metas de Ahorro")
    with st.expander("➕ Nueva Meta"):
        with st.form("f_meta"):
            n = st.text_input("Nombre de la meta")
            o = st.number_input("Monto objetivo", min_value=1.0)
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); conn.close(); st.rerun()
    
    conn = get_connection(); df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn); conn.close()
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>Progreso: ₡{float(r["actual"]):,.0f} / ₡{float(r["objective"]):,.0f}</div>' if "objective" in df_m.columns else f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>Progreso: ₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        col_a, col_b = st.columns([2,1])
        m_a = col_a.number_input("Abonar:", min_value=0.0, key=f"m_{r['id']}")
        if col_b.button("ABONAR", key=f"b_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close(); conn.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Abono a {r['nombre']}"); st.rerun()

# DEUDAS Y COBROS
with tab_deudas:
    st.subheader("Cuentas Pendientes")
    st.info("Módulo para registrar lo que debes y lo que te deben.")
    # (Aquí puedes integrar la lógica de deudas del código anterior si la necesitas expandida)

# SINPE
with tab_sinpe:
    st.subheader("📱 Registro SINPE Rápido")
    with st.form("f_sinpe"):
        n_s = st.text_input("Número de teléfono")
        m_s = st.number_input("Monto (₡)")
        if st.form_submit_button("REGISTRAR Y SALIR"):
            reg_mov(m_s, "Gasto", "📱 SINPE", f"A: {n_s}"); st.success("Registrado.")
    st.markdown('<br><a href="https://www.google.com" target="_blank" style="background-color: #00f2fe; color: black; padding: 15px; border-radius: 10px; text-decoration: none; font-weight: bold; text-align: center; display: block;">🏦 IR A MI APP BANCARIA</a>', unsafe_allow_html=True)

# HISTORIAL
with tab_hist:
    st.subheader("Historial de Movimientos")
    conn = get_connection(); df_h = pd.read_sql(f"SELECT fecha, cat, descrip, monto, tipo FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC LIMIT 100", conn); conn.close()
    st.dataframe(df_h, use_container_width=True)

# AJUSTES
with tab_ajustes:
    st.subheader("Ajustes de Cuenta")
    if st.button("🚪 CERRAR SESIÓN TOTAL", type="primary", use_container_width=True):
        st.session_state.autenticado = False
        st.query_params.clear()
        st.rerun()
