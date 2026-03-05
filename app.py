import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io

# --- 1. CONFIGURACIÓN Y ESTÉTICA PREMIUM ---
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
    /* Estilos para botones especiales en Admin */
    .btn-pdf>div>button { background: #f1c40f !important; color: black !important; }
    .btn-ws>div>button { background: #25d366 !important; color: white !important; }
    .btn-del>div>button { background: #ff4b2b !important; color: white !important; }
    
    .user-card {
        background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 15px;
        border: 1px solid #333; margin-bottom: 15px; border-left: 5px solid #00c6ff;
    }
    .termo-container { 
        width: 100%; background-color: #333; border-radius: 10px; 
        margin: 10px 0; height: 30px; border: 1px solid #444;
    }
    .whatsapp-footer { 
        background-color: #25d366; color: white; padding: 12px; 
        border-radius: 10px; text-align: center; text-decoration: none; display: block; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS (POSTGRESQL) ---
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    # Tabla de Usuarios con columna Precio y Plan
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, 
                  plan TEXT, precio TEXT, presupuesto DECIMAL DEFAULT 250000)''')
    # Tabla de Movimientos (Ingresos y Gastos)
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)''')
    # Tabla de Metas de Ahorro
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)''')
    # Tabla de Deudas y Préstamos
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo TEXT)''')
    
    # Crear Usuario Admin por defecto
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', 'N/A'))
    conn.commit(); c.close(); conn.close()

try: 
    inicializar_db()
except Exception as e: 
    st.error(f"Error de conexión a la base de datos: {e}")
    st.stop()

# --- 3. FUNCIONES DE GENERACIÓN DE RECIBO PDF ---
def generar_recibo_pdf(nombre, plan, monto, fecha_venc):
    pdf = FPDF()
    pdf.add_page()
    # Fondo oscuro
    pdf.set_fill_color(11, 14, 20); pdf.rect(0, 0, 210, 297, 'F')
    # Texto
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 26)
    pdf.cell(200, 30, "GEZO ELITE PRO 💎", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "COMPROBANTE DE PAGO OFICIAL", ln=True, align='C')
    pdf.ln(20); pdf.set_font("Arial", '', 14)
    pdf.cell(200, 10, f"Cliente: {nombre.upper()}", ln=True)
    pdf.cell(200, 10, f"Plan Adquirido: {plan}", ln=True)
    pdf.cell(200, 10, f"Monto Cancelado: {monto}", ln=True)
    pdf.cell(200, 10, f"Fecha de Vencimiento: {fecha_venc}", ln=True)
    pdf.ln(40); pdf.set_font("Arial", 'I', 11)
    pdf.multi_cell(190, 10, "Este documento certifica su acceso exclusivo a la plataforma GeZo Elite Pro. Gracias por confiar en nosotros para su libertad financiera.", align='C')
    return pdf.output(dest='S').encode('latin-1')

# --- 4. SISTEMA DE LOGIN Y ACCESO ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    st.subheader("Bienvenido a la Elite Financiera de Costa Rica")
    with st.form("login_form"):
        u_input = st.text_input("Nombre de Usuario")
        p_input = st.text_input("Contraseña de Acceso", type="password")
        if st.form_submit_button("INICIAR SESIÓN"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u_input, p_input))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[4]:
                    st.error("⚠️ Su suscripción ha expirado. Por favor contacte a GeZo.")
                    st.markdown(f'<a href="https://wa.me/50663712477?text=Hola,%20mi%20suscripcion%20vencio" class="whatsapp-footer">📲 Renovar Membresía por WhatsApp</a>', unsafe_allow_html=True)
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    st.rerun()
            else: st.error("Usuario o clave incorrectos. Intente de nuevo.")
            c.close(); conn.close()
    st.stop()

def fmt(n): return f"₡{float(n):,.0f}" if st.session_state.get('ver_montos', True) else "₡ *.*"

# --- 5. INTERFAZ Y NAVEGACIÓN ---
with st.sidebar:
    st.title(f"👑 Bienvenido, {st.session_state.uname}")
    st.info(f"Suscripción: {st.session_state.plan}")
    if st.button("👁️ Modo Privacidad"):
        st.session_state.ver_montos = not st.session_state.get('ver_montos', True)
        st.rerun()
    
    opciones = ["📊 Dashboard IA", "💸 Registrar Movimiento", "🎯 Metas de Ahorro", "🤝 Deudas y Cobros", "⚙️ Panel de Control Admin"]
    menu = st.radio("Seleccione una sección:", opciones)
    
    st.divider()
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 6. DASHBOARD CON TERMÓMETRO FINANCIERO ---
if menu == "📊 Dashboard IA":
    st.header("Análisis de Salud Financiera 🤖")
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    ingresos = float(df[df['tipo']=='Ingreso']['monto'].sum()) if not df.empty else 0.0
    gastos = float(df[df['tipo']=='Gasto']['monto'].sum()) if not df.empty else 0.0
    balance = ingresos - gastos
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos Totales", fmt(ingresos))
    c2.metric("Gastos Totales", fmt(gastos), delta=fmt(-gastos), delta_color="inverse")
    c3.metric("Saldo Disponible", fmt(balance))

    # --- TERMÓMETRO DE GASTO ---
    st.subheader("🌡️ Termómetro de Salud Financiera")
    if ingresos > 0:
        porcentaje_gasto = min((gastos / ingresos) * 100, 100)
        color_barra = "#25d366" if porcentaje_gasto < 50 else "#f1c40f" if porcentaje_gasto < 80 else "#ff4b2b"
        
        st.markdown(f"""
            <div class="termo-container">
                <div style="width: {porcentaje_gasto}%; background-color: {color_barra}; height: 100%; border-radius: 10px; text-align: center; color: black; font-weight: bold; padding-top: 3px;">
                    {porcentaje_gasto:.1f}% del presupuesto consumido
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        if porcentaje_gasto > 85:
            st.warning("🚨 ALERTA: Estás en zona crítica. Tus gastos están por consumir todo tu ingreso.")
        elif porcentaje_gasto < 40:
            st.success("💎 EXCELENTE: Tu capacidad de ahorro es nivel Elite.")
    
    if not df.empty:
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark", title="Distribución de tus Gastos"))

# --- 7. REGISTRO DE MOVIMIENTOS ---
elif menu == "💸 Registrar Movimiento":
    st.header("Registrar Nuevo Ingreso o Gasto")
    with st.form("registro_f"):
        detalle = st.text_input("¿En qué gastaste o qué recibiste?")
        monto_mov = st.number_input("Monto en Colones (₡)", min_value=0.0)
        cat_mov = st.selectbox("Categoría", ["🛒 Súper", "⛽ Gasolina", "🏠 Casa", "⚡ Servicios", "📱 SINPE", "💡 Gastos Hormiga", "🏦 Deudas", "💰 Ahorro", "💵 Salario", "📦 Otros"])
        tipo_mov = st.selectbox("Tipo de Movimiento", ["Gasto", "Ingreso"])
        
        if st.form_submit_button("GUARDAR MOVIMIENTO"):
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                        (st.session_state.uid, datetime.now().date(), detalle, monto_mov, tipo_mov, cat_mov))
            conn.commit(); cur.close(); conn.close()
            st.success("✅ ¡Registrado con éxito!")

# --- 8. PANEL DE CONTROL ADMIN (PDF, WHATSAPP, BORRADO) ---
elif menu == "⚙️ Panel de Control Admin":
    if st.session_state.rol == 'admin':
        st.header("💎 Gestión de Membresías GeZo")
        
        planes_info = {
            "Mensual": {"d": 30, "p": "₡5,000"},
            "Trimestral": {"d": 90, "p": "₡13,500"},
            "Semestral": {"d": 180, "p": "₡25,000"},
            "Anual": {"d": 365, "p": "₡45,000"},
            "Eterno": {"d": 36500, "p": "₡100,000"}
        }

        with st.expander("➕ ACTIVAR NUEVO CLIENTE"):
            u_nom = st.text_input("Nombre de Usuario Nuevo")
            u_cla = st.text_input("Clave Temporal")
            u_pla = st.selectbox("Seleccione el Plan Vendido", list(planes_info.keys()))
            st.info(f"💰 Precio a cobrar: {planes_info[u_pla]['p']}")
            
            if st.button("CONFIRMAR Y ACTIVAR CUENTA"):
                fecha_exp = (datetime.now() + timedelta(days=planes_info[u_pla]['d'])).date()
                conn = get_connection(); c = conn.cursor()
                try:
                    c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                              (u_nom, u_cla, fecha_exp, 'usuario', u_pla, planes_info[u_pla]['p']))
                    conn.commit()
                    st.success(f"¡Usuario {u_nom} activado hasta {fecha_exp}!")
                except: st.error("Error: El nombre de usuario ya está tomado.")
                finally: c.close(); conn.close()
                st.rerun()

        st.divider()
        st.subheader("👥 Clientes en el Sistema")
        usuarios_registrados = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin' ORDER BY expira DESC", get_connection())
        
        for i, row in usuarios_registrados.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="user-card">
                    <b>👤 {row['nombre']}</b><br>
                    💎 Plan: {row['plan']} | 💰 Pagó: {row['precio']} <br>
                    📅 Vence: {row['expira']}
                </div>
                """, unsafe_allow_html=True)
                
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    st.markdown('<div class="btn-pdf">', unsafe_allow_html=True)
                    recibo_bin = generar_recibo_pdf(row['nombre'], row['plan'], row['precio'], str(row['expira']))
                    st.download_button("📄 Descargar Recibo", data=recibo_bin, file_name=f"Recibo_GeZo_{row['nombre']}.pdf", mime="application/pdf")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col_b:
                    st.markdown('<div class="btn-ws">', unsafe_allow_html=True)
                    msg_wa = f"Hola {row['nombre']}, ¡Bienvenido a GeZo Elite Pro! Tu membresia {row['plan']} ha sido activada con exito hasta el {row['expira']}. Gracias por tu pago de {row['precio']}."
                    url_wa = f"https://wa.me/50663712477?text={msg_wa.replace(' ', '%20')}"
                    st.markdown(f'<a href="{url_wa}" target="_blank" style="text-decoration:none;"><button style="width:100%; height:2.5em; background:#25d366; color:white; border:none; border-radius:10px; font-weight:bold;">📲 Avisar por WhatsApp</button></a>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col_c:
                    st.markdown('<div class="btn-del">', unsafe_allow_html=True)
                    if st.button(f"🗑️ Borrar Cliente", key=f"eliminar_{row['id']}"):
                        conn = get_connection(); c = conn.cursor()
                        c.execute(f"DELETE FROM movimientos WHERE usuario_id={row['id']}")
                        c.execute(f"DELETE FROM deudas WHERE usuario_id={row['id']}")
                        c.execute(f"DELETE FROM metas WHERE usuario_id={row['id']}")
                        c.execute(f"DELETE FROM usuarios WHERE id={row['id']}")
                        conn.commit(); c.close(); conn.close()
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

# --- 9. DEUDAS Y METAS ---
elif menu == "🤝 Deudas y Cobros":
    st.header("Gestión de Préstamos y Deudas")
    with st.form("deudas_form"):
        persona = st.text_input("¿Quién debe o a quién le debes?")
        monto_d = st.number_input("Monto total", min_value=0.0)
        tipo_d = st.selectbox("Situación", ["Me deben dinero", "Yo debo dinero"])
        if st.form_submit_button("REGISTRAR DEUDA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo) VALUES (%s,%s,%s,%s)", (st.session_state.uid, persona, monto_d, tipo_d))
            conn.commit(); c.close(); conn.close(); st.rerun()

elif menu == "🎯 Metas de Ahorro":
    st.header("Tus Metas de Ahorro")
    with st.form("metas_form"):
        meta_nombre = st.text_input("Nombre de la Meta (ej: Viaje, Carro, Fondo de Emergencia)")
        meta_objetivo = st.number_input("Monto Objetivo (₡)", min_value=1.0)
        if st.form_submit_button("CREAR META"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, meta_nombre, meta_objetivo))
            conn.commit(); c.close(); conn.close(); st.rerun()
