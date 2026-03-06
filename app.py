import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import re
import base64

# ==========================================
# 1. CONFIGURACIÓN ELITE Y UI NATIVA (CTO)
# ==========================================
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Bloqueo total de Streamlit UI para Look Nativo */
    header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer, .stDeployButton {display: none !important;}
    .block-container {padding-top: 1.5rem !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    
    /* Componentes Visuales Elite */
    .balance-card { background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%); border-radius: 12px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.85em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    .bac-card { background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%); border-radius: 10px; padding: 10px; text-align: center; border: 1px solid #ff4b4b; color: white; font-weight: bold; }
    
    /* Cajas de Asesoría Financiera IA */
    .ia-box-verde { background: rgba(46, 204, 113, 0.05); border: 1px solid #2ecc71; padding: 20px; border-radius: 12px; border-left: 5px solid #2ecc71; margin-top: 10px; margin-bottom: 15px; }
    .ia-box-roja { background: rgba(255, 75, 75, 0.05); border: 1px solid #ff4b4b; padding: 20px; border-radius: 12px; border-left: 5px solid #ff4b4b; margin-top: 10px; margin-bottom: 15px; }
    .ia-box-azul { background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; padding: 20px; border-radius: 12px; border-left: 5px solid #00f2fe; margin-top: 10px; margin-bottom: 15px; }
    
    /* Utilidades */
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 10px; border: 1px solid #222; border-left: 4px solid #00f2fe; margin-bottom: 10px; }
    .alert-box { background: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; padding: 15px; border-radius: 10px; color: #ff4b4b; font-weight: bold; margin-bottom: 15px; }
    .btn-banco { background-color: #00f2fe; color: #000 !important; padding: 15px; border-radius: 8px; text-decoration: none; font-weight: 900; text-align: center; display: block; margin-top: 10px; transition: 0.3s; }
    .btn-banco:hover { background-color: #00c3cc; color: black !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE BASE DE DATOS Y ARQUITECTURA
# ==========================================
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"])
    except Exception:
        st.error("Conectando con Servidor Financiero Seguro...")
        return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Tablas Maestras
    tablas = [
        "usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT)",
        "movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)",
        "metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)",
        "deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo_registro TEXT, fecha_vence DATE)",
        "contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)",
        "presupuestos (id SERIAL PRIMARY KEY, usuario_id INTEGER, cat TEXT, limite DECIMAL)",
        "suscripciones (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto DECIMAL, dia_cobro INTEGER, cat TEXT, moneda TEXT)",
        "historial_suscripciones (id SERIAL PRIMARY KEY, suscripcion_id INTEGER, mes_anio TEXT)",
        "billeteras (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, tipo TEXT, moneda TEXT)",
        "proyectos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT)"
    ]
    for t in tablas:
        c.execute(f"CREATE TABLE IF NOT EXISTS {t}")
    
    # Inyección de columnas seguras (Backward Compatibility)
    cols_mov = [
        "moneda TEXT DEFAULT 'CRC'", 
        "comprobante TEXT DEFAULT NULL", 
        "billetera_id INTEGER DEFAULT 0", 
        "proyecto_id INTEGER DEFAULT 0", 
        "impuesto_reserva DECIMAL DEFAULT 0"
    ]
    for col in cols_mov:
        c.execute(f"ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS {col}")
        
    cols_deu = [
        "moneda TEXT DEFAULT 'CRC'", 
        "tasa_interes DECIMAL DEFAULT 0", 
        "plazo_meses INTEGER DEFAULT 1"
    ]
    for col in cols_deu:
        c.execute(f"ALTER TABLE deudas ADD COLUMN IF NOT EXISTS {col}")
        
    c.execute("ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS periodo TEXT DEFAULT 'Mensual'")
    
    # Usuario Administrador Default
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño SaaS')")
    
    conn.commit()
    c.close()
    conn.close()

inicializar_db()

# ==========================================
# CONSTANTES FINANCIERAS Y DE NEGOCIO (CFO)
# ==========================================
TIPO_CAMBIO_COMPRA = 512.00
TIPO_CAMBIO_VENTA = 524.00

PLANES = ["🎁 Prueba Gratis (1 Mes) - ₡0", "🥉 Mensual - ₡2,500", "🥈 Trimestral - ₡6,500", "🥇 Semestral - ₡12,000", "💎 Anual - ₡20,000", "👑 Vitalicio - ₡50,000"]
DIAS_PLAN = {PLANES[0]: 30, PLANES[1]: 30, PLANES[2]: 90, PLANES[3]: 180, PLANES[4]: 365, PLANES[5]: 27000}

# Categorías contables (Incluye cuentas puente para no afectar P&L)
CAT_GASTOS = [
    "Alimentación / Supermercado", "Comida Fuera / Restaurantes", 
    "Transporte / Gasolina / Uber", "Casa / Alquiler / Hipoteca", 
    "Servicios (Luz, Agua, Internet)", "Pensión Alimenticia", 
    "Salud / Farmacia / Médicos", "Educación / Cuotas", 
    "Ocio / Entretenimiento", "Ropa / Cuidado Personal", 
    "Mascotas", "Insumos de Negocio", "Préstamos / Tarjetas", 
    "Transferencia entre cuentas", "Otros Gastos"
]

CAT_INGRESOS = [
    "Ajuste / Saldo Inicial", "Sueldo / Salario", 
    "Aguinaldo / Bonos", "Ventas de Negocio", 
    "Servicios Profesionales", "Pensión Recibida", 
    "Premios / Rifas", "Rendimientos / Intereses", 
    "Regalos / Donaciones", "Transferencia entre cuentas", "Otros Ingresos"
]

# ==========================================
# FUNCIONES FINANCIERAS CORE
# ==========================================
def calcular_cuota_nivelada(monto, tasa_anual, meses):
    if tasa_anual == 0 or meses == 0:
        return monto / max(1, meses)
    tasa_mensual = (tasa_anual / 100) / 12
    return monto * (tasa_mensual * (1 + tasa_mensual)**meses) / ((1 + tasa_mensual)**meses - 1)

def reg_mov(monto, tipo, cat, desc, moneda="CRC", comprobante=None, b_id=0, p_id=0, imp=0):
    if monto > 0:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""INSERT INTO movimientos 
                     (usuario_id, fecha, descrip, monto, tipo, cat, moneda, comprobante, billetera_id, proyecto_id, impuesto_reserva) 
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat, moneda, comprobante, b_id, p_id, imp))
        conn.commit()
        c.close()
        conn.close()

def procesar_suscripciones():
    hoy = date.today()
    mes_actual = hoy.strftime("%Y-%m")
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, nombre, monto, dia_cobro, cat, moneda FROM suscripciones WHERE usuario_id=%s", (st.session_state.uid,))
    suscripciones = c.fetchall()
    
    for sub in suscripciones:
        sub_id, nombre, monto, dia_cobro, cat, moneda = sub
        # Algoritmo de Fechas para evitar errores en Febrero o meses de 30 días
        ultimo_dia_mes = ((hoy.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
        dia_efectivo = min(dia_cobro, ultimo_dia_mes)
        
        if hoy.day >= dia_efectivo:
            c.execute("SELECT id FROM historial_suscripciones WHERE suscripcion_id=%s AND mes_anio=%s", (sub_id, mes_actual))
            if not c.fetchone():
                c.execute("""INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, moneda, billetera_id) 
                             VALUES (%s,%s,%s,%s,%s,%s,%s,0)""", 
                          (st.session_state.uid, hoy, f"Auto-Cobro: {nombre}", monto, "Gasto", cat, moneda))
                c.execute("INSERT INTO historial_suscripciones (suscripcion_id, mes_anio) VALUES (%s,%s)", (sub_id, mes_actual))
    
    conn.commit()
    c.close()
    conn.close()

# ==========================================
# 3. SEGURIDAD, LOGIN Y SHADOW STATE
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    if "session_token" in st.query_params:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE id=%s", (st.query_params["session_token"],))
        res = c.fetchone()
        c.close()
        conn.close()
        
        if res and date.today() <= res[4]:
            st.session_state.update({"autenticado": True, "uid": res[0], "uname": res[1], "rol": res[2], "plan": res[3]})
            st.query_params.clear()
            st.rerun()

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #00f2fe; margin-top: 10vh;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login_form"):
            st.markdown("### Acceso al Sistema")
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            mantener = st.checkbox("Mantener mi sesión iniciada", value=True)
            
            if st.form_submit_button("INICIAR SESIÓN", use_container_width=True):
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone()
                c.close()
                conn.close()
                
                if res:
                    if date.today() <= res[4]:
                        st.session_state.update({"autenticado": True, "uid": res[0], "uname": res[1], "rol": res[2], "plan": res[3]})
                        if mantener:
                            st.query_params["session_token"] = str(res[0])
                        st.rerun()
                    else:
                        st.error("Membresía expirada. Contacta al administrador para renovar tu plan.")
                else:
                    st.error("Credenciales incorrectas.")
    st.stop()

# Ejecutar motor fantasma de suscripciones al iniciar sesión
procesar_suscripciones()

# ==========================================
# 4. NAVEGACIÓN Y PANEL ADMIN (SaaS)
# ==========================================
st.markdown(f"### 👑 **{st.session_state.uname}** | Plan: {st.session_state.plan}")

lista_tabs = ["📊 DASHBOARD", "💸 REGISTRO", "💼 BILLETERAS Y NEGOCIOS", "🚧 FIJOS Y PRESUPUESTOS", "🎯 METAS", "🏦 DEUDAS Y COBROS", "📱 SINPE", "📜 HISTORIAL"]

if st.session_state.rol == "admin":
    lista_tabs.insert(0, "🏢 PANEL ADMIN SAAS")
    tabs = st.tabs(lista_tabs)
    t_admin = tabs[0]
    t1, t2, t3, t4, t5, t6, t7, t8 = tabs[1:]
    
    with t_admin:
        st.markdown("### 💼 Gestión Comercial de Clientes")
        
        with st.expander("➕ Vender Licencia a Nuevo Cliente"):
            with st.form("f_nuevo_usuario"):
                cu1, cu2 = st.columns(2)
                n_user = cu1.text_input("Nombre de Usuario (Login)")
                n_pass = cu2.text_input("Contraseña Asignada")
                plan_sel = st.selectbox("Seleccionar Plan Comercial:", PLANES)
                
                if st.form_submit_button("CREAR CLIENTE Y ACTIVAR", use_container_width=True):
                    if n_user and n_pass:
                        f_vence = date.today() + timedelta(days=DIAS_PLAN[plan_sel])
                        try:
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (%s, %s, %s, 'user', %s)", 
                                      (n_user, n_pass, f_vence, plan_sel.split(" - ")[0]))
                            conn.commit()
                            c.close()
                            conn.close()
                            st.success(f"Cliente '{n_user}' creado exitosamente. Su acceso expira el {f_vence}.")
                            st.rerun()
                        except:
                            st.error("El nombre de usuario ya existe en la base de datos.")
                    else:
                        st.error("Por favor, completa usuario y contraseña.")
        
        st.markdown("### 👥 Cartera de Clientes Activos e Inactivos")
        conn = get_connection()
        df_cli = pd.read_sql("SELECT id, nombre, plan, expira FROM usuarios WHERE rol != 'admin' ORDER BY expira ASC", conn)
        conn.close()
        
        if not df_cli.empty:
            for _, ru in df_cli.iterrows():
                activo = ru['expira'] >= date.today()
                borde = "#2ecc71" if activo else "#ff4b4b"
                estado = "🟢 Activo" if activo else "🔴 Bloqueado (Falta de Pago)"
                
                st.markdown(f'<div class="user-card" style="border-left: 5px solid {borde};"><b>{ru["nombre"]}</b> | Plan actual: {ru["plan"]} | Fecha de corte: {ru["expira"]} | {estado}</div>', unsafe_allow_html=True)
                
                cr1, cr2, cr3 = st.columns([2, 1, 1])
                ren_plan = cr1.selectbox("Opciones de Renovación:", PLANES, key=f"rp_{ru['id']}")
                
                if cr2.button("RENOVAR ACCESO", key=f"rbtn_{ru['id']}", use_container_width=True):
                    nueva_f = date.today() + timedelta(days=DIAS_PLAN[ren_plan])
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("UPDATE usuarios SET expira=%s, plan=%s WHERE id=%s", (nueva_f, ren_plan.split(" - ")[0], ru['id']))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.success("Licencia renovada con éxito.")
                    st.rerun()
                    
                if cr3.button("🗑️ Eliminar", key=f"dbtn_{ru['id']}", use_container_width=True):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM usuarios WHERE id=%s", (ru['id'],))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.rerun()
        else:
            st.info("Aún no tienes clientes registrados en tu plataforma.")

else:
    tabs = st.tabs(lista_tabs)
    t1, t2, t3, t4, t5, t6, t7, t8 = tabs

# ==========================================
# 5. MÓDULOS FINANCIEROS (100% COMPLETOS)
# ==========================================

# --- ALERTAS GLOBALES DE VENCIMIENTO ---
conn = get_connection()
df_alertas = pd.read_sql("SELECT nombre, fecha_vence, monto_total, pagado, moneda FROM deudas WHERE usuario_id=%s AND tipo_registro='DEUDA' AND pagado < monto_total", conn, params=(st.session_state.uid,))
conn.close()
if not df_alertas.empty:
    for _, r in df_alertas.iterrows():
        dias_restantes = (r['fecha_vence'] - date.today()).days
        if 0 <= dias_restantes <= 2:
            st.markdown(f'<div class="alert-box">⚠️ ALERTA DE PAGO: Tu obligación con **{r["nombre"]}** vence en {dias_restantes} días.</div>', unsafe_allow_html=True)
        elif dias_restantes < 0:
            st.markdown(f'<div class="alert-box" style="background: rgba(200,0,0,0.2);">🚨 DEUDA VENCIDA: Tienes un atraso de {abs(dias_restantes)} días con **{r["nombre"]}**.</div>', unsafe_allow_html=True)

# --- TAB 1: DASHBOARD, RENTABILIDAD, IA Y CONCILIACIÓN ---
with t1:
    cb1, cb2, cb3 = st.columns([1,1,2])
    cb1.markdown(f'<div class="bac-card"><small>BAC COMPRA (USD)</small><br>₡{TIPO_CAMBIO_COMPRA}</div>', unsafe_allow_html=True)
    cb2.markdown(f'<div class="bac-card"><small>BAC VENTA (USD)</small><br>₡{TIPO_CAMBIO_VENTA}</div>', unsafe_allow_html=True)
    
    st.divider()
    rango = st.radio("Analizar datos de:", ["Este Mes", "Toda mi historia"], horizontal=True)
    f_inicio = date.today().replace(day=1) if rango == "Este Mes" else date.today() - timedelta(days=9999)
    
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM movimientos WHERE usuario_id=%s AND fecha >= %s", conn, params=(st.session_state.uid, f_inicio))
    df_hist_completo = pd.read_sql("SELECT billetera_id, tipo, monto, moneda, fecha, cat FROM movimientos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    df_proy = pd.read_sql("SELECT * FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    df_pres = pd.read_sql("SELECT * FROM presupuestos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    df_bill = pd.read_sql("SELECT id, nombre, tipo, moneda FROM billeteras WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    conn.close()
    
    if not df.empty:
        def convertir_a_colones(fila):
            valor = float(fila['monto'])
            if fila['moneda'] == 'USD':
                return valor * TIPO_CAMBIO_COMPRA if fila['tipo'] == 'Ingreso' else valor * TIPO_CAMBIO_VENTA
            return valor
            
        df['monto_crc'] = df.apply(convertir_a_colones, axis=1)
        df['impuesto_reserva'] = df['impuesto_reserva'].fillna(0)
        
        impuestos_totales = df['impuesto_reserva'].sum()
        
        # Filtro CFO Contable: Ignorar Saldos Iniciales y Transferencias del cálculo de Ganancias/Pérdidas del mes
        df_pl = df[~df['cat'].isin(["Ajuste / Saldo Inicial", "Transferencia entre cuentas"])]
        ingresos_brutos = df_pl[df_pl['tipo'] == 'Ingreso']['monto_crc'].sum()
        gastos_totales = df_pl[df_pl['tipo'] == 'Gasto']['monto_crc'].sum()
        capital_real_neto = (ingresos_brutos - gastos_totales) - impuestos_totales
        
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="balance-card"><p class="metric-label">Dinero Entrante (CRC)</p><p class="metric-value">₡{ingresos_brutos:,.0f}</p></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="balance-card"><p class="metric-label">Dinero Saliente (CRC)</p><p class="metric-value" style="color:#ff4b4b;">₡{gastos_totales:,.0f}</p></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="balance-card"><p class="metric-label">Me sobra (Ganancia)</p><p class="metric-value" style="color:#2ecc71;">₡{capital_real_neto:,.0f}</p></div>', unsafe_allow_html=True)
        
        # 🧠 GEZO AI ASESOR FINANCIERO AVANZADO
        if capital_real_neto < 0:
            gastos_cat = df_pl[df_pl['tipo'] == 'Gasto'].groupby('cat')['monto_crc'].sum().sort_values(ascending=False)
            fuga_principal = gastos_cat.index[0] if not gastos_cat.empty else "Varios"
            
            st.markdown(f'''<div class="ia-box-roja">🤖 <b>GeZo AI (Alerta de Déficit):</b> 
            Estás gastando más de lo que ganas. Tienes un déficit de <b>₡{abs(capital_real_neto):,.0f}</b>. 
            <br>🔍 <b>Análisis:</b> Tu mayor fuga de dinero está en la categoría: <b>{fuga_principal}</b>. 
            <br>💡 <b>Consejo:</b> Frena inmediatamente las compras no esenciales y no adquieras deudas nuevas este mes.</div>''', unsafe_allow_html=True)
        elif capital_real_neto > 0:
            st.markdown(f'''<div class="ia-box-verde">🤖 <b>GeZo AI (Análisis Positivo):</b> 
            ¡Excelente manejo financiero! Tienes un superávit de <b>₡{capital_real_neto:,.0f}</b> libres. 
            <br>💡 <b>Opciones para multiplicar tu dinero:</b> 
            <br>1️⃣ Abre un Certificado a Plazo (CDP) en tu banco con ₡{capital_real_neto * 0.4:,.0f}.
            <br>2️⃣ Abona dinero extra a la deuda que te cobre la tasa de interés más alta.
            <br>3️⃣ Inyecta capital a uno de tus negocios para generar más ventas.</div>''', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ia-box-azul">🤖 <b>GeZo AI:</b> Estás en punto de equilibrio exacto. Tus ingresos cubren tus gastos sin sobrantes.</div>', unsafe_allow_html=True)
            
        if impuestos_totales > 0:
            st.markdown(f'<div class="ia-box-azul">🛡️ Tienes <b>₡{impuestos_totales:,.0f}</b> apartados sanamente gracias a tu Escudo Fiscal. Este dinero ya se restó de tu capital libre para protegerte.</div>', unsafe_allow_html=True)

        # CONCILIACIÓN BANCARIA (SALDOS FÍSICOS REALES)
        st.markdown("### 🏦 ¿Dónde está mi dinero físico? (Saldos Reales)")
        lista_ctas = [{"id": 0, "nombre": "💵 Mi Efectivo Personal", "moneda": "CRC", "tipo": "Efectivo"}]
        for _, r in df_bill.iterrows():
            icono = "💳" if "Tarjeta" in r['tipo'] else "🏦"
            lista_ctas.append({"id": r["id"], "nombre": f"{icono} {r['nombre']}", "moneda": r["moneda"], "tipo": r["tipo"]})
            
        if not df_hist_completo.empty:
            cols_cta = st.columns(3)
            for i, cta in enumerate(lista_ctas):
                df_c = df_hist_completo[df_hist_completo['billetera_id'] == cta['id']]
                saldo_c = 0
                if not df_c.empty:
                    for _, m in df_c.iterrows():
                        valor = float(m['monto'])
                        if m['moneda'] == 'USD' and cta['moneda'] == 'CRC':
                            valor = valor * TIPO_CAMBIO_COMPRA if m['tipo'] == 'Ingreso' else valor * TIPO_CAMBIO_VENTA
                        elif m['moneda'] == 'CRC' and cta['moneda'] == 'USD':
                            valor = valor / TIPO_CAMBIO_VENTA if m['tipo'] == 'Ingreso' else valor / TIPO_CAMBIO_COMPRA
                        
                        if m['tipo'] == 'Ingreso':
                            saldo_c += valor
                        else:
                            saldo_c -= valor
                
                color_s = "#2ecc71" if saldo_c >= 0 else "#ff4b4b"
                with cols_cta[i % 3]:
                    st.markdown(f'<div class="user-card" style="text-align:center;"><b>{cta["nombre"]}</b><br><span style="font-size:1.5em; color:{color_s}; font-weight:bold;">{cta["moneda"]} {saldo_c:,.2f}</span></div>', unsafe_allow_html=True)
        
        # SEMÁFORO DE PRESUPUESTOS FLEXIBLES
        if not df_pres.empty:
            st.markdown("### 🚧 Semáforo de Presupuestos")
            df_hist_completo['monto_crc'] = df_hist_completo.apply(lambda f: float(f['monto']) * TIPO_CAMBIO_VENTA if f['moneda']=='USD' else float(f['monto']), axis=1)
            hoy = date.today()
            
            for _, rp in df_pres.iterrows():
                if rp['periodo'] == 'Semanal':
                    inicio_p = hoy - timedelta(days=hoy.weekday())
                elif rp['periodo'] == 'Quincenal':
                    inicio_p = hoy.replace(day=1) if hoy.day <= 15 else hoy.replace(day=16)
                else: 
                    inicio_p = hoy.replace(day=1)
                
                df_periodo = df_hist_completo[(df_hist_completo['tipo'] == 'Gasto') & (df_hist_completo['cat'] == rp['cat']) & (pd.to_datetime(df_hist_completo['fecha']).dt.date >= inicio_p)]
                gastado = df_periodo['monto_crc'].sum() if not df_periodo.empty else 0
                limite = float(rp['limite'])
                pct = min(gastado / limite, 1.0) if limite > 0 else 1.0
                
                st.write(f"**{rp['cat']} ({rp['periodo']})** | Consumido: ₡{gastado:,.0f} de ₡{limite:,.0f}")
                st.progress(pct)
                if pct >= 0.9:
                    st.error(f"⚠️ Cuidado: Estás a punto de romper tu límite de {rp['cat']} en este periodo.")

        # RENTABILIDAD DE NEGOCIOS
        if not df_proy.empty:
            st.markdown("### 🏢 Mis Negocios (Rentabilidad)")
            for _, rp in df_proy.iterrows():
                df_p = df[df['proyecto_id'] == rp['id']]
                # Excluir saldo inicial para ver margen real de operación
                df_p_real = df_p[df_p['cat'] != "Ajuste / Saldo Inicial"]
                
                i_p = df_p_real[df_p_real['tipo'] == 'Ingreso']['monto_crc'].sum() if not df_p_real.empty else 0
                g_p = df_p_real[df_p_real['tipo'] == 'Gasto']['monto_crc'].sum() if not df_p_real.empty else 0
                margen = i_p - g_p
                color_m = "#2ecc71" if margen >= 0 else "#ff4b4b"
                
                st.markdown(f'<div class="user-card"><b>{rp["nombre"]}</b> | Entró: ₡{i_p:,.0f} | Salió: ₡{g_p:,.0f} | <span style="color:{color_m};">Ganancia Operativa: ₡{margen:,.0f}</span></div>', unsafe_allow_html=True)
    else:
        st.info("Aún no tienes movimientos. Ve a la pestaña de 'Registro' para empezar (puedes agregar un Saldo Inicial).")

# --- TAB 2: REGISTRO UX SIMPLIFICADO ---
with t2:
    tab_manual, tab_magico = st.tabs(["✍️ Anotar Movimiento Manual", "🪄 Leer Mensaje del Banco (SMS)"])
    
    with tab_manual:
        conn = get_connection()
        df_bill = pd.read_sql("SELECT id, nombre, moneda FROM billeteras WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        df_pry = pd.read_sql("SELECT id, nombre FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        conn.close()
        
        b_opciones = [{"label": f"💵 Mi Efectivo Personal ({r['moneda']})" if r['id']==0 else f"💳 {r['nombre']} ({r['moneda']})", "id": r['id']} for _, r in df_bill.iterrows()] if not df_bill.empty else [{"label": "💵 Mi Efectivo Personal (CRC)", "id": 0}]
        p_opciones = [{"label": "👤 Para mi uso personal", "id": 0}] + [{"label": f"🏢 Para mi negocio: {r['nombre']}", "id": r['id']} for _, r in df_pry.iterrows()]
        
        tipo_mov = st.radio("¿Qué pasó con el dinero?", ["Salió de mi cuenta (Gasto)", "Entró a mi cuenta (Ingreso)"], horizontal=True)
        tipo_db = "Gasto" if "Salió" in tipo_mov else "Ingreso"
        categorias_finales = CAT_GASTOS if tipo_db == "Gasto" else CAT_INGRESOS
        
        with st.form("f_registro_sencillo"):
            c_origen = st.selectbox("¿De dónde sale o a dónde entra el dinero?", [x['label'] for x in b_opciones])
            c_proy = st.selectbox("¿A qué corresponde este movimiento?", [x['label'] for x in p_opciones])
            
            b_id = next(b['id'] for b in b_opciones if b['label'] == c_origen)
            p_id = next(p['id'] for p in p_opciones if p['label'] == c_proy)
            
            monto_r = st.number_input("Monto del movimiento", min_value=0.0, step=1000.0)
            cat_r = st.selectbox("¿En qué categoría encaja mejor?", categorias_finales)
            
            imp_r = 0.0
            if tipo_db == "Ingreso" and p_id != 0 and cat_r != "Ajuste / Saldo Inicial" and cat_r != "Transferencia entre cuentas":
                if st.checkbox("🛡️ Soy responsable: Apartar el 13% para pagar impuestos después."):
                    imp_r = monto_r * 0.13
                    
            desc_r = st.text_input("Añadir una pequeña nota o detalle (Opcional)")
            
            st.markdown("📄 **Guardar el Recibo/Factura como evidencia**")
            modo_foto = st.radio("¿Cómo quieres subir el recibo?", ["Buscar en la galería", "Tomar foto con la cámara"], horizontal=True)
            foto_final = None
            
            if modo_foto == "Buscar en la galería":
                foto_final = st.file_uploader("Selecciona la imagen", type=["jpg", "png", "jpeg"])
            else:
                foto_final = st.camera_input("Enfoca la factura y toma la foto")
            
            if st.form_submit_button("GUARDAR MOVIMIENTO", use_container_width=True):
                moneda_transaccion = "USD" if "USD" in c_origen else "CRC"
                imagen_codificada = base64.b64encode(foto_final.read()).decode('utf-8') if foto_final else None
                
                reg_mov(monto_r, tipo_db, cat_r, desc_r, moneda_transaccion, imagen_codificada, b_id, p_id, imp_r)
                st.success("✅ ¡Anotado correctamente en tu contabilidad!")
                st.rerun()

    with tab_magico:
        st.markdown("Copia el texto del mensaje que te envía el banco por compras y pégalo aquí.")
        txt_sms = st.text_area("Ejemplo: 'BAC Credomatic: Compra aprobada por ₡15,000 en WALMART'")
        
        if st.button("🪄 Extraer Gasto de forma automática", use_container_width=True):
            if txt_sms:
                mt = re.search(r'[\$₡]?\s?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', txt_sms)
                if mt:
                    ml = float(mt.group(1).replace(',', ''))
                    md = "USD" if "USD" in txt_sms.upper() else "CRC"
                    
                    cat_sug = "Otros Gastos"
                    texto_upper = txt_sms.upper()
                    if any(w in texto_upper for w in ["WALMART", "MASXMENOS", "AUTO MERCADO", "PALI"]):
                        cat_sug = "Alimentación / Supermercado"
                    elif any(w in texto_upper for w in ["UBER", "DIDDI", "GAS", "DELTA", "PUMA"]):
                        cat_sug = "Transporte / Gasolina / Uber"
                    elif any(w in texto_upper for w in ["KFC", "MCDONALDS", "STARBUCKS", "RESTAURANTE"]):
                        cat_sug = "Comida Fuera / Restaurantes"
                    elif any(w in texto_upper for w in ["FARMACIA", "FISCHEL", "SUCRE"]):
                        cat_sug = "Salud / Farmacia / Médicos"
                    
                    st.success(f"¡Detectamos un gasto de **{md} {ml:,.2f}**! (Sugerencia: {cat_sug})")
                    
                    if st.button(f"Confirmar y Guardar en Libro Mayor"):
                        reg_mov(ml, "Gasto", cat_sug, txt_sms[:40], md)
                        st.success("Gasto automatizado registrado.")
                        st.rerun()
                else:
                    st.error("No encontramos ningún monto numérico en el texto.")

# --- TAB 3: BILLETERAS Y NEGOCIOS ---
with t3:
    col_billetera, col_proyecto = st.columns(2)
    
    with col_billetera:
        st.markdown("### 💳 Mis Cuentas / Tarjetas")
        with st.form("form_nueva_billetera"):
            n_bill = st.text_input("Nombre de la Tarjeta o Cuenta Bancaria")
            t_bill = st.selectbox("Tipo de Dinero", ["Dinero Propio (Débito/Ahorros)", "Dinero Prestado (Tarjeta de Crédito)"])
            m_bill = st.selectbox("Moneda Principal", ["CRC", "USD"])
            if st.form_submit_button("AGREGAR CUENTA", use_container_width=True):
                if n_bill:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO billeteras (usuario_id, nombre, tipo, moneda) VALUES (%s,%s,%s,%s)", 
                              (st.session_state.uid, n_bill, t_bill, m_bill))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.rerun()
        
        conn = get_connection()
        df_billeteras_lista = pd.read_sql("SELECT * FROM billeteras WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        conn.close()
        
        for _, r in df_billeteras_lista.iterrows():
            st.markdown(f'<div class="user-card">💳 <b>{r["nombre"]}</b> | {r["tipo"]} | Moneda: {r["moneda"]}</div>', unsafe_allow_html=True)
            
    with col_proyecto:
        st.markdown("### 🏢 Mis Emprendimientos")
        with st.form("form_nuevo_proyecto"):
            n_proy = st.text_input("Nombre del Negocio o Actividad Extra")
            if st.form_submit_button("CREAR NEGOCIO", use_container_width=True):
                if n_proy:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO proyectos (usuario_id, nombre) VALUES (%s,%s)", (st.session_state.uid, n_proy))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.rerun()
                
        conn = get_connection()
        df_proyectos_lista = pd.read_sql("SELECT * FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        conn.close()
        
        for _, r in df_proyectos_lista.iterrows():
            st.markdown(f'<div class="user-card">🏢 <b>{r["nombre"]}</b></div>', unsafe_allow_html=True)

# --- TAB 4: FIJOS Y PRESUPUESTOS ---
with t4:
    tab_limites, tab_suscripciones = st.tabs(["🚧 Mis Límites de Gasto", "🔁 Pagos que se cobran solos"])
    
    with tab_limites:
        st.write("Dile a la app cuánto quieres gastar máximo y ella vigilará que no te pases.")
        with st.form("form_nuevo_presupuesto"):
            cat_presupuesto = st.selectbox("¿A qué quieres ponerle un freno?", CAT_GASTOS)
            limite_presupuesto = st.number_input("Monto máximo a gastar", min_value=1.0)
            periodo_presupuesto = st.selectbox("¿Cada cuánto se reinicia este límite?", ["Semanal", "Quincenal", "Mensual"])
            
            if st.form_submit_button("ACTIVAR LÍMITE"):
                conn = get_connection()
                cr = conn.cursor()
                cr.execute("DELETE FROM presupuestos WHERE usuario_id=%s AND cat=%s", (st.session_state.uid, cat_presupuesto))
                cr.execute("INSERT INTO presupuestos (usuario_id, cat, limite, periodo) VALUES (%s,%s,%s,%s)", 
                           (st.session_state.uid, cat_presupuesto, limite_presupuesto, periodo_presupuesto))
                conn.commit()
                cr.close()
                conn.close()
                st.rerun()
                
        conn = get_connection()
        df_presupuestos_lista = pd.read_sql("SELECT * FROM presupuestos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        conn.close()
        
        for _, r in df_presupuestos_lista.iterrows():
            st.markdown(f'<div class="user-card">🚧 <b>{r["cat"]}</b> | Límite {r["periodo"]}: ₡{float(r["limite"]):,.0f}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Quitar Límite", key=f"del_pres_{r['id']}"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("DELETE FROM presupuestos WHERE id=%s", (r['id'],))
                conn.commit()
                c.close()
                conn.close()
                st.rerun()

    with tab_suscripciones:
        st.write("Registra tus pagos automáticos. El sistema los debitará de tu Efectivo el día correspondiente sin que hagas nada.")
        with st.form("form_nueva_suscripcion"):
            n_sub = st.text_input("Nombre de la obligación (Ej: Pensión, Netflix, Préstamo)")
            col_sub1, col_sub2 = st.columns(2)
            mon_sub = col_sub1.selectbox("Moneda del Cobro", ["CRC", "USD"])
            monto_sub = col_sub2.number_input("Monto exacto a pagar", min_value=1.0)
            
            dia_sub = st.number_input("Día de cobro en el mes (1 al 31)", min_value=1, max_value=31)
            cat_sub = st.selectbox("Clasificación Contable", CAT_GASTOS)
            
            if st.form_submit_button("QUE LA APP LO PAGUE SOLA CADA MES", use_container_width=True):
                if n_sub:
                    conn = get_connection()
                    cr = conn.cursor()
                    cr.execute("INSERT INTO suscripciones (usuario_id, nombre, monto, dia_cobro, cat, moneda) VALUES (%s,%s,%s,%s,%s,%s)", 
                               (st.session_state.uid, n_sub, monto_sub, dia_sub, cat_sub, mon_sub))
                    conn.commit()
                    cr.close()
                    conn.close()
                    st.rerun()
                
        conn = get_connection()
        df_suscripciones_lista = pd.read_sql("SELECT * FROM suscripciones WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        conn.close()
        
        for _, r in df_suscripciones_lista.iterrows():
            st.markdown(f'<div class="user-card">🔁 <b>{r["nombre"]}</b> | {r["moneda"]} {float(r["monto"]):,.0f} | Se debita el día {r["dia_cobro"]}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Detener Auto-Pago", key=f"del_sub_{r['id']}"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("DELETE FROM suscripciones WHERE id=%s", (r['id'],))
                conn.commit()
                c.close()
                conn.close()
                st.rerun()

# --- TAB 5: METAS DE AHORRO ---
with t5:
    with st.expander("➕ Crear Nuevo Proyecto de Ahorro"):
        with st.form("form_nueva_meta"):
            n_meta = st.text_input("¿Qué sueño quieres alcanzar? (Ej: Viaje a Europa)")
            obj_meta = st.number_input("Monto Total Objetivo a Ahorrar (CRC)", min_value=1.0)
            
            if st.form_submit_button("INICIAR PROYECTO DE AHORRO", use_container_width=True):
                if n_meta:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n_meta, obj_meta))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.rerun()
                
    conn = get_connection()
    df_metas_lista = pd.read_sql("SELECT * FROM metas WHERE usuario_id=%s ORDER BY id DESC", conn, params=(st.session_state.uid,))
    conn.close()
    
    for _, r in df_metas_lista.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>Progreso: ₡{float(r["actual"]):,.0f} de ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        
        col_meta1, col_meta2, col_meta3 = st.columns([2, 1, 1])
        monto_abono = col_meta1.number_input("Monto a inyectar:", min_value=0.0, key=f"abono_meta_{r['id']}")
        
        if col_meta2.button("DEPOSITAR", key=f"btn_meta_{r['id']}", use_container_width=True):
            conn = get_connection()
            c = conn.cursor()
            c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (monto_abono, r['id']))
            conn.commit()
            c.close()
            conn.close()
            reg_mov(monto_abono, "Gasto", "Otros Gastos", f"Inyección a Meta: {r['nombre']}")
            st.rerun()
            
        if col_meta3.button("🗑️ Eliminar", key=f"del_meta_{r['id']}", use_container_width=True):
            conn = get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM metas WHERE id=%s", (r['id'],))
            conn.commit()
            c.close()
            conn.close()
            st.rerun()

# --- TAB 6: DEUDAS Y COBROS (CALCULADORA DE AMORTIZACIÓN) ---
with t6:
    tab_deudas, tab_cobros = st.tabs(["🏦 Mis Obligaciones Bancarias", "🟢 Cuentas por Cobrar a Terceros"])
    
    with tab_deudas:
        with st.expander("➕ Adquirir Nuevo Préstamo o Deuda"):
            with st.form("form_nueva_deuda"):
                n_acreedor = st.text_input("Nombre de la Entidad Bancaria o Prestamista")
                col_d1, col_d2, col_d3 = st.columns(3)
                monto_prestamo = col_d1.number_input("Capital Total Prestado", min_value=1.0)
                tasa_interes_anual = col_d2.number_input("Tasa de Interés Anual (%)", min_value=0.0)
                plazo_meses = col_d3.number_input("Plazo Total en Meses", min_value=1)
                moneda_prestamo = st.selectbox("Moneda del Préstamo", ["CRC", "USD"])
                
                if st.form_submit_button("REGISTRAR OBLIGACIÓN", use_container_width=True):
                    if n_acreedor:
                        vence_prestamo = date.today() + timedelta(days=plazo_meses*30)
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence, moneda, tasa_interes, plazo_meses) VALUES (%s,%s,%s,'DEUDA',%s,%s,%s,%s)", 
                                  (st.session_state.uid, n_acreedor, monto_prestamo, vence_prestamo, moneda_prestamo, tasa_interes_anual, plazo_meses))
                        conn.commit()
                        c.close()
                        conn.close()
                        st.rerun()
                    
        conn = get_connection()
        df_deudas_lista = pd.read_sql("SELECT * FROM deudas WHERE usuario_id=%s AND tipo_registro='DEUDA' ORDER BY fecha_vence", conn, params=(st.session_state.uid,))
        conn.close()
        
        for _, r in df_deudas_lista.iterrows():
            saldo_pendiente = float(r['monto_total']) - float(r['pagado'])
            cuota_sugerida = calcular_cuota_nivelada(float(r['monto_total']), float(r['tasa_interes']), int(r['plazo_meses']))
            
            st.markdown(f'<div class="user-card">🏦 <b>{r["nombre"]}</b> | Saldo Vivo: {r["moneda"]} {saldo_pendiente:,.0f}<br>Tasa: {r["tasa_interes"]}% | Cuota Mensual Sugerida: <b>{r["moneda"]} {cuota_sugerida:,.0f}</b></div>', unsafe_allow_html=True)
            
            if saldo_pendiente > 0:
                col_pago1, col_pago2, col_pago3 = st.columns([2,1,1])
                abono_deuda = col_pago1.number_input("Monto a amortizar", min_value=0.0, value=min(cuota_sugerida, saldo_pendiente), key=f"abono_deuda_{r['id']}")
                
                if col_pago2.button("PAGAR CUOTA", key=f"btn_pagar_deuda_{r['id']}", use_container_width=True):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (abono_deuda, r['id']))
                    conn.commit()
                    c.close()
                    conn.close()
                    reg_mov(abono_deuda, "Gasto", "Préstamos / Tarjetas", f"Abono a {r['nombre']}", r['moneda'])
                    st.rerun()
                    
                if col_pago3.button("🗑️ Borrar", key=f"del_deuda_{r['id']}", use_container_width=True):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM deudas WHERE id=%s", (r['id'],))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.rerun()

    with tab_cobros:
        with st.expander("➕ Registrar Nueva Cuenta por Cobrar"):
            with st.form("form_nuevo_cobro"):
                n_deudor = st.text_input("Nombre de la persona que te debe")
                col_cob1, col_cob2 = st.columns([1,3])
                moneda_cobro = col_cob1.selectbox("Moneda", ["CRC", "USD"])
                monto_cobro = col_cob2.number_input("Monto Total", min_value=1.0)
                fecha_promesa = st.date_input("Fecha límite prometida")
                
                if st.form_submit_button("GUARDAR REGISTRO DE COBRO", use_container_width=True):
                    if n_deudor:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence, moneda) VALUES (%s,%s,%s,'COBRO',%s,%s)", 
                                  (st.session_state.uid, n_deudor, monto_cobro, fecha_promesa, moneda_cobro))
                        conn.commit()
                        c.close()
                        conn.close()
                        st.rerun()
                    
        conn = get_connection()
        df_cobros_lista = pd.read_sql("SELECT * FROM deudas WHERE usuario_id=%s AND tipo_registro='COBRO' ORDER BY fecha_vence", conn, params=(st.session_state.uid,))
        conn.close()
        
        for _, r in df_cobros_lista.iterrows():
            saldo_por_cobrar = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🟢 <b>{r["nombre"]}</b> | Falta que te paguen: {r["moneda"]} {saldo_por_cobrar:,.0f}</div>', unsafe_allow_html=True)
            
            if saldo_por_cobrar > 0:
                col_rec1, col_rec2, col_rec3 = st.columns([2,1,1])
                ingreso_cobro = col_rec1.number_input("Monto recibido", min_value=0.0, max_value=saldo_por_cobrar, key=f"ingreso_cobro_{r['id']}")
                
                if col_rec2.button("RECIBIR DINERO", key=f"btn_recibir_cobro_{r['id']}", use_container_width=True):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (ingreso_cobro, r['id']))
                    conn.commit()
                    c.close()
                    conn.close()
                    reg_mov(ingreso_cobro, "Ingreso", "Otros Ingresos", f"Pago recibido de {r['nombre']}", r['moneda'])
                    st.rerun()
                    
                if col_rec3.button("🗑️ Borrar", key=f"del_cobro_{r['id']}", use_container_width=True):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM deudas WHERE id=%s", (r['id'],))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.rerun()

# --- TAB 7: SINPE MÓVIL Y AGENDA INTELIGENTE ---
with t7:
    conn = get_connection()
    df_contactos_lista = pd.read_sql("SELECT * FROM contactos WHERE usuario_id=%s ORDER BY nombre", conn, params=(st.session_state.uid,))
    conn.close()
    
    col_sinpe_izq, col_sinpe_der = st.columns([1.2, 1])
    
    with col_sinpe_izq:
        st.markdown("### 💸 Transferencia SINPE Rápida")
        opciones_sinpe = ["✏️ Escribir número manualmente..."] + [f"{r['nombre']} - {r['telefono']}" for _, r in df_contactos_lista.iterrows()]
        seleccion_sinpe = st.selectbox("Seleccionar un contacto frecuente:", opciones_sinpe)
        
        with st.form("form_envio_sinpe"):
            es_ingreso_manual = "✏️" in seleccion_sinpe
            num_destino_final = st.text_input("Número de Teléfono a transferir:", value="" if es_ingreso_manual else seleccion_sinpe.split(" - ")[1])
            monto_transferencia = st.number_input("Monto a enviar (₡):", min_value=0.0, step=1000.0)
            detalle_transferencia = st.text_input("Detalle de la transferencia (Opcional):")
            
            if st.form_submit_button("REGISTRAR GASTO Y ABRIR BANCO", use_container_width=True):
                if num_destino_final and monto_transferencia > 0:
                    nombre_destinatario = "Transferencia Manual" if es_ingreso_manual else seleccion_sinpe.split(" - ")[0]
                    reg_mov(monto_transferencia, "Gasto", "Transferencia entre cuentas", f"SINPE enviado a: {nombre_destinatario} ({num_destino_final}) - {detalle_transferencia}", "CRC")
                    st.markdown('<a href="https://www.google.com" target="_blank" class="btn-banco">🏦 CLICK AQUÍ PARA ABRIR TU APP DEL BANCO</a>', unsafe_allow_html=True)
                else:
                    st.error("Es obligatorio digitar un número válido y un monto mayor a cero.")

    with col_sinpe_der:
        st.markdown("### 📖 Mi Agenda de Contactos")
        with st.expander("➕ Guardar un nuevo contacto"):
            with st.form("form_agregar_contacto"):
                nombre_contacto = st.text_input("Nombre Completo de la Persona")
                telefono_contacto = st.text_input("Número de Teléfono (Sin guiones)")
                
                if st.form_submit_button("GUARDAR EN AGENDA", use_container_width=True):
                    if nombre_contacto and telefono_contacto:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("INSERT INTO contactos (usuario_id, nombre, telefono) VALUES (%s, %s, %s)", 
                                  (st.session_state.uid, nombre_contacto, telefono_contacto))
                        conn.commit()
                        c.close()
                        conn.close()
                        st.rerun()
                    else:
                        st.error("Debes llenar ambos campos.")
        
        if not df_contactos_lista.empty:
            st.markdown("**Directorio Guardado:**")
            for _, r in df_contactos_lista.iterrows():
                col_list_cnt1, col_list_cnt2 = st.columns([4, 1])
                col_list_cnt1.markdown(f"👤 **{r['nombre']}** ({r['telefono']})")
                
                if col_list_cnt2.button("🗑️", key=f"del_contacto_{r['id']}"):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM contactos WHERE id=%s", (r['id'],))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.rerun()
        else:
            st.info("Tu agenda está vacía en este momento.")

# --- TAB 8: HISTORIAL, BÓVEDA DE FACTURAS Y AJUSTES ---
with t8:
    st.subheader("📜 Bóveda de Recibos y Libro Mayor Contable")
    
    conn = get_connection()
    df_historial = pd.read_sql("SELECT id, fecha, tipo, cat, monto, moneda, descrip, impuesto_reserva, comprobante FROM movimientos WHERE usuario_id=%s ORDER BY id DESC LIMIT 100", conn, params=(st.session_state.uid,))
    conn.close()
    
    if not df_historial.empty:
        # Generación de archivo CSV para Exportar
        df_exportacion = df_historial.drop(columns=['comprobante']).rename(columns={
            'fecha': 'Fecha', 
            'tipo': 'Tipo', 
            'cat': 'Categoría', 
            'monto': 'Monto', 
            'moneda': 'Divisa', 
            'descrip': 'Detalle', 
            'impuesto_reserva': 'Impuesto_Retenido'
        })
        datos_csv = df_exportacion.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Descargar Contabilidad en Excel (.CSV)", 
            data=datos_csv, 
            file_name=f'GeZo_Contabilidad_{date.today()}.csv', 
            mime='text/csv'
        )
        st.divider()
        
        # Visor Interactivo y Bóveda
        for _, r in df_historial.head(50).iterrows():
            with st.expander(f"{r['fecha']} | {r['tipo']} | {r['moneda']} {float(r['monto']):,.0f} | {r['cat']}"):
                st.write(f"**Nota / Descripción:** {r['descrip']}")
                
                if pd.notnull(r['impuesto_reserva']) and float(r['impuesto_reserva']) > 0: 
                    st.write(f"🛡️ **Apartado para Impuestos (Escudo Fiscal):** ₡{float(r['impuesto_reserva']):,.0f}")
                
                if r['comprobante']: 
                    try:
                        st.image(base64.b64decode(r['comprobante']), caption="Fotografía / Archivo del Recibo", use_container_width=True)
                    except:
                        st.warning("⚠️ La imagen adjunta no se pudo cargar o el formato no es soportado.")
                        
                if st.button("🗑️ Eliminar este registro de mi historia", key=f"del_hist_{r['id']}"):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM movimientos WHERE id=%s", (r['id'],))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.rerun()
    else: 
        st.info("El libro mayor está limpio. No hay movimientos registrados.")
    
    st.divider()
    st.markdown("### ⚙️ Configuración y Seguridad de la Cuenta")
    
    with st.form("form_cambio_clave"):
        nueva_clave = st.text_input("Ingresa tu nueva contraseña para acceder al sistema", type="password")
        if st.form_submit_button("ACTUALIZAR CLAVE"):
            if nueva_clave:
                conn = get_connection()
                c = conn.cursor()
                c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (nueva_clave, st.session_state.uid))
                conn.commit()
                c.close()
                conn.close()
                st.success("✅ La contraseña ha sido actualizada correctamente.")
            else:
                st.error("No puedes dejar la contraseña en blanco.")
                
    st.divider()
    if st.button("🚪 CERRAR SESIÓN Y SALIR DE FORMA SEGURA", type="primary", use_container_width=True):
        st.session_state.autenticado = False
        st.query_params.clear()
        st.rerun()
