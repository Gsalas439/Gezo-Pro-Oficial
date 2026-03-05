import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import re
import base64

# ==========================================
# 1. CONFIGURACIÓN ELITE Y UI NATIVA
# ==========================================
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Bloqueo total de Streamlit UI */
    header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer, .stDeployButton {display: none !important;}
    .block-container {padding-top: 1.5rem !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    
    /* Componentes Visuales Elite */
    .balance-card { background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%); border-radius: 12px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .metric-value { font-size: 2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.8em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    .bac-card { background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%); border-radius: 10px; padding: 10px; text-align: center; border: 1px solid #ff4b4b; color: white; font-weight: bold; }
    .ia-box { background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; padding: 20px; border-radius: 12px; border-left: 5px solid #00f2fe; margin-top: 10px; margin-bottom: 15px; }
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
        st.error("Conectando con Servidor Seguro...")
        return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Tablas maestras
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
    
    # Inyección segura de columnas (Actualización ERP)
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
    
    # Crear cuenta de Administrador del SaaS si no existe
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño SaaS')")
    
    conn.commit()
    c.close()
    conn.close()

inicializar_db()

# Variables Globales de Negocio
TIPO_CAMBIO_COMPRA = 512.00
TIPO_CAMBIO_VENTA = 524.00
PLANES = ["🎁 Prueba Gratis (1 Mes) - ₡0", "🥉 Mensual - ₡2,500", "🥈 Trimestral - ₡6,500", "🥇 Semestral - ₡12,000", "💎 Anual - ₡20,000", "👑 Vitalicio - ₡50,000"]
DIAS_PLAN = {PLANES[0]: 30, PLANES[1]: 30, PLANES[2]: 90, PLANES[3]: 180, PLANES[4]: 365, PLANES[5]: 27000}

# Funciones Financieras Core
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

# Motor Fantasma de Suscripciones (Auto-Cobros)
def procesar_suscripciones():
    hoy = date.today()
    mes_actual = hoy.strftime("%Y-%m")
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, nombre, monto, dia_cobro, cat, moneda FROM suscripciones WHERE usuario_id=%s", (st.session_state.uid,))
    suscripciones = c.fetchall()
    
    for sub in suscripciones:
        sub_id, nombre, monto, dia_cobro, cat, moneda = sub
        # Ajuste inteligente para meses que no tienen 31 días
        ultimo_dia_mes = ((hoy.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
        dia_efectivo = min(dia_cobro, ultimo_dia_mes)
        
        if hoy.day >= dia_efectivo:
            # Validar que no se haya cobrado ya este mes
            c.execute("SELECT id FROM historial_suscripciones WHERE suscripcion_id=%s AND mes_anio=%s", (sub_id, mes_actual))
            if not c.fetchone():
                # Registrar el gasto en la billetera principal (0) por defecto
                c.execute("""INSERT INTO movimientos 
                             (usuario_id, fecha, descrip, monto, tipo, cat, moneda, billetera_id) 
                             VALUES (%s,%s,%s,%s,%s,%s,%s,0)""", 
                          (st.session_state.uid, hoy, f"Auto-Cobro: {nombre}", monto, "Gasto", cat, moneda))
                
                # Dejar constancia de que ya se cobró este mes
                c.execute("INSERT INTO historial_suscripciones (suscripcion_id, mes_anio) VALUES (%s,%s)", (sub_id, mes_actual))
    
    conn.commit()
    c.close()
    conn.close()

# ==========================================
# 3. SEGURIDAD Y ACCESO (SHADOW STATE)
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# Auto-Login silencioso vía URL Token
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
            st.query_params.clear()  # Limpiar URL por seguridad
            st.rerun()

# Pantalla de Login Manual
if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #00f2fe; margin-top: 10vh;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login_form"):
            st.markdown("### Acceso al Sistema")
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            mantener = st.checkbox("Mantener sesión iniciada", value=True)
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

lista_tabs = ["📊 DASHBOARD", "💸 REGISTRO", "💼 BILLETERAS Y PROYECTOS", "🚧 FIJOS Y PRESUPUESTOS", "🎯 METAS", "🏦 DEUDAS Y COBROS", "📱 SINPE", "📜 HISTORIAL"]

# Inyectar Panel de Control solo si el usuario es Admin
if st.session_state.rol == "admin":
    lista_tabs.insert(0, "🏢 PANEL ADMIN SAAS")
    tabs = st.tabs(lista_tabs)
    t_admin = tabs[0]
    t1, t2, t3, t4, t5, t6, t7, t8 = tabs[1:]
    
    # ----- MÓDULO EXCLUSIVO ADMINISTRADOR -----
    with t_admin:
        st.markdown("### 💼 Gestión Comercial y Facturación de Clientes")
        
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
# 5. MÓDULOS FINANCIEROS DEL USUARIO
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

# --- TAB 1: DASHBOARD, RENTABILIDAD Y CONCILIACIÓN ---
with t1:
    cb1, cb2, cb3 = st.columns([1,1,2])
    cb1.markdown(f'<div class="bac-card"><small>BAC COMPRA (USD)</small><br>₡{TIPO_CAMBIO_COMPRA}</div>', unsafe_allow_html=True)
    cb2.markdown(f'<div class="bac-card"><small>BAC VENTA (USD)</small><br>₡{TIPO_CAMBIO_VENTA}</div>', unsafe_allow_html=True)
    
    st.divider()
    rango = st.radio("Filtro de Análisis:", ["Mes Actual", "Histórico Total"], horizontal=True)
    f_inicio = date.today().replace(day=1) if rango == "Mes Actual" else date.today() - timedelta(days=9999)
    
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM movimientos WHERE usuario_id=%s AND fecha >= %s", conn, params=(st.session_state.uid, f_inicio))
    df_historico_completo = pd.read_sql("SELECT billetera_id, tipo, monto, moneda FROM movimientos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    df_proy = pd.read_sql("SELECT * FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    df_pres = pd.read_sql("SELECT * FROM presupuestos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    df_billeteras_activas = pd.read_sql("SELECT id, nombre, tipo, moneda FROM billeteras WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    conn.close()
    
    # MÉTRICAS PRINCIPALES
    if not df.empty:
        # Lógica de Conversión Segura
        def convertir_a_colones(fila):
            valor = float(fila['monto'])
            if fila['moneda'] == 'USD':
                return valor * TIPO_CAMBIO_COMPRA if fila['tipo'] == 'Ingreso' else valor * TIPO_CAMBIO_VENTA
            return valor
            
        df['monto_crc'] = df.apply(convertir_a_colones, axis=1)
        df['impuesto_reserva'] = df['impuesto_reserva'].fillna(0)
        
        impuestos_totales = df['impuesto_reserva'].sum()
        ingresos_brutos = df[df['tipo'] == 'Ingreso']['monto_crc'].sum()
        gastos_totales = df[df['tipo'] == 'Gasto']['monto_crc'].sum()
        capital_real_neto = (ingresos_brutos - gastos_totales) - impuestos_totales
        
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos Brutos (CRC)</p><p class="metric-value">₡{ingresos_brutos:,.0f}</p></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="balance-card"><p class="metric-label">Gastos (CRC)</p><p class="metric-value" style="color:#ff4b4b;">₡{gastos_totales:,.0f}</p></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="balance-card"><p class="metric-label">Capital Libre y Real</p><p class="metric-value" style="color:#2ecc71;">₡{capital_real_neto:,.0f}</p></div>', unsafe_allow_html=True)
        
        st.markdown(f'<div class="ia-box">🤖 <b>GeZo CFO AI:</b> Tienes <b>₡{impuestos_totales:,.0f}</b> congelados en reservas de impuestos (Escudo Fiscal). Te sugerimos mover ₡{max(0, capital_real_neto * 0.2):,.0f} a tus proyectos de ahorro este mes.</div>', unsafe_allow_html=True)
        
        # CONCILIACIÓN BANCARIA (SALDOS REALES POR BILLETERA)
        st.markdown("### 🏦 Saldos Reales por Cuenta (Conciliación)")
        lista_ctas = [{"id": 0, "nombre": "Efectivo Principal", "moneda": "CRC", "tipo": "Efectivo"}]
        for _, r in df_billeteras_activas.iterrows():
            lista_ctas.append({"id": r["id"], "nombre": r["nombre"], "moneda": r["moneda"], "tipo": r["tipo"]})
            
        if not df_historico_completo.empty:
            cols_cta = st.columns(3)
            for i, cta in enumerate(lista_ctas):
                df_c = df_historico_completo[df_historico_completo['billetera_id'] == cta['id']]
                saldo_c = 0
                if not df_c.empty:
                    for _, m in df_c.iterrows():
                        valor = float(m['monto'])
                        # Ajuste si hubo transacciones en moneda distinta a la moneda principal de la billetera
                        if m['moneda'] == 'USD' and cta['moneda'] == 'CRC':
                            valor = valor * TIPO_CAMBIO_COMPRA if m['tipo'] == 'Ingreso' else valor * TIPO_CAMBIO_VENTA
                        elif m['moneda'] == 'CRC' and cta['moneda'] == 'USD':
                            valor = valor / TIPO_CAMBIO_VENTA if m['tipo'] == 'Ingreso' else valor / TIPO_CAMBIO_COMPRA
                            
                        if m['tipo'] == 'Ingreso':
                            saldo_c += valor
                        else:
                            saldo_c -= valor
                
                color_s = "#2ecc71" if saldo_c >= 0 else "#ff4b4b"
                icono = "💳" if "Tarjeta" in cta['tipo'] else "💵"
                with cols_cta[i % 3]:
                    st.markdown(f'<div class="user-card" style="text-align:center;">{icono} <b>{cta["nombre"]}</b><br><span style="font-size:1.5em; color:{color_s}; font-weight:bold;">{cta["moneda"]} {saldo_c:,.2f}</span></div>', unsafe_allow_html=True)
        
        # SEMÁFORO DE PRESUPUESTOS
        if not df_pres.empty and rango == "Mes Actual":
            st.markdown("### 🚧 Control de Presupuestos (Mes Actual)")
            g_mes = df[df['tipo'] == 'Gasto'].groupby('cat')['monto_crc'].sum().reset_index()
            for _, rp in df_pres.iterrows():
                serie_gasto = g_mes[g_mes['cat'] == rp['cat']]['monto_crc']
                gastado = serie_gasto.sum() if not serie_gasto.empty else 0
                limite = float(rp['limite'])
                pct = min(gastado / limite, 1.0) if limite > 0 else 1.0
                
                st.write(f"**{rp['cat']}** | Ejecutado: ₡{gastado:,.0f} de ₡{limite:,.0f}")
                st.progress(pct)
                if pct >= 0.9:
                    st.error(f"⚠️ ¡Atención! Has consumido el 90% o más de tu presupuesto para {rp['cat']}")

        # RENTABILIDAD DE PROYECTOS (CENTROS DE COSTO)
        if not df_proy.empty:
            st.markdown("### 🏢 Rentabilidad de Proyectos / Negocios")
            for _, rp in df_proy.iterrows():
                df_p = df[df['proyecto_id'] == rp['id']]
                i_p = df_p[df_p['tipo'] == 'Ingreso']['monto_crc'].sum() if not df_p.empty else 0
                g_p = df_p[df_p['tipo'] == 'Gasto']['monto_crc'].sum() if not df_p.empty else 0
                margen = i_p - g_p
                color_m = "#2ecc71" if margen >= 0 else "#ff4b4b"
                
                st.markdown(f'<div class="user-card"><b>{rp["nombre"]}</b> | Ingresos: ₡{i_p:,.0f} | Costos: ₡{g_p:,.0f} | <span style="color:{color_m};">Margen Neto: ₡{margen:,.0f}</span></div>', unsafe_allow_html=True)
    else:
        st.info("Aún no tienes movimientos financieros registrados en este periodo.")

# --- TAB 2: REGISTRO MÁGICO Y MANUAL ---
with t2:
    tab_manual, tab_magico = st.tabs(["✍️ Registro Manual y Bóveda", "🪄 Lector Mágico de SMS"])
    
    with tab_manual:
        conn = get_connection()
        df_bill = pd.read_sql("SELECT id, nombre, moneda FROM billeteras WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        df_pry = pd.read_sql("SELECT id, nombre FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        conn.close()
        
        billeteras_opciones = [{"label": f"{r['nombre']} ({r['moneda']})", "id": r['id']} for _, r in df_bill.iterrows()] if not df_bill.empty else [{"label": "Efectivo Principal (CRC)", "id": 0}]
        proyectos_opciones = [{"label": "Ninguno (Gasto Personal)", "id": 0}] + [{"label": r['nombre'], "id": r['id']} for _, r in df_pry.iterrows()]
        
        tipo_mov = st.radio("Selecciona el tipo de transacción:", ["Gasto", "Ingreso"], horizontal=True)
        categorias = ["Súper/Comida", "Servicios", "Casa/Alquiler", "Transporte", "Ocio", "Salud", "Educación", "Insumos Negocio", "Otros"] if tipo_mov == "Gasto" else ["Ventas", "Servicios Profesionales", "Salario Fijo", "Otros"]
        
        with st.form("f_registro_manual"):
            col_sel1, col_sel2 = st.columns(2)
            billetera_seleccionada = col_sel1.selectbox("¿Cuenta de Origen / Destino?", [x['label'] for x in billeteras_opciones])
            proyecto_seleccionado = col_sel2.selectbox("Asignar a Proyecto Comercial:", [x['label'] for x in proyectos_opciones])
            
            b_id = next(b['id'] for b in billeteras_opciones if b['label'] == billetera_seleccionada)
            p_id = next(p['id'] for p in proyectos_opciones if p['label'] == proyecto_seleccionado)
            
            monto_reg = st.number_input("Monto de la transacción", min_value=0.0, step=1000.0)
            categoria_reg = st.selectbox("Clasificación Contable", categorias)
            
            impuesto_reg = 0.0
            if tipo_mov == "Ingreso" and p_id != 0:
                if st.checkbox("🛡️ Aplicar Escudo Fiscal (Retener automáticamente el 13% para impuestos)"):
                    impuesto_reg = monto_reg * 0.13
                    
            desc_reg = st.text_input("Nota o descripción (Opcional)")
            foto_reg = st.file_uploader("📸 Adjuntar Factura / Recibo (La app lo guardará en tu Bóveda)", type=["jpg", "png", "jpeg"])
            
            if st.form_submit_button("REGISTRAR EN EL LIBRO MAYOR", use_container_width=True):
                moneda_transaccion = "USD" if "USD" in billetera_seleccionada else "CRC"
                imagen_codificada = base64.b64encode(foto_reg.read()).decode('utf-8') if foto_reg else None
                
                reg_mov(monto_reg, tipo_mov, categoria_reg, desc_reg, moneda_transaccion, imagen_codificada, b_id, p_id, impuesto_reg)
                st.success("✅ Transacción guardada con éxito.")
                st.rerun()

    with tab_magico:
        st.markdown("Copia el texto del mensaje que te envía el banco por compras y pégalo aquí.")
        texto_sms = st.text_area("Ejemplo: 'BAC Credomatic: Compra aprobada por ₡15,000 en WALMART'")
        
        if st.button("🪄 Analizar SMS con Inteligencia Artificial", use_container_width=True):
            if texto_sms:
                monto_match = re.search(r'[\$₡]?\s?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', texto_sms)
                if monto_match:
                    monto_limpio = float(monto_match.group(1).replace(',', ''))
                    moneda_detectada = "USD" if "$" in texto_sms or "USD" in texto_sms.upper() else "CRC"
                    
                    cat_sugerida = "Otros"
                    texto_upper = texto_sms.upper()
                    if any(w in texto_upper for w in ["WALMART", "MASXMENOS", "AUTO MERCADO", "PALI"]):
                        cat_sugerida = "Súper/Comida"
                    elif any(w in texto_upper for w in ["UBER", "DIDDI", "GAS", "DELTA", "PUMA"]):
                        cat_sugerida = "Transporte"
                    elif any(w in texto_upper for w in ["KFC", "MCDONALDS", "STARBUCKS", "RESTAURANTE"]):
                        cat_sugerida = "Ocio"
                    
                    st.success(f"Detección exitosa: **{moneda_detectada} {monto_limpio:,.2f}** (Sugerencia: {cat_sugerida})")
                    
                    if st.button(f"Confirmar Registro de Gasto Rápido"):
                        reg_mov(monto_limpio, "Gasto", cat_sugerida, texto_sms[:40], moneda_detectada)
                        st.success("Gasto automatizado registrado en tu historial.")
                        st.rerun()
                else:
                    st.error("La Inteligencia Artificial no logró extraer un monto válido del mensaje. Asegúrate de que contenga números y símbolos de moneda.")

# --- TAB 3: BILLETERAS Y PROYECTOS ---
with t3:
    col_billetera, col_proyecto = st.columns(2)
    
    with col_billetera:
        st.markdown("### 💳 Administrar Billeteras y Tarjetas")
        with st.form("form_nueva_billetera"):
            n_bill = st.text_input("Nombre (Ej: Tarjeta Débito BAC)")
            t_bill = st.selectbox("Naturaleza de la Cuenta", ["Efectivo / Débito", "Tarjeta de Crédito (Pasivo)"])
            m_bill = st.selectbox("Moneda Principal", ["CRC", "USD"])
            if st.form_submit_button("AÑADIR BILLETERA", use_container_width=True):
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
        st.markdown("### 🏢 Crear Proyectos / Negocios")
        with st.form("form_nuevo_proyecto"):
            n_proy = st.text_input("Nombre del Centro de Costo (Ej: Ventas de Comida)")
            if st.form_submit_button("CREAR PROYECTO", use_container_width=True):
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
    tab_limites, tab_suscripciones = st.tabs(["🚧 Control de Presupuestos", "🔁 Gestor de Gastos Fijos"])
    
    with tab_limites:
        st.write("Establece un techo máximo de dinero para tus categorías. Te avisaremos si te acercas al límite.")
        with st.form("form_nuevo_presupuesto"):
            cat_presupuesto = st.selectbox("Categoría a monitorear", ["Súper/Comida", "Transporte", "Ocio", "Casa/Alquiler", "Otros"])
            limite_presupuesto = st.number_input("Límite de Gasto Mensual (CRC)", min_value=1.0)
            
            if st.form_submit_button("FIJAR LÍMITE DE PRESUPUESTO"):
                conn = get_connection()
                cr = conn.cursor()
                cr.execute("DELETE FROM presupuestos WHERE usuario_id=%s AND cat=%s", (st.session_state.uid, cat_presupuesto))
                cr.execute("INSERT INTO presupuestos (usuario_id, cat, limite) VALUES (%s,%s,%s)", (st.session_state.uid, cat_presupuesto, limite_presupuesto))
                conn.commit()
                cr.close()
                conn.close()
                st.rerun()
                
        conn = get_connection()
        df_presupuestos_lista = pd.read_sql("SELECT * FROM presupuestos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        conn.close()
        
        for _, r in df_presupuestos_lista.iterrows():
            st.markdown(f'<div class="user-card">🚧 <b>{r["cat"]}</b> | Límite Activo: ₡{float(r["limite"]):,.0f}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Eliminar Límite", key=f"del_pres_{r['id']}"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("DELETE FROM presupuestos WHERE id=%s", (r['id'],))
                conn.commit()
                c.close()
                conn.close()
                st.rerun()

    with tab_suscripciones:
        st.write("Registra tus pagos automáticos. GeZo los debitará de tu balance principal (Efectivo) el día correspondiente de cada mes.")
        with st.form("form_nueva_suscripcion"):
            n_sub = st.text_input("Nombre de la Suscripción (Ej: Netflix, Spotify, Gimnasio)")
            col_sub1, col_sub2 = st.columns(2)
            mon_sub = col_sub1.selectbox("Moneda del Cobro", ["CRC", "USD"])
            monto_sub = col_sub2.number_input("Monto a Cobrar", min_value=1.0)
            
            dia_sub = st.number_input("Día de cobro en el mes (1-31)", min_value=1, max_value=31)
            cat_sub = st.selectbox("Clasificación Contable", ["Servicios", "Ocio", "Casa/Alquiler", "Educación", "Otros"])
            
            if st.form_submit_button("ACTIVAR AUTO-PAGO", use_container_width=True):
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
            st.markdown(f'<div class="user-card">🔁 <b>{r["nombre"]}</b> | {r["moneda"]} {float(r["monto"]):,.0f} | Se debita el día {r["dia_cobro"]} del mes.</div>', unsafe_allow_html=True)
            if st.button("🗑️ Cancelar Suscripción", key=f"del_sub_{r['id']}"):
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
        monto_abono = col_meta1.number_input("Monto a inyectar al proyecto:", min_value=0.0, key=f"abono_meta_{r['id']}")
        
        if col_meta2.button("DEPOSITAR DINERO", key=f"btn_meta_{r['id']}", use_container_width=True):
            conn = get_connection()
            c = conn.cursor()
            c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (monto_abono, r['id']))
            conn.commit()
            c.close()
            conn.close()
            # El dinero que va a una meta sale de tu bolsillo principal, es un gasto para el balance
            reg_mov(monto_abono, "Gasto", "🎯 Ahorro", f"Inyección a Meta: {r['nombre']}")
            st.rerun()
            
        if col_meta3.button("🗑️ Eliminar Meta", key=f"del_meta_{r['id']}", use_container_width=True):
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
                
                if st.form_submit_button("REGISTRAR OBLIGACIÓN FINANCIERA", use_container_width=True):
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
            
            st.markdown(f'<div class="user-card">🏦 <b>{r["nombre"]}</b> | Saldo Vivo: {r["moneda"]} {saldo_pendiente:,.0f}<br>Tasa Pactada: {r["tasa_interes"]}% | Cuota Nivelada Sugerida: <b>{r["moneda"]} {cuota_sugerida:,.0f}</b></div>', unsafe_allow_html=True)
            
            if saldo_pendiente > 0:
                col_pago1, col_pago2, col_pago3 = st.columns([2,1,1])
                abono_deuda = col_pago1.number_input("Monto a amortizar hoy", min_value=0.0, value=min(cuota_sugerida, saldo_pendiente), key=f"abono_deuda_{r['id']}")
                
                if col_pago2.button("PAGAR CUOTA", key=f"btn_pagar_deuda_{r['id']}", use_container_width=True):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (abono_deuda, r['id']))
                    conn.commit()
                    c.close()
                    conn.close()
                    reg_mov(abono_deuda, "Gasto", "🏦 Préstamo", f"Abono a {r['nombre']}", r['moneda'])
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
                n_deudor = st.text_input("Nombre de la persona o empresa que te debe")
                col_cob1, col_cob2 = st.columns([1,3])
                moneda_cobro = col_cob1.selectbox("Moneda de la Deuda", ["CRC", "USD"])
                monto_cobro = col_cob2.number_input("Monto Total de la Deuda", min_value=1.0)
                fecha_promesa = st.date_input("Fecha límite de promesa de pago")
                
                if st.form_submit_button("GUARDAR REGISTRO DE COBRO", use_container_width=True):
                    if n_deudor:
                        conn = get_connection()
                        c = conn.cursor()
                        # Corrección Bug N°2: Guardar la moneda correcta
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
                ingreso_cobro = col_rec1.number_input("Monto de dinero recibido hoy", min_value=0.0, max_value=saldo_por_cobrar, key=f"ingreso_cobro_{r['id']}")
                
                if col_rec2.button("RECIBIR DINERO", key=f"btn_recibir_cobro_{r['id']}", use_container_width=True):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (ingreso_cobro, r['id']))
                    conn.commit()
                    c.close()
                    conn.close()
                    # Entra dinero a favor
                    reg_mov(ingreso_cobro, "Ingreso", "💸 Cobro", f"Pago recibido de {r['nombre']}", r['moneda'])
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
                    # SINPE siempre es en Colones (CRC)
                    reg_mov(monto_transferencia, "Gasto", "📱 SINPE", f"Enviado a: {nombre_destinatario} ({num_destino_final}) - {detalle_transferencia}", "CRC")
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

# --- TAB 8: HISTORIAL, EXPORTACIÓN Y AJUSTES ---
with t8:
    st.subheader("📜 Libro Mayor Contable (Auditoría Global)")
    
    conn = get_connection()
    # Consulta anti-errores (todo en minúsculas)
    df_historial = pd.read_sql("SELECT id, fecha, tipo, cat, monto, moneda, descrip, impuesto_reserva, comprobante FROM movimientos WHERE usuario_id=%s ORDER BY id DESC LIMIT 100", conn, params=(st.session_state.uid,))
    conn.close()
    
    if not df_historial.empty:
        # Generación de archivo CSV limpio para Exportar
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
            file_name=f'GeZo_Contabilidad_Global_{date.today()}.csv', 
            mime='text/csv'
        )
        st.divider()
        
        # Visor Interactivo y Bóveda de Facturas
        for _, r in df_historial.head(50).iterrows():
            with st.expander(f"{r['fecha']} | {r['tipo']} | {r['moneda']} {float(r['monto']):,.0f} | {r['cat']}"):
                st.write(f"**Descripción de la Operación:** {r['descrip']}")
                
                # Verificación segura del impuesto
                if pd.notnull(r['impuesto_reserva']) and float(r['impuesto_reserva']) > 0: 
                    st.write(f"🛡️ **Escudo Fiscal (Impuesto Reservado):** ₡{float(r['impuesto_reserva']):,.0f}")
                
                # Renderizado seguro de imágenes base64
                if r['comprobante']: 
                    try:
                        st.image(base64.b64decode(r['comprobante']), caption="Factura / Recibo Adjunto Original", use_container_width=True)
                    except:
                        st.warning("⚠️ El recibo adjunto está corrupto o el formato no es soportado por el navegador.")
                        
                if st.button("🗑️ Eliminar este registro del balance general", key=f"del_hist_{r['id']}"):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM movimientos WHERE id=%s", (r['id'],))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.rerun()
    else: 
        st.info("El libro mayor está limpio. No existen movimientos registrados en la base de datos para auditar.")
    
    st.divider()
    st.markdown("### ⚙️ Configuración y Seguridad de la Cuenta")
    
    with st.form("form_cambio_clave"):
        nueva_clave = st.text_input("Ingresa tu nueva contraseña para acceder al sistema", type="password")
        if st.form_submit_button("ACTUALIZAR CREDENCIALES DE ACCESO"):
            if nueva_clave:
                conn = get_connection()
                c = conn.cursor()
                c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (nueva_clave, st.session_state.uid))
                conn.commit()
                c.close()
                conn.close()
                st.success("✅ La contraseña ha sido actualizada correctamente en los servidores de GeZo.")
            else:
                st.error("No puedes dejar la contraseña en blanco.")
                
    st.divider()
    if st.button("🚪 CERRAR SESIÓN DE FORMA SEGURA", type="primary", use_container_width=True):
        st.session_state.autenticado = False
        st.query_params.clear()
        st.rerun()
