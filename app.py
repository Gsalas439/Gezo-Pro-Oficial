import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import requests
import io

# --- 1. ESTÉTICA Y CONFIGURACIÓN ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.05);
        border-radius: 15px; padding: 20px; border: 1px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        color: black; font-weight: bold; width: 100%; border: none; height: 3.5em;
    }
    .coach-box { padding: 20px; border-radius: 15px; margin: 10px 0; border-left: 8px solid; line-height: 1.6; }
    .rojo { background-color: rgba(255, 75, 75, 0.1); border-color: #ff4b4b; color: #ff4b4b; }
    .verde { background-color: rgba(37, 211, 102, 0.1); border-color: #25d366; color: #25d366; }
    .alerta { background-color: rgba(241, 196, 15, 0.1); border-color: #f1c40f; color: #f1c40f; }
    .user-card {
        background: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 12px;
        border: 1px solid #333; margin-bottom: 10px; border-left: 4px solid #00c6ff;
    }
    .bank-btn {
        background-color: #1e2129; border: 1px solid #00c6ff; color: #00c6ff;
        padding: 12px; border-radius: 8px; text-align: center; display: block; text-decoration: none; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS ---
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, 
                  plan TEXT, precio TEXT, presupuesto DECIMAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo TEXT)''')
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', 'N/A'))
    conn.commit(); c.close(); conn.close()

try: inicializar_db()
except: st.error("Error de base de datos."); st.stop()

# --- 3. FUNCIONES ESPECIALES (ANTI-ERROR UNICODE) ---
def corregir_texto(texto):
    if not texto: return ""
    remplazos = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC ","Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U"}
    for k, v in remplazos.items(): texto = texto.replace(k, v)
    return str(texto).encode('latin-1', 'ignore').decode('latin-1')

def generar_pdf_final(nombre, plan, monto, fecha):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(11, 14, 20); pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 24)
    pdf.cell(200, 30, corregir_texto("GEZO ELITE PRO"), ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", '', 14)
    pdf.cell(200, 10, f"Cliente: {corregir_texto(nombre)}", ln=True)
    pdf.cell(200, 10, f"Plan: {corregir_texto(plan)}", ln=True)
    pdf.cell(200, 10, f"Monto: {corregir_texto(str(monto))}", ln=True)
    pdf.cell(200, 10, f"Vence: {fecha}", ln=True)
    return pdf.output(dest='S').encode('latin-1', errors='replace')

def get_tipo_cambio():
    return {"compra": 510.50, "venta": 520.10}

# --- 4. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.form_submit_button("ENTRAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[4]: st.error("Suscripción vencida."); st.stop()
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                st.rerun()
            else: st.error("Datos incorrectos.")
            c.close(); conn.close()
    st.stop()

# --- 5. SIDEBAR (MENÚ COMPLETO) ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    tc = get_tipo_cambio()
    st.metric("💵 Dólar Venta", f"₡{tc['venta']}")
    st.metric("💵 Dólar Compra", f"₡{tc['compra']}")
    st.divider()
    # AQUÍ ESTÁN TODAS LAS SECCIONES QUE PEDISTE
    menu = st.radio("Navegación:", [
        "📊 Dashboard IA", 
        "💸 Registrar Cuentas", 
        "📱 SINPE Rápido", 
        "⚖️ Pensión y Aguinaldo", 
        "🤝 Deudas y Metas", 
        "💱 Conversor", 
        "⚙️ Admin"
    ])
    if st.button("Cerrar Sesión"): st.session_state.autenticado = False; st.rerun()

# --- 6. DASHBOARD + IA ---
if menu == "📊 Dashboard IA":
    st.header("Análisis de Inteligencia Financiera 🤖")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    ing = float(df[df['tipo']=='Ingreso']['monto'].sum()) if not df.empty else 0
    gas = float(df[df['tipo']=='Gasto']['monto'].sum()) if not df.empty else 0
    bal = ing - gas
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", f"₡{ing:,.0f}"); c2.metric("Gastos", f"₡{gas:,.0f}", delta_color="inverse"); c3.metric("Saldo", f"₡{bal:,.0f}")

    if ing > 0:
        porc = (gas / ing) * 100
        if bal < 0:
            st.markdown(f'<div class="coach-box rojo"><h3>🚨 ESTÁS EN ROJO</h3><p>Gastaste <b>₡{abs(bal):,.0f}</b> más de lo que tenés. ¡Dejá de comprar lo que no necesitás! Cortá hoy mismo los lujos o vas a terminar pidiendo prestado.</p></div>', unsafe_allow_html=True)
        elif porc > 80:
            st.markdown(f'<div class="coach-box alerta"><h3>🧐 CUIDADO</h3><p>Has gastado el <b>{porc:.1f}%</b> de tu ingreso. Estás a un imprevisto de los números rojos. ¡Guardá el 10% de lo que te queda YA!</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="coach-box verde"><h3>💎 SOS UN CRACK</h3><p>Gastás el <b>{porc:.1f}%</b>. Tenés <b>₡{bal:,.0f}</b> libres. ¡Pura vida! Seguí así y pronto estarás invirtiendo en grande.</p></div>', unsafe_allow_html=True)
    
    if not df.empty:
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark", title="Distribución de Gastos"))

# --- 7. REGISTRO DETALLADO + ALERTAS ---
elif menu == "💸 Registrar Cuentas":
    st.header("Registro de Movimientos y Servicios")
    cats_gastos = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "📱 Plan Telefónico", "🏠 Alquiler/Hipoteca", "🏦 Préstamo", "🛒 Súper", "💡 Gastos Hormiga", "📦 Otros"]
    cats_ingresos = ["💵 Salario", "📱 SINPE Recibido", "💰 Ventas", "💸 Remesas", "📦 Otros"]

    with st.form("reg_det"):
        t = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
        c = st.selectbox("Categoría:", cats_gastos if t == "Gasto" else cats_ingresos)
        m = st.number_input("Monto (₡)", min_value=0.0)
        v = st.date_input("Fecha de Vencimiento", datetime.now())
        a = st.checkbox("🔔 Alerta automática (1 día antes)")
        
        if st.form_submit_button("GUARDAR"):
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                      (st.session_state.uid, datetime.now().date(), f"Pago {c}", m, t, c, v))
            conn.commit(); cur.close(); conn.close()
            if a: st.info(f"📅 Recordatorio programado para el {v - timedelta(days=1)}")
            st.success("✅ Guardado correctamente.")

# --- 8. SINPE RÁPIDO ---
elif menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil Express")
    with st.form("sn"):
        num = st.text_input("Número de Teléfono")
        mon = st.number_input("Monto a enviar (₡)", min_value=0)
        ban = st.selectbox("Abrir Banco:", ["BNCR", "BAC", "BCR", "BP"])
        if st.form_submit_button("REGISTRAR Y PAGAR"):
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                      (st.session_state.uid, datetime.now().date(), f"SINPE a {num}", mon, "Gasto", "📱 SINPE Rápido"))
            conn.commit(); cur.close(); conn.close()
            l = {"BNCR": "https://www.bnmovil.fi.cr/", "BAC": "https://www.baccredomatic.com/", "BCR": "https://www.bancobcr.com/", "BP": "https://www.bancopopular.fi.cr/"}
            st.markdown(f'<a href="{l[ban]}" target="_blank" class="bank-btn">🚀 Ir a App de {ban}</a>', unsafe_allow_html=True)

# --- 9. PENSIÓN Y AGUINALDO ---
elif menu == "⚖️ Pensión y Aguinaldo":
    st.header("Cálculos Legales Costa Rica")
    sal = st.number_input("Salario Bruto Mensual (₡)", min_value=0.0)
    st.info(f"⚖️ Pensión Alimentaria Est. (35%): ₡{(sal*0.35):,.0f}")
    st.success(f"💰 Aguinaldo Proyectado: ₡{sal:,.0f}")

# --- 10. DEUDAS Y METAS ---
elif menu == "🤝 Deudas y Metas":
    st.header("Gestión de Deudas y Metas de Ahorro")
    tab1, tab2 = st.tabs(["🎯 Metas", "🏦 Deudas"])
    with tab1:
        with st.form("met"):
            n = st.text_input("Nombre de la Meta"); obj = st.number_input("Monto Objetivo", min_value=1.0)
            if st.form_submit_button("CREAR META"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, obj))
                conn.commit(); c.close(); conn.close(); st.rerun()
    with tab2:
        st.write("Registra tus deudas bancarias para que la IA te ayude a salir de ellas.")

# --- 11. CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Conversor de Moneda Real")
    m_c = st.number_input("Monto", min_value=0.0)
    st.metric("De Colones a Dólares", f"${(m_c / tc['venta']):,.2f}")
    st.metric("De Dólares a Colones", f"₡{(m_c * tc['compra']):,.2f}")

# --- 12. ADMIN (PLANES Y USUARIOS) ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Panel de Administración GeZo")
    # PLANES INCLUYENDO LA SEMANA GRATIS
    planes = {"Semana Gratis":7, "Mensual":30, "Trimestral":90, "Semestral":180, "Anual":365, "Eterno":36500}
    precios = {"Semana Gratis":"₡0", "Mensual":"₡5,000", "Trimestral":"₡13,500", "Semestral":"₡25,000", "Anual":"₡45,000", "Eterno":"₡100,000"}
    
    with st.expander("➕ Crear Nuevo Usuario"):
        un = st.text_input("Usuario"); pn = st.text_input("Clave"); ps = st.selectbox("Plan", list(planes.keys()))
        if st.button("ACTIVAR"):
            vf = (datetime.now() + timedelta(days=planes[ps])).date()
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (un, pn, vf, 'usuario', ps, precios[ps]))
            conn.commit(); c.close(); conn.close(); st.rerun()

    users = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for i, r in users.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card"><b>👤 {r["nombre"]}</b> | {r["plan"]} | Expira: {r["expira"]}</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                p_data = generar_pdf_final(r['nombre'], r['plan'], r['precio'], str(r['expira']))
                st.download_button("📄 Recibo", p_data, f"Recibo_{r['nombre']}.pdf")
            with c2:
                msg = f"Hola {r['nombre']}, tu plan {r['plan']} esta activo hasta el {r['expira']}. Gracias por ser GeZo Elite."
                url = f"https://wa.me/50663712477?text={msg.replace(' ','%20')}"
                st.markdown(f'<a href="{url}" target="_blank" style="text-decoration:none; font-weight:bold; color:#25d366;">📲 WhatsApp</a>', unsafe_allow_html=True)
            with c3:
                if st.button("🗑️ Borrar", key=f"del_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM usuarios WHERE id={r['id']}"); conn.commit(); c.close(); conn.close(); st.rerun()
