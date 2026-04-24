# Corra el programa: python -m streamlit run notificador_teams.py
# Dependencias: pip install streamlit requests supabase

import os
import json
import streamlit as st
import re
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

COLOMBIA_TZ = ZoneInfo('America/Bogota')
from supabase import create_client

### --- 0. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="Notificador de Incidentes", page_icon="🚨")

# ==============================================================================
# SUPABASE + WEBHOOKS
# ==============================================================================
SUPABASE_URL = "https://btgvgkqbhcvnfnayfuyo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ0Z3Zna3FiaGN2bmZuYXlmdXlvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY4NzkxMjcsImV4cCI6MjA5MjQ1NTEyN30.gQFjjEmvsgNIfhBPW60ArbYOY9CNVEQo9n8G52-pWeM"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ARCHIVO_LOCAL = "estado_plantillas.json"

_URL_1 = "https://bancolombia.webhook.office.com/webhookb2/e126a021-2786-40af-9af6-6921684d3c4f@b5e244bd-c492-495b-8b10-61bfd453e423/IncomingWebhook/f07e473cdb9a44258b1ea146832401d1/94d1f457-3cf7-4e68-890f-31aa6d2bc930/V2unN_qcS3H_JfUcSUwPlWC0U29uIeCbKi_-jfi6_oSe01"
_URL_2 = "https://bancolombia.webhook.office.com/webhookb2/e126a021-2786-40af-9af6-6921684d3c4f@b5e244bd-c492-495b-8b10-61bfd453e423/IncomingWebhook/6ff718d420024fe5a6e4a716eacdcd55/94d1f457-3cf7-4e68-890f-31aa6d2bc930/V2_jfe8qFPIqQoNVEkWkI9D-ooJ1-HNCH0lP896k7rcWo1"

# ==============================================================================
# FUNCIONES DE GUARDADO Y CARGA
# ==============================================================================
def obtener_datos_plantilla(t):
    """Recolecta todos los campos de una plantilla desde session_state."""
    avances = [st.session_state.get(f"av_{i}_{t}", "") for i in range(st.session_state.get(f"num_av_{t}", 1))]
    num_serv = st.session_state.get(f"num_serv_{t}", 1)
    estados = [st.session_state.get(f"e_{i}_{t}", "✅") for i in range(num_serv)]
    servicios = [st.session_state.get(f"s_list_{i}_{t}", "") for i in range(num_serv)]
    horas_ini = [st.session_state.get(f"i_{i}_{t}", "") for i in range(num_serv)]
    horas_fin = [st.session_state.get(f"f_{i}_{t}", "") for i in range(num_serv)]
    return {
        "tipo": t,
        "jira": st.session_state.get(f"jira_in_{t}", ""),
        "caso": st.session_state.get(f"caso_in_{t}", ""),
        "componente": st.session_state.get(f"comp_in_{t}", ""),
        "impacto": st.session_state.get(f"imp_in_{t}", ""),
        "funcionalidades": st.session_state.get(f"fun_in_{t}", ""),
        "descripcion": st.session_state.get(f"des_in_{t}", ""),
        "avances": avances,
        "solucion": st.session_state.get(f"sol_txt_{t}", ""),
        "check_solucion": st.session_state.get(f"check_sol_{t}", False),
        "num_serv": num_serv,
        "estados": estados,
        "servicios": servicios,
        "horas_ini": horas_ini,
        "horas_fin": horas_fin,
        "updated_at": datetime.now(COLOMBIA_TZ).isoformat()
    }

def guardar_en_supabase(t):
    """Guarda o actualiza los datos de una plantilla en Supabase."""
    try:
        datos = obtener_datos_plantilla(t)
        supabase.table("plantillas").upsert(datos, on_conflict="tipo").execute()
        return True
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar en Supabase: {e}")
        return False

def guardar_en_json(t):
    """Guarda los datos de todas las plantillas en un archivo JSON local."""
    try:
        estado = {}
        if os.path.exists(ARCHIVO_LOCAL):
            with open(ARCHIVO_LOCAL, "r", encoding="utf-8") as f:
                estado = json.load(f)
        estado[t] = obtener_datos_plantilla(t)
        with open(ARCHIVO_LOCAL, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar localmente: {e}")
        return False

def cargar_datos_en_session(t, datos):
    """Carga los datos de una plantilla en session_state."""
    if not datos:
        return
    st.session_state[f"jira_in_{t}"] = datos.get("jira", "")
    st.session_state[f"caso_in_{t}"] = datos.get("caso", "")
    st.session_state[f"comp_in_{t}"] = datos.get("componente", "")
    st.session_state[f"imp_in_{t}"] = datos.get("impacto", "")
    st.session_state[f"fun_in_{t}"] = datos.get("funcionalidades", "")
    st.session_state[f"des_in_{t}"] = datos.get("descripcion", "")
    st.session_state[f"check_sol_{t}"] = datos.get("check_solucion", False)
    st.session_state[f"sol_txt_{t}"] = datos.get("solucion", "Estabilidad evidenciada...")
    avances = datos.get("avances", [""])
    st.session_state[f"num_av_{t}"] = max(1, len(avances))
    for i, av in enumerate(avances):
        st.session_state[f"av_{i}_{t}"] = av
    # Restaurar estados, servicios y horas de la tabla
    num_serv = datos.get("num_serv", 1)
    if num_serv > 1:
        st.session_state[f"num_serv_{t}"] = num_serv
    estados = datos.get("estados", [])
    servicios = datos.get("servicios", [])
    horas_ini = datos.get("horas_ini", [])
    horas_fin = datos.get("horas_fin", [])
    for i in range(num_serv):
        if i < len(estados): st.session_state[f"e_{i}_{t}"] = estados[i]
        if i < len(servicios): st.session_state[f"s_list_{i}_{t}"] = servicios[i]
        if i < len(horas_ini): st.session_state[f"i_{i}_{t}"] = horas_ini[i]
        if i < len(horas_fin): st.session_state[f"f_{i}_{t}"] = horas_fin[i]

def cargar_desde_supabase(t):
    """Carga datos de Supabase para una plantilla y los mete en session_state."""
    try:
        res = supabase.table("plantillas").select("*").eq("tipo", t).execute()
        if res.data:
            cargar_datos_en_session(t, res.data[0])
            return True
    except Exception:
        pass
    return False

def cargar_desde_json(t):
    """Carga datos del archivo JSON local como respaldo."""
    try:
        if os.path.exists(ARCHIVO_LOCAL):
            with open(ARCHIVO_LOCAL, "r", encoding="utf-8") as f:
                estado = json.load(f)
            if t in estado:
                cargar_datos_en_session(t, estado[t])
                return True
    except Exception:
        pass
    return False

# ==============================================================================
# CONSTANTES
# ==============================================================================
FUNCIONALIDADES_BASE = (
    "Ingreso APP Nequi, Consulta de Saldo, Envio Bancolombia a Nequi, "
    "Envio Nequi a Bancolombia, Envio Nequi a Nequi, Envio a otros Bancos, "
    "Generación de OTP Retiros, Retiros Cajeros, Envio Bre-B, Recepcion Bre-B, "
    "Tarjeta Física, Tarjeta Digital, Recargas CB Bancolombia, Retiros CB Bancolombia, "
    "Recargas CB Nequi, Retiros CB Nequi, Pagos PSE, Recargas PSE, Apis, "
    "Pagos de Creditos, Pay Pal, Remesas, "
    "Servicios Armario - Recargas y Paquetes (operador Tigo), "
    "Servicios Armario - Recargas y Paquetes (operador Claro), Vinculación"
)

FUNCIONALIDADES_BASE_MASIVO = (
    "Ingreso APP Nequi, Consulta de Saldo, Envio Bancolombia a Nequi, "
    "Envio Nequi a Bancolombia, Envio Nequi a Nequi, Envio a otros Bancos, "
    "Generación de OTP Retiros, Retiros Cajeros ATM, Envio Bre-B, Recepcion Bre-B, "
    "Tarjeta Física, Tarjeta Digital, Recargas CB Bancolombia, Retiros CB Bancolombia, "
    "Recargas CB Nequi, Retiros CB Nequi, Pagos PSE, Recargas PSE, Apis, "
    "Pagos de Creditos, Pay Pal, Remesas, "
    "Servicios Armario - Recargas y Paquetes (operador Tigo), "
    "Servicios Armario - Recargas y Paquetes (operador Claro), Vinculación"
)

### --- 1. LISTADOS DE SERVICIOS ---
LISTA_SERVICIOS_GRAL = [
    "Descarga App", "Descarga App GT", "Ingreso App Nequi", "Cierre de Cuenta",
    "Vinculacion (Vinculacion liviana)", "Vinculacion", "Tarjeta", "Tarjeta Pismo",
    "Remesas RIA (deshabilitado)", "PayPal",
    "Reportería Airflow - Deshabilitado", "Reportería Airflow Aliados - Deshabilitado",
    "Reportería Airflow Contabilidad - Deshabilitado", "Reportería Airflow Legales - Deshabilitado",
    "Reportería Airflow clientes B2b- Deshabilitado", "Reporteria Metabase- Deshabilitado",
    "Pagos atraves QR Bancolombia a Nequi P2P EMVCO", "Pagos a traves QR Datafono",
    "Pagos a traves QR Interoperable otros Bancos", "QR Interoperable Nequi",
    "Credito", "Prestamo Salvavidas - DESHABILITADO",
    "Envio entre Nequis", "Envio entre Nequis con QR",
    "Envio Nequi a Bancolombia", "Envio Nequi a Bancolombia por QR",
    "Envio a otros bancos (ACH)", "Envio Nequi a otros bancos GT - Deshabilitado",
    "Enviar por Transfiya", "Pagos Automaticos", "Recarga plata al toque", "Payoneer",
    "Gestion llaves BreB", "Transacciones SPI Breb",
    "Sacar (Deshabilitado)", "Recarga (Deshabilitado)", "Seguridad (Deshabiltado)",
    "Pagos PSE", "Paso PSE Avanza",
    "Solcitud Documentos (Deshabilitado)", "Distribucion plata (Deshabilitado)",
    "Vinculacion de cuenta de ahorro (Romper Topes)", "Remesas Terrapay",
    "Solicitud documentos credito - DESHABILITADO", "Retiros en contingencia",
    "Servicios Financieros - DESHABILITADO",
    "Api Codigos por plata", "Api Dispersiones", "Api pagos push", "Api pagos QR",
    "Api pago suscripciones", "Api Super QR", "Cobros Nequi", "Registro negocios Nequi",
    "Pagar boton de negocios", "Beneficios NEQUI", "Api Experiencias Embebidas",
    "Servicios hogar y paquetes", "Entretenimiento", "Transportes recargas",
    "Donaciones", "Servicios Publicos", "Seguridad y Salud", "Recaudos Masivos",
    "Paquetes y recargas celular", "Ventas por catalogo", "Financiero",
    "Envio Bancolombia a Nequi", "Recarga PSE",
    "Recargas Nequi desde otros Bancos (Deshabilitado)",
    "Recibir por Transfiya (Deshabilitado)", "Pago de nomina",
    "Recargas CB Bancolombia", "Recarga CB Nequi Punto Red", "Recarga CB Nequi PTM",
    "Recargas CB Nequi", "Credito OAF (Originacion al frente)", "Credito desde boton Nequi",
    "Experiencias digitales - Deshabilitado",
    "Retiro CB Nequi PTM", "Retiro CB Nequi Punto Red", "Retiros CB Nequi",
    "Retiros CB Bancolombia", "Retiros cajeros ATM", "Generacion de OTP Retiros",
    "Servicio PTM", "Remesas", "Consulta de movimientos", "Colchon",
    "Consulta de saldo", "Consulta de Bolsillos", "Sobres - Bolsillos",
    "Metas", "Metas (Chubales)", "App nequi negocios",
    "Pide a un Nequi", "Pide por transfiya (Deshabilitado)",
    "Certificacion Bancaria", "Certificado declaracion de renta",
    "Generar el reporte de extracto",
    "Experiencias Embebidas FLIPCAT", "Experiencias Embebidas GOAMA",
    "Experiencias Embebidas PINBUS", "Experiencias Embebidas GOPASS",
    "Transferencia ACH - Nequi", "Transferencia Bam - Nequi", "Transferencia Nequi - Bam",
    "Cashout Aliado Pronet", "Cashout Aliado 5B", "Cashin Aliado Pronet",
    "Boton de pagos", "Consulta de cupo de credito desde comercios",
    "Giros a un link", "Integracion tecnica", "Gestion de la cuenta",
    "Transacciones activos digitales"
]

LISTA_BANCO = [
    "Envio Bancolombia a Nequi", "Recarga plata al toque", "Api Dispersiones",
    "Remesas", "PayPal", "Envio Nequi a Bancolombia",
    "Envio Bre-B", "Recepcion Bre-B"
]

LISTA_MASIVO = [
    "Ingreso APP Nequi", "Consulta de Saldo", "Envio Bancolombia a Nequi",
    "Envio Nequi a Bancolombia", "Envio Nequi a Nequi",
    "Envio a otros Bancos", "Generación de OTP Retiros", "Retiros Cajeros ATM",
    "Envio Bre-B", "Recepcion Bre-B", "Tarjeta Física", "Tarjeta Digital",
    "Recargas CB Bancolombia", "Retiros CB Bancolombia", "Recargas CB Nequi",
    "Retiros CB Nequi", "Pagos PSE", "Recargas PSE", "Apis", "Pagos de Creditos",
    "Pay Pal", "Remesas",
    "Servicios Armario - Recargas y Paquetes (operador Tigo)",
    "Servicios Armario - Recargas y Paquetes (operador Claro)", "Vinculación"
]

LISTA_BANCOS_BREB = [
    "Envío Bre-B (BANCO DE BOGOTA)",
    "Recepción Bre-B (BANCO DE BOGOTA)",
    "Envío Bre-B (BANCO POPULAR)",
    "Recepción Bre-B (BANCO POPULAR)",
    "Envío Bre-B (BANCO GNB SUDAMERIS)",
    "Recepción Bre-B (BANCO GNB SUDAMERIS)",
    "Envío Bre-B (SERVITRUST GNB SUDAMERIS)",
    "Recepción Bre-B (SERVITRUST GNB SUDAMERIS)",
    "Envío Bre-B (BBVA COLOMBIA)",
    "Recepción Bre-B (BBVA COLOMBIA)",
    "Envío Bre-B (ITAU CORPBANCA COLOMBIA S.A.)",
    "Recepción Bre-B (ITAU CORPBANCA COLOMBIA S.A.)",
    "Envío Bre-B (BANCO DE OCCIDENTE)",
    "Recepción Bre-B (BANCO DE OCCIDENTE)",
    "Envío Bre-B (BANCO AGRARIO DE COLOMBIA S.A.- BANAGRARIO)",
    "Recepción Bre-B (BANCO AGRARIO DE COLOMBIA S.A.- BANAGRARIO)",
    "Envío Bre-B (BANCO DAVIVIENDA)",
    "Recepción Bre-B (BANCO DAVIVIENDA)",
    "Envío Bre-B (BANCO DE LAS MICROFINANZAS BANCAMIA S.A.)",
    "Recepción Bre-B (BANCO DE LAS MICROFINANZAS BANCAMIA S.A.)",
    "Envío Bre-B (BANCO FALABELLA S.A.)",
    "Recepción Bre-B (BANCO FALABELLA S.A.)",
    "Envío Bre-B (BANCO FINANDINA S.A.)",
    "Recepción Bre-B (BANCO FINANDINA S.A.)",
    "Envío Bre-B (BANCO MUNDO MUJER)",
    "Recepción Bre-B (BANCO MUNDO MUJER)",
    "Envío Bre-B (AVAL SOLUCIONES DIGITALES S.A. (DALE))",
    "Recepción Bre-B (AVAL SOLUCIONES DIGITALES S.A. (DALE))",
    "Envío Bre-B (BANCO COMERCIAL AV VILLAS)",
    "Recepción Bre-B (BANCO COMERCIAL AV VILLAS)",
    "Envío Bre-B (BANCO CAJA SOCIAL)",
    "Recepción Bre-B (BANCO CAJA SOCIAL)",
    "Envío Bre-B (MULTIBANCA COLPATRIA)",
    "Recepción Bre-B (MULTIBANCA COLPATRIA)",
    "Envío Bre-B (CONFIAR - COOPERATIVA FINANCIERA)",
    "Recepción Bre-B (CONFIAR - COOPERATIVA FINANCIERA)",
    "Envío Bre-B (COOPERATIVA FINANCIERA DE ANTIOQUIA)",
    "Recepción Bre-B (COOPERATIVA FINANCIERA DE ANTIOQUIA)",
    "Envío Bre-B (FONDO DE EMPLEADOS PRESENTE)",
    "Recepción Bre-B (FONDO DE EMPLEADOS PRESENTE)",
    "Envío Bre-B (COMULTRASAN)",
    "Recepción Bre-B (COMULTRASAN)",
    "Envío Bre-B (COTRAFA - COOPERATIVA FINANCIERA)",
    "Recepción Bre-B (COTRAFA - COOPERATIVA FINANCIERA)",
    "Envío Bre-B (BAN100)",
    "Recepción Bre-B (BAN100)",
    "Envío Bre-B (BANCO W)",
    "Recepción Bre-B (BANCO W)",
    "Envío Bre-B (BANCO COOMEVA S.A.)",
    "Recepción Bre-B (BANCO COOMEVA S.A.)",
    "Envío Bre-B (OPPORTUNITY INTERNATIONAL COLOMBIA S.A. (CREZCAMOS))",
    "Recepción Bre-B (OPPORTUNITY INTERNATIONAL COLOMBIA S.A. (CREZCAMOS))",
    "Envío Bre-B (PAGOS GDE S.A)",
    "Recepción Bre-B (PAGOS GDE S.A)",
    "Envío Bre-B (BTG PACTUAL)",
    "Recepción Bre-B (BTG PACTUAL)",
    "Envío Bre-B (BANCO CONTACTAR S.A.)",
    "Recepción Bre-B (BANCO CONTACTAR S.A.)",
    "Envío Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO LA PLAYA DE BELEN)",
    "Recepción Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO LA PLAYA DE BELEN)",
    "Envío Bre-B (COFINCAFE)",
    "Recepción Bre-B (COFINCAFE)",
    "Envío Bre-B (BANCO UNION S.A.)",
    "Recepción Bre-B (BANCO UNION S.A.)",
    "Envío Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO DE TEORAMA LIMITADA)",
    "Recepción Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO DE TEORAMA LIMITADA)",
    "Envío Bre-B (FONDO DE EMPLEADOS DOCENTES DE LA UNIVERSIDAD NACIONAL DE COLOMBIA)",
    "Recepción Bre-B (FONDO DE EMPLEADOS DOCENTES DE LA UNIVERSIDAD NACIONAL DE COLOMBIA)",
    "Envío Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO COINPROGUA)",
    "Recepción Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO COINPROGUA)",
    "Envío Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO COOPIGON)",
    "Recepción Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO COOPIGON)",
    "Envío Bre-B (BANCO SERFINANZA)",
    "Recepción Bre-B (BANCO SERFINANZA)",
    "Envío Bre-B (COOPERATIVA MULTIACTIVA COOTREGUA)",
    "Recepción Bre-B (COOPERATIVA MULTIACTIVA COOTREGUA)",
    "Envío Bre-B (ASOCIACION MUTUAL BIENESTAR)",
    "Recepción Bre-B (ASOCIACION MUTUAL BIENESTAR)",
    "Envío Bre-B (COOTRAUNION)",
    "Recepción Bre-B (COOTRAUNION)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO CREAFAM COOCREAFAM)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO CREAFAM COOCREAFAM)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO TABACALERA Y AGROPECUARIA LIMITADA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO TABACALERA Y AGROPECUARIA LIMITADA)",
    "Envío Bre-B (FONDO DE EMPLEADOS FECSA)",
    "Recepción Bre-B (FONDO DE EMPLEADOS FECSA)",
    "Envío Bre-B (ASOCIACION MUTUAL PREVENSERVICIOS)",
    "Recepción Bre-B (ASOCIACION MUTUAL PREVENSERVICIOS)",
    "Envío Bre-B (ASOCIACION MUTUAL AMIGO REAL- AMAR)",
    "Recepción Bre-B (ASOCIACION MUTUAL AMIGO REAL- AMAR)",
    "Envío Bre-B (VIDASOL)",
    "Recepción Bre-B (VIDASOL)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO MANUELITA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO MANUELITA)",
    "Envío Bre-B (BANCO COOPCENTRAL)",
    "Recepción Bre-B (BANCO COOPCENTRAL)",
    "Envío Bre-B (FONDO DE EMPLEADOS DE SIEMENS EN COLOMBIA)",
    "Recepción Bre-B (FONDO DE EMPLEADOS DE SIEMENS EN COLOMBIA)",
    "Envío Bre-B (CREDISERVIR)",
    "Recepción Bre-B (CREDISERVIR)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE TRABAJADORES DE PELDAR Y OTROS DE COLOMBIA COOTRAPELDAR)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE TRABAJADORES DE PELDAR Y OTROS DE COLOMBIA COOTRAPELDAR)",
    "Envío Bre-B (COOMULDESA)",
    "Recepción Bre-B (COOMULDESA)",
    "Envío Bre-B (COOPERATIVA ALIANZA)",
    "Recepción Bre-B (COOPERATIVA ALIANZA)",
    "Envío Bre-B (COGRANADA)",
    "Recepción Bre-B (COGRANADA)",
    "Envío Bre-B (COOPERATIVA NACIONAL DE AHORRO Y CREDITO AVANZA)",
    "Recepción Bre-B (COOPERATIVA NACIONAL DE AHORRO Y CREDITO AVANZA)",
    "Envío Bre-B (COOFISAM)",
    "Recepción Bre-B (COOFISAM)",
    "Envío Bre-B (FONDO DE EMPLEADOS DEL PARQUE INDUSTRIAL MALAMBO)",
    "Recepción Bre-B (FONDO DE EMPLEADOS DEL PARQUE INDUSTRIAL MALAMBO)",
    "Envío Bre-B (ULTRAHUILCA)",
    "Recepción Bre-B (ULTRAHUILCA)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO VILLANUEVA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO VILLANUEVA)",
    "Envío Bre-B (A&C COLANTA)",
    "Recepción Bre-B (A&C COLANTA)",
    "Envío Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO MULTICOOP)",
    "Recepción Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO MULTICOOP)",
    "Envío Bre-B (BENEFICIAR)",
    "Recepción Bre-B (BENEFICIAR)",
    "Envío Bre-B (COOPERATIVA ENERGETICA DE AHORRO Y CREDITO)",
    "Recepción Bre-B (COOPERATIVA ENERGETICA DE AHORRO Y CREDITO)",
    "Envío Bre-B (COMEDAL)",
    "Recepción Bre-B (COMEDAL)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE PROFESORES COOPROFESORES)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE PROFESORES COOPROFESORES)",
    "Envío Bre-B (SUCREDITO)",
    "Recepción Bre-B (SUCREDITO)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO VALLE DE SAN JOSE LIMITADA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO VALLE DE SAN JOSE LIMITADA)",
    "Envío Bre-B (FEBOR)",
    "Recepción Bre-B (FEBOR)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO COPACREDITO)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO COPACREDITO)",
    "Envío Bre-B (COOPRUDEA)",
    "Recepción Bre-B (COOPRUDEA)",
    "Envío Bre-B (SERVIMCOOP COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO)",
    "Recepción Bre-B (SERVIMCOOP COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO)",
    "Envío Bre-B (COOPERATIVA MULTIACTIVA DE PROFESIONALES DE SANTANDER - COOPROFESIONALES)",
    "Recepción Bre-B (COOPERATIVA MULTIACTIVA DE PROFESIONALES DE SANTANDER - COOPROFESIONALES)",
    "Envío Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO LTDA. SERVICONAL)",
    "Recepción Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO LTDA. SERVICONAL)",
    "Envío Bre-B (COOPERATIVA MULTISERVICIOS BARICHARA)",
    "Recepción Bre-B (COOPERATIVA MULTISERVICIOS BARICHARA)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO DEL PARAMO LTDA COOPARAMO LTDA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO DEL PARAMO LTDA COOPARAMO LTDA)",
    "Envío Bre-B (COOPERATIVA ESPECIALIZADA EN AHORRO Y CREDITO)",
    "Recepción Bre-B (COOPERATIVA ESPECIALIZADA EN AHORRO Y CREDITO)",
    "Envío Bre-B (COOPERATIVA MULTIACTIVA CON SECCION DE AHORRO Y CREDITO DEL CENTRO COMERCIAL SANANDRESITO LA ISLA)",
    "Recepción Bre-B (COOPERATIVA MULTIACTIVA CON SECCION DE AHORRO Y CREDITO DEL CENTRO COMERCIAL SANANDRESITO LA ISLA)",
    "Envío Bre-B (COOPERATIVA DE EMPLEADOS DEL SECTOR COOPERATIVO)",
    "Recepción Bre-B (COOPERATIVA DE EMPLEADOS DEL SECTOR COOPERATIVO)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO FINANCIERA COAGROSUR)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO FINANCIERA COAGROSUR)",
    "Envío Bre-B (COOPERATIVA GRANCOOP)",
    "Recepción Bre-B (COOPERATIVA GRANCOOP)",
    "Envío Bre-B (FONDO DE EMPLEADOS DEL SECTOR INDUSTRIAL, TURISTICO, COMERCIAL Y DE SERVICIOS)",
    "Recepción Bre-B (FONDO DE EMPLEADOS DEL SECTOR INDUSTRIAL, TURISTICO, COMERCIAL Y DE SERVICIOS)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO SOCIAL PROSPERANDO)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO SOCIAL PROSPERANDO)",
    "Envío Bre-B (COOPERATIVA MULTIACTIVA SAN SIMON)",
    "Recepción Bre-B (COOPERATIVA MULTIACTIVA SAN SIMON)",
    "Envío Bre-B (CESCA)",
    "Recepción Bre-B (CESCA)",
    "Envío Bre-B (COOPERATIVA MULTIACTIVA EL BAGRE)",
    "Recepción Bre-B (COOPERATIVA MULTIACTIVA EL BAGRE)",
    "Envío Bre-B (COOPANTEX COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO)",
    "Recepción Bre-B (COOPANTEX COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO JUAN DE DIOS GOMEZ)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO JUAN DE DIOS GOMEZ)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE LA PROVINCIA DE VELEZ LIMITADA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE LA PROVINCIA DE VELEZ LIMITADA)",
    "Envío Bre-B (COOPERATIVA DE YARUMAL)",
    "Recepción Bre-B (COOPERATIVA DE YARUMAL)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO COOTRAMED)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO COOTRAMED)",
    "Envío Bre-B (COOPERATIVA DE TRABAJADORES DEL SENA)",
    "Recepción Bre-B (COOPERATIVA DE TRABAJADORES DEL SENA)",
    "Envío Bre-B (COOPERATIVA UNIVERSITARIA BOLIVARIANA)",
    "Recepción Bre-B (COOPERATIVA UNIVERSITARIA BOLIVARIANA)",
    "Envío Bre-B (COOPERATIVA SAN ROQUE)",
    "Recepción Bre-B (COOPERATIVA SAN ROQUE)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO SANTA ROSA DE OSOS LIMITADA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO SANTA ROSA DE OSOS LIMITADA)",
    "Envío Bre-B (COOPERATIVA BELEN AHORRO Y CREDITO)",
    "Recepción Bre-B (COOPERATIVA BELEN AHORRO Y CREDITO)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO COOTRADEPARTAMENTALES)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO COOTRADEPARTAMENTALES)",
    "Envío Bre-B (COOPERATIVA RIACHON LTDA)",
    "Recepción Bre-B (COOPERATIVA RIACHON LTDA)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE ENTRERRIOS)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE ENTRERRIOS)",
    "Envío Bre-B (COOPERATIVA SUYA)",
    "Recepción Bre-B (COOPERATIVA SUYA)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO SAN LUIS)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO SAN LUIS)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO CREAR LTDA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO CREAR LTDA)",
    "Envío Bre-B (COOPEREN COOPERATIVA DE AHORRO Y CREDITO)",
    "Recepción Bre-B (COOPEREN COOPERATIVA DE AHORRO Y CREDITO)",
    "Envío Bre-B (FONDO DE EMPLEADOS Y PENSIONADOS DEL SECTOR SALUD DE ANTIOQUIA)",
    "Recepción Bre-B (FONDO DE EMPLEADOS Y PENSIONADOS DEL SECTOR SALUD DE ANTIOQUIA)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO COOSERVUNAL)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO COOSERVUNAL)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO COMUNA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO COMUNA)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO GOMEZ PLATA LTDA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO GOMEZ PLATA LTDA)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO DEL FUTURO LTDA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO DEL FUTURO LTDA)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE LOS TRABAJADORES DE LA EDUCACION DE RISARALDA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE LOS TRABAJADORES DE LA EDUCACION DE RISARALDA)",
    "Envío Bre-B (COPROCENVA COOPERATIVA DE AHORRO Y CREDITO)",
    "Recepción Bre-B (COPROCENVA COOPERATIVA DE AHORRO Y CREDITO)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE DROGUISTAS DETALLISTAS)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO DE DROGUISTAS DETALLISTAS)",
    "Envío Bre-B (BANCOLOMBIA S.A.)",
    "Recepción Bre-B (BANCOLOMBIA S.A.)",
    "Envío Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO AFROAMERICANA)",
    "Recepción Bre-B (COOPERATIVA ESPECIALIZADA DE AHORRO Y CREDITO AFROAMERICANA)",
    "Envío Bre-B (RAPPIPAY COMPAÑÍA DE FINANCIAMIENTO S.A.)",
    "Recepción Bre-B (RAPPIPAY COMPAÑÍA DE FINANCIAMIENTO S.A.)",
    "Envío Bre-B (FINCOMERCIO)",
    "Recepción Bre-B (FINCOMERCIO)",
    "Envío Bre-B (NU. COLOMBIA COMPAÑIA DE FINANCIAMIENTO S.A.)",
    "Recepción Bre-B (NU. COLOMBIA COMPAÑIA DE FINANCIAMIENTO S.A.)",
    "Envío Bre-B (COLTEFINANCIERA)",
    "Recepción Bre-B (COLTEFINANCIERA)",
    "Envío Bre-B (DAVIPLATA)",
    "Recepción Bre-B (DAVIPLATA)",
    "Envío Bre-B (MONO COLOMBIA)",
    "Recepción Bre-B (MONO COLOMBIA)",
    "Envío Bre-B (COOPERATIVA DE AHORRO Y CREDITO PIO XII DE COCORNA LTDA)",
    "Recepción Bre-B (COOPERATIVA DE AHORRO Y CREDITO PIO XII DE COCORNA LTDA)",
    "Envío Bre-B (PAYU COLOMBIA SAS)",
    "Recepción Bre-B (PAYU COLOMBIA SAS)",
    "Envío Bre-B (PEXTO COLOMBIA SAS)",
    "Recepción Bre-B (PEXTO COLOMBIA SAS)",
    "Envío Bre-B (LULO BANK S.A.)",
    "Recepción Bre-B (LULO BANK S.A.)",
    "Envío Bre-B (MOVII S.A. SOCIEDAD ESPECIALIZADA EN DEPÓSITOS Y PAGOS ELECTRÓNICOS)",
    "Recepción Bre-B (MOVII S.A. SOCIEDAD ESPECIALIZADA EN DEPÓSITOS Y PAGOS ELECTRÓNICOS)",
    "Envío Bre-B (DING (TECNIPAGOS))",
    "Recepción Bre-B (DING (TECNIPAGOS))",
    "Envío Bre-B (ACCIONES & VALORES S.A.)",
    "Recepción Bre-B (ACCIONES & VALORES S.A.)",
    "Envío Bre-B (BOLD COMPAÑÍA DE FINANCIAMIENTO)",
    "Recepción Bre-B (BOLD COMPAÑÍA DE FINANCIAMIENTO)",
    "Envío Bre-B (COOFRASA)",
    "Recepción Bre-B (COOFRASA)",
    "Envío Bre-B (NEQUI)",
    "Recepción Bre-B (NEQUI)"
]

LISTA_PSE = ["Pagos PSE", "Recargas PSE"]
mapping_estados = {"✅": "OK", "❌": "TOTAL", "⚠️": "PARCIAL"}

### --- 2. INICIALIZACIÓN DE ESTADOS ---
if 'lista_tipo' not in st.session_state:
    st.session_state.lista_tipo = "completa"
if 'cargado_desde_db' not in st.session_state:
    st.session_state.cargado_desde_db = set()

tipo = st.session_state.lista_tipo

for t in ["completa", "banco", "pse", "spi_breb", "masivo"]:
    if f'num_serv_{t}' not in st.session_state: st.session_state[f'num_serv_{t}'] = 1
    if f'num_av_{t}' not in st.session_state: st.session_state[f'num_av_{t}'] = 1
    st.session_state[f'h_ref_ini_{t}'] = datetime.now(COLOMBIA_TZ).strftime("%d/%m/%Y %H:%M")
    if f'h_ref_fin_{t}' not in st.session_state: st.session_state[f'h_ref_fin_{t}'] = ""
    if f'jira_in_{t}' not in st.session_state: st.session_state[f'jira_in_{t}'] = ""
    if f'caso_in_{t}' not in st.session_state: st.session_state[f'caso_in_{t}'] = ""
    if f'comp_in_{t}' not in st.session_state: st.session_state[f'comp_in_{t}'] = ""
    if f'imp_in_{t}' not in st.session_state: st.session_state[f'imp_in_{t}'] = ""
    if f'fun_in_{t}' not in st.session_state: st.session_state[f'fun_in_{t}'] = ""
    if f'fun_base_{t}' not in st.session_state: st.session_state[f'fun_base_{t}'] = ""
    if f'des_in_{t}' not in st.session_state: st.session_state[f'des_in_{t}'] = ""
    if f'check_sol_{t}' not in st.session_state: st.session_state[f'check_sol_{t}'] = False
    if f'sol_txt_{t}' not in st.session_state: st.session_state[f'sol_txt_{t}'] = "Estabilidad evidenciada..."
    if f'av_0_{t}' not in st.session_state: st.session_state[f'av_0_{t}'] = ""

# Cargar datos (solo una vez por pestaña por sesión)
# Prioridad: JSON local (rápido) → Supabase como respaldo
if tipo not in st.session_state.cargado_desde_db:
    if not cargar_desde_json(tipo):
        cargar_desde_supabase(tipo)
    st.session_state.cargado_desde_db.add(tipo)

### --- 3. BARRA LATERAL ---
st.sidebar.header("⌚ Gestión de Tiempo")
h_ini_in = st.sidebar.text_input("Hora Inicio Referencia:", value=st.session_state[f'h_ref_ini_{tipo}'])
if st.sidebar.button("🕒 Aplicar Inicio a Plantilla Actual"):
    st.session_state[f'h_ref_ini_{tipo}'] = h_ini_in
    for i in range(st.session_state[f'num_serv_{tipo}']):
        st.session_state[f"i_{i}_{tipo}"] = h_ini_in
    st.rerun()

h_fin_in = st.sidebar.text_input("Hora Fin Referencia:", value=st.session_state[f'h_ref_fin_{tipo}'] if st.session_state[f'h_ref_fin_{tipo}'] else datetime.now(COLOMBIA_TZ).strftime("%d/%m/%Y %H:%M"))
if st.sidebar.button("🕒 Aplicar Fin a Plantilla Actual"):
    st.session_state[f'h_ref_fin_{tipo}'] = h_fin_in
    for i in range(st.session_state[f'num_serv_{tipo}']):
        st.session_state[f"f_{i}_{tipo}"] = h_fin_in
    st.rerun()

if st.sidebar.button("🧹 Limpiar Horas, Jira, Caso y Avances"):
    for i in range(st.session_state[f'num_serv_{tipo}']):
        st.session_state[f"i_{i}_{tipo}"] = ""
        st.session_state[f"f_{i}_{tipo}"] = ""
        # Resetear estado y afectación a OK
        st.session_state[f"e_{i}_{tipo}"] = "✅"
    st.session_state[f'jira_in_{tipo}'] = ""
    st.session_state[f'caso_in_{tipo}'] = ""
    st.session_state[f'h_ref_ini_{tipo}'] = datetime.now(COLOMBIA_TZ).strftime("%d/%m/%Y %H:%M")
    st.session_state[f'h_ref_fin_{tipo}'] = ""
    if f'comp_in_{tipo}' in st.session_state: st.session_state[f'comp_in_{tipo}'] = ""
    # Limpiar avances
    for i in range(st.session_state.get(f'num_av_{tipo}', 1)):
        st.session_state[f"av_{i}_{tipo}"] = ""
    st.session_state[f'num_av_{tipo}'] = 1
    st.session_state[f'av_0_{tipo}'] = ""
    st.rerun()

st.sidebar.divider()
st.sidebar.header("🚀 Cargar / Resetear (¡BORRA DATOS!)")

if st.sidebar.button("Cargar Plantilla Inicial"):
    t = "completa"; st.session_state.lista_tipo = t
    st.session_state[f'num_serv_{t}'] = 1
    st.session_state[f's_list_0_{t}'] = "Ingreso APP Nequi"
    st.session_state[f'imp_in_{t}'] = "Se presenta afectación en el servicio"
    st.session_state[f'fun_in_{t}'] = FUNCIONALIDADES_BASE
    st.session_state[f'fun_base_{t}'] = FUNCIONALIDADES_BASE
    st.session_state[f'des_in_{t}'] = "Se evidencia disminución de transacciones en el servicio señalado. En el momento estamos validando la situación e identificación de la posible causa raíz."
    st.session_state.cargado_desde_db.discard(t)
    st.rerun()

if st.sidebar.button("Cargar Plantilla PSE"):
    t = "pse"; st.session_state.lista_tipo = t
    st.session_state[f'num_serv_{t}'] = 2
    # Usar índices de LISTA_SERVICIOS_GRAL
    st.session_state[f's_list_0_{t}'] = "Pagos PSE"
    st.session_state[f's_list_1_{t}'] = "Recarga PSE"
    st.session_state[f'imp_in_{t}'] = "Usuarios presentan problemas para realizar transacciones a través del servicio PSE."
    st.session_state[f'fun_in_{t}'] = FUNCIONALIDADES_BASE
    st.session_state[f'fun_base_{t}'] = FUNCIONALIDADES_BASE
    st.session_state[f'des_in_{t}'] = "Se evidencia disminución de transacciones con servicio PSE. En el momento estamos validando la situación e identificación de la posible causa raíz."
    st.session_state.cargado_desde_db.discard(t)
    st.rerun()


if st.sidebar.button("Cargar Plantilla Banco"):
    t = "banco"; st.session_state.lista_tipo = t
    st.session_state[f'num_serv_{t}'] = len(LISTA_BANCO)
    for i, s_val in enumerate(LISTA_BANCO): st.session_state[f's_list_{i}_{t}'] = s_val
    st.session_state[f'imp_in_{t}'] = "Se evidencia bajo flujo transaccional en la transferencia Bancolombia a Nequi"
    st.session_state[f'fun_in_{t}'] = FUNCIONALIDADES_BASE
    st.session_state[f'fun_base_{t}'] = FUNCIONALIDADES_BASE
    st.session_state[f'des_in_{t}'] = "Se observa caída transaccional en el servicio de transferencia Bancolombia a Nequi"
    st.session_state.cargado_desde_db.discard(t)
    st.rerun()

if st.sidebar.button("Cargar Plantilla SPI BreB"):
    t = "spi_breb"; st.session_state.lista_tipo = t
    st.session_state[f'num_serv_{t}'] = 2
    st.session_state[f's_list_0_{t}'] = "Envío Bre-B"
    st.session_state[f's_list_1_{t}'] = "Recepción Bre-B"
    st.session_state[f'imp_in_{t}'] = "Se registra afectación en el servicio de Transacciones SPI BreB para P2P – P2M."
    st.session_state[f'fun_in_{t}'] = FUNCIONALIDADES_BASE
    st.session_state[f'fun_base_{t}'] = FUNCIONALIDADES_BASE
    st.session_state[f'des_in_{t}'] = "Se presenta rechazos de transacciones SPI Bre-B. En el momento estamos validando la situación e identificación de la posible causa raíz."
    st.session_state.cargado_desde_db.discard(t)
    st.rerun()

if st.sidebar.button("Cargar Evento Masivo"):
    t = "masivo"; st.session_state.lista_tipo = t
    st.session_state[f'num_serv_{t}'] = len(LISTA_MASIVO)
    for i, s_val in enumerate(LISTA_MASIVO): st.session_state[f's_list_{i}_{t}'] = s_val
    st.session_state[f'imp_in_{t}'] = "Se presenta intermitencia en los servicios de Nequi"
    st.session_state[f'fun_in_{t}'] = FUNCIONALIDADES_BASE_MASIVO
    st.session_state[f'fun_base_{t}'] = FUNCIONALIDADES_BASE_MASIVO
    st.session_state[f'des_in_{t}'] = "Actualmente estamos presentando intermitencia en nuestros servicios. En el momento estamos validando la situación e identificación de la posible causa raíz."
    st.session_state.cargado_desde_db.discard(t)
    st.rerun()

st.sidebar.divider()
st.sidebar.header("⚙️ Canales")
webhook_1 = st.sidebar.text_input("Webhook Canal 1", value=_URL_1)
webhook_2 = st.sidebar.text_input("Webhook Canal 2", value=_URL_2)

### --- 4. TABLA DE SERVICIOS ---
st.subheader(f"Servicio Impactado ({tipo.upper()}):")
st.write("**Cambio de Estado Global:**")
cg1, cg2, cg3 = st.columns(3)

if cg1.button("🔴 Todos TOTAL"):
    for i in range(st.session_state[f'num_serv_{tipo}']): st.session_state[f"e_{i}_{tipo}"] = "❌"
    st.rerun()
if cg2.button("⚠️ Todos PARCIAL"):
    for i in range(st.session_state[f'num_serv_{tipo}']): st.session_state[f"e_{i}_{tipo}"] = "⚠️"
    st.rerun()
if cg3.button("🟢 Todos OK"):
    for i in range(st.session_state[f'num_serv_{tipo}']): st.session_state[f"e_{i}_{tipo}"] = "✅"
    st.rerun()

c_add, c_rem, _ = st.columns(3)
with c_add:
    if st.button("➕ Agregar"):
        st.session_state[f'num_serv_{tipo}'] += 1; st.rerun()
with c_rem:
    if st.button("➖ Quitar"):
        st.session_state[f'num_serv_{tipo}'] = max(1, st.session_state[f'num_serv_{tipo}'] - 1); st.rerun()

col_widths = [0.5, 3.0, 1.2, 1.5, 1.2, 0.4]
h1, h2, h3, h4, h5, h6 = st.columns(col_widths)
h1.write("**ESTADO**"); h2.write("**SERVICIO**"); h3.write("**AFECTACIÓN**")
h4.write("**INICIO**"); h5.write("**FIN**"); h6.write("🗑️")

for i in range(st.session_state[f'num_serv_{tipo}']):
    col_widths_ext = [0.5, 3.0, 1.2, 1.5, 1.2, 0.4]
    c1, c2, c3, c4, c5, c6 = st.columns(col_widths_ext)
    with c1:
        est = st.selectbox(f"E{i}", list(mapping_estados.keys()), key=f"e_{i}_{tipo}", label_visibility="collapsed")
    with c2:
        if tipo == "spi_breb": cur_list = LISTA_BANCOS_BREB
        elif tipo == "banco": cur_list = LISTA_SERVICIOS_GRAL
        elif tipo == "masivo": cur_list = LISTA_MASIVO
        elif tipo == "pse": cur_list = LISTA_SERVICIOS_GRAL
        else: cur_list = LISTA_SERVICIOS_GRAL
        s_val = st.session_state.get(f's_list_{i}_{tipo}')
        idx = cur_list.index(s_val) if s_val in cur_list else (i if i < len(cur_list) else 0)
        st.selectbox(f"Sl_{i}", cur_list, index=idx, key=f"s_list_{i}_{tipo}", label_visibility="collapsed")
    with c3:
        st.text_input(f"T{i}", value=mapping_estados[est], key=f"t_in_{i}_{tipo}_{est}", label_visibility="collapsed")
    with c4:
        st.text_input(f"I{i}", value=st.session_state.get(f"i_{i}_{tipo}", st.session_state[f'h_ref_ini_{tipo}']), key=f"i_{i}_{tipo}", label_visibility="collapsed")
    with c5:
        st.text_input(f"F{i}", value=st.session_state.get(f"f_{i}_{tipo}", st.session_state[f'h_ref_fin_{tipo}']), key=f"f_{i}_{tipo}", label_visibility="collapsed")
    with c6:
        if st.button("🗑️", key=f"del_serv_{i}_{tipo}", help=f"Eliminar servicio {i+1}"):
            n = st.session_state[f'num_serv_{tipo}']
            # Guardar valores actuales en listas temporales
            estados = [st.session_state.get(f"e_{j}_{tipo}", "✅") for j in range(n)]
            servicios = [st.session_state.get(f"s_list_{j}_{tipo}", "") for j in range(n)]
            horas_i = [st.session_state.get(f"i_{j}_{tipo}", "") for j in range(n)]
            horas_f = [st.session_state.get(f"f_{j}_{tipo}", "") for j in range(n)]
            # Eliminar el índice i
            estados.pop(i); servicios.pop(i); horas_i.pop(i); horas_f.pop(i)
            # Limpiar todas las keys actuales
            for j in range(n):
                for k in [f"e_{j}_{tipo}", f"s_list_{j}_{tipo}", f"i_{j}_{tipo}", f"f_{j}_{tipo}"]:
                    if k in st.session_state: del st.session_state[k]
            # Reasignar con nueva lista
            nuevo_n = max(1, n - 1)
            for j in range(nuevo_n):
                st.session_state[f"e_{j}_{tipo}"] = estados[j]
                st.session_state[f"s_list_{j}_{tipo}"] = servicios[j]
                st.session_state[f"i_{j}_{tipo}"] = horas_i[j]
                st.session_state[f"f_{j}_{tipo}"] = horas_f[j]
            st.session_state[f'num_serv_{tipo}'] = nuevo_n
            st.rerun()

### --- 5. CAMPOS TÉCNICOS ---
st.divider()

base_fun = st.session_state.get(f'fun_base_{tipo}', "")
if base_fun and base_fun != "N/A":
    lista_actual = base_fun
    for i in range(st.session_state[f'num_serv_{tipo}']):
        estado = st.session_state.get(f"e_{i}_{tipo}")
        serv_nombre = st.session_state.get(f"s_list_{i}_{tipo}", "").strip()
        if estado in ["❌", "⚠️"] and serv_nombre:
            # Intentar eliminar con coma al final, con coma al inicio, o solo el nombre
            for patron in [f"{serv_nombre}, ", f", {serv_nombre}", serv_nombre]:
                if patron in lista_actual:
                    lista_actual = lista_actual.replace(patron, "", 1)
                    break
    # Limpiar espacios y comas residuales
    lista_actual = re.sub(r',[[:space:]]*,', ',', lista_actual)
    lista_actual = lista_actual.strip().strip(',').strip()
    st.session_state[f'fun_in_{tipo}'] = lista_actual

st.text_area("Impacto A Usuarios", key=f"imp_in_{tipo}")
st.text_area("Funcionalidades OK", key=f"fun_in_{tipo}")
st.text_area("Descripción de la falla", key=f"des_in_{tipo}")
col_j, col_c = st.columns(2)
with col_j: st.text_input("Jira", key=f"jira_in_{tipo}")
with col_c: st.text_input("Caso Aliado / Incidente Banco", key=f"caso_in_{tipo}")
st.text_input("Componente Afectado:", key=f"comp_in_{tipo}")

st.subheader("Seguimiento:")
if st.button("➕ Nuevo Avance"):
    st.session_state[f'num_av_{tipo}'] += 1; st.rerun()
for i in range(st.session_state[f'num_av_{tipo}']):
    col_av, col_del = st.columns([11, 1])
    with col_av:
        st.text_area(f"Avance {i+1}", key=f"av_{i}_{tipo}")
    with col_del:
        st.write("")
        st.write("")
        if st.button("🗑️", key=f"del_av_{i}_{tipo}", help=f"Eliminar avance {i+1}"):
            n = st.session_state[f'num_av_{tipo}']
            # Guardar en lista temporal
            avances = [st.session_state.get(f"av_{j}_{tipo}", "") for j in range(n)]
            avances.pop(i)
            # Limpiar keys actuales
            for j in range(n):
                if f"av_{j}_{tipo}" in st.session_state: del st.session_state[f"av_{j}_{tipo}"]
            # Reasignar
            nuevo_n = max(1, n - 1)
            for j in range(nuevo_n):
                st.session_state[f"av_{j}_{tipo}"] = avances[j]
            st.session_state[f'num_av_{tipo}'] = nuevo_n
            st.rerun()

check_sol = st.checkbox("✅ ¿Incluir Solución Final?", key=f"check_sol_{tipo}")
if check_sol:
    st.text_area("Solución Final:", key=f"sol_txt_{tipo}", value="Estabilidad evidenciada...", label_visibility="collapsed")

### --- BOTÓN GUARDAR ---
st.divider()
if st.button("💾 GUARDAR PLANTILLA ACTUAL", use_container_width=True):
    ok_supa = guardar_en_supabase(tipo)
    ok_json = guardar_en_json(tipo)
    if ok_supa and ok_json:
        st.success(f"✅ Plantilla '{vistas.get(tipo, tipo)}' guardada en Supabase y localmente.")
    elif ok_json:
        st.warning("⚠️ Guardado solo localmente (Supabase no disponible).")
    else:
        st.error("❌ No se pudo guardar.")

### --- 6. ENVÍO A TEAMS ---
st.divider()
canales_sel = st.multiselect("Canales de envío:", ["Canal 1", "Canal 2"], default=["Canal 1"])

if st.button("🚀 DESPLEGAR NOTIFICACIÓN A TEAMS", type="primary", use_container_width=True):
    tabla = "| ESTADO | SERVICIO | TIPO DE AFECTACIÓN | HORA INICIO | HORA FIN |\n| :--- | :--- | :--- | :--- | :--- |\n"
    for i in range(st.session_state[f'num_serv_{tipo}']):
        e = st.session_state[f'e_{i}_{tipo}']
        s = st.session_state[f's_list_{i}_{tipo}']
        t_val = st.session_state[f't_in_{i}_{tipo}_{e}']
        ini = st.session_state.get(f'i_{i}_{tipo}', '')
        fin = st.session_state.get(f'f_{i}_{tipo}', '')
        tabla += f"| {e} | {s} | {t_val} | {ini} | {fin} |\n"

    avances_body = "".join([
        f"- **Avance {idx+1}:** {st.session_state.get(f'av_{idx}_{tipo}', '').strip()}\n"
        for idx in range(st.session_state[f'num_av_{tipo}'])
    ])

    mensaje_final = (
        f"### 🚨 Notificador de Incidentes\n\n"
        f"#### Servicios Afectados:\n{tabla}\n\n"
        f"****\n\n"
        f"**Impacto A Usuarios:** {st.session_state[f'imp_in_{tipo}']}\n\n"
        f"**Funcionalidades OK:** {st.session_state[f'fun_in_{tipo}']}\n\n"
        f"**Descripción de la falla:** {st.session_state[f'des_in_{tipo}']}\n\n"
        f"**Jira:** {st.session_state[f'jira_in_{tipo}']}\n\n"
        f"**Caso Aliado / Incidente Banco:** {st.session_state[f'caso_in_{tipo}']}\n\n"
        f"**Componente Afectado:** {st.session_state.get(f'comp_in_{tipo}', 'N/A')}\n\n"
        f"\n\n{avances_body}"
    )

    if st.session_state.get(f'check_sol_{tipo}'):
        mensaje_final += f"\n\n**✅ Solución Final:** {st.session_state.get(f'sol_txt_{tipo}', '')}"

    for c in canales_sel:
        target = webhook_1 if c == "Canal 1" else webhook_2
        if not target or not target.startswith("http"):
            st.warning(f"⚠️ El webhook de {c} no está configurado.")
            continue
        try:
            # Canal 1 usa Power Automate (Adaptive Card)
            # Canal 2 usa webhook clásico de Teams (text)
            payload = {"text": mensaje_final}
            r = requests.post(target, json=payload, timeout=15)
            if r.status_code in [200, 202]:
                st.success(f"✅ Notificación enviada correctamente a {c}.")
            else:
                st.error(f"❌ Error en {c}: código {r.status_code}")
        except requests.exceptions.Timeout:
            st.error(f"❌ Tiempo agotado en {c}.")
        except requests.exceptions.ConnectionError:
            st.error(f"❌ No se pudo conectar a {c}.")
        except Exception as ex:
            st.error(f"❌ Error inesperado en {c}: {ex}")
