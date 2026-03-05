import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px

# --- 1. CONFIGURACIÓN DE INTERFAZ ELITE (UI NATIVA) ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Ocultar elementos de Streamlit */
    header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer, .stDeployButton {display: none !important;}
    .block-container {padding-top: 1rem !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    
    /* Estilo de Tarjetas */
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 15px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 15px;
    }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.85em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    
    .bac-card { background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%); border-radius: 12px; padding: 12px; text-align: center; border: 1px solid #ff4b4b; color: white; }
    .ia-box { background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; padding: 20px; border-radius: 15px; border-left: 8px solid #00f2fe; margin-top: 10px; }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; border: 1px solid #222; border-left: 5px solid #00f2fe; margin-bottom: 10px; }
    
    /* Botón SINPE Estilo Banco */
    .btn-banco {
        background-color: #00f2fe; color: #000 !important; padding: 18px; border-radius: 12px;
        text-decoration: none; font-weight: bold; text-align: center; display: block; margin-top: 10px;
        box-shadow: 0 4px 15px rgba(0, 242, 254, 0.3);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS ---
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close(); conn.close()

# --- 3. LOGIN CON PARCHE DE SEGURIDAD (URL CLEANER) ---
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
            if st.form_submit_button("ACCEDER AL SISTEMA", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone(); c.close(); conn.close()
                if res:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    st.query_params["session_token"] = str(res[0]); st.rerun()
                else: st.error("Credenciales incorrectas")
    st.stop()

# --- 4. ESTRUCTURA DE NAVEGACIÓN ---
st.markdown(f"### 👑 **{st.session_state.uname}** | Panel {st.session_state.plan}")
t1, t2, t3, t4, t5, t6, t7 = st.tabs(["📊 DASHBOARD", "💸 REGISTRO", "🎯 METAS", "🏦 DEUDAS/COBROS", "📱 SINPE", "📜 HISTORIAL", "⚙️ AJUSTES"])

# --- DASHBOARD & IA ---
with t1:
    c_bac1, c_bac2, c_bac3 = st.columns([1,1,2])
    c_bac1.markdown('<div class="bac-card"><small>BAC COMPRA</small><br><b>₡512.00</b></div>', unsafe_allow_html=True)
    c_bac2.markdown('<div class="bac-card"><small>BAC VENTA</small><br><b>₡524.00</b></div>', unsafe_allow_html=True)
    
    st.divider()
    rango = st.radio("Periodo:", ["Hoy", "7 días", "30 días"], horizontal=True)
    dias = {"Hoy": 0, "7 días": 7, "30 días": 30}
    f_inicio = date.today() - timedelta(days=dias[rango])
    
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{f_inicio}'", conn)
    df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND pagado < monto_total", conn)
    conn.close()
    
    ing = float(df[df['tipo']=='Ingreso']['monto'].sum()) if not df.empty else 0
    gas = float(df[df['tipo']=='Gasto']['monto'].sum()) if not df.empty else 0
    neto = ing - gas
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="balance-card"><p class="metric-label">Gastos</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
    col3.markdown(f'<div class="balance-card"><p class="metric-label">Neto</p><p class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</p></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="ia-box">', unsafe_allow_html=True)
    st.markdown("#### 🤖 GeZo AI Advisor")
    if not df_d.empty: st.warning(f"⚠️ Alerta: Tienes {len(df_d)} cuentas pendientes de pago.")
    st.write(f"Tu capacidad de ahorro actual para este periodo es de **₡{max(0, neto*0.2):,.0f}** (20%).")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if not df[df['tipo']=='Gasto'].empty:
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=0.5, template="plotly_dark"), use_container_width=True)

# --- REGISTRO ---
with t2:
    tipo = st.radio("Tipo de Movimiento", ["Gasto", "Ingreso"], horizontal=True)
    cats = ["Súper/Comida", "Servicios", "Casa", "Transporte", "Ocio", "Salud", "Educación", "Otros"] if tipo == "Gasto" else ["Salario", "Venta", "Intereses", "Regalo"]
    with st.form("f_registro"):
        m = st.number_input("Monto (₡)", min_value=0.0, step=500.0)
        c = st.selectbox("Categoría", cats)
        d = st.text_input("Descripción opcional")
        if st.form_submit_button("GUARDAR EN DB", use_container_width=True):
            reg_mov(m, tipo, c, d); st.success("¡Registrado con éxito!"); st.rerun()

# --- METAS ---
with t3:
    with st.expander("➕ Crear Nueva Meta"):
        with st.form("f_metas"):
            n = st.text_input("¿Qué quieres lograr?"); o = st.number_input("Precio total", min_value=1.0)
            if st.form_submit_button("CREAR PROYECTO"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); conn.close(); st.rerun()
    
    conn = get_connection(); df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn); conn.close()
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>Progreso: ₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        ca, cb, cc = st.columns([2,1,1])
        m_a = ca.number_input("Abonar monto:", min_value=0.0, key=f"ma_{r['id']}")
        if cb.button("DEPOSITAR", key=f"ba_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close(); conn.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}"); st.rerun()
        if cc.button("🗑️", key=f"dm_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM metas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- DEUDAS Y COBROS ---
with t4:
    tab_d, tab_c = st.tabs(["🔴 DEUDAS", "🟢 COBROS"])
    def render_seccion(tipo_rec):
        with st.expander(f"➕ Registrar {tipo_rec}"):
            with st.form(f"f_{tipo_rec}"):
                nom = st.text_input("Nombre / Entidad"); mon = st.number_input("Monto", min_value=1.0); ven = st.date_input("Fecha Vencimiento")
                if st.form_submit_button("GUARDAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,%s,%s)", (st.session_state.uid, nom, mon, tipo_rec, ven)); conn.commit(); c.close(); conn.close(); st.rerun()
        
        conn = get_connection(); df_x = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='{tipo_rec}'", conn); conn.close()
        for _, r in df_x.iterrows():
            pend = float(r['monto_total']) - float(r['pagado'])
            vence_rojo = "color:#ff4b4b;" if r['fecha_vence'] <= date.today() and pend > 0 else ""
            st.markdown(f'<div class="user-card"><b>{r["nombre"]}</b> | Pendiente: ₡{pend:,.0f}<br><span style="{vence_rojo}">Vence: {r["fecha_vence"]}</span></div>', unsafe_allow_html=True)
            if pend > 0:
                c1, c2, c3 = st.columns([2,1,1])
                m_p = c1.number_input("Abono", min_value=0.0, max_value=pend, key=f"px_{r['id']}")
                if c2.button("ABONAR", key=f"bx_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (m_p, r['id'])); conn.commit(); c.close(); conn.close()
                    reg_mov(m_p, "Gasto" if tipo_rec=='DEUDA' else "Ingreso", f"🏦 {tipo_rec}", f"Pago a {r['nombre']}"); st.rerun()
                if c3.button("🗑️", key=f"del_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM deudas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()
    with tab_d: render_seccion('DEUDA')
    with tab_c: render_seccion('COBRO')

# --- SINPE MÓVIL (COMPLETO) ---
with t5:
    st.subheader("📱 Registro SINPE Rápido")
    with st.form("f_sinpe_full"):
        col_s1, col_s2 = st.columns(2)
        num_s = col_s1.text_input("Número de Teléfono")
        mon_s = col_s2.number_input("Monto a enviar (₡)", min_value=0.0, step=100.0)
        det_s = st.text_input("Detalle del SINPE")
        if st.form_submit_button("REGISTRAR GASTO Y ABRIR BANCO", use_container_width=True):
            reg_mov(mon_s, "Gasto", "📱 SINPE", f"SINPE a: {num_s} ({det_s})")
            st.success("Gasto registrado. Ahora abre tu banco.")
    
    st.markdown('<a href="https://www.google.com" target="_blank" class="btn-banco">🏦 ABRIR APLICACIÓN BANCARIA</a>', unsafe_allow_html=True)

# --- HISTORIAL ---
with t6:
    st.subheader("📜 Movimientos Recientes")
    conn = get_connection(); df_h = pd.read_sql(f"SELECT fecha, tipo, cat, monto, descrip FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC LIMIT 100", conn); conn.close()
    st.dataframe(df_h, use_container_width=True, hide_index=True)

# --- AJUSTES ---
with t7:
    st.subheader("Configuración")
    with st.form("f_pass"):
        new_p = st.text_input("Nueva Contraseña", type="password")
        if st.form_submit_button("ACTUALIZAR CONTRASEÑA"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (new_p, st.session_state.uid)); conn.commit(); c.close(); conn.close(); st.success("Contraseña actualizada.")
    
    st.divider()
    if st.button("🚪 CERRAR SESIÓN TOTAL", type="primary", use_container_width=True):
        st.session_state.autenticado = False; st.query_params.clear(); st.rerun()
