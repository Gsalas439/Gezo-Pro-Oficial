import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date

# --- 1. CONFIGURACIÓN BÁSICA (SIN CSS COMPLEJO PARA EVITAR ERRORES) ---
st.set_page_config(page_title="GeZo Elite", layout="wide")

# --- 2. MOTOR DB ---
@st.cache_resource
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"])
    except: st.error("Error de conexión DB"); st.stop()

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close()

# --- 3. LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.header("💎 GeZo Elite Pro - Acceso")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("ENTRAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res and date.today() <= res[2]:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1]})
                st.rerun()
            else: st.error("Error en datos o membresía vencida.")
    st.stop()

# --- 4. MENÚ PRINCIPAL POR PESTAÑAS (ARRIBA Y VISIBLE) ---
st.title(f"👑 Panel de {st.session_state.uname}")

# Aquí creamos los botones grandes en la parte superior
t_dash, t_reg, t_metas, t_deudas, t_sinpe, t_pass = st.tabs([
    "📊 DASHBOARD & IA", 
    "💸 REGISTRAR", 
    "🎯 METAS", 
    "🏦 DEUDAS/COBROS", 
    "📱 SINPE", 
    "🔐 MI CLAVE"
])

# --- 5. CONTENIDO DE CADA PESTAÑA ---

with t_dash:
    st.subheader("Indicadores BAC (Tipo de Cambio)")
    c1, c2 = st.columns(2)
    c1.metric("BAC COMPRA", "₡512.00")
    c2.metric("BAC VENTA", "₡524.00")
    
    st.divider()
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    if not df.empty:
        neto = float(df[df['tipo']=='Ingreso'].monto.sum()) - float(df[df['tipo']=='Gasto'].monto.sum())
        
        st.info(f"🤖 IA ADVISOR: Tu balance es ₡{neto:,.0f}. Ahorro sugerido (20%): ₡{neto*0.20:,.0f}")
        
        import plotly.express as px
        fig = px.pie(df, values='monto', names='tipo', hole=.3, color_discrete_sequence=['#00f2fe', '#ff4b4b'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No hay datos registrados aún.")

with t_reg:
    st.subheader("Registrar Movimiento")
    with st.form("f_reg"):
        tipo = st.radio("Tipo", ["Gasto", "Ingreso"], horizontal=True)
        monto = st.number_input("Monto ₡", min_value=0.0)
        cat = st.selectbox("Categoría", ["Salario", "Venta", "Comida", "Servicios", "Otros"])
        desc = st.text_input("Nota")
        if st.form_submit_button("GUARDAR"):
            reg_mov(monto, tipo, cat, desc)
            st.success("Guardado correctamente")

with t_metas:
    st.subheader("Metas de Ahorro")
    # Formulario rápido para metas
    with st.expander("Crear Meta"):
        m_nom = st.text_input("Nombre Meta")
        m_obj = st.number_input("Monto Objetivo")
        if st.button("Crear"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, m_nom, m_obj))
            conn.commit(); c.close(); st.rerun()

with t_deudas:
    st.subheader("Deudas y Cobros")
    # Lógica simplificada de visualización
    st.write("Gestiona tus cuentas pendientes aquí.")

with t_sinpe:
    st.subheader("Registro SINPE")
    s_num = st.text_input("Número")
    s_mon = st.number_input("Monto SINPE")
    if st.button("Registrar SINPE"):
        reg_mov(s_mon, "Gasto", "SINPE", f"A: {s_num}")
        st.success("Registrado. Recuerda hacer la transferencia en tu app bancaria.")

with t_pass:
    st.subheader("Seguridad")
    new_p = st.text_input("Nueva Contraseña", type="password")
    if st.button("Cambiar Clave"):
        conn = get_connection(); c = conn.cursor()
        c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (new_p, st.session_state.uid))
        conn.commit(); c.close(); st.success("Clave actualizada")

if st.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()
