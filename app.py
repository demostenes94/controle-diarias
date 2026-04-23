import streamlit as st
import psycopg2
from datetime import datetime

# ===== CONFIG (COLOQUE SUA SENHA) =====
DB_HOST = "db.zwmktbajouwpgrxzfnww.supabase.co"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "projetodiarias"
DB_PORT = "5432"


def conectar():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT,
        sslmode="require"
    )


def calcular_diarias(inicio, fim):
    dias = (fim.date() - inicio.date()).days + 1

    if fim.hour < 12:
        return dias + 0.5
    else:
        return dias


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


# ===============================
# NOVA VIAGEM
# ===============================
st.header("Nova Viagem")

funcionario_id = st.number_input("ID Funcionário", min_value=1)

inicio = st.datetime_input("Data início")
fim = st.datetime_input("Data fim")

natureza = st.selectbox("Natureza", ["Operacional", "Administrativa"])

if st.button("Calcular Diárias"):
    diarias = calcular_diarias(inicio, fim)
    st.info(f"Diárias calculadas: {diarias}")


if st.button("Salvar Viagem"):
    conn = conectar()
    cur = conn.cursor()

    diarias = calcular_diarias(inicio, fim)

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
