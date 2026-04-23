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
        SELECT f.nome, COALESCE(SUM(v.diarias), 0) AS total
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

def historico_viagens(funcionario_id=None):
    conn = conectar()
    cur = conn.cursor()

    if funcionario_id:
        cur.execute("""
            SELECT f.nome, v.data_inicio, v.data_fim, v.natureza,
                   v.diarias, v.autorizado_por, v.justificativa
            FROM viagens v
            JOIN funcionarios f ON f.id = v.funcionario_id
            WHERE f.id = %s
            ORDER BY v.data_inicio DESC
        """, (funcionario_id,))
    else:
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
# NOVA VIAGEM
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

if st.button("Simular"):
    if fim < inicio:
        st.error("Data inválida")
    else:
        diarias = calcular_diarias(inicio, fim)
        total_atual = total_geral(funcionario_id, inicio.year)
        total_final = total_atual + diarias

        st.info(f"Diárias: {diarias} | Total atual: {total_atual}")

        if total_final >= 70:
            st.error("Necessita autorização")
        elif total_final >= 60:
            st.warning("Atenção")
        else:
            st.success("OK")

st.subheader("Autorização")
autorizado_por = st.text_input("Autorizado por")
justificativa = st.text_area("Justificativa")

if st.button("Salvar Viagem"):
    diarias = calcular_diarias(inicio, fim)
    total_final = total_geral(funcionario_id, inicio.year) + diarias

    if total_final >= 70 and (not autorizado_por or not justificativa):
        st.error("Preencha autorização e justificativa")
        st.stop()

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
        diarias, inicio.year, autorizado_por, justificativa
    ))

    conn.commit()
    conn.close()

    st.success("Viagem salva!")
    st.rerun()

# ===============================
# RESUMO
# ===============================
st.header("Resumo do Funcionário")

for nat, total in total_por_natureza(funcionario_id, inicio.year):
    st.write(f"{nat}: {total} diárias")

st.write(f"Total: {total_geral(funcionario_id, inicio.year)} diárias")

# ===============================
# DASHBOARD
# ===============================
st.header("Dashboard")

ano = st.number_input("Ano", value=datetime.now().year)
dados = resumo_funcionarios(ano)

if dados:
    total_funcionarios = len(dados)
    acima_70 = sum(1 for _, t in dados if float(t) >= 70)
    alerta = sum(1 for _, t in dados if 60 <= float(t) < 70)
    ok = sum(1 for _, t in dados if float(t) < 60)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Funcionários", total_funcionarios)
    col2.metric("🔴 Bloqueados", acima_70)
    col3.metric("🟡 Atenção", alerta)
    col4.metric("🟢 OK", ok)

    df = pd.DataFrame(dados, columns=["Funcionário", "Diárias"])
    st.bar_chart(df.set_index("Funcionário"))

# ===============================
# HISTÓRICO + AUTORIZAÇÕES
# ===============================
st.header("Histórico de Viagens")

filtro = st.selectbox(
    "Filtrar por funcionário",
    ["Todos"] + [f[0] for f in funcionarios]
)

if filtro == "Todos":
    dados_hist = historico_viagens()
else:
    id_filtrado = next(id for nome, id in opcoes.items() if nome == filtro)
    dados_hist = historico_viagens(id_filtrado)

if dados_hist:
    df_hist = pd.DataFrame(dados_hist, columns=[
        "Funcionário", "Início", "Fim", "Natureza",
        "Diárias", "Autorizado por", "Justificativa"
    ])

    st.dataframe(df_hist)

    st.subheader("Autorizações (>70)")

    df_aut = df_hist[df_hist["Autorizado por"].notnull()]

    if not df_aut.empty:
        st.dataframe(df_aut)
    else:
        st.info("Nenhuma autorização registrada")

else:
    st.info("Sem histórico")
