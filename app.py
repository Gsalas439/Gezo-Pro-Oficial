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
    .balance-card { background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%); border-radius: 12px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .metric-value { font-size: 2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.8em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    .bac-card { background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%); border-radius: 10px; padding: 10px; text-align: center; border: 1px solid #ff4b4b; color: white; font-weight: bold; }
    .ia-box { background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; padding: 20px; border-radius: 12px; border-left: 5px solid #00f2fe; margin-top: 10px; margin-bottom: 15px; }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 12px; border-radius: 10px; border: 1px solid #222; border-left: 4px solid #00f2fe; margin-bottom: 8px; }
    .alert-box { background: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; padding: 15px; border-radius: 10px; color: #ff4b4b; font-weight: bold; margin-bottom: 15px; }
    .btn-banco { background-color: #00f2fe; color: #000 !important; padding: 12px; border-radius: 8px; text-decoration: none; font-weight: 900; text-align: center; display: block; margin-top: 10px; transition: 0.3s; }
    .btn-banco:hover { background-color: #00c3cc; color: black !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS Y ARQUITECTURA ERP (BLINDADA) ---
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"])
    except Exception as e: st.error("Conectando con Servidor Seguro..."); return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo_registro TEXT, fecha_vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS presupuestos (id SERIAL PRIMARY KEY, usuario_id INTEGER, cat TEXT, limite DECIMAL)")
    c.execute("CREATE TABLE IF NOT EXISTS suscripciones (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto DECIMAL, dia_cobro INTEGER, cat TEXT, moneda TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS historial_suscripciones (id SERIAL PRIMARY KEY, suscripcion_id INTEGER, mes_anio TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS billeteras (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, tipo TEXT, moneda TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS proyectos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT)")
    
    cols_mov = ["moneda TEXT DEFAULT 'CRC'", "comprobante TEXT DEFAULT NULL", "billetera_id INTEGER DEFAULT 0", "proyecto_id INTEGER DEFAULT 0", "impuesto_reserva DECIMAL DEFAULT 0"]
    for col in cols_mov: c.execute(f"ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS {col}")
    cols_deu = ["moneda TEXT DEFAULT 'CRC'", "tasa_interes DECIMAL DEFAULT 0", "plazo_meses INTEGER DEFAULT 1"]
    for col in cols_deu: c.execute(f"ALTER TABLE deudas ADD COLUMN IF NOT EXISTS {col}")
    
    conn.commit(); c.close(); conn.close()

inicializar_db()

TIPO_CAMBIO_COMPRA = 512.00
TIPO_CAMBIO_VENTA = 524.00

def calcular_cuota_nivelada(monto, tasa_anual, meses):
    if tasa_anual == 0 or meses == 0: return monto / max(1, meses)
    tasa_mensual = (tasa_anual / 100) / 12
    return monto * (tasa_mensual * (1 + tasa_mensual)**meses) / ((1 + tasa_mensual)**meses - 1)

def reg_mov(monto, tipo, cat, desc, moneda="CRC", comprobante=None, billetera_id=0, proyecto_id=0, impuesto=0):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, moneda, comprobante, billetera_id, proyecto_id, impuesto_reserva) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat, moneda, comprobante, billetera_id, proyecto_id, impuesto))
        conn.commit(); c.close(); conn.close()

def procesar_suscripciones_pendientes():
    hoy = date.today()
    mes_actual = hoy.strftime("%Y-%m")
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT id, nombre, monto, dia_cobro, cat, moneda FROM suscripciones WHERE usuario_id=%s", (st.session_state.uid,))
    suscripciones = c.fetchall()
    for sub in suscripciones:
        sub_id, nombre, monto, dia_cobro, cat, moneda = sub
        # Lógica inteligente para fin de mes (ej. febrero 28)
        ultimo_dia_mes = (hoy.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        dia_efectivo = min(dia_cobro, ultimo_dia_mes.day)
        
        if hoy.day >= dia_efectivo:
            c.execute("SELECT id FROM historial_suscripciones WHERE suscripcion_id=%s AND mes_anio=%s", (sub_id, mes_actual))
            if not c.fetchone():
                c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, moneda) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                          (st.session_state.uid, hoy, f"Auto-Cobro: {nombre}", monto, "Gasto", cat, moneda))
                c.execute("INSERT INTO historial_suscripciones (suscripcion_id, mes_anio) VALUES (%s,%s)", (sub_id, mes_actual))
    conn.commit(); c.close(); conn.close()

# --- 3. LOGIN & SEGURIDAD URL ---
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
            if st.form_submit_button("INICIAR SESIÓN", use_container_width=True):
                conn = get_connection(); c = conn.cursor(); c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone(); c.close(); conn.close()
                if res:
                    if date.today() <= res[4]:
                        st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                        if mantener: st.query_params["session_token"] = str(res[0])
                        st.rerun()
                    else: st.error("Membresía expirada.")
                else: st.error("Credenciales incorrectas.")
    st.stop()

# Procesar cobros automáticos (Motor Fantasma)
procesar_suscripciones_pendientes()

# --- 4. NAVEGACIÓN COMPLETA ERP ---
st.markdown(f"### 👑 **{st.session_state.uname}** | ERP System")

# Alertas Proactivas Blindadas
conn = get_connection()
df_alertas = pd.read_sql("SELECT nombre, fecha_vence, monto_total, pagado, moneda FROM deudas WHERE usuario_id=%s AND tipo_registro='DEUDA' AND pagado < monto_total", conn, params=(st.session_state.uid,))
conn.close()
if not df_alertas.empty:
    for _, r in df_alertas.iterrows():
        dias = (r['fecha_vence'] - date.today()).days
        if 0 <= dias <= 2: st.markdown(f'<div class="alert-box">⚠️ ALERTA: Tu obligación con **{r["nombre"]}** vence en {dias} días.</div>', unsafe_allow_html=True)
        elif dias < 0: st.markdown(f'<div class="alert-box" style="background: rgba(200,0,0,0.2);">🚨 VENCIDA: Atraso de {abs(dias)} días con **{r["nombre"]}**.</div>', unsafe_allow_html=True)

t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(["📊 DASHBOARD", "💸 REGISTRO", "💼 BILLETERAS & PROY", "🚧 FIJOS & PRES", "🎯 METAS", "🏦 DEUDAS", "📱 SINPE", "📜 HISTORIAL Y AJUSTES"])

# --- T1: DASHBOARD & RENTABILIDAD ---
with t1:
    cb1, cb2, cb3 = st.columns([1,1,2])
    cb1.markdown(f'<div class="bac-card"><small>BAC COMPRA (USD)</small><br>₡{TIPO_CAMBIO_COMPRA}</div>', unsafe_allow_html=True)
    cb2.markdown(f'<div class="bac-card"><small>BAC VENTA (USD)</small><br>₡{TIPO_CAMBIO_VENTA}</div>', unsafe_allow_html=True)
    
    st.divider()
    rango = st.radio("Filtro Temporal:", ["Mes Actual", "Histórico"], horizontal=True)
    f_inicio = date.today().replace(day=1) if rango == "Mes Actual" else date.today() - timedelta(days=9999)
    
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM movimientos WHERE usuario_id=%s AND fecha >= %s", conn, params=(st.session_state.uid, f_inicio))
    df_proy = pd.read_sql("SELECT * FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    df_pres = pd.read_sql("SELECT * FROM presupuestos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    conn.close()
    
    def cvt(fila):
        m = float(fila['monto'])
        return m * TIPO_CAMBIO_COMPRA if fila['moneda'] == 'USD' and fila['tipo'] == 'Ingreso' else (m * TIPO_CAMBIO_VENTA if fila['moneda'] == 'USD' else m)

    if not df.empty:
        df['monto_crc'] = df.apply(cvt, axis=1)
        df['impuesto_reserva'] = df['impuesto_reserva'].fillna(0)
        impuestos_reserva = df['impuesto_reserva'].sum()
        
        ing = df[df['tipo']=='Ingreso']['monto_crc'].sum()
        gas = df[df['tipo']=='Gasto']['monto_crc'].sum()
        neto_bruto = ing - gas
        neto_real = neto_bruto - impuestos_reserva
        
        col1, col2, col3 = st.columns(3)
        col1.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos Brutos</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
        col2.markdown(f'<div class="balance-card"><p class="metric-label">Gastos</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
        col3.markdown(f'<div class="balance-card"><p class="metric-label">Capital Libre</p><p class="metric-value" style="color:#2ecc71;">₡{neto_real:,.0f}</p></div>', unsafe_allow_html=True)
        
        st.markdown(f'<div class="ia-box">🤖 <b>GeZo AI:</b> Tienes <b>₡{impuestos_reserva:,.0f}</b> retenidos para impuestos. Te sugerimos ahorrar ₡{max(0, neto_real*0.2):,.0f} este periodo.</div>', unsafe_allow_html=True)
        
        # Semáforo Presupuestos
        if not df_pres.empty and rango == "Mes Actual":
            st.markdown("### 🚧 Semáforo de Presupuestos (Este Mes)")
            gastos_mes = df[df['tipo']=='Gasto'].groupby('cat')['monto_crc'].sum().reset_index()
            for _, rp in df_pres.iterrows():
                gasto_serie = gastos_mes[gastos_mes['cat'] == rp['cat']]['monto_crc']
                gastado = gasto_serie.sum() if not gasto_serie.empty else 0
                limite = float(rp['limite'])
                pct = min(gastado / limite, 1.0) if limite > 0 else 1.0
                st.write(f"**{rp['cat']}** | Gastado: ₡{gastado:,.0f} / ₡{limite:,.0f}")
                st.progress(pct)
                if pct >= 0.9: st.error(f"⚠️ ¡Alerta! Límite casi superado en {rp['cat']}")

        # Rentabilidad Proyectos
        if not df_proy.empty:
            st.markdown("### 🏢 Rentabilidad por Centros de Costo")
            for _, rp in df_proy.iterrows():
                df_p = df[df['proyecto_id'] == rp['id']]
                ing_p = df_p[df_p['tipo']=='Ingreso']['monto_crc'].sum() if not df_p.empty else 0
                gas_p = df_p[df_p['tipo']=='Gasto']['monto_crc'].sum() if not df_p.empty else 0
                margen = ing_p - gas_p
                color_m = "#2ecc71" if margen >= 0 else "#ff4b4b"
                st.markdown(f'<div class="user-card"><b>{rp["nombre"]}</b> | Ingresos: ₡{ing_p:,.0f} | Gastos: ₡{gas_p:,.0f} | <span style="color:{color_m};">Margen: ₡{margen:,.0f}</span></div>', unsafe_allow_html=True)
    else:
        st.info("No hay transacciones en este periodo.")

# --- T2: REGISTRO MÁGICO Y MANUAL ---
with t2:
    tab_manual, tab_magico = st.tabs(["✍️ Registro y Bóveda", "🪄 Lector SMS Bancario"])
    
    with tab_manual:
        conn = get_connection()
        df_bill = pd.read_sql("SELECT id, nombre, moneda FROM billeteras WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        df_pry = pd.read_sql("SELECT id, nombre FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        conn.close()
        
        billeteras_op = [{"label": f"{r['nombre']} ({r['moneda']})", "id": r['id']} for _, r in df_bill.iterrows()] if not df_bill.empty else [{"label": "Cuenta Principal (CRC)", "id": 0}]
        proyectos_op = [{"label": "Ninguno (Gasto Personal)", "id": 0}] + [{"label": r['nombre'], "id": r['id']} for _, r in df_pry.iterrows()]
        
        tipo = st.radio("Tipo de Transacción", ["Gasto", "Ingreso"], horizontal=True)
        cats = ["Súper/Comida", "Servicios", "Casa/Alquiler", "Transporte", "Ocio", "Salud", "Educación", "Otros"] if tipo == "Gasto" else ["Ventas", "Servicios Profesionales", "Salario Fijo", "Otros"]
        
        with st.form("f_registro"):
            c1, c2 = st.columns(2)
            b_sel = c1.selectbox("¿De qué billetera / cuenta?", [b['label'] for b in billeteras_op])
            p_sel = c2.selectbox("Asignar a Proyecto:", [p['label'] for p in proyectos_op])
            
            b_id = next(b['id'] for b in billeteras_op if b['label'] == b_sel)
            p_id = next(p['id'] for p in proyectos_op if p['label'] == p_sel)
            
            monto = st.number_input("Monto", min_value=0.0, step=1000.0)
            cat = st.selectbox("Categoría", cats)
            
            impuesto = 0.0
            if tipo == "Ingreso" and p_id != 0:
                if st.checkbox("🛡️ Aplicar Escudo Fiscal (Congelar 13% IVA/Renta)"): impuesto = monto * 0.13
            
            desc = st.text_input("Descripción opcional")
            foto = st.file_uploader("📸 Adjuntar Factura / Recibo", type=["png", "jpg", "jpeg"])
            
            if st.form_submit_button("REGISTRAR MOVIMIENTO", use_container_width=True):
                img_str = base64.b64encode(foto.read()).decode('utf-8') if foto else None
                moneda_b = "USD" if "USD" in b_sel else "CRC"
                reg_mov(monto, tipo, cat, desc, moneda_b, img_str, b_id, p_id, impuesto)
                st.success("✅ Guardado correctamente."); st.rerun()

    with tab_magico:
        texto_sms = st.text_area("Pega el SMS de tu banco aquí:")
        if st.button("🪄 Extraer Gasto de SMS"):
            if texto_sms:
                monto_match = re.search(r'[\$₡]?\s?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', texto_sms)
                mon_det = "USD" if "$" in texto_sms or "USD" in texto_sms.upper() else "CRC"
                cat_det = "Otros"
                if any(w in texto_sms.upper() for w in ["WALMART", "MASXMENOS", "AUTO MERCADO", "PALI"]): cat_det = "Súper/Comida"
                elif any(w in texto_sms.upper() for w in ["UBER", "DIDDI", "GAS", "DELTA", "PUMA"]): cat_det = "Transporte"
                elif any(w in texto_sms.upper() for w in ["KFC", "MCDONALDS", "STARBUCKS", "RESTAURANTE"]): cat_det = "Ocio"
                
                if monto_match:
                    monto_limpio = float(monto_match.group(1).replace(',', ''))
                    st.info(f"IA Detectó: **{mon_det} {monto_limpio}** (Sugerencia: {cat_det})")
                    if st.button("Confirmar Gasto Rápido"):
                        reg_mov(monto_limpio, "Gasto", cat_det, texto_sms[:30], mon_det)
                        st.success("Registrado."); st.rerun()
                else: st.error("No se detectó un monto válido.")

# --- T3: BILLETERAS Y PROYECTOS ---
with t3:
    col_b, col_p = st.columns(2)
    with col_b:
        st.markdown("### 💳 Mis Billeteras")
        with st.form("f_bill"):
            n_b = st.text_input("Nombre (Ej: Tarjeta BAC)"); t_b = st.selectbox("Tipo", ["Débito / Efectivo", "Tarjeta de Crédito"]); m_b = st.selectbox("Moneda", ["CRC", "USD"])
            if st.form_submit_button("CREAR BILLETERA"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO billeteras (usuario_id, nombre, tipo, moneda) VALUES (%s,%s,%s,%s)", (st.session_state.uid, n_b, t_b, m_b)); conn.commit(); c.close(); conn.close(); st.rerun()
        conn = get_connection(); df_b = pd.read_sql("SELECT * FROM billeteras WHERE usuario_id=%s", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_b.iterrows(): st.markdown(f'<div class="user-card">💳 {r["nombre"]} ({r["moneda"]})</div>', unsafe_allow_html=True)
            
    with col_p:
        st.markdown("### 🏢 Centros de Costo")
        with st.form("f_proy"):
            n_p = st.text_input("Nombre del Proyecto")
            if st.form_submit_button("CREAR PROYECTO"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO proyectos (usuario_id, nombre) VALUES (%s,%s)", (st.session_state.uid, n_p)); conn.commit(); c.close(); conn.close(); st.rerun()
        conn = get_connection(); df_p = pd.read_sql("SELECT * FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_p.iterrows(): st.markdown(f'<div class="user-card">🏢 {r["nombre"]}</div>', unsafe_allow_html=True)

# --- T4: FIJOS Y PRESUPUESTOS ---
with t4:
    tab_pres, tab_fijos = st.tabs(["🚧 Límites Mensuales", "🔁 Suscripciones"])
    with tab_pres:
        with st.form("f_pres"):
            cat_p = st.selectbox("Categoría a limitar", ["Súper/Comida", "Transporte", "Ocio", "Otros"])
            lim = st.number_input("Límite mensual (CRC)", min_value=1.0)
            if st.form_submit_button("ESTABLECER LÍMITE"):
                conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM presupuestos WHERE usuario_id=%s AND cat=%s", (st.session_state.uid, cat_p)); c.execute("INSERT INTO presupuestos (usuario_id, cat, limite) VALUES (%s,%s,%s)", (st.session_state.uid, cat_p, lim)); conn.commit(); c.close(); conn.close(); st.success("Límite activo."); st.rerun()
        conn = get_connection(); df_pr = pd.read_sql("SELECT * FROM presupuestos WHERE usuario_id=%s", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_pr.iterrows():
            st.markdown(f'<div class="user-card">🚧 <b>{r["cat"]}</b> | Límite: ₡{float(r["limite"]):,.0f}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Quitar límite", key=f"dp_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM presupuestos WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

    with tab_fijos:
        st.write("GeZo registrará estos cobros automáticamente el día indicado.")
        with st.form("f_susc"):
            n_s = st.text_input("Nombre (Ej: Netflix)")
            c1, c2 = st.columns(2); mon_s = c1.selectbox("Moneda", ["CRC", "USD"]); m_s = c2.number_input("Monto", min_value=1.0)
            d_c = st.number_input("Día de cobro cada mes (1-31)", min_value=1, max_value=31)
            cat_s = st.selectbox("Categoría", ["Servicios", "Ocio", "Casa/Alquiler", "Otros"])
            if st.form_submit_button("AGREGAR GASTO FIJO"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO suscripciones (usuario_id, nombre, monto, dia_cobro, cat, moneda) VALUES (%s,%s,%s,%s,%s,%s)", (st.session_state.uid, n_s, m_s, d_c, cat_s, mon_s)); conn.commit(); c.close(); conn.close(); st.success("Suscripción activa."); st.rerun()
        conn = get_connection(); df_sub = pd.read_sql("SELECT * FROM suscripciones WHERE usuario_id=%s", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_sub.iterrows():
            st.markdown(f'<div class="user-card">🔁 <b>{r["nombre"]}</b> | {r["moneda"]} {float(r["monto"]):,.0f} | Día {r["dia_cobro"]}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Cancelar Auto-Pago", key=f"dsub_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM suscripciones WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- T5: METAS ---
with t5:
    with st.expander("➕ Crear Nueva Meta"):
        with st.form("f_metas"):
            n = st.text_input("Nombre de la meta"); o = st.number_input("Monto a alcanzar", min_value=1.0)
            if st.form_submit_button("CREAR META"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); conn.close(); st.rerun()
    conn = get_connection(); df_m = pd.read_sql("SELECT * FROM metas WHERE usuario_id=%s ORDER BY id DESC", conn, params=(st.session_state.uid,)); conn.close()
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>Llevas: ₡{float(r["actual"]):,.0f} de ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        ca, cb, cc = st.columns([2,1,1]); m_a = ca.number_input("Depositar:", min_value=0.0, key=f"ma_{r['id']}")
        if cb.button("ABONAR", key=f"ba_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close(); conn.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}"); st.rerun()
        if cc.button("🗑️", key=f"dm_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM metas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- T6: DEUDAS Y COBROS (CON AMORTIZACIÓN) ---
with t6:
    td, tc = st.tabs(["🏦 Calculadora de Préstamos (Deudas)", "🟢 Cuentas por Cobrar"])
    with td:
        with st.expander("➕ Ingresar Préstamo o Deuda"):
            with st.form("f_pres_bancario"):
                banco = st.text_input("Entidad Financiera"); col_d1, col_d2, col_d3 = st.columns(3)
                m_d = col_d1.number_input("Monto Total", min_value=1.0); tasa = col_d2.number_input("Tasa Interés Anual (%)", min_value=0.0); plazo = col_d3.number_input("Plazo (Meses)", min_value=1)
                mon_d = st.selectbox("Moneda", ["CRC", "USD"])
                if st.form_submit_button("REGISTRAR OBLIGACIÓN"):
                    vence = date.today() + timedelta(days=plazo*30)
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence, moneda, tasa_interes, plazo_meses) VALUES (%s,%s,%s,'DEUDA',%s,%s,%s,%s)", (st.session_state.uid, banco, m_d, vence, mon_d, tasa, plazo)); conn.commit(); c.close(); conn.close(); st.rerun()
        conn = get_connection(); df_d = pd.read_sql("SELECT * FROM deudas WHERE usuario_id=%s AND tipo_registro='DEUDA'", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_d.iterrows():
            pend = float(r['monto_total']) - float(r['pagado'])
            cuota = calcular_cuota_nivelada(float(r['monto_total']), float(r['tasa_interes']), int(r['plazo_meses']))
            st.markdown(f'<div class="user-card">🏦 <b>{r["nombre"]}</b> | Saldo: {r["moneda"]} {pend:,.0f}<br>Tasa: {r["tasa_interes"]}% | Cuota Mensual: <b>{r["moneda"]} {cuota:,.0f}</b></div>', unsafe_allow_html=True)
            if pend > 0:
                c1, c2, c3 = st.columns([2,1,1]); m_p = c1.number_input("Abono", min_value=0.0, value=min(cuota, pend), key=f"p_{r['id']}")
                if c2.button("ABONAR", key=f"b_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (m_p, r['id'])); conn.commit(); c.close(); conn.close()
                    reg_mov(m_p, "Gasto", "🏦 Préstamo", f"Cuota a {r['nombre']}", r['moneda']); st.rerun()
                if c3.button("🗑️", key=f"dd_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM deudas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()
    with tc:
        with st.expander("➕ Registrar Cobro"):
            with st.form("fc"):
                p = st.text_input("Deudor"); c_m1, c_m2 = st.columns([1,3]); md_c = c_m1.selectbox("Mon", ["CRC", "USD"]); m_c = c_m2.number_input("Monto", min_value=1.0); v_c = st.date_input("Fecha promesa")
                if st.form_submit_button("GUARDAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence, moneda) VALUES (%s,%s,%s,'COBRO',%s,%s)", (st.session_state.uid, p, m_c, v_c, md_c)); conn.commit(); c.close(); conn.close(); st.rerun()
        conn = get_connection(); df_c = pd.read_sql("SELECT * FROM deudas WHERE usuario_id=%s AND tipo_registro='COBRO'", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_c.iterrows():
            pen = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🟢 <b>{r["nombre"]}</b> | Falta que paguen: {r["moneda"]} {pen:,.0f}</div>', unsafe_allow_html=True)
            if pen > 0:
                c1, c2, c3 = st.columns([2,1,1]); p_c = c1.number_input("Recibir", min_value=0.0, max_value=pen, key=f"pc_{r['id']}")
                if c2.button("REGISTRAR", key=f"bc_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (p_c, r['id'])); conn.commit(); c.close(); conn.close()
                    reg_mov(p_c, "Ingreso", "💸 Cobro", f"De: {r['nombre']}", r['moneda']); st.rerun()
                if c3.button("🗑️", key=f"dc_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM deudas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- T7: SINPE MÓVIL Y AGENDA ---
with t7:
    conn = get_connection(); df_cnt = pd.read_sql("SELECT * FROM contactos WHERE usuario_id=%s ORDER BY nombre", conn, params=(st.session_state.uid,)); conn.close()
    col_s1, col_s2 = st.columns([1.2, 1])
    with col_s1:
        st.markdown("**1. Enviar Dinero**")
        sel = st.selectbox("Contacto:", ["✏️ Manual..."] + [f"{r['nombre']} - {r['telefono']}" for _, r in df_cnt.iterrows()])
        with st.form("f_sinpe_pago"):
            es_manual = "✏️" in sel
            num_final = st.text_input("Teléfono:", value="" if es_manual else sel.split(" - ")[1])
            monto_s = st.number_input("Monto (₡):", min_value=0.0, step=500.0)
            det_s = st.text_input("Detalle:")
            if st.form_submit_button("REGISTRAR Y BANCO", use_container_width=True):
                if num_final and monto_s > 0:
                    n_dest = "Manual" if es_manual else sel.split(" - ")[0]
                    reg_mov(monto_s, "Gasto", "📱 SINPE", f"A: {n_dest} ({num_final}) - {det_s}", "CRC")
                    st.markdown('<a href="https://www.google.com" target="_blank" class="btn-banco">🏦 IR AL BANCO AHORA</a>', unsafe_allow_html=True)
                else: st.error("Ingresa número y monto.")

    with col_s2:
        st.markdown("**2. Agenda**")
        with st.expander("➕ Nuevo contacto"):
            with st.form("f_nuevo_contacto"):
                n_c = st.text_input("Nombre"); t_c = st.text_input("Teléfono")
                if st.form_submit_button("GUARDAR"):
                    if n_c and t_c:
                        conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO contactos (usuario_id, nombre, telefono) VALUES (%s, %s, %s)", (st.session_state.uid, n_c, t_c)); conn.commit(); c.close(); conn.close(); st.rerun()
        if not df_cnt.empty:
            for _, r in df_cnt.iterrows():
                ca, cb = st.columns([4, 1])
                ca.markdown(f"👤 {r['nombre']} ({r['telefono']})")
                if cb.button("🗑️", key=f"del_c_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM contactos WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- T8: HISTORIAL Y AJUSTES ---
with t8:
    st.subheader("📜 Libro Mayor Contable y Ajustes")
    conn = get_connection()
    df_h = pd.read_sql("SELECT id, fecha, tipo, cat, monto, moneda, descrip, impuesto_reserva, comprobante FROM movimientos WHERE usuario_id=%s ORDER BY id DESC LIMIT 100", conn, params=(st.session_state.uid,))
    conn.close()
    
    if not df_h.empty:
        df_csv = df_h.drop(columns=['comprobante']).rename(columns={'fecha':'Fecha', 'tipo':'Tipo', 'cat':'Categoría', 'monto':'Monto', 'moneda':'Divisa', 'descrip':'Detalle', 'impuesto_reserva':'Retenido'})
        csv = df_csv.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Libro Mayor (Excel/CSV)", data=csv, file_name=f'GeZo_Auditoria_{date.today()}.csv', mime='text/csv')
        st.divider()
        
        for _, r in df_h.head(30).iterrows():
            with st.expander(f"{r['fecha']} | {r['tipo']} | {r['moneda']} {float(r['monto']):,.0f} | {r['cat']}"):
                st.write(f"**Detalle:** {r['descrip']}")
                if pd.notnull(r['impuesto_reserva']) and float(r['impuesto_reserva']) > 0: 
                    st.write(f"**Impuesto Retenido:** ₡{float(r['impuesto_reserva']):,.0f}")
                if r['comprobante']: 
                    try:
                        st.image(base64.b64decode(r['comprobante']), caption="Recibo Adjunto", use_container_width=True)
                    except:
                        st.warning("El formato del recibo no es soportado o está corrupto.")
                if st.button("🗑️ Borrar registro", key=f"delh_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM movimientos WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()
    else: 
        st.info("Sin registros.")
    
    st.divider()
    st.markdown("### Configuración de Seguridad")
    with st.form("f_pass"):
        new_p = st.text_input("Nueva contraseña", type="password")
        if st.form_submit_button("ACTUALIZAR CONTRASEÑA"):
            if new_p:
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (new_p, st.session_state.uid)); conn.commit(); c.close(); conn.close(); st.success("Actualizada.")
    if st.button("🚪 CERRAR SESIÓN TOTAL (Recomendado)", type="primary", use_container_width=True):
        st.session_state.autenticado = False; st.query_params.clear(); st.rerun()
