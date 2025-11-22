import sqlite3

# Caminho para o banco de dados
db_path = "instance/database.db"

# Conectar ao banco
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Executar o DELETE para remover duplicados
delete_query = """
DELETE FROM checklist_preenchido
WHERE id NOT IN (
    SELECT MIN(id)
    FROM checklist_preenchido
    GROUP BY data_preenchimento_brt, veiculo_id, checklist_id, motorista_id
);
"""
cursor.execute(delete_query)

# Salvar alterações
conn.commit()
conn.close()

print("Duplicados removidos com sucesso!")
