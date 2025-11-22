import sqlite3

db_path = "instance/database.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

query = """
SELECT data_preenchimento_brt, veiculo_id, checklist_id, motorista_id, COUNT(*)
FROM checklist_preenchido
GROUP BY data_preenchimento_brt, veiculo_id, checklist_id, motorista_id
HAVING COUNT(*) > 1;
"""
cursor.execute(query)

rows = cursor.fetchall()
if rows:
    print("Ainda existem duplicados:")
    for row in rows:
        print(row)
else:
    print("Nenhum duplicado encontrado! ✅")

conn.close()
