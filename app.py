import streamlit as st
import psycopg2
from datetime import datetime

# ===== CONFIG =====
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
# REGRAS DE NEGÓCIO
# ===============================
def calcular_diarias(inicio, fim):
    dias = (fim.date() - inicio.date()).days + 1

    if fim.hour < 12:
        return dias + 0.5
    else:
        return dias


# ===============================
# FUNÇÕES DE BANCO
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


# ===============================
# INTERFACE
# ===============================
st.title("Controle de Diárias")

# ===============================
# CADASTRO FUNCIONÁRIO
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

if funcionarios:
    opcoes = {nome: id for id, nome in funcionarios}

    nome_selecionado = st.selectbox("Funcionário", list(opcoes.keys()))
    funcionario_id = opcoes[nome_selecionado]
else:
    st.warning("Nenhum funcionário cadastrado")
    st.stop()


inicio = st.datetime_input("Data início")
fim = st.datetime_input("Data fim")

natureza = st.selectbox("Natureza", ["Operacional", "Administrativa"])


# ===============================
# CÁLCULO + SIMULAÇÃO
# ===============================
if st.button("Calcular Diárias"):
    if fim < inicio:
        st.error("Data fim não pode ser menor que data início")
    else:
        diarias = calcular_diarias(inicio, fim)
        total_atual = total_geral(funcionario_id, inicio.year)
        total_final = total_atual + diarias

        st.subheader("Simulação")

        st.info(f"Diárias da missão: {diarias}")
        st.info(f"Total atual no ano: {total_atual}")

        if total_final >= 70:
            st.error(f"Total após missão: {total_final} → NECESSITA AUTORIZAÇÃO")
        elif total_final >= 60:
            st.warning(f"Total após missão: {total_final} → ATENÇÃO")
        else:
            st.success(f"Total após missão: {total_final}")


# ===============================
# SALVAR VIAGEM
# ===============================
if st.button("Salvar Viagem"):
    if fim < inicio:
        st.error("Data fim inválida")
    else:
        conn = conectar()
        cur = conn.cursor()

        diarias = calcular_diarias(inicio, fim)
        total_atual = total_geral(funcionario_id, inicio.year)
        total_final = total_atual + diarias

        # 🚨 BLOQUEIO AUTOMÁTICO
        if total_final >= 70:
            st.error("Viagem não pode ser salva sem autorização (>=70 diárias)")
        else:
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
    st.write(f"{nat}: {total} diárias")

st.subheader("Total Geral")
st.write(total_geral(funcionario_id, inicio.year))
