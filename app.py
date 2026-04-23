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
        SELECT f.id, f.nome, f.setor, f.qualificacao,
               COALESCE(SUM(v.diarias), 0) AS total
        FROM funcionarios f
        LEFT JOIN viagens v 
            ON f.id = v.funcionario_id 
            AND v.ano_referencia = %s
        GROUP BY f.id, f.nome, f.setor, f.qualificacao
    """, (ano,))
    dados = cur.fetchall()
    conn.close()
    return dados

def total_por_natureza(funcionario_id, ano):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT natureza, COALESCE(SUM(diarias), 0)
        FROM viagens
        WHERE funcionario_id = %s AND ano_referencia = %s
        GROUP BY natureza
    """, (funcionario_id, ano))
    dados = cur.fetchall()
    conn.close()
    return dict(dados)

# ===============================
# UI
# ===============================
st.set_page_config(layout="wide")
st.title("Controle de Diárias")

tabs = st.tabs(["Cadastro", "Viagens", "Simulação", "Dashboard", "Histórico"])

# ===============================
# CADASTRO
# ===============================
with tabs[0]:
    st.header("Cadastro")

    nome = st.text_input("Nome")
    setor = st.text_input("Setor")
    supervisor = st.text_input("Supervisor")

    qualificacao = st.selectbox("Qualificação", ["CC", "AJCC", "COAM", "CTAM"])

    if st.button("Salvar Funcionário"):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO funcionarios (nome, setor, supervisor, qualificacao)
            VALUES (%s, %s, %s, %s)
        """, (nome, setor, supervisor, qualificacao))
        conn.commit()
        conn.close()
        st.success("Cadastrado!")
        st.rerun()

# ===============================
# SIMULAÇÃO AVANÇADA
# ===============================
with tabs[2]:
    st.header("Simulação de Missão")

    funcionarios = listar_funcionarios()
    nomes = [f[1] for f in funcionarios]

    selecionados = st.multiselect("Selecionar equipe", nomes)

    inicio = st.datetime_input("Início da missão")
    fim = st.datetime_input("Fim da missão")

    natureza = st.selectbox("Natureza da missão", ["Operacional", "Administrativa"])

    if st.button("Simular"):

        if not selecionados:
            st.warning("Selecione pelo menos um funcionário")
        elif fim < inicio:
            st.error("Data inválida")
        else:

            diarias = calcular_diarias(inicio, fim)
            dados = resumo_funcionarios(inicio.year)

            df_base = pd.DataFrame(dados, columns=[
                "ID", "Nome", "Setor", "Qualificação", "Atual"
            ])

            df_base = df_base[df_base["Nome"].isin(selecionados)]

            resultado = []

            for _, row in df_base.iterrows():
                total = float(row["Atual"])
                total_final = total + diarias

                natureza_atual = total_por_natureza(row["ID"], inicio.year)

                oper = natureza_atual.get("Operacional", 0)
                adm = natureza_atual.get("Administrativa", 0)

                if natureza == "Operacional":
                    oper += diarias
                else:
                    adm += diarias

                if total_final >= 70:
                    status = "🔴 BLOQUEADO"
                elif total_final >= 60:
                    status = "🟡 RISCO"
                else:
                    status = "🟢 OK"

                resultado.append([
                    row["Nome"],
                    row["Qualificação"],
                    total,
                    total_final,
                    oper,
                    adm,
                    status
                ])

            df = pd.DataFrame(resultado, columns=[
                "Nome", "Qualificação",
                "Atual", "Após Missão",
                "Operacional", "Administrativa",
                "Status"
            ])

            st.dataframe(df)

# ===============================
# DASHBOARD COM FILTRO
# ===============================
with tabs[3]:
    st.header("Dashboard")

    ano = st.number_input("Ano", value=datetime.now().year)
    dados = resumo_funcionarios(ano)

    if dados:
        df = pd.DataFrame(dados, columns=[
            "ID", "Nome", "Setor", "Qualificação", "Diárias"
        ])

        filtro_qual = st.selectbox(
            "Filtrar por qualificação",
            ["Todos"] + sorted(df["Qualificação"].dropna().unique())
        )

        if filtro_qual != "Todos":
            df = df[df["Qualificação"] == filtro_qual]

        st.bar_chart(df.set_index("Nome")["Diárias"])
        st.dataframe(df)

# ===============================
# HISTÓRICO
# ===============================
with tabs[4]:
    st.header("Histórico")

    conn = conectar()
    df = pd.read_sql("""
        SELECT f.nome, v.data_inicio, v.data_fim,
               v.natureza, v.diarias,
               v.autorizado_por, v.justificativa
        FROM viagens v
        JOIN funcionarios f ON f.id = v.funcionario_id
        ORDER BY v.data_inicio DESC
    """, conn)

    conn.close()

    st.dataframe(df)
