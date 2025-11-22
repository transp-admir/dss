import sqlite3

conn = sqlite3.connect("instance/database.db")
cursor = conn.cursor()

query = """
SELECT id, data_preenchimento_brt, veiculo_id, checklist_id, motorista_id
FROM checklist_preenchido
WHERE veiculo_id = 1 AND checklist_id = 2 AND motorista_id = 7;
"""
cursor.execute(query)
rows = cursor.fetchall()
for row in rows:
    print(row)

conn.close()
