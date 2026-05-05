import streamlit as st
import pandas as pd
from datetime import datetime
import re

# ------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------------
st.set_page_config(
    page_title="CCR – UFF/UNIRIO",
    layout="wide"
)

# ------------------------------------------------------
# LOGO + TÍTULO
# ------------------------------------------------------
col1, col2, col3 = st.columns([1, 3, 1])

with col1:
    st.image("logo-cecierj.png", width=130)

with col2:
    st.markdown("""
        <h1 style='text-align: center; margin-bottom: 0; color: #0b5c73;'>
            Controle de Cadastro Reserva Matemática
        </h1>
        <h3 style='text-align: center; margin-top: 5px; color: #0b5c73;'>
            UFF/UNIRIO – CEDERJ
        </h3>
        """, unsafe_allow_html=True)

with col3:
    st.empty()

# ------------------------------------------------------
# LEITURA DA BASE (Google Sheets - CSV)
# ------------------------------------------------------
@st.cache_data(ttl=60)
def carregar_dados() -> pd.DataFrame:
    sheet_id = "1Njfuxo4usLFCbxl_bLg77n9pCFiHSu5IL1nlxHSSCsI"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar planilha: {str(e)}")
        return pd.DataFrame()

df = carregar_dados()

if df.empty:
    st.stop()

# ------------------------------------------------------
# LIMPEZA DE LINHAS SUJEIRA
# ------------------------------------------------------
df = df[df["Edital"] != "Edital"]
df = df[~df["Grupo"].astype(str).str.contains("Disciplina", case=False, na=False)]
df = df[~df["Grupo"].astype(str).str.contains("Posição", case=False, na=False)]
df = df[~df["Status"].astype(str).str.contains("Data convocação", case=False, na=False)]
df = df[df["Função"].notna()]

# ------------------------------------------------------
# FUNÇÃO PARA CONVERTER DATAS
# ------------------------------------------------------
def converter_para_calculo(data_str):
    if pd.isna(data_str) or data_str == "":
        return pd.NaT
    
    data_str = str(data_str).strip()
    
    match = re.match(r"(\w+) de (\d{4})", data_str)
    if match:
        mes_nome, ano = match.groups()
        meses = {
            "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4,
            "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8,
            "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
        }
        mes_num = meses.get(mes_nome, 1)
        return datetime(int(ano), mes_num, 1)
    
    for fmt in ["%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(data_str, fmt)
        except:
            continue
    
    return pd.NaT

# ------------------------------------------------------
# FORMATAÇÃO DE DATAS PARA EXIBIÇÃO
# ------------------------------------------------------
def formatar_datas(df_mostrar: pd.DataFrame) -> pd.DataFrame:
    return df_mostrar

# ------------------------------------------------------
# BUSCA POR CANDIDATO
# ------------------------------------------------------
def buscar_ocorrencias_candidato(nome_parcial: str, df_base: pd.DataFrame) -> pd.DataFrame:
    mask_nome = df_base["Candidato"].str.contains(nome_parcial, case=False, na=False)
    df_encontrados = df_base[mask_nome].copy()

    if df_encontrados.empty:
        return pd.DataFrame()

    colunas_layout = [
        "Edital", "Função", "Grupo", "Posição", "Candidato",
        "Titulação", "Status", "Data convocação", "Prazo para convocação",
        "Validade pagamento bolsa", "Obs"
    ]

    colunas_existentes = [col for col in colunas_layout if col in df_encontrados.columns]

    return df_encontrados.sort_values(
        by=["Candidato", "Edital", "Função", "Grupo", "Posição"]
    )[colunas_existentes]

# ------------------------------------------------------
# CÁLCULO DE KPIs (AGORA COM RECUSOU)
# ------------------------------------------------------
def calcular_kpis(df_base: pd.DataFrame) -> dict:
    df_tmp = df_base.copy()

    if "Prazo para convocação" in df_tmp.columns:
        df_tmp["Prazo para convocação"] = pd.to_datetime(
            df_tmp["Prazo para convocação"], errors="coerce"
        )

    hoje = pd.Timestamp.today().normalize()

    expirado_por_prazo = (
        (df_tmp["Status"] == "Aguardando convocação")
        & df_tmp["Prazo para convocação"].notna()
        & (df_tmp["Prazo para convocação"] < hoje)
    )

    expirado_por_texto = (
        df_tmp["Data convocação"]
        .fillna("")
        .astype(str)
        .str.contains("expirado para convocação", case=False)
    )

    expirados_mask = expirado_por_prazo | expirado_por_texto

    total = len(df_tmp)

    convocados = (
        (df_tmp["Status"] == "Convocado").sum()
        if "Status" in df_tmp.columns else 0
    )

    recusou = (
        (df_tmp["Status"] == "Recusou").sum()
        if "Status" in df_tmp.columns else 0
    )

    aguardando = (
        (df_tmp["Status"] == "Aguardando convocação")
        & (~expirados_mask)
    ).sum() if "Status" in df_tmp.columns else 0

    expirados = expirados_mask.sum()

    return {
        "Total de candidatos": total,
        "Convocados": convocados,
        "Aguardando convocação": aguardando,
        "Expirados": expirados,
        "Recusou": recusou,
    }

# ------------------------------------------------------
# KPIs COM FILTRO POR EDITAL
# ------------------------------------------------------
st.markdown("---")
st.subheader("📊 Indicadores")

opcoes_edital_kpi = ["(todos)"] + sorted(df["Edital"].dropna().unique().tolist())
edital_kpi = st.selectbox("Filtrar indicadores por edital:", opcoes_edital_kpi)

df_kpi = df if edital_kpi == "(todos)" else df[df["Edital"] == edital_kpi]
kpis = calcular_kpis(df_kpi)

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("📝 Total", kpis["Total de candidatos"])
col2.metric("✅ Convocados", kpis["Convocados"])
col3.metric("⏳ Aguardando", kpis["Aguardando convocação"])
col4.metric("⚠️ Expirados", kpis["Expirados"])
col5.metric("❌ Recusou", kpis["Recusou"])

# ------------------------------------------------------
# BUSCA POR CANDIDATO
# ------------------------------------------------------
st.markdown("---")
st.subheader("🔍 Buscar candidato (todas as ocorrências)")

nome = st.text_input("Digite pelo menos 3 letras do nome:")

if nome and len(nome.strip()) >= 3:
    resultado = buscar_ocorrencias_candidato(nome.strip(), df)

    if resultado.empty:
        st.info("ℹ️ Nenhum candidato encontrado para essa busca.")
    else:
        st.success(f"✅ {len(resultado)} ocorrência(s) encontrada(s)")
        st.dataframe(formatar_datas(resultado.copy()), use_container_width=True)
elif nome:
    st.warning("⚠️ Digite pelo menos 3 letras do nome.")

# ------------------------------------------------------
# FILTROS TIPO EXCEL
# ------------------------------------------------------
st.markdown("---")
st.subheader("📋 Fila por Edital / Função / Grupo")

df_filtrado = df.copy()

# ---- FILTRO EDITAL ----
opcoes_edital = ["(todos)"] + sorted(df_filtrado["Edital"].dropna().unique().tolist())
edital_sel = st.selectbox("📌 Edital", options=opcoes_edital)

if edital_sel != "(todos)":
    df_filtrado = df_filtrado[df_filtrado["Edital"] == edital_sel]

# ---- FILTRO FUNÇÃO ----
funcoes_validas = df_filtrado["Função"].dropna()
funcoes_str = funcoes_validas.astype(str).unique().tolist()
funcao_options = ["(todos)"] + sorted(funcoes_str)
funcao_sel = st.selectbox("💼 Função", options=funcao_options)

if funcao_sel != "(todos)":
    df_filtrado = df_filtrado[df_filtrado["Função"].astype(str) == funcao_sel]

# ---- FILTRO GRUPO ----
df_filtrado = df_filtrado[df_filtrado["Grupo"].notna() | (df_filtrado["Função"] == "Coordenador de Tutoria")]

grupos_validos = df_filtrado["Grupo"].dropna()
if not grupos_validos.empty:
    grupos_str = grupos_validos.astype(str).unique().tolist()
    grupo_options = ["(todos)"] + sorted(grupos_str)
    grupo_sel = st.selectbox("📚 Grupo", options=grupo_options)

    if grupo_sel != "(todos)":
        df_filtrado = df_filtrado[df_filtrado["Grupo"].astype(str) == grupo_sel]

# ---- FILTRO STATUS ----
status_validos = df_filtrado["Status"].dropna().unique().tolist()
status_options = ["(todos)"] + sorted(status_validos)
status_sel = st.selectbox("🏷️ Status", options=status_options)

if status_sel != "(todos)":
    df_filtrado = df_filtrado[df_filtrado["Status"] == status_sel]

# ---- TRATAMENTO DA POSIÇÃO E EXIBIÇÃO ----
if "Posição" in df_filtrado.columns:
    df_filtrado["Posição"] = pd.to_numeric(df_filtrado["Posição"], errors="coerce")

colunas_layout = [
    "Edital", "Função", "Grupo", "Posição", "Candidato",
    "Titulação", "Status", "Data convocação", "Prazo para convocação",
    "Validade pagamento bolsa", "Obs"
]

colunas_existentes = [col for col in colunas_layout if col in df_filtrado.columns]

if "Posição" in colunas_existentes:
    df_mostrar = df_filtrado.sort_values(by="Posição", na_position="last")[colunas_existentes].copy()
else:
    df_mostrar = df_filtrado[colunas_existentes].copy()

st.caption(f"📊 Mostrando {len(df_mostrar)} registro(s)")
st.dataframe(df_mostrar, use_container_width=True)