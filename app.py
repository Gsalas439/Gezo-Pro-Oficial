import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import re
import base64

# --- 1. CONFIGURACIÓN DE INTERFAZ ELITE ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer, .stDeployButton {display: none !important;}
    .block-container {padding-top: 1.5rem !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    .balance-card { background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%); border-radius: 15px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.85em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    .bac-card { background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%); border-radius: 12px; padding: 12px; text-align: center; border: 1px solid #ff4b4b; color: white; font-weight: bold; }
    .ia-box { background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; padding: 20px; border-radius: 15px; border-left: 8px solid #00f2fe; margin-top: 10px; }
    .alert-box { background: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; padding: 15px; border-radius: 10px; color: #ff4b4b; font-weight: bold; margin-bottom: 15px; }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; border: 1px solid #222; border-left: 5px solid #00f2fe; margin-bottom: 10px; }
    .btn-banco { background-color: #00f2fe; color: #000 !important; padding: 15px; border-radius: 10px; text-decoration: none; font-weight: 900; text-align: center; display: block; margin-top: 10px; transition: 0.3s; }
    .btn-banco:hover { background-color: #00c3cc; color: black !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS Y NUEVOS MÓDULOS ---
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"])
    except: st.error("Reconectando a la base de datos..."); return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS presupuestos (id SERIAL PRIMARY KEY, usuario_id INTEGER, cat TEXT, limite DECIMAL)")
    c.execute("CREATE TABLE IF NOT EXISTS suscripciones (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto DECIMAL, dia_cobro INTEGER, cat TEXT, moneda TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS historial_suscripciones (id SERIAL PRIMARY KEY, suscripcion_id INTEGER, mes_anio TEXT)")
    
    # Parche para columnas nuevas sin borrar datos viejos
    c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'CRC'")
    c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS comprobante TEXT DEFAULT NULL")
    c.execute("ALTER TABLE deudas ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'CRC'")
    conn.commit(); c.close(); conn.close()

inicializar_db()

TIPO_CAMBIO_COMPRA = 512.00
TIPO_CAMBIO_VENTA = 524.00

def reg_mov(monto, tipo, cat, desc, moneda="CRC", comprobante=None):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, moneda, comprobante) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat, moneda, comprobante))
        conn.commit(); c.close(); conn.close()

# AUTO-COBRO DE SUSCRIPCIONES Y GASTOS FIJOS (Motor Fantasma)
def procesar_suscripciones_pendientes():
    hoy = date.today()
    mes_actual = hoy.strftime("%Y-%m")
    dia_actual = hoy.day
    
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT id, nombre, monto, dia_cobro, cat, moneda FROM suscripciones WHERE usuario_id=%s", (st.session_state.uid,))
    suscripciones = c.fetchall()
    
    for sub in suscripciones:
        sub_id, nombre, monto, dia_cobro, cat, moneda = sub
        if dia_actual >= dia_cobro:
            # Verifica si ya se cobró este mes
            c.execute("SELECT id FROM historial_suscripciones WHERE suscripcion_id=%s AND mes_anio=%s", (sub_id, mes_actual))
            if not c.fetchone():
                # Registrar el gasto fijo automáticamente
                c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, moneda) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                          (st.session_state.uid, date.today(), f"Cobro Automático: {nombre}", monto, "Gasto", cat, moneda))
                c.execute("INSERT INTO historial_suscripciones (suscripcion_id, mes_anio) VALUES (%s,%s)", (sub_id, mes_actual))
    conn.commit(); c.close(); conn.close()

# --- 3. LOGIN & SEGURIDAD (URL CLEANER) ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    token_url = st.query_params.get("session_token")
    if token_url:
        conn = get_connection(); c = conn.cursor(); c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE id=%s", (token_url,))
        res = c.fetchone(); c.close(); conn.close()
        if res and date.today() <= res[4]:
            st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
            st.query_params.clear(); st.rerun()

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #00f2fe; margin-top: 10vh;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login"):
            u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
            mantener = st.checkbox("Mantener sesión iniciada", value=True)
            if st.form_submit_button("ACCEDER AL SISTEMA", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone(); c.close(); conn.close()
                if res:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    if mantener: st.query_params["session_token"] = str(res[0])
                    st.rerun()
                else: st.error("Credenciales incorrectas.")
    st.stop()

# Procesar cobros automáticos al entrar
procesar_suscripciones_pendientes()

# --- 4. MOTOR INTELIGENTE Y NAVEGACIÓN ---
st.markdown(f"### 👑 **{st.session_state.uname}** | Panel {st.session_state.plan}")

conn = get_connection()
df_alertas = pd.read_sql(f"SELECT nombre, fecha_vence, monto_total, pagado, moneda FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA' AND pagado < monto_total", conn)
conn.close()
for _, r in df_alertas.iterrows():
    dias = (r['fecha_vence'] - date.today()).days
    if 0 <= dias <= 2: st.markdown(f'<div class="alert-box">⚠️ ALERTA: Tu deuda con **{r["nombre"]}** vence en {dias} días. ({r["moneda"]} {float(r["monto_total"] - r["pagado"]):,.0f})</div>', unsafe_allow_html=True)
    elif dias < 0: st.markdown(f'<div class="alert-box" style="background: rgba(200,0,0,0.2);">🚨 VENCIDA: Atraso de {abs(dias)} días con **{r["nombre"]}**.</div>', unsafe_allow_html=True)

# 8 Pestañas Ultra Completas
t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(["📊 DASHBOARD", "💸 REGISTRO", "🚧 PRESUPUESTOS & FIJOS", "🎯 METAS", "🏦 DEUDAS", "📱 SINPE", "📜 HISTORIAL", "⚙️ AJUSTES"])

# --- DASHBOARD Y MULTI-MONEDA ---
with t1:
    c_bac1, c_bac2, c_bac3 = st.columns([1,1,2])
    c_bac1.markdown(f'<div class="bac-card"><small>BAC COMPRA (USD)</small><br>₡{TIPO_CAMBIO_COMPRA}</div>', unsafe_allow_html=True)
    c_bac2.markdown(f'<div class="bac-card"><small>BAC VENTA (USD)</small><br>₡{TIPO_CAMBIO_VENTA}</div>', unsafe_allow_html=True)
    
    st.divider()
    rango = st.radio("Filtro de Tiempo:", ["Mes Actual", "7 días", "Histórico"], horizontal=True)
    
    # Lógica de Fechas
    if rango == "Mes Actual": f_inicio = date.today().replace(day=1)
    elif rango == "7 días": f_inicio = date.today() - timedelta(days=7)
    else: f_inicio = date.today() - timedelta(days=9999)
    
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{f_inicio}'", conn)
    df_pres = pd.read_sql(f"SELECT cat, limite FROM presupuestos WHERE usuario_id={st.session_state.uid}", conn)
    conn.close()
    
    def cvt_colones(fila):
        m = float(fila['monto'])
        if fila['moneda'] == 'USD': return m * TIPO_CAMBIO_COMPRA if fila['tipo'] == 'Ingreso' else m * TIPO_CAMBIO_VENTA
        return m

    if not df.empty:
        df['monto_crc'] = df.apply(cvt_colones, axis=1)
        ing = df[df['tipo']=='Ingreso']['monto_crc'].sum(); gas = df[df['tipo']=='Gasto']['monto_crc'].sum(); neto = ing - gas
        
        col1, col2, col3 = st.columns(3)
        col1.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos (CRC)</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
        col2.markdown(f'<div class="balance-card"><p class="metric-label">Gastos (CRC)</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
        col3.markdown(f'<div class="balance-card"><p class="metric-label">Patrimonio Neto</p><p class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</p></div>', unsafe_allow_html=True)
        
        # MONITOR DE PRESUPUESTOS (NUEVO)
        if not df_pres.empty and rango == "Mes Actual":
            st.markdown("### 🚧 Semáforo de Presupuestos (Este Mes)")
            gastos_mes = df[df['tipo']=='Gasto'].groupby('cat')['monto_crc'].sum().reset_index()
            for _, rp in df_pres.iterrows():
                gastado = gastos_mes[gastos_mes['cat'] == rp['cat']]['monto_crc'].sum() if rp['cat'] in gastos_mes['cat'].values else 0
                limite = float(rp['limite'])
                porcentaje = min(gastado / limite, 1.0) if limite > 0 else 1.0
                st.write(f"**{rp['cat']}** | Gastado: ₡{gastado:,.0f} de ₡{limite:,.0f}")
                st.progress(porcentaje)
                if porcentaje >= 0.9: st.error(f"⚠️ Estás a punto de exceder tu límite en {rp['cat']}!")

        st.markdown('<div class="ia-box">#### 🤖 GeZo Predictive AI<br>', unsafe_allow_html=True)
        if neto > 0: st.write(f"Liquidez sana. Mueve **₡{neto*0.2:,.0f}** a tus metas de ahorro.")
        else: st.write("Déficit detectado. Frena los gastos variables.")
        st.markdown('</div>', unsafe_allow_html=True)
    else: st.info("No hay movimientos.")

# --- REGISTRO Y BÓVEDA ---
with t2:
    tab_manual, tab_magico = st.tabs(["✍️ Registro y Bóveda de Recibos", "🪄 Lector SMS Bancario"])
    
    with tab_manual:
        tipo = st.radio("Tipo de Movimiento", ["Gasto", "Ingreso"], horizontal=True)
        cats = ["Súper/Comida", "Servicios", "Casa/Alquiler", "Transporte", "Ocio", "Salud", "Educación", "Otros"] if tipo == "Gasto" else ["Salario", "Venta", "Intereses", "Regalo", "Otros"]
        with st.form("f_registro"):
            c_m1, c_m2 = st.columns([1,3])
            moneda = c_m1.selectbox("Moneda", ["CRC", "USD"])
            m = c_m2.number_input("Monto", min_value=0.0, step=500.0)
            c = st.selectbox("Categoría", cats)
            d = st.text_input("Descripción opcional")
            foto = st.file_uploader("📸 Subir Recibo/Factura (Opcional)", type=["png", "jpg", "jpeg"])
            
            if st.form_submit_button("GUARDAR EN BÓVEDA", use_container_width=True):
                img_b64 = None
                if foto: img_b64 = base64.b64encode(foto.read()).decode('utf-8')
                reg_mov(m, tipo, c, d, moneda, img_b64)
                st.success("✅ Guardado con recibo incluido."); st.rerun()
                
    with tab_magico:
        texto_sms = st.text_area("Pega el SMS de tu banco:")
        if st.button("🪄 Extraer Gasto de SMS"):
            if texto_sms:
                monto_match = re.search(r'[\$₡]?\s?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', texto_sms)
                mon_det = "USD" if "$" in texto_sms or "USD" in texto_sms.upper() else "CRC"
                cat_det = "Otros"
                if any(w in texto_sms.upper() for w in ["WALMART", "MASXMENOS", "AUTO MERCADO", "PALI"]): cat_det = "Súper/Comida"
                elif any(w in texto_sms.upper() for w in ["UBER", "DIDDI", "GAS", "DELTA"]): cat_det = "Transporte"
                elif any(w in texto_sms.upper() for w in ["KFC", "MCDONALDS", "STARBUCKS"]): cat_det = "Ocio"
                
                if monto_match:
                    monto_limpio = float(monto_match.group(1).replace(',', ''))
                    st.info(f"Detectado: **{mon_det} {monto_limpio}** ({cat_det})")
                    if st.button("Confirmar Gasto Rápido"):
                        reg_mov(monto_limpio, "Gasto", cat_det, texto_sms[:30], mon_det)
                        st.success("Registrado."); st.rerun()
                else: st.error("No se detectó un monto.")

# --- PRESUPUESTOS Y GASTOS FIJOS (NUEVO) ---
with t3:
    tab_pres, tab_fijos = st.tabs(["🚧 Límites Mensuales", "🔁 Gastos Fijos (Suscripciones)"])
    with tab_pres:
        with st.form("f_pres"):
            cat_p = st.selectbox("Categoría a limitar", ["Súper/Comida", "Transporte", "Ocio", "Otros"])
            lim = st.number_input("Límite mensual (CRC)", min_value=1.0)
            if st.form_submit_button("ESTABLECER LÍMITE"):
                conn = get_connection(); c = conn.cursor()
                c.execute("DELETE FROM presupuestos WHERE usuario_id=%s AND cat=%s", (st.session_state.uid, cat_p))
                c.execute("INSERT INTO presupuestos (usuario_id, cat, limite) VALUES (%s,%s,%s)", (st.session_state.uid, cat_p, lim))
                conn.commit(); c.close(); conn.close(); st.success("Límite activo."); st.rerun()
                
        conn = get_connection(); df_pr = pd.read_sql(f"SELECT * FROM presupuestos WHERE usuario_id={st.session_state.uid}", conn); conn.close()
        for _, r in df_pr.iterrows():
            st.markdown(f'<div class="user-card">🚧 <b>{r["cat"]}</b> | Límite: ₡{float(r["limite"]):,.0f}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Quitar límite", key=f"dp_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM presupuestos WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

    with tab_fijos:
        st.write("Registra tus pagos automáticos. GeZo los cobrará el día que indiques.")
        with st.form("f_susc"):
            n_s = st.text_input("Nombre (Ej: Netflix, Préstamo)")
            c1, c2 = st.columns(2)
            mon_s = c1.selectbox("Moneda", ["CRC", "USD"])
            m_s = c2.number_input("Monto", min_value=1.0)
            d_c = st.number_input("Día de cobro cada mes (1-31)", min_value=1, max_value=31)
            cat_s = st.selectbox("Categoría", ["Servicios", "Ocio", "Casa/Alquiler", "Otros"])
            if st.form_submit_button("AGREGAR GASTO FIJO"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO suscripciones (usuario_id, nombre, monto, dia_cobro, cat, moneda) VALUES (%s,%s,%s,%s,%s,%s)", (st.session_state.uid, n_s, m_s, d_c, cat_s, mon_s)); conn.commit(); c.close(); conn.close(); st.success("Suscripción activa."); st.rerun()
        
        conn = get_connection(); df_sub = pd.read_sql(f"SELECT * FROM suscripciones WHERE usuario_id={st.session_state.uid}", conn); conn.close()
        for _, r in df_sub.iterrows():
            st.markdown(f'<div class="user-card">🔁 <b>{r["nombre"]}</b> | {r["moneda"]} {float(r["monto"]):,.0f} | Se cobra el día {r["dia_cobro"]}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Cancelar Auto-Pago", key=f"dsub_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM suscripciones WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- METAS (T4) ---
with t4:
    with st.expander("➕ Crear Nuevo Proyecto"):
        with st.form("f_metas"):
            n = st.text_input("Nombre de la meta"); o = st.number_input("Monto a alcanzar", min_value=1.0)
            if st.form_submit_button("CREAR META"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); conn.close(); st.rerun()
    
    conn = get_connection(); df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", conn); conn.close()
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        ca, cb, cc = st.columns([2,1,1])
        m_a = ca.number_input("Depositar:", min_value=0.0, key=f"ma_{r['id']}")
        if cb.button("ABONAR", key=f"ba_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close(); conn.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}"); st.rerun()
        if cc.button("🗑️", key=f"dm_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM metas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- DEUDAS/COBROS (T5) ---
with t5:
    tab_d, tab_c = st.tabs(["🔴 DEUDAS", "🟢 COBROS"])
    def render_cuentas(t_r):
        with st.expander("➕ Nuevo Registro"):
            with st.form(f"f_{t_r}"):
                nom = st.text_input("Entidad/Persona"); col_m1, col_m2 = st.columns([1,3]); md = col_m1.selectbox("Mon", ["CRC", "USD"], key=f"m_{t_r}"); mon = col_m2.number_input("Monto", min_value=1.0); ven = st.date_input("Vence")
                if st.form_submit_button("GUARDAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence, moneda) VALUES (%s,%s,%s,%s,%s,%s)", (st.session_state.uid, nom, mon, t_r, ven, md)); conn.commit(); c.close(); conn.close(); st.rerun()
        conn = get_connection(); df_x = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='{t_r}' ORDER BY fecha_vence ASC", conn); conn.close()
        for _, r in df_x.iterrows():
            pend = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card"><b>{r["nombre"]}</b> | Pendiente: {r["moneda"]} {pend:,.0f} | Vence: {r["fecha_vence"]}</div>', unsafe_allow_html=True)
            if pend > 0:
                c1, c2, c3 = st.columns([2,1,1]); m_p = c1.number_input("Abono", min_value=0.0, max_value=pend, key=f"px_{r['id']}")
                if c2.button("PAGAR", key=f"bx_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (m_p, r['id'])); conn.commit(); c.close(); conn.close()
                    reg_mov(m_p, "Gasto" if t_r=='DEUDA' else "Ingreso", f"🏦 {t_r}", f"Abono a {r['nombre']}", r['moneda']); st.rerun()
                if c3.button("🗑️", key=f"dx_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM deudas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()
    with tab_d: render_cuentas('DEUDA')
    with tab_c: render_cuentas('COBRO')

# --- SINPE (T6) ---
with t6:
    conn = get_connection(); df_cnt = pd.read_sql(f"SELECT * FROM contactos WHERE usuario_id={st.session_state.uid} ORDER BY nombre", conn); conn.close()
    col_s1, col_s2 = st.columns([1.2, 1])
    with col_s1:
        st.markdown("**Enviar Dinero**")
        sel = st.selectbox("Contacto:", ["✏️ Manual..."] + [f"{r['nombre']} - {r['telefono']}" for _, r in df_cnt.iterrows()])
        with st.form("fs"):
            num = st.text_input("Teléfono:", value="" if "✏️" in sel else sel.split(" - ")[1])
            mon = st.number_input("Monto (₡):", min_value=0.0, step=500.0)
            det = st.text_input("Detalle:")
            if st.form_submit_button("REGISTRAR Y BANCO", use_container_width=True):
                if num and mon > 0:
                    reg_mov(mon, "Gasto", "📱 SINPE", f"A: {num} - {det}")
                    st.markdown('<a href="https://www.google.com" target="_blank" class="btn-banco">🏦 IR AL BANCO</a>', unsafe_allow_html=True)
    with col_s2:
        st.markdown("**Agenda**")
        with st.expander("➕ Nuevo"):
            with st.form("fc"):
                nc = st.text_input("Nombre"); tc = st.text_input("Teléfono")
                if st.form_submit_button("GUARDAR"):
                    if nc and tc:
                        conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO contactos (usuario_id, nombre, telefono) VALUES (%s,%s,%s)", (st.session_state.uid, nc, tc)); conn.commit(); c.close(); conn.close(); st.rerun()
        if not df_cnt.empty:
            for _, r in df_cnt.iterrows():
                ca, cb = st.columns([4, 1])
                ca.markdown(f"👤 {r['nombre']} ({r['telefono']})")
                if cb.button("🗑️", key=f"dc_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM contactos WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- HISTORIAL, REPORTES & RECIBOS (T7) ---
with t7:
    st.subheader("📜 Movimientos, Reportes y Recibos")
    conn = get_connection()
    df_h = pd.read_sql(f"SELECT id, fecha, tipo, cat, monto, moneda, descrip, comprobante FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", conn)
    conn.close()
    
    if not df_h.empty:
        csv = df_h.drop(columns=['comprobante']).to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Descargar CSV para Excel", data=csv, file_name=f'Reporte_{date.today()}.csv', mime='text/csv')
        st.divider()
        
        for _, r in df_h.head(50).iterrows(): # Muestra últimos 50
            with st.expander(f"{r['fecha']} | {r['tipo']} | {r['cat']} | {r['moneda']} {float(r['monto']):,.0f} | {r['descrip'][:20]}"):
                st.write(f"**Detalle completo:** {r['descrip']}")
                if r['comprobante']:
                    st.image(base64.b64decode(r['comprobante']), caption="Recibo adjunto", use_container_width=True)
                else:
                    st.info("Sin recibo adjunto.")
                if st.button("🗑️ Borrar registro", key=f"delh_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM movimientos WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()
    else: st.info("Sin registros.")

# --- AJUSTES (T8) ---
with t8:
    st.subheader("⚙️ Configuración")
    with st.form("f_pass"):
        new_p = st.text_input("Nueva contraseña", type="password")
        if st.form_submit_button("ACTUALIZAR"):
            if new_p:
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (new_p, st.session_state.uid)); conn.commit(); c.close(); conn.close(); st.success("Actualizada.")
    st.divider()
    if st.button("🚪 CERRAR SESIÓN TOTAL", type="primary", use_container_width=True):
        st.session_state.autenticado = False; st.query_params.clear(); st.rerun()
