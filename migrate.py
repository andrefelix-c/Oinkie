import os
from sqlalchemy import text
from database import engine, init_db

def migrate():
    print("Executando init_db()...")
    init_db()
    
    print("Iniciando alterações nas tabelas...")
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE gastos ADD COLUMN forma_pagamento VARCHAR;"))
            print("Coluna forma_pagamento adicionada em gastos.")
        except Exception as e:
            print("Erro em gastos (pode já existir):", e)
            
        try:
            conn.execute(text("ALTER TABLE gastos_recorrentes ADD COLUMN forma_pagamento VARCHAR;"))
            print("Coluna forma_pagamento adicionada em gastos_recorrentes.")
        except Exception as e:
            print("Erro em gastos_recorrentes (pode já existir):", e)
    
    print("Migração finalizada.")

if __name__ == "__main__":
    migrate()
