import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import requests

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="GeZo Elite Pro", page_icon="🚀", layout="wide")

# 2. CONEXIÓN Y ESTRUCTURA DE BASE DE DATOS
conn = sqlite3.connect('gezo_finanzas.db', check_same_thread=False)
c = conn.cursor()

# Creación de tablas (Estructura limpia y completa)
c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, 
              pago_hora REAL DEFAULT 0, primer_login INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto_col REAL, tipo TEXT, categoria TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS deudas 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total REAL, fecha_meta TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS prestamos 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, deudor TEXT, monto_total REAL, saldo_pendiente REAL, fecha_pago TEXT)''')
conn.commit()

# Crear usuario administrador si no existe
c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
if not c.fetchone():
    c.execute("INSERT INTO usuarios (nombre, clave, expira, primer_login) VALUES (?,?,?,?)", 
              ('admin', 'admin123', '2030-12-31', 0))
    conn.commit()

# 3. FUNCIÓN TIPO DE CAMBIO (COSTA RICA)
def get_tipo_cambio():
    try:
        url = "https://tipodecambio.paginasweb.cr/api" 
        response = requests.get(url, timeout=5)
        datos = response.json()
        return float(datos['compra']), float(datos['venta'])
    except:
        return 515.0, 525.0 

# 4. SISTEMA DE AUTENTICACIÓN
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🚀 GeZo Elite Pro")
    st.subheader("Tu Asistente Financiero Inteligente 🇨🇷")
    with st.form("login"):
        user = st.text_input("Usuario")
        pw = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar"):
            c.execute("SELECT id, nombre, expira, primer_login FROM usuarios WHERE nombre=? AND clave=?", (user, pw))
            res = c.fetchone()
            if res:
                st.session_state.autenticado = True
                st.session_state.usuario_id = res[0]
                st.session_state.usuario_nombre = res[1]
                st.session_state.es_admin = (res[1] == 'admin')
                st.session_state.debe_cambiar = bool(res[3])
                st.rerun()
            else:
                st.error("Datos incorrectos")
    st.stop()

# 5. SEGURIDAD: CAMBIO OBLIGATORIO PARA CUENTAS NUEVAS
if st.session_state.debe_cambiar and not st.session_state.es_admin:
    st.warning("🛡️ SEGURIDAD: Personaliza tu cuenta para continuar")
    with st.form("cambio_clave"):
        nu = st.text_input("Nuevo Nombre de Usuario")
        np = st.text_input("Nueva Contraseña", type="password")
        cp = st.text_input("Confirmar Contraseña", type="password")
        if st.form_submit_button("Activar Mi Cuenta ✅"):
            if np == cp and nu and np:
                c.execute("UPDATE usuarios SET nombre=?, clave=?, primer_login=0 WHERE id=?", (nu, np, st.session_state.usuario_id))
                conn.commit()
                st.session_state.usuario_nombre = nu
                st.session_state.debe_cambiar = False
                st.success("¡Cuenta activada con éxito!")
                st.rerun()
            else:
                st.error("Las contraseñas no coinciden o faltan datos")
    st.stop()

# 6. MENÚ LATERAL
t_compra, t_venta = get_tipo_cambio()
with st.sidebar:
    st.header(f"👤 {st.session_state.usuario_nombre}")
    st.write(f"💵 Dólar: ₡{t_compra} / ₡{t_venta}")
    menu = ["🏠 Resumen", "💵 Registrar", "🤝 Me Deben", "📉 Mis Deudas"]
    if st.session_state.es_admin: menu.append("👤 ADMIN")
    seccion = st.radio("Ir a:", menu)
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

id_actual = st.session_state.usuario_id

# ---------------- SECCIONES ----------------

if seccion == "🏠 Resumen":
    st.header("📊 Resumen General")
    df = pd.read_sql_query(f"SELECT tipo, monto_col, categoria FROM movimientos WHERE usuario_id={id_actual}", conn)
    ing = df[df['tipo']=='Ingreso']['monto_col'].sum()
    gas = df[df['tipo']=='Gasto']['monto_col'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", f"₡{ing:,.0f}")
    c2.metric("Gastos", f"₡{gas:,.0f}", delta_color="inverse")
    c3.metric("Saldo", f"₡{(ing-gas):,.0f}")

    if not df[df['tipo']=='Gasto'].empty:
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto_col', names='categoria', hole=0.4, title="Distribución de Gastos")
        st.plotly_chart(fig, use_container_width=True)

elif seccion == "💵 Registrar":
    st.header("📝 Nuevo Registro")
    with st.form("mov"):
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        cat = st.selectbox("Categoría", ["🏠 Vivienda", "⚡ Servicios", "⛽ Gasolina", "🛒 Súper", "🍕 Comida", "🎓 Educación", "🛍️ Compras", "💰 Salario", "💼 Negocio", "🔄 Otros"])
        desc = st.text_input("Detalle")
        monto = st.number_input("Monto", min_value=0.0)
        moneda = st.radio("Moneda", ["₡ Colones", "$ Dólares"], horizontal=True)
        if st.form_submit_button("Guardar"):
            m_final = monto * (t_venta if tipo == "Gasto" else t_compra) if "$" in moneda else monto
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto_col, tipo, categoria) VALUES (?,?,?,?,?,?)",
                      (id_actual, datetime.now().strftime("%Y-%m-%d"), desc, m_final, tipo, cat))
            conn.commit()
            st.success(f"Registrado correctamente")

elif seccion == "🤝 Me Deben":
    st.header("🤝 Préstamos Realizados")
    with st.form("pres"):
        deud = st.text_input("¿Quién le debe?")
        mont = st.number_input("Monto Prestado", min_value=0.0)
        if st.form_submit_button("Registrar Préstamo"):
            c.execute("INSERT INTO prestamos (usuario_id, deudor, monto_total, saldo_pendiente, fecha_pago) VALUES (?,?,?,?,?)",
                      (id_actual, deud, mont, mont, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            st.success("Préstamo guardado")

elif seccion == "📉 Mis Deudas":
    st.header("📉 Control de Mis Deudas")
    with st.form("deu"):
        nom = st.text_input("Entidad o Persona")
        tot = st.number_input("Monto de la Deuda", min_value=0.0)
        if st.form_submit_button("Registrar Deuda"):
            c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, fecha_meta) VALUES (?,?,?,?)",
                      (id_actual, nom, tot, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            st.success("Deuda guardada")

elif seccion == "👤 ADMIN" and st.session_state.es_admin:
    st.header("⚙️ Panel de Administración")
    with st.form("nuevo_cliente"):
        u = st.text_input("Usuario Temporal")
        p = st.text_input("Clave Temporal")
        d = st.selectbox("Plan (Días)", [7, 30, 365])
        if st.form_submit_button("Crear Acceso Premium"):
            fv = (datetime.now() + timedelta(days=d)).strftime("%Y-%m-%d")
            # Si el plan es de más de 7 días, obligamos a cambiar clave (primer_login = 1)
            debe = 1 if d > 7 else 0
            c.execute("INSERT INTO usuarios (nombre, clave, expira, primer_login) VALUES (?,?,?,?)", (u, p, fv, debe))
            conn.commit()
            st.success(f"Cliente {u} creado exitosamente")
