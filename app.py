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

def total_geral(funcionario_id, ano):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(diarias), 0)
        FROM viagens
        WHERE funcionario_id = %s AND ano_referencia = %s
    """, (funcionario_id, ano))
    total = cur.fetchone()[0]
    conn.close()
    return total

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

def historico_viagens():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT f.nome, v.data_inicio, v.data_fim, v.natureza,
               v.diarias, v.autorizado_por, v.justificativa
        FROM viagens v
        JOIN funcionarios f ON f.id = v.funcionario_id
        ORDER BY v.data_inicio DESC
    """)
    dados = cur.fetchall()
    conn.close()
    return dados

# ===============================
# UI
# ===============================
st.set_page_config(layout="wide")
st.title("Controle de Diárias")

tabs = st.tabs(["Cadastro", "Viagens", "Simulação", "Dashboard", "Histórico"])

# ===============================
# ABA 1 - CADASTRO
# ===============================
with tabs[0]:
    st.header("Cadastro de Funcionário")

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
        st.success("Cadastrado!")
        st.rerun()

# ===============================
# ABA 2 - VIAGENS
# ===============================
with tabs[1]:
    st.header("Registrar Viagem")

    funcionarios = listar_funcionarios()
    opcoes = {f[1]: f[0] for f in funcionarios}

    nome_sel = st.selectbox("Funcionário", list(opcoes.keys()))
    funcionario_id = opcoes[nome_sel]

    inicio = st.datetime_input("Data início")
    fim = st.datetime_input("Data fim")

    natureza = st.selectbox("Natureza", ["Operacional", "Administrativa"])

    autorizado = st.text_input("Autorizado por")
    justificativa = st.text_area("Justificativa")

    if st.button("Salvar Viagem"):
        diarias = calcular_diarias(inicio, fim)
        total_final = total_geral(funcionario_id, inicio.year) + diarias

        if total_final >= 70 and (not autorizado or not justificativa):
            st.error("Necessita autorização")
        else:
            conn = conectar()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO viagens (
                    funcionario_id, data_inicio, data_fim,
                    natureza, diarias, ano_referencia,
                    autorizado_por, justificativa
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                funcionario_id, inicio, fim, natureza,
                diarias, inicio.year, autorizado, justificativa
            ))

            conn.commit()
            conn.close()
            st.success("Salvo!")

# ===============================
# ABA 3 - SIMULAÇÃO
# ===============================
with tabs[2]:
    st.header("Simulação de Missão")

    inicio = st.datetime_input("Início da missão")
    fim = st.datetime_input("Fim da missão")

    if st.button("Simular"):
        diarias = calcular_diarias(inicio, fim)
        dados = resumo_funcionarios(inicio.year)

        resultado = []
        for _, nome, setor, qual, total in dados:
            total_final = float(total) + diarias

            if total_final >= 70:
                status = "🔴 BLOQUEADO"
            elif total_final >= 60:
                status = "🟡 RISCO"
            else:
                status = "🟢 OK"

            resultado.append([nome, qual, total, total_final, status])

        df = pd.DataFrame(resultado, columns=[
            "Nome", "Qualificação", "Atual", "Após Missão", "Status"
        ])

        st.dataframe(df)

# ===============================
# ABA 4 - DASHBOARD
# ===============================
with tabs[3]:
    st.header("Dashboard")

    ano = st.number_input("Ano", value=datetime.now().year)
    dados = resumo_funcionarios(ano)

    if dados:
        df = pd.DataFrame(dados, columns=[
            "ID", "Nome", "Setor", "Qualificação", "Diárias"
        ])

        st.bar_chart(df.set_index("Nome")["Diárias"])

# ===============================
# ABA 5 - HISTÓRICO
# ===============================
with tabs[4]:
    st.header("Histórico")

    df = pd.DataFrame(historico_viagens(), columns=[
        "Funcionário", "Início", "Fim",
        "Natureza", "Diárias", "Autorizado", "Justificativa"
    ])

    st.dataframe(df)
