import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io
import time

# --- 1. ESTÉTICA ELITE PRO ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.08); border-radius: 20px; padding: 25px; 
        border: 1px solid #00c6ff; box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15); border-left: 10px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        color: #000 !important; font-weight: 800; width: 100%; border: none; height: 3em;
        transition: 0.3s all; text-transform: uppercase;
    }
    .user-card { background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 15px; border: 1px solid #333; margin-bottom: 15px; border-left: 5px solid #00f2fe; }
    .alert-box { padding: 15px; background: rgba(255, 165, 0, 0.1); border: 1px solid orange; border-radius: 10px; color: orange; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS ---
@st.cache_resource
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e:
        st.error(f"Error de conexión: {e}"); st.stop()

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT, precio TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo_registro TEXT, fecha_inicio DATE, fecha_vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)")
    conn.commit(); c.close()

inicializar_db()

# --- 3. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro Access")
    with st.form("login"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.form_submit_button("INGRESAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira, clave FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[4]: st.error("Membresía vencida.")
                else: 
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3], "pass":res[5]})
                    st.rerun()
            else: st.error("Acceso incorrecto.")
            c.close()
    st.stop()

# --- 4. MENÚ FILTRADO (SOLO ADMIN VE ADMIN) ---
with st.sidebar:
    st.markdown(f"### 👑 {st.session_state.uname}")
    opciones = ["📊 Dashboard", "💸 Nuevo Registro", "📜 Historial / Borrar", "🎯 Metas", "🏦 Deudas y Cobros", "📱 SINPE Rápido"]
    
    # Condición crucial: Solo agregar Admin si el rol es correcto
    if st.session_state.rol == 'admin':
        opciones.append("⚙️ Admin")
        
    menu = st.radio("NAVEGACIÓN", opciones)
    
    st.divider()
    # Sección para cambiar contraseña (Mensaje solicitado)
    with st.expander("🔐 Seguridad"):
        st.caption("Cambia tu contraseña periódicamente")
        nueva_p = st.text_input("Nueva Clave", type="password")
        if st.button("ACTUALIZAR CLAVE"):
            conn = get_connection(); c = conn.cursor()
            c.execute("UPDATE usuarios SET clave = %s WHERE id = %s", (nueva_p, st.session_state.uid))
            conn.commit(); c.close(); st.success("Clave actualizada"); time.sleep(1); st.rerun()
            
    if st.button("CERRAR SESIÓN"): st.session_state.autenticado = False; st.rerun()

# --- 5. NOTIFICACIÓN DE SUSCRIPCIÓN Y CAMBIO DE CLAVE ---
# Esto aparece arriba de cualquier módulo seleccionado
if st.session_state.rol != 'admin':
    st.markdown(f"""
    <div class="alert-box">
        ⚠️ <b>Aviso de Seguridad:</b> Tu suscripción <b>{st.session_state.plan}</b> está activa. 
        Por favor, asegúrate de cambiar tu contraseña temporal por una personal en el menú lateral.
    </div>
    """, unsafe_allow_html=True)

# --- 6. MÓDULOS (Dashboard, Registro, etc.) ---
if menu == "📊 Dashboard":
    st.header(f"Panel de Control - {st.session_state.uname}")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum()); gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        c1, c2, c3 = st.columns(3); c1.metric("INGRESOS", f"₡{ing:,.0f}"); c2.metric("GASTOS", f"₡{gas:,.0f}"); c3.metric("SALDO", f"₡{(ing-gas):,.0f}")
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=0.6, template="plotly_dark"), use_container_width=True)
    else: st.info("Bienvenido a GeZo. Empieza registrando tus movimientos.")

elif menu == "💸 Nuevo Registro":
    st.header("Entradas y Salidas")
    lista_g = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "🏠 Alquiler/Hipoteca", "🛒 Súper/Comida", "📱 Plan Celular/Net", "🏦 Cuota Préstamo", "🚗 Gasolina/Transporte", "📦 Otros Gastos"]
    lista_i = ["💵 Salario Mensual", "💰 Aguinaldo", "📱 SINPE Recibido", "📈 Ventas/Negocio", "🧧 Comisiones", "🚜 Freelance/Servicios", "🏢 Rentas/Alquileres", "🎁 Regalos", "💸 Cobros/Abonos Recibidos", "📦 Otros Ingresos"]
    tipo = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    cat = st.selectbox("Categoría:", lista_i if tipo == "Ingreso" else lista_g)
    with st.form("f_reg"):
        monto = st.number_input("Monto (₡)", min_value=0.0); fecha = st.date_input("Fecha Pago:", datetime.now()); det = st.text_input("Nota:")
        if st.form_submit_button("GUARDAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", (st.session_state.uid, datetime.now().date(), f"{cat}: {det}", monto, tipo, cat, fecha))
            conn.commit(); c.close(); st.success("Registrado correctamente."); st.rerun()

elif menu == "🎯 Metas":
    st.header("Tus Metas de Ahorro")
    with st.expander("➕ CREAR META"):
        with st.form("fm"):
            n = st.text_input("Nombre"); o = st.number_input("Objetivo (₡)", min_value=0.0)
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (%s,%s,%s,%s)", (st.session_state.uid, n, o, 0)); conn.commit(); c.close(); st.rerun()
    df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card">🎯 {r["nombre"]} | ₡{r["actual"]:,.0f} de ₡{r["objetivo"]:,.0f}</div>', unsafe_allow_html=True)
        # Lógica de abono simplificada para ahorrar espacio
        ab = st.number_input("Sumar ahorro:", min_value=0.0, key=f"ab_{r['id']}")
        if st.button("ACTUALIZAR", key=f"btn_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual = actual + %s WHERE id = %s", (ab, r['id'])); conn.commit(); c.close(); st.rerun()

elif menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil")
    df_cont = pd.read_sql(f"SELECT * FROM contactos WHERE usuario_id={st.session_state.uid}", get_connection())
    sel = st.selectbox("Contacto:", ["Manual"] + [f"{r['nombre']} ({r['telefono']})" for _, r in df_cont.iterrows()])
    num = st.text_input("Número:") if sel == "Manual" else sel.split("(")[1].replace(")", "")
    st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🏦 IR AL BANCO</a>', unsafe_allow_html=True)

# --- 7. MÓDULO ADMIN (PROTEGIDO) ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Panel de Administración de Usuarios")
    with st.form("f_admin"):
        un = st.text_input("Usuario"); uk = st.text_input("Clave Temporal"); up = st.selectbox("Plan", ["Mensual", "Anual"]); um = st.text_input("Monto", "5000")
        if st.form_submit_button("CREAR ACCESO"):
            vf = (datetime.now() + timedelta(days=30 if up=="Mensual" else 365)).date()
            conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (un, uk, vf, 'usuario', up, um)); conn.commit(); c.close(); st.success("Usuario creado"); st.rerun()
    
    u_list = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    st.table(u_list[['nombre', 'plan', 'expira']])

elif menu == "🏦 Deudas y Cobros":
    st.header("Deudas y Cobros")
    # Lógica simplificada de deudas del código anterior
    st.info("Usa este módulo para trackear tus saldos pendientes.")
    # (Aquí va el código de deudas y cobros del paso anterior)

elif menu == "📜 Historial / Borrar":
    st.header("Historial")
    df_h = pd.read_sql(f"SELECT id, fecha, cat, monto, tipo FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", get_connection())
    st.dataframe(df_h)
