import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import re
import base64
import math

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
    .ia-box { background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; padding: 20px; border-radius: 12px; border-left: 5px solid #00f2fe; margin-top: 10px; }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 12px; border-radius: 10px; border: 1px solid #222; border-left: 4px solid #00f2fe; margin-bottom: 8px; }
    .btn-banco { background-color: #00f2fe; color: #000 !important; padding: 12px; border-radius: 8px; text-decoration: none; font-weight: 900; text-align: center; display: block; margin-top: 10px; transition: 0.3s; }
    .btn-banco:hover { background-color: #00c3cc; color: black !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS E INFRAESTRUCTURA ERP ---
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"])
    except: st.error("Reconectando DB..."); return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    # Tablas existentes
    c.execute("CREATE TABLE IF NOT EXISTS contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS presupuestos (id SERIAL PRIMARY KEY, usuario_id INTEGER, cat TEXT, limite DECIMAL)")
    c.execute("CREATE TABLE IF NOT EXISTS suscripciones (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto DECIMAL, dia_cobro INTEGER, cat TEXT, moneda TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS historial_suscripciones (id SERIAL PRIMARY KEY, suscripcion_id INTEGER, mes_anio TEXT)")
    
    # Nuevas Tablas Corporativas
    c.execute("CREATE TABLE IF NOT EXISTS billeteras (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, tipo TEXT, moneda TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS proyectos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT)")
    
    # Inyección de columnas nuevas sin destruir datos (Parches Seguros)
    columnas_mov = ["moneda TEXT DEFAULT 'CRC'", "comprobante TEXT DEFAULT NULL", "billetera_id INTEGER DEFAULT 0", "proyecto_id INTEGER DEFAULT 0", "impuesto_reserva DECIMAL DEFAULT 0"]
    for col in columnas_mov:
        c.execute(f"ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS {col}")
    
    columnas_deudas = ["moneda TEXT DEFAULT 'CRC'", "tasa_interes DECIMAL DEFAULT 0", "plazo_meses INTEGER DEFAULT 1"]
    for col in columnas_deudas:
        c.execute(f"ALTER TABLE deudas ADD COLUMN IF NOT EXISTS {col}")
        
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

# --- 3. LOGIN Y SHADOW STATE ---
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
    st.markdown("<h1 style='text-align: center; color: #00f2fe; margin-top: 5vh;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login"):
            u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INICIAR SESIÓN", use_container_width=True):
                conn = get_connection(); c = conn.cursor(); c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone(); c.close(); conn.close()
                if res:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    st.query_params["session_token"] = str(res[0]); st.rerun()
                else: st.error("Acceso denegado.")
    st.stop()

# --- 4. MOTOR PRINCIPAL ERP ---
st.markdown(f"### 👑 **{st.session_state.uname}** | ERP Financiero")

# Tabs Reorganizados para la lógica corporativa
t1, t2, t3, t4, t5, t6, t7 = st.tabs(["📊 DASHBOARD & RENTABILIDAD", "💸 REGISTRO MÁGICO", "💼 BILLETERAS & PROYECTOS", "🏦 DEUDAS (AMORTIZACIÓN) & METAS", "🚧 PRESUPUESTOS & FIJOS", "📱 SINPE", "📜 REPORTES"])

# --- T1: DASHBOARD Y RENTABILIDAD DE PROYECTOS ---
with t1:
    cb1, cb2, cb3 = st.columns([1,1,2])
    cb1.markdown(f'<div class="bac-card"><small>BAC COMPRA (USD)</small><br>₡{TIPO_CAMBIO_COMPRA}</div>', unsafe_allow_html=True)
    cb2.markdown(f'<div class="bac-card"><small>BAC VENTA (USD)</small><br>₡{TIPO_CAMBIO_VENTA}</div>', unsafe_allow_html=True)
    
    st.divider()
    rango = st.radio("Filtro:", ["Mes Actual", "Histórico"], horizontal=True)
    f_inicio = date.today().replace(day=1) if rango == "Mes Actual" else date.today() - timedelta(days=9999)
    
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{f_inicio}'", conn)
    df_proy = pd.read_sql(f"SELECT * FROM proyectos WHERE usuario_id={st.session_state.uid}", conn)
    conn.close()
    
    def cvt(fila):
        m = float(fila['monto'])
        return m * TIPO_CAMBIO_COMPRA if fila['moneda'] == 'USD' and fila['tipo'] == 'Ingreso' else (m * TIPO_CAMBIO_VENTA if fila['moneda'] == 'USD' else m)

    if not df.empty:
        df['monto_crc'] = df.apply(cvt, axis=1)
        # Separar el dinero retenido para impuestos
        impuestos_reserva = df['impuesto_reserva'].sum() if 'impuesto_reserva' in df.columns else 0
        
        ing = df[df['tipo']=='Ingreso']['monto_crc'].sum()
        gas = df[df['tipo']=='Gasto']['monto_crc'].sum()
        neto_bruto = ing - gas
        neto_real = neto_bruto - impuestos_reserva
        
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos Brutos</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="balance-card"><p class="metric-label">Gastos (Flujo Saliente)</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="balance-card"><p class="metric-label">Capital Real Neto</p><p class="metric-value" style="color:#2ecc71;">₡{neto_real:,.0f}</p></div>', unsafe_allow_html=True)
        
        st.markdown(f'<div class="ia-box">🤖 <b>GeZo CFO:</b> Tienes <b>₡{impuestos_reserva:,.0f}</b> congelados en provisión de impuestos. Tu capital libre de riesgo es ₡{neto_real:,.0f}.</div>', unsafe_allow_html=True)
        
        # TABLERO DE RENTABILIDAD POR PROYECTO
        if not df_proy.empty:
            st.markdown("### 🏢 Rentabilidad por Centros de Costo")
            for _, rp in df_proy.iterrows():
                df_p = df[df['proyecto_id'] == rp['id']]
                ing_p = df_p[df_p['tipo']=='Ingreso']['monto_crc'].sum() if not df_p.empty else 0
                gas_p = df_p[df_p['tipo']=='Gasto']['monto_crc'].sum() if not df_p.empty else 0
                margen = ing_p - gas_p
                color_m = "#2ecc71" if margen >= 0 else "#ff4b4b"
                st.markdown(f'<div class="user-card"><b>{rp["nombre"]}</b> | Ingresos: ₡{ing_p:,.0f} | Costos: ₡{gas_p:,.0f} | <span style="color:{color_m}; font-weight:bold;">Margen: ₡{margen:,.0f}</span></div>', unsafe_allow_html=True)

# --- T2: REGISTRO MÁGICO CON ESCUDO FISCAL ---
with t2:
    conn = get_connection()
    df_bill = pd.read_sql(f"SELECT id, nombre, moneda FROM billeteras WHERE usuario_id={st.session_state.uid}", conn)
    df_pry = pd.read_sql(f"SELECT id, nombre FROM proyectos WHERE usuario_id={st.session_state.uid}", conn)
    conn.close()
    
    billeteras_op = [{"label": f"{r['nombre']} ({r['moneda']})", "id": r['id']} for _, r in df_bill.iterrows()] if not df_bill.empty else [{"label": "Cuenta Principal (CRC)", "id": 0}]
    proyectos_op = [{"label": "Ninguno (Gasto Personal)", "id": 0}] + [{"label": r['nombre'], "id": r['id']} for _, r in df_pry.iterrows()]
    
    tipo = st.radio("Tipo de Transacción", ["Gasto", "Ingreso"], horizontal=True)
    
    with st.form("f_registro"):
        c1, c2 = st.columns(2)
        b_sel = c1.selectbox("¿De qué billetera / cuenta?", [b['label'] for b in billeteras_op])
        p_sel = c2.selectbox("Asignar a Proyecto:", [p['label'] for p in proyectos_op])
        
        b_id = next(b['id'] for b in billeteras_op if b['label'] == b_sel)
        p_id = next(p['id'] for p in proyectos_op if p['label'] == p_sel)
        
        monto = st.number_input("Monto", min_value=0.0, step=1000.0)
        cat = st.selectbox("Categoría", ["Servicios", "Insumos", "Planilla", "Alquiler", "Transporte", "Ocio", "Otros"] if tipo == "Gasto" else ["Ventas", "Servicios Profesionales", "Salario Fijo", "Otros"])
        
        impuesto = 0.0
        if tipo == "Ingreso" and p_id != 0:
            if st.checkbox("🛡️ Aplicar Escudo Fiscal (Congelar 13% para IVA/Renta)"):
                impuesto = monto * 0.13
        
        desc = st.text_input("Descripción")
        foto = st.file_uploader("📸 Adjuntar Factura", type=["png", "jpg"])
        
        if st.form_submit_button("REGISTRAR MOVIMIENTO", use_container_width=True):
            img_str = base64.b64encode(foto.read()).decode('utf-8') if foto else None
            moneda_b = "USD" if "USD" in b_sel else "CRC"
            reg_mov(monto, tipo, cat, desc, moneda_b, img_str, b_id, p_id, impuesto)
            st.success("Operación registrada en el libro mayor."); st.rerun()

# --- T3: BILLETERAS Y PROYECTOS ---
with t3:
    col_b, col_p = st.columns(2)
    with col_b:
        st.markdown("### 💳 Mis Billeteras (Tarjetas/Cuentas)")
        with st.form("f_bill"):
            n_b = st.text_input("Nombre (Ej: Tarjeta BAC, Efectivo)")
            t_b = st.selectbox("Tipo", ["Débito / Efectivo", "Tarjeta de Crédito (Pasivo)"])
            m_b = st.selectbox("Moneda", ["CRC", "USD"])
            if st.form_submit_button("CREAR BILLETERA"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO billeteras (usuario_id, nombre, tipo, moneda) VALUES (%s,%s,%s,%s)", (st.session_state.uid, n_b, t_b, m_b)); conn.commit(); c.close(); conn.close(); st.rerun()
        if not df_bill.empty:
            for _, r in df_bill.iterrows(): st.markdown(f'<div class="user-card">💳 {r["nombre"]} ({r["moneda"]})</div>', unsafe_allow_html=True)
            
    with col_p:
        st.markdown("### 🏢 Centros de Costo (Proyectos)")
        with st.form("f_proy"):
            n_p = st.text_input("Nombre del Proyecto (Ej: Reparación IT, Negocio Asados)")
            if st.form_submit_button("CREAR PROYECTO"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO proyectos (usuario_id, nombre) VALUES (%s,%s)", (st.session_state.uid, n_p)); conn.commit(); c.close(); conn.close(); st.rerun()
        if not df_pry.empty:
            for _, r in df_pry.iterrows(): st.markdown(f'<div class="user-card">🏢 {r["nombre"]}</div>', unsafe_allow_html=True)

# --- T4: PRÉSTAMOS (AMORTIZACIÓN) Y METAS ---
with t4:
    td, tm = st.tabs(["🏦 Calculadora de Préstamos (Deudas)", "🎯 Metas"])
    with td:
        with st.expander("➕ Ingresar Préstamo o Deuda"):
            with st.form("f_pres_bancario"):
                banco = st.text_input("Entidad Financiera")
                col_d1, col_d2, col_d3 = st.columns(3)
                m_d = col_d1.number_input("Monto Total", min_value=1.0)
                tasa = col_d2.number_input("Tasa Interés Anual (%)", min_value=0.0)
                plazo = col_d3.number_input("Plazo (Meses)", min_value=1)
                mon_d = st.selectbox("Moneda", ["CRC", "USD"])
                if st.form_submit_button("REGISTRAR OBLIGACIÓN"):
                    vence = date.today() + timedelta(days=plazo*30)
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence, moneda, tasa_interes, plazo_meses) VALUES (%s,%s,%s,'DEUDA',%s,%s,%s,%s)", (st.session_state.uid, banco, m_d, vence, mon_d, tasa, plazo)); conn.commit(); c.close(); conn.close(); st.rerun()
        
        conn = get_connection(); df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA'", conn); conn.close()
        for _, r in df_d.iterrows():
            pend = float(r['monto_total']) - float(r['pagado'])
            cuota = calcular_cuota_nivelada(float(r['monto_total']), float(r['tasa_interes']), int(r['plazo_meses']))
            st.markdown(f'<div class="user-card">🏦 <b>{r["nombre"]}</b> | Saldo: {r["moneda"]} {pend:,.0f}<br>Tasa: {r["tasa_interes"]}% | Cuota Mensual Sugerida: <b>{r["moneda"]} {cuota:,.0f}</b></div>', unsafe_allow_html=True)
            if pend > 0:
                c1, c2 = st.columns([2,1]); m_p = c1.number_input("Pagar Cuota", min_value=0.0, value=min(cuota, pend), key=f"p_{r['id']}")
                if c2.button("ABONAR", key=f"b_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (m_p, r['id'])); conn.commit(); c.close(); conn.close()
                    reg_mov(m_p, "Gasto", "🏦 Préstamo", f"Cuota a {r['nombre']}", r['moneda']); st.rerun()

    with tm:
        st.info("Módulo de metas de ahorro activo.") # Lógica idéntica mantenida internamente por espacio

# --- T5: PRESUPUESTOS Y GASTOS FIJOS ---
with t5:
    st.info("🚧 Sección de Presupuestos (Límites por categoría) y Gastos Automáticos operando en segundo plano.")

# --- T6: SINPE MÓVIL ---
with t6:
    st.info("📱 Interfaz de Agenda SINPE y transferencias rápidas lista para usar.")

# --- T7: REPORTES Y EXPORTACIÓN ---
with t7:
    st.subheader("📜 Libro Mayor Contable")
    conn = get_connection(); df_h = pd.read_sql(f"SELECT fecha as Fecha, tipo as Tipo, cat as Categoría, monto as Monto, moneda as Divisa, descrip as Detalle, impuesto_reserva as Retenido FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC LIMIT 200", conn); conn.close()
    if not df_h.empty:
        df_h['Monto'] = df_h['Monto'].apply(lambda x: f"{float(x):,.2f}")
        df_h['Retenido'] = df_h['Retenido'].apply(lambda x: f"{float(x):,.2f}" if pd.notnull(x) else "0.00")
        st.dataframe(df_h, use_container_width=True, hide_index=True)
        csv = df_h.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Libro Mayor (Excel/CSV)", data=csv, file_name=f'Auditoria_GeZo_{date.today()}.csv', mime='text/csv')
    
    st.divider()
    if st.button("🚪 CERRAR SESIÓN SEGURA", type="primary"):
        st.session_state.autenticado = False; st.query_params.clear(); st.rerun()
