import sqlite3
import json

c = sqlite3.connect(r"E:/MILA GOLD/n8n-data/.n8n/database.sqlite")
for name, nodes_json in c.execute(
    "SELECT name, nodes FROM workflow_entity WHERE name LIKE 'MILA %' ORDER BY name"
):
    types = [n["type"].split(".")[-1] for n in json.loads(nodes_json)]
    print(name, "->", types)
