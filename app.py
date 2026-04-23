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
    cur.execute("SELECT id, nome FROM funcionarios ORDER BY nome")
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
    return dados

def resumo_funcionarios(ano):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT f.nome, COALESCE(SUM(v.diarias), 0)
        FROM funcionarios f
        LEFT JOIN viagens v 
            ON f.id = v.funcionario_id 
            AND v.ano_referencia = %s
        GROUP BY f.nome
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

if st.button("Salvar Funcionário"):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO funcionarios (nome, setor, supervisor)
        VALUES (%s, %s, %s)
    """, (nome, setor, supervisor))
    conn.commit()
    conn.close()
    st.success("Funcionário cadastrado!")
    st.rerun()

# ===============================
# VIAGEM + SIMULAÇÃO
# ===============================
st.header("Nova Viagem")

funcionarios = listar_funcionarios()

if not funcionarios:
    st.warning("Nenhum funcionário cadastrado")
    st.stop()

opcoes = {nome: id for id, nome in funcionarios}
nome_sel = st.selectbox("Funcionário", list(opcoes.keys()))
funcionario_id = opcoes[nome_sel]

inicio = st.datetime_input("Data início")
fim = st.datetime_input("Data fim")
natureza = st.selectbox("Natureza", ["Operacional", "Administrativa"])

# ===============================
# SIMULAÇÃO
# ===============================
if st.button("Simular"):
    if fim < inicio:
        st.error("Data inválida")
    else:
        diarias = calcular_diarias(inicio, fim)
        total_atual = total_geral(funcionario_id, inicio.year)
        total_final = total_atual + diarias

        st.subheader("Resultado da Simulação")
        st.info(f"Diárias da missão: {diarias}")
        st.info(f"Total atual: {total_atual}")

        if total_final >= 70:
            st.error(f"{total_final} → BLOQUEADO")
        elif total_final >= 60:
            st.warning(f"{total_final} → ATENÇÃO")
        else:
            st.success(f"{total_final} → OK")

# ===============================
# SALVAR
# ===============================
if st.button("Salvar Viagem"):
    if fim < inicio:
        st.error("Data inválida")
    else:
        diarias = calcular_diarias(inicio, fim)
        total_atual = total_geral(funcionario_id, inicio.year)
        total_final = total_atual + diarias

        if total_final >= 70:
            st.error("Necessita autorização (>=70 diárias)")
        else:
            conn = conectar()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO viagens (
                    funcionario_id, data_inicio, data_fim,
                    natureza, diarias, ano_referencia
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                funcionario_id,
                inicio,
                fim,
                natureza,
                diarias,
                inicio.year
            ))

            conn.commit()
            conn.close()

            st.success("Viagem salva!")
            st.rerun()

# ===============================
# RESUMO
# ===============================
st.header("Resumo do Funcionário")

totais = total_por_natureza(funcionario_id, inicio.year)

for nat, total in totais:
    st.write(f"{nat}: {total}")

st.subheader("Total Geral")
st.write(total_geral(funcionario_id, inicio.year))

# ===============================
# DASHBOARD
# ===============================
st.header("Dashboard")

ano = st.number_input("Ano", value=datetime.now().year)

dados = resumo_funcionarios(ano)

if dados:
    df = pd.DataFrame(dados, columns=["Funcionário", "Diárias"])
    st.bar_chart(df.set_index("Funcionário"))

    st.subheader("Status")

    for nome, total in dados:
        total = float(total)

        if total >= 70:
            st.error(f"{nome}: {total} → BLOQUEADO")
        elif total >= 60:
            st.warning(f"{nome}: {total} → ATENÇÃO")
        else:
            st.success(f"{nome}: {total} → OK")
else:
    st.info("Sem dados para o ano")
