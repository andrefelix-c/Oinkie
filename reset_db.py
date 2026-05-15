from database import Base, engine, init_db

def resetar_banco():
    print("⚠️ ATENÇÃO: Esta ação irá APAGAR TODOS OS DADOS de todas as tabelas (usuários, gastos, cartões).")
    resposta = input("Tem certeza que deseja continuar? (s/n): ")
    
    if resposta.lower() == 's':
        print("Apagando tabelas...")
        Base.metadata.drop_all(engine)
        print("Recriando tabelas...")
        init_db()
        print("✅ Banco de dados zerado com sucesso!")
    else:
        print("Operação cancelada. Nenhum dado foi apagado.")

if __name__ == "__main__":
    resetar_banco()
