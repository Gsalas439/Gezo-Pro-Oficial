import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import time

# --- 1. ESTÉTICA ELITE PRO (ULTRA LIMPIEZA) ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    /* Esconder TODO lo que diga Streamlit */
    #MainMenu {visibility: hidden;} 
    header {visibility: hidden;} 
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    section[data-testid="stSidebar"] .custom-sidebar-title { color: #00f2fe; font-weight: bold; }
    
    /* Estilo General */
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    
    .bac-card {
        background: linear-gradient(135deg, #ff4b4b 0%, #a30000 100%);
        border-radius: 15px; padding: 15px; text-align: center; border: 1px solid #ff4b4b; margin-bottom: 10px;
    }
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 20px; padding: 20px; border: 1px solid #333; text-align: center;
    }
    .ia-box {
        background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe;
        padding: 20px; border-radius: 20px; border-left: 10px solid #00f2fe; margin-top: 20px;
    }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; border-left: 5px solid #00f2fe; margin-bottom: 10px; }
    .bank-btn { background: #00f2fe; color: #000 !important; padding: 12px; border-radius: 10px; text-align: center; display: block; text-decoration: none; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DB ---
@st.cache_resource
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e: st.error(f"Error Crítico DB: {e}"); st.stop()

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close()

# --- 3. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login_form"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.form_submit_button("ACCEDER AL SISTEMA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res and date.today() <= res[4]:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                st.rerun()
            else: st.error("Credenciales inválidas o cuenta expirada."); c.close()
    st.stop()

# --- 4. NAVEGACIÓN COMPLETA ---
with st.sidebar:
    st.markdown(f"## 👑 {st.session_state.uname}")
    st.info(f"Plan: {st.session_state.plan}")
    
    # Menú extendido para que no se pase nada por alto
    menu = st.radio("SECCIONES", [
        "📊 Dashboard & IA", 
        "💸 Registrar Movimiento", 
        "🎯 Mis Metas", 
        "💸 Deudas (Yo debo)", 
        "💰 Cobros (Me deben)", 
        "📱 SINPE Móvil", 
        "📜 Historial Completo"
    ])
    
    st.divider()
    with st.expander("⚙️ Ajustes de Cuenta"):
        nv_p = st.text_input("Nueva Clave", type="password")
        if st.button("Actualizar Clave"):
            conn = get_connection(); c = conn.cursor()
            c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (nv_p, st.session_state.uid))
            conn.commit(); c.close(); st.success("Clave cambiada.")
    
    if st.button("🔴 CERRAR SESIÓN"):
        st.session_state.autenticado = False
        st.rerun()

# --- 5. MÓDULOS DE LA APP ---

if menu == "📊 Dashboard & IA":
    st.header("Análisis de Generación y Divisas")
    
    # 🏦 TIPO DE CAMBIO BAC
    c_bac1, c_bac2 = st.columns(2)
    with c_bac1: st.markdown('<div class="bac-card"><small>BAC COMPRA</small><br><b>₡512.00</b></div>', unsafe_allow_html=True)
    with c_bac2: st.markdown('<div class="bac-card"><small>BAC VENTA</small><br><b>₡524.00</b></div>', unsafe_allow_html=True)
    
    per = st.select_slider("Rango:", options=["Día", "Semana", "Mes"])
    dias = {"Día": 0, "Semana": 7, "Mes": 30}
    f_in = date.today() - timedelta(days=dias[per])
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{f_in}'", get_connection())
    
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso'].monto.sum())
        gas = float(df[df['tipo']=='Gasto'].monto.sum())
        neto = ing - gas
        
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(f'<div class="balance-card"><small>INGRESOS</small><br><span class="metric-value">₡{ing:,.0f}</span></div>', unsafe_allow_html=True)
        with col2: st.markdown(f'<div class="balance-card"><small>GASTOS</small><br><span class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</span></div>', unsafe_allow_html=True)
        with col3: st.markdown(f'<div class="balance-card"><small>GENERACIÓN</small><br><span class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</span></div>', unsafe_allow_html=True)
        
        # IA CONSEJOS
        st.markdown('<div class="ia-box">', unsafe_allow_html=True)
        st.subheader("🤖 Consejo de GeZo AI")
        if neto > 0:
            ahorro = neto * 0.20
            st.success(f"¡Excelente balance! Tu liquidez ideal sugiere ahorrar **₡{ahorro:,.0f}** hoy.")
        else:
            st.error(f"Estás en déficit por ₡{abs(neto):,.0f}. ¡Cuidado con el gasto hormiga!")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.plotly_chart(px.bar(df, x='cat', y='monto', color='tipo', barmode='group', template="plotly_dark"), use_container_width=True)
    else:
        st.info("No hay datos para mostrar en este periodo.")

elif menu == "💸 Registrar Movimiento":
    st.header("Registro Manual")
    tipo = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    cats = ["Comida", "Servicios", "Salario", "Venta", "Transporte", "Ocio", "Salud", "Otro"]
    cat = st.selectbox("Categoría:", cats)
    with st.form("reg_form"):
        m = st.number_input("Monto ₡", min_value=0.0)
        d = st.text_input("Descripción")
        if st.form_submit_button("GUARDAR"):
            reg_mov(m, tipo, cat, d); st.success("Registrado."); time.sleep(0.5); st.rerun()

elif menu == "🎯 Mis Metas":
    st.header("Metas de Ahorro")
    with st.expander("➕ NUEVA META"):
        with st.form("meta_new"):
            n = st.text_input("¿Qué quieres lograr?"); obj = st.number_input("Monto Meta")
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, obj))
                conn.commit(); c.close(); st.rerun()
    
    df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>{r["nombre"]}</b>: ₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        c1, c2, c3 = st.columns([2,1,1])
        m_a = c1.number_input("Monto a abonar:", min_value=0.0, key=f"ma{r['id']}")
        if c2.button("ABONAR", key=f"ba{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}"); st.rerun()
        if c3.button("🗑️", key=f"del{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM metas WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()

elif menu == "💸 Deudas (Yo debo)":
    st.header("Mis Deudas Pendientes")
    with st.expander("➕ REGISTRAR DEUDA"):
        with st.form("d_new"):
            n = st.text_input("Acreedor"); m = st.number_input("Total"); fv = st.date_input("Vence")
            if st.form_submit_button("GUARDAR"):
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,'DEUDA',%s)", (st.session_state.uid, n, m, fv))
                conn.commit(); c.close(); st.rerun()
    
    df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA'", get_connection())
    for _, r in df_d.iterrows():
        pend = float(r['monto_total']) - float(r['pagado'])
        st.markdown(f'<div class="user-card">🔴 {r["nombre"]} | Pendiente: <b>₡{pend:,.0f}</b></div>', unsafe_allow_html=True)
        c1, c2 = st.columns([2,1]); m_p = c1.number_input("Pagar:", min_value=0.0, key=f"pd{r['id']}")
        if c2.button("PROCESAR PAGO", key=f"bpd{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (m_p, r['id'])); conn.commit(); c.close()
            reg_mov(m_p, "Gasto", "🏦 Pago Deuda", f"A: {r['nombre']}"); st.rerun()

elif menu == "💰 Cobros (Me deben)":
    st.header("Cuentas por Cobrar")
    with st.expander("➕ REGISTRAR COBRO"):
        with st.form("c_new"):
            n = st.text_input("Persona"); m = st.number_input("Monto"); fv = st.date_input("Fecha Promesa")
            if st.form_submit_button("GUARDAR"):
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,'COBRO',%s)", (st.session_state.uid, n, m, fv))
                conn.commit(); c.close(); st.rerun()
    
    df_c = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='COBRO'", get_connection())
    for _, r in df_c.iterrows():
        pend = float(r['monto_total']) - float(r['pagado'])
        st.markdown(f'<div class="user-card">🟢 {r["nombre"]} | Pendiente: <b>₡{pend:,.0f}</b></div>', unsafe_allow_html=True)
        c1, c2 = st.columns([2,1]); m_r = c1.number_input("Recibido:", min_value=0.0, key=f"pc{r['id']}")
        if c2.button("RECIBIR PAGO", key=f"bpc{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (m_r, r['id'])); conn.commit(); c.close()
            reg_mov(m_r, "Ingreso", "💸 Cobro Recibido", f"De: {r['nombre']}"); st.rerun()

elif menu == "📱 SINPE Móvil":
    st.header("SINPE Directo")
    num = st.text_input("Número de Teléfono:"); monto = st.number_input("Monto ₡", min_value=0.0)
    if st.button("REGISTRAR Y ABRIR BANCO"):
        reg_mov(monto, "Gasto", "📱 SINPE", f"Pago a: {num}")
        st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🏦 IR AL BANCO AHORA</a>', unsafe_allow_html=True)

elif menu == "📜 Historial Completo":
    st.header("Registro Histórico")
    df_h = pd.read_sql(f"SELECT id, fecha, cat, monto, tipo, descrip FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", get_connection())
    st.dataframe(df_h, use_container_width=True)
    if st.button("BORRAR TODO EL HISTORIAL"):
        conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM movimientos WHERE usuario_id={st.session_state.uid}"); conn.commit(); c.close(); st.rerun()
