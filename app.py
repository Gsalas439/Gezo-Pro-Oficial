import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import io

# --- 1. ESTÉTICA DE ALTO CONTRASTE (DISEÑO IPHONE/DARK) ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(0, 198, 255, 0.1) 0%, rgba(0, 114, 255, 0.1) 100%);
        border-radius: 15px; padding: 20px; border: 1px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        color: black; font-weight: bold; height: 3.5em; width: 100%; border: none;
    }
    .whatsapp-btn {
        background-color: #25d366; color: white; padding: 15px; text-align: center;
        border-radius: 12px; text-decoration: none; display: block; font-weight: bold; margin-top: 20px;
    }
    .coach-box {
        background: rgba(255, 255, 255, 0.03); padding: 20px; border-radius: 15px;
        border: 1px dashed #00f2fe; margin: 20px 0;
    }
    .emergencia-box {
        background: linear-gradient(90deg, #333333 0%, #222222 100%);
        padding: 15px; border-radius: 12px; border-left: 5px solid #ff007f; margin-bottom: 20px;
    }
    .status-tag {
        padding: 4px 10px; border-radius: 15px; font-size: 11px;
        background: rgba(0, 198, 255, 0.2); border: 1px solid #00c6ff; color: #00c6ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS (BASE DE DATOS INTEGRAL) ---
conn = sqlite3.connect('gezo_master_ultimate.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, 
                  plan TEXT, presupuesto REAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo REAL, actual REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total REAL, pagado REAL DEFAULT 0, tipo TEXT)''')
    
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (?,?,?,?,?)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master'))
    conn.commit()

inicializar_db()

# --- 3. LOGICA DE SEGURIDAD Y TIPO DE CAMBIO ---
WHATSAPP_NUM = "50663712477"
TC_DOLAR = 518.00 

if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'ver_montos' not in st.session_state: st.session_state.ver_montos = True

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INGRESAR"):
            c.execute("SELECT id, nombre, rol, presupuesto, plan, expira FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            if res:
                venc = datetime.strptime(res[5], "%Y-%m-%d").date()
                if datetime.now().date() > venc:
                    st.error("Suscripción vencida.")
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}?text=Renovar cuenta: {u}" class="whatsapp-btn">📲 Contactar Soporte</a>', unsafe_allow_html=True)
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[3], "plan":res[4]})
                    st.rerun()
            else: st.error("Credenciales incorrectas.")
    st.stop()

def fmt(n): return f"₡{n:,.0f}" if st.session_state.ver_montos else "₡ *.*"

# --- 4. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    st.markdown(f'<span class="status-tag">{st.session_state.plan}</span>', unsafe_allow_html=True)
    if st.button("👁️ Modo Privacidad"):
        st.session_state.ver_montos = not st.session_state.ver_montos
        st.rerun()
    menu = st.radio("Menú Principal", ["📊 Dashboard IA", "📱 SINPE Rápido", "💸 Registrar", "🤝 Deudas y Cobros", "💱 Conversor", "🎯 Metas", "⚙️ Admin"])
    st.markdown("---")
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 5. MÓDULOS DEL SISTEMA ---

# --- DASHBOARD IA + FONDO EMERGENCIA + EXPORTAR ---
if menu == "📊 Dashboard IA":
    st.header("Salud Financiera GeZo")
    
    st.markdown("""
        <div class="emergencia-box">
            <span style='color:#ff007f; font-weight:bold;'>🛡️ RETO DE SEGURIDAD:</span> 
            Tu meta actual es un <b>Fondo de Emergencia de ₡500,000</b>. ¡No lo toques a menos que sea una urgencia real!
        </div>
    """, unsafe_allow_html=True)

    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    balance = ing - gas
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt(ing))
    c2.metric("Gastos", fmt(gas), delta_color="inverse")
    c3.metric("Saldo Disponible", fmt(balance))

    st.markdown('<div class="coach-box">', unsafe_allow_html=True)
    st.subheader("🤖 Coach IA GeZo")
    if balance < 0:
        st.error(f"⚠️ *Números Rojos:* Estás gastando {fmt(abs(balance))} más de lo que ganas. Revisa la categoría '⚖️ Pensión' o '📱 SINPE'.")
    elif balance > 0 and balance < (st.session_state.pres * 0.1):
        st.warning("🧐 *Margen Crítico:* Tu saldo libre es poco. Evita compras fuera de presupuesto.")
    else:
        st.success("💎 *Balance Elite:* ¡Excelente! Tienes un buen margen. ¿Ya abonaste a tu Meta?")
    st.markdown('</div>', unsafe_allow_html=True)

    if not df.empty:
        # Botón de exportar a Excel (CSV)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Movimientos (Excel/CSV)", csv, "Mis_Finanzas_GeZo.csv", "text/csv")
        
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark", title="¿En qué gastas?")
        st.plotly_chart(fig, use_container_width=True)

# --- SINPE RÁPIDO ---
elif menu == "📱 SINPE Rápido":
    st.header("📱 SINPE Móvil y Registro")
    st.info("Primero registra el envío aquí para que no se te olvide, luego abre tu banco.")
    with st.form("sinpe_form"):
        tel = st.text_input("Número de Destino (8 dígitos)", placeholder="88887777")
        mon_s = st.number_input("Monto del envío (₡)", min_value=0)
        det_s = st.text_input("¿Para qué es?", placeholder="Pago almuerzo, feria, etc.")
        banc = st.selectbox("Abrir Aplicación de:", ["BNCR", "BAC", "BCR", "BP", "Promerica"])
        if st.form_submit_button("REGISTRAR Y IR AL BANCO"):
            if len(tel) == 8:
                c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                          (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), f"SINPE a {tel}: {det_s}", mon_s, "Gasto", "📱 SINPE"))
                conn.commit()
                st.success("✅ Gasto anotado en tu historial.")
                links = {"BNCR": "https://www.bnmovil.fi.cr/", "BAC": "https://www.baccredomatic.com/", "BCR": "https://www.bancobcr.com/", "BP": "https://www.bancopopular.fi.cr/"}
                st.markdown(f'<a href="{links.get(banc, "https://google.com")}" target="_blank" class="whatsapp-btn">🚀 Abrir App de {banc} Ahora</a>', unsafe_allow_html=True)
            else: st.error("Número inválido.")

# --- REGISTRO MANUAL ---
elif menu == "💸 Registrar":
    st.header("Nuevo Movimiento Manual")
    with st.form("reg_m"):
        desc = st.text_input("Descripción")
        mont = st.number_input("Monto", min_value=0.0)
        moneda = st.radio("Moneda", ["₡ Colones", "$ Dólares"], horizontal=True)
        cate = st.selectbox("Categoría", ["⚖️ Pensión", "⛽ Gasolina", "🛒 Súper", "🍱 Salidas", "🏠 Casa", "⚡ Servicios", "📱 SINPE", "🎬 Suscripciones", "💡 Gastos Hormiga", "🏦 Deudas", "💰 Ahorro", "💵 Salario", "📦 Otros"])
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        if st.form_submit_button("GUARDAR EN NUBE"):
            f_mont = mont if "₡" in moneda else mont * TC_DOLAR
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, f_mont, tipo, cate))
            conn.commit()
            st.success("¡Guardado!")

# --- DEUDAS CON ABONO AUTOMÁTICO ---
elif menu == "🤝 Deudas y Cobros":
    st.header("Préstamos y Deudas")
    t1, t2 = st.tabs(["➕ Nueva", "📋 Gestión"])
    with t1:
        with st.form("deu_n"):
            p_nom = st.text_input("Nombre de la Persona")
            p_tot = st.number_input("Monto Total", min_value=0.0)
            p_tip = st.selectbox("Relación", ["Me deben (Cobro)", "Yo debo (Deuda)"])
            if st.form_submit_button("REGISTRAR"):
                c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo) VALUES (?,?,?,?,?)", (st.session_state.uid, p_nom, p_tot, 0, p_tip))
                conn.commit()
                st.rerun()
    with t2:
        deudas = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid}", conn)
        for i, r in deudas.iterrows():
            falta = r['monto_total'] - r['pagado']
            st.write(f"*{r['nombre']}* | Resta: {fmt(falta)}")
            if falta > 0:
                with st.expander("Registrar Abono"):
                    abo = st.number_input("Monto Abono", min_value=0.0, key=f"abo_{r['id']}")
                    if st.button("Abonar", key=f"btn_{r['id']}"):
                        c.execute("UPDATE deudas SET pagado = pagado + ? WHERE id = ?", (abo, r['id']))
                        # Vinculación automática a movimientos
                        tipo_mov = "Ingreso" if "Me deben" in r['tipo'] else "Gasto"
                        c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                                  (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), f"Abono de/a {r['nombre']}", abo, tipo_mov, "🤝 Deudas/Cobros"))
                        conn.commit()
                        st.rerun()

# --- CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Calculadora CRC / USD")
    v_c = st.number_input("Cantidad", min_value=0.0)
    st.write(f"En colones: *₡{v_c * TC_DOLAR:,.2f}*")
    st.write(f"En dólares: *${v_c / TC_DOLAR:,.2f}*")

# --- METAS ---
elif menu == "🎯 Metas":
    st.header("Metas de Ahorro")
    with st.expander("Nueva Meta"):
        m_n = st.text_input("¿Qué quieres comprar?")
        m_o = st.number_input("Monto Objetivo", min_value=0.0)
        if st.button("Crear Meta"):
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (?,?,?,?)", (st.session_state.uid, m_n, m_o, 0))
            conn.commit()
            st.rerun()
    metas = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn)
    for i, r in metas.iterrows():
        st.write(f"*{r['nombre']}*")
        st.progress(r['actual']/r['objetivo'] if r['objetivo'] > 0 else 0)

# --- ADMIN ---
elif menu == "⚙️ Admin":
    if st.session_state.rol == 'admin':
        st.header("Panel de Administración Master")
        with st.form("admin_u"):
            nu, nc = st.text_input("Usuario"), st.text_input("Clave")
            np = st.number_input("Presupuesto Sugerido", value=250000)
            nplan = st.selectbox("Plan", ["Prueba (7d)", "Mensual", "Anual", "Eterno"])
            dias = 7 if "Prueba" in nplan else 30 if "Mensual" in nplan else 365 if "Anual" in nplan else 36500
            if st.form_submit_button("CREAR CLIENTE"):
                v_f = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, presupuesto) VALUES (?,?,?,?,?,?)", (nu, nc, v_f, 'usuario', nplan, np))
                conn.commit()
                st.success(f"Usuario {nu} creado.")
        st.table(pd.read_sql("SELECT nombre, plan, expira FROM usuarios WHERE rol!='admin'", conn))
