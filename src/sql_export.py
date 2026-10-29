"""Write a portable SQLite SQL seed script from generated CSV table records."""
import sqlite3

def export_sql(tables, target):
    conn=sqlite3.connect(":memory:")
    for name,rows in tables.items():
        if not rows: continue
        cols=list(rows[0])
        conn.execute(f'CREATE TABLE "{name}" ('+", ".join(f'"{col}" TEXT' for col in cols)+")")
        conn.executemany(f'INSERT INTO "{name}" VALUES ('+", ".join("?" for _ in cols)+")",[tuple(str(row[c]) for c in cols) for row in rows])
    script="\n".join(conn.iterdump())+"\n"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(script,encoding="utf-8")
    conn.close()
