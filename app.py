import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io
import time

# --- 1. ESTÉTICA ELITE PRO + LIMPIEZA TOTAL ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    /* Ocultar interfaz nativa de Streamlit para apariencia profesional */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid="stToolbar"] {display: none !important;}
    
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.08); border-radius: 20px; padding: 25px; 
        border: 1px solid #00c6ff; box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15); border-left: 10px solid #00c6ff;
    }
    .user-card { background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 15px; border: 1px solid #333; margin-bottom: 15px; border-left: 5px solid #00f2fe; }
    .sinpe-card { background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%); padding: 25px; border-radius: 20px; border: 1px solid #00f2fe; text-align: center; }
    .bank-btn { 
        background: #00f2fe; color: #000 !important; padding: 18px; border-radius: 15px; 
        text-align: center; display: block; text-decoration: none; font-weight: 900; 
        margin-top: 20px; font-size: 1.1em; transition: 0.3s;
    }
    .bank-btn:hover { background: #4facfe; transform: scale(1.02); }
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
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[4]: st.error("Membresía vencida.")
                else: 
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    st.rerun()
            else: st.error("Acceso incorrecto.")
            c.close()
    st.stop()

# --- 4. MENÚ ---
with st.sidebar:
    st.markdown(f"### 👑 {st.session_state.uname}")
    opciones = ["📊 Dashboard", "💸 Nuevo Registro", "📜 Historial / Borrar", "🎯 Metas", "🏦 Deudas y Cobros", "📱 SINPE Rápido"]
    if st.session_state.rol == 'admin': opciones.append("⚙️ Admin")
    menu = st.radio("NAVEGACIÓN", opciones)
    
    with st.expander("🔐 Seguridad"):
        nueva_p = st.text_input("Nueva Clave", type="password")
        if st.button("ACTUALIZAR CLAVE"):
            conn = get_connection(); c = conn.cursor()
            c.execute("UPDATE usuarios SET clave = %s WHERE id = %s", (nueva_p, st.session_state.uid))
            conn.commit(); c.close(); st.success("Clave actualizada"); st.rerun()
            
    if st.button("CERRAR SESIÓN"): st.session_state.autenticado = False; st.rerun()

# --- 5. MÓDULO: SINPE RÁPIDO (RESTAURADO Y MEJORADO) ---
if menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil Express")
    
    # Obtener contactos
    df_cont = pd.read_sql(f"SELECT * FROM contactos WHERE usuario_id={st.session_state.uid}", get_connection())
    
    col_ag, col_env = st.columns([1, 2])
    
    with col_ag:
        st.subheader("👥 Agenda")
        with st.expander("Nuevo Contacto"):
            with st.form("add_c"):
                n = st.text_input("Nombre"); t = st.text_input("Teléfono")
                if st.form_submit_button("Guardar"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("INSERT INTO contactos (usuario_id, nombre, telefono) VALUES (%s,%s,%s)", (st.session_state.uid, n, t))
                    conn.commit(); c.close(); st.rerun()
        
        for _, r in df_cont.iterrows():
            st.caption(f"👤 {r['nombre']}: {r['telefono']}")

    with col_env:
        st.subheader("💸 Preparar Envío")
        sel = st.selectbox("Elegir destino:", ["Manual"] + [f"{r['nombre']} ({r['telefono']})" for _, r in df_cont.iterrows()])
        
        num_dest = ""
        if sel == "Manual":
            num_dest = st.text_input("Número de teléfono:", placeholder="88888888")
        else:
            num_dest = sel.split("(")[1].replace(")", "")
            st.success(f"Seleccionado: {num_dest}")

        # REINCORPORADO: Monto a transferir
        monto_sinpe = st.number_input("Monto a enviar (₡):", min_value=0.0, step=1000.0)
        
        if num_dest:
            st.markdown(f"""
            <div class="sinpe-card">
                <h3 style="color:#00f2fe; margin:0;">PASO FINAL</h3>
                <p>Vas a enviar <b>₡{monto_sinpe:,.0f}</b> a:</p>
                <h1 style="font-size: 2.5em; letter-spacing: 2px;">{num_dest}</h1>
                <p style="font-size: 0.9em; color: #888;">Copia el número y abre tu banco aquí abajo:</p>
                <a href="https://www.google.com" target="_blank" class="bank-btn">🏦 ABRIR APP DEL BANCO</a>
            </div>
            """, unsafe_allow_html=True)

# --- 6. RESTO DE MÓDULOS (Resumen) ---
elif menu == "📊 Dashboard":
    st.header(f"Panel Financiero - {st.session_state.uname}")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum()); gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        c1, c2, c3 = st.columns(3); c1.metric("INGRESOS", f"₡{ing:,.0f}"); c2.metric("GASTOS", f"₡{gas:,.0f}"); c3.metric("SALDO", f"₡{(ing-gas):,.0f}")
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=0.6, template="plotly_dark"), use_container_width=True)

elif menu == "💸 Nuevo Registro":
    st.header("Entradas y Salidas")
    tipo = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    lista_g = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "🏠 Alquiler/Hipoteca", "🛒 Súper/Comida", "📱 Plan Celular/Net", "🏦 Cuota Préstamo", "🚗 Gasolina/Transporte", "📦 Otros Gastos"]
    lista_i = ["💵 Salario Mensual", "💰 Aguinaldo", "📱 SINPE Recibido", "📈 Ventas/Negocio", "🧧 Comisiones", "🚜 Freelance/Servicios", "🏢 Rentas/Alquileres", "🎁 Regalos", "💸 Cobros/Abonos Recibidos", "📦 Otros Ingresos"]
    cat = st.selectbox("Categoría:", lista_i if tipo == "Ingreso" else lista_g)
    with st.form("f_reg"):
        monto = st.number_input("Monto (₡)", min_value=0.0); fecha = st.date_input("Fecha Pago:", datetime.now()); det = st.text_input("Nota:")
        if st.form_submit_button("GUARDAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", (st.session_state.uid, datetime.now().date(), f"{cat}: {det}", monto, tipo, cat, fecha))
            conn.commit(); c.close(); st.success("Registrado."); st.rerun()

elif menu == "🎯 Metas":
    st.header("Metas de Ahorro")
    df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card">🎯 {r["nombre"]} | ₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)

elif menu == "🏦 Deudas y Cobros":
    st.header("Deudas y Cobros")
    df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid}", get_connection())
    st.dataframe(df_d)

elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Admin")
    # Lógica de admin aquí...
