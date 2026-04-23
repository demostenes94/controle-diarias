import streamlit as st
import psycopg2
from datetime import datetime
import pandas as pd

# ===============================
# CONFIG
# ===============================
DB_HOST = st.secrets["DB_HOST"]
DB_NAME = st.secrets["DB_NAME"]
DB_USER = st.secrets["DB_USER"]
DB_PASS = st.secrets["DB_PASS"]
DB_PORT = st.secrets["DB_PORT"]

# ===============================
# CONEXÃO
# ===============================
def conectar():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT,
        sslmode="require"
    )

# ===============================
# REGRAS
# ===============================
def calcular_diarias(inicio, fim):
    dias = (fim.date() - inicio.date()).days + 1
    return dias + 0.5 if fim.hour < 12 else dias

# ===============================
# BANCO
# ===============================
def listar_funcionarios():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nome, setor, qualificacao 
        FROM funcionarios
        ORDER BY nome
    """)
    dados = cur.fetchall()
    conn.close()
    return dados

def resumo_funcionarios(ano):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT f.nome, f.setor, f.qualificacao,
               COALESCE(SUM(v.diarias), 0) AS total
        FROM funcionarios f
        LEFT JOIN viagens v 
            ON f.id = v.funcionario_id 
            AND v.ano_referencia = %s
        GROUP BY f.nome, f.setor, f.qualificacao
        ORDER BY total DESC
    """, (ano,))
    dados = cur.fetchall()
    conn.close()
    return dados

# ===============================
# INTERFACE
# ===============================
st.title("Controle de Diárias")

# ===============================
# CADASTRO
# ===============================
st.header("Cadastrar Funcionário")

nome = st.text_input("Nome")
setor = st.text_input("Setor")
supervisor = st.text_input("Supervisor")

qualificacao = st.selectbox(
    "Qualificação",
    ["CC", "AJCC", "COAM", "CTAM"]
)

if st.button("Salvar Funcionário"):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO funcionarios (nome, setor, supervisor, qualificacao)
        VALUES (%s, %s, %s, %s)
    """, (nome, setor, supervisor, qualificacao))

    conn.commit()
    conn.close()

    st.success("Funcionário cadastrado!")
    st.rerun()

# ===============================
# DASHBOARD AVANÇADO
# ===============================
st.header("Dashboard Operacional")

ano = st.number_input("Ano", value=datetime.now().year)

dados = resumo_funcionarios(ano)

if dados:

    df = pd.DataFrame(
        dados,
        columns=["Nome", "Setor", "Qualificação", "Diárias"]
    )

    # ===============================
    # FILTROS
    # ===============================
    st.subheader("Filtros")

    col1, col2, col3 = st.columns(3)

    with col1:
        filtro_nome = st.text_input("Buscar funcionário")

    with col2:
        setores = ["Todos"] + sorted(df["Setor"].dropna().unique().tolist())
        filtro_setor = st.selectbox("Setor", setores)

    with col3:
        qualificacoes = ["Todos"] + sorted(df["Qualificação"].dropna().unique().tolist())
        filtro_qual = st.selectbox("Qualificação", qualificacoes)

    # ===============================
    # APLICAR FILTROS
    # ===============================
    df_filtrado = df.copy()

    if filtro_nome:
        df_filtrado = df_filtrado[df_filtrado["Nome"].str.contains(filtro_nome, case=False)]

    if filtro_setor != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Setor"] == filtro_setor]

    if filtro_qual != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Qualificação"] == filtro_qual]

    # ===============================
    # KPIs DINÂMICOS
    # ===============================
    total_funcionarios = len(df_filtrado)
    acima_70 = (df_filtrado["Diárias"] >= 70).sum()
    alerta = ((df_filtrado["Diárias"] >= 60) & (df_filtrado["Diárias"] < 70)).sum()
    ok = (df_filtrado["Diárias"] < 60).sum()

    if acima_70 > 0:
        st.error(f"{acima_70} acima de 70 diárias")
    elif alerta > 0:
        st.warning(f"{alerta} próximos do limite")
    else:
        st.success("Situação controlada")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Funcionários", total_funcionarios)
    col2.metric("🔴 Bloqueados", acima_70)
    col3.metric("🟡 Atenção", alerta)
    col4.metric("🟢 OK", ok)

    # ===============================
    # GRÁFICO
    # ===============================
    st.subheader("Ranking")

    st.bar_chart(df_filtrado.set_index("Nome")["Diárias"])

    # ===============================
    # TABELA COMPLETA
    # ===============================
    st.subheader("Visão Detalhada")

    st.dataframe(df_filtrado)

else:
    st.info("Sem dados")
