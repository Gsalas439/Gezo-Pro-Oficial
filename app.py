import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACIÓN ELITE & MÓVIL ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

# Diseño CSS de alto impacto (Optimizado para iPhone y Carga Veloz)
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    /* Botones grandes para dedos */
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #004a99; color: white; font-weight: bold; border: none; }
    /* Tarjetas de Métricas */
    div[data-testid="stMetric"] { background-color: white; padding: 15px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee; }
    /* Estilo de Anuncios */
    .anuncio-card { background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); padding: 15px; border-radius: 12px; border-left: 5px solid #1976d2; margin-bottom: 20px; }
    /* Ocultar scrollbars laterales en móvil */
    @media (max-width: 640px) { .stMetric { margin-bottom: 10px; } }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS ---
conn = sqlite3.connect('gezo_master_v6.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, presupuesto REAL DEFAULT 200000)')
c.execute('CREATE TABLE IF NOT EXISTS movimientos (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)')
conn.commit()

# --- 3. FUNCIONES DE APOYO ---
def obtener_tc(): return {"compra": 512.45, "venta": 518.30}

def formato_dinero(monto, ocultar=False):
    if ocultar: return "₡ *.*"
    return f"₡{monto:,.0f}"

# --- 4. SISTEMA DE SESIÓN & PRIVACIDAD ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'ocultar_montos' not in st.session_state: st.session_state.ocultar_montos = False

if not st.session_state.autenticado:
    st.title("🚀 GeZo Elite Pro")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INGRESAR"):
            c.execute("SELECT id, nombre, rol, expira, presupuesto FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            if res:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[4]})
                st.rerun()
            else: st.error("Error de acceso")
    st.stop()

# --- 5. INTERFAZ Y NAVEGACIÓN ---
tc = obtener_tc()

with st.sidebar:
    st.title(f"Hola, {st.session_state.uname}")
    # MODO PRIVACIDAD (EL OJO)
    if st.button("👁️ Ocultar/Mostrar Montos"):
        st.session_state.ocultar_montos = not st.session_state.ocultar_montos
        st.rerun()
    
    st.markdown(f"*Dólar BCCR:* ₡{tc['venta']}")
    menu = st.radio("Módulos", ["🏠 Inicio", "💸 Sinpe/Gastos", "💱 Conversor", "⚙️ Admin"])
    
    # FILTRO DE MES (Para que la app sea veloz)
    mes_filtro = st.selectbox("Mes de Consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
    
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- MÓDULO INICIO (DASHBOARD) ---
if menu == "🏠 Inicio":
    st.header(f"Resumen de {mes_filtro}")
    
    # Anuncios Automáticos (Basados en fecha y presupuesto)
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    gas_total = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    
    if datetime.now().day in [15, 30]:
        st.markdown('<div class="anuncio-card">💰 <b>Día de Pago:</b> ¡Recuerda priorizar tus deudas y ahorros antes de gastar!</div>', unsafe_allow_html=True)
    
    # Métricas Principales con Filtro de Seguridad
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", formato_dinero(ing, st.session_state.ocultar_montos))
    c2.metric("Gastos", formato_dinero(gas_total, st.session_state.ocultar_montos), delta_color="inverse")
    c3.metric("Disponible", formato_dinero(ing - gas_total, st.session_state.ocultar_montos))

    # Radar de Presupuesto
    st.write(f"*Radar de Presupuesto (Límite: ₡{st.session_state.pres:,.0f})*")
    porc = min((gas_total / st.session_state.pres if st.session_state.pres > 0 else 0), 1.0)
    st.progress(porc)
    
    if not df.empty:
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, title="Distribución de Gastos")
        st.plotly_chart(fig, use_container_width=True)

# --- MÓDULO MOVIMIENTOS (CON BOTÓN SINPE) ---
elif menu == "💸 Sinpe/Gastos":
    st.header("Registrar Movimiento")
    tipo_reg = st.radio("Tipo de Registro", ["Gasto Normal", "Pago SINPE 📱", "Ingreso"], horizontal=True)
    
    with st.form("reg"):
        desc = st.text_input("Detalle / Persona")
        monto = st.number_input("Monto (₡)", min_value=0)
        cat = st.selectbox("Categoría", ["Comida", "Casa", "Servicios", "Transporte", "Diversión", "Salud", "Otros"])
        if st.form_submit_button("GUARDAR AHORA"):
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, monto, "Gasto" if "Ingreso" not in tipo_reg else "Ingreso", cat))
            conn.commit()
            st.success("¡Registro guardado con éxito! 🚀")

# --- MÓDULO CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Calculadora de Dólares")
    usd = st.number_input("Dólares ($)", min_value=0.0)
    st.subheader(f"Equivale a: ₡{usd * tc['venta']:,.2f}")
    st.write(f"Tipo de cambio usado: ₡{tc['venta']}")

# --- MÓDULO ADMIN ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Control de Usuarios")
    with st.form("admin"):
        nu, np = st.text_input("Usuario"), st.text_input("Clave")
        pl = st.selectbox("Plan", ["Semanal", "Mensual", "Semestral", "Anual", "Eterno"])
        if st.form_submit_button("ACTIVAR"):
            dias = {"Semanal":7, "Mensual":30, "Semestral":180, "Anual":365, "Eterno":36500}[pl]
            fv = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol) VALUES (?,?,?,?)", (nu, np, fv, 'usuario'))
            conn.commit()
            st.success("Usuario creado")
