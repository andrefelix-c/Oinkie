import os
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, extract, or_
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.environ["DATABASE_URL"])
Session = sessionmaker(bind=engine)
Base = declarative_base()

FUSO_BR = timezone(timedelta(hours=-3))

def agora_br():
    return datetime.now(FUSO_BR).replace(tzinfo=None)


class Usuario(Base):
    __tablename__ = "usuarios"

    telegram_user_id  = Column(String, primary_key=True)
    telegram_username = Column(String, nullable=True)
    permitido         = Column(Boolean, default=False)
    criado_em         = Column(DateTime, default=agora_br)


class Cartao(Base):
    __tablename__ = "cartoes"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id  = Column(String, nullable=False)
    nome              = Column(String, nullable=False)
    dia_fechamento    = Column(Integer, nullable=False)
    dia_vencimento    = Column(Integer, nullable=False)
    criado_em         = Column(DateTime, default=agora_br)


class Gasto(Base):
    __tablename__ = "gastos"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id  = Column(String, nullable=False)
    telegram_username = Column(String, nullable=True)
    data_hora         = Column(DateTime, nullable=True)
    descricao         = Column(String, nullable=True)
    estabelecimento   = Column(String, nullable=True)
    valor_total       = Column(Float, nullable=False)
    valor_parcela     = Column(Float, nullable=True)
    moeda             = Column(String, default="BRL")
    categoria         = Column(String, nullable=True)
    quem_gastou       = Column(String, nullable=True)
    forma_pagamento   = Column(String, nullable=True)
    cartao            = Column(String, nullable=True)
    parcelado         = Column(Boolean, default=False)
    num_parcelas      = Column(Integer, nullable=True)
    observacoes       = Column(Text, nullable=True)
    criado_em         = Column(DateTime, default=agora_br)


class GastoRecorrente(Base):
    __tablename__ = "gastos_recorrentes"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id  = Column(String, nullable=False)
    telegram_username = Column(String, nullable=True)
    descricao         = Column(String, nullable=True)
    estabelecimento   = Column(String, nullable=True)
    valor             = Column(Float, nullable=False)
    moeda             = Column(String, default="BRL")
    categoria         = Column(String, nullable=True)
    quem_gastou       = Column(String, nullable=True)
    forma_pagamento   = Column(String, nullable=True)
    cartao            = Column(String, nullable=True)
    dia_cobranca      = Column(Integer, nullable=True)
    ativo             = Column(Boolean, default=True)
    observacoes       = Column(Text, nullable=True)
    criado_em         = Column(DateTime, default=agora_br)


def init_db():
    Base.metadata.create_all(engine)


def obter_ou_criar_usuario(user_id: str, username: str) -> bool:
    session = Session()
    try:
        user_id_str = str(user_id)
        usuario = session.query(Usuario).filter(Usuario.telegram_user_id == user_id_str).first()
        if not usuario:
            usuario = Usuario(
                telegram_user_id=user_id_str,
                telegram_username=username,
                permitido=False
            )
            session.add(usuario)
            session.commit()
            return False
        return usuario.permitido
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def obter_pessoas_registradas(user_id: str) -> list[str]:
    session = Session()
    try:
        user_id_str = str(user_id)
        pessoas_set = set()

        # Pessoas de quem_gastou nos Gastos
        gastos_quem = session.query(Gasto.quem_gastou).filter(
            Gasto.telegram_user_id == user_id_str,
            Gasto.quem_gastou.isnot(None),
            Gasto.quem_gastou != "",
            Gasto.quem_gastou != "Eu"
        ).all()
        
        for (quem,) in gastos_quem:
            if quem:
                for p in quem.split(","):
                    p = p.strip()
                    if p.lower() != "eu":
                        pessoas_set.add(p.title())

        # Pessoas de estabelecimentos onde categoria = Terceiros/Dívidas
        gastos_est = session.query(Gasto.estabelecimento).filter(
            Gasto.telegram_user_id == user_id_str,
            Gasto.categoria == "Terceiros/Dívidas",
            Gasto.estabelecimento.isnot(None),
            Gasto.estabelecimento != ""
        ).all()
        
        for (est,) in gastos_est:
            if est:
                pessoas_set.add(est.strip().title())

        # Pessoas de quem_gastou nos Gastos Recorrentes
        recorrentes_quem = session.query(GastoRecorrente.quem_gastou).filter(
            GastoRecorrente.telegram_user_id == user_id_str,
            GastoRecorrente.quem_gastou.isnot(None),
            GastoRecorrente.quem_gastou != "",
            GastoRecorrente.quem_gastou != "Eu"
        ).all()
        
        for (quem,) in recorrentes_quem:
            if quem:
                for p in quem.split(","):
                    p = p.strip()
                    if p.lower() != "eu":
                        pessoas_set.add(p.title())

        # Pessoas de estabelecimentos em Recorrentes onde categoria = Terceiros/Dívidas
        recorrentes_est = session.query(GastoRecorrente.estabelecimento).filter(
            GastoRecorrente.telegram_user_id == user_id_str,
            GastoRecorrente.categoria == "Terceiros/Dívidas",
            GastoRecorrente.estabelecimento.isnot(None),
            GastoRecorrente.estabelecimento != ""
        ).all()
        
        for (est,) in recorrentes_est:
            if est:
                pessoas_set.add(est.strip().title())

        return sorted(list(pessoas_set))
    except Exception as e:
        return []
    finally:
        session.close()

def salvar_gasto_unico(gasto: dict, user_id: str, username: str) -> int:
    session = Session()
    try:
        registro = Gasto(
            telegram_user_id  = str(user_id),
            telegram_username = username,
            data_hora         = datetime.fromisoformat(gasto["data_hora"]) if gasto.get("data_hora") else None,
            descricao         = gasto.get("descricao"),
            estabelecimento   = gasto.get("estabelecimento"),
            valor_total       = gasto.get("valor"),
            moeda             = gasto.get("moeda", "BRL"),
            categoria         = gasto.get("categoria"),
            quem_gastou       = gasto.get("quem_gastou"),
            forma_pagamento   = gasto.get("forma_pagamento"),
            cartao            = gasto.get("cartao"),
            parcelado         = False,
            observacoes       = gasto.get("observacoes"),
        )
        session.add(registro)
        session.commit()
        return registro.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def salvar_gasto_parcelado(gasto: dict, user_id: str, username: str) -> list[int]:
    session = Session()
    try:
        num_parcelas  = gasto.get("num_parcelas", 1)
        valor_total   = gasto.get("valor")
        valor_parcela = gasto.get("valor_parcela") or round(valor_total / num_parcelas, 2)
        data_base     = datetime.fromisoformat(gasto["data_hora"]) if gasto.get("data_hora") else agora_br()

        registros = []
        for i in range(num_parcelas):
            registro = Gasto(
                telegram_user_id  = str(user_id),
                telegram_username = username,
                data_hora         = data_base + relativedelta(months=i),
                descricao         = f"{gasto.get('descricao')} ({i+1}/{num_parcelas})",
                estabelecimento   = gasto.get("estabelecimento"),
                valor_total       = valor_parcela,
                moeda             = gasto.get("moeda", "BRL"),
                categoria         = gasto.get("categoria"),
                quem_gastou       = gasto.get("quem_gastou"),
                forma_pagamento   = gasto.get("forma_pagamento"),
                cartao            = gasto.get("cartao"),
                parcelado         = True,
                num_parcelas      = num_parcelas,
                observacoes       = gasto.get("observacoes"),
            )
            session.add(registro)
            registros.append(registro)

        session.flush()
        session.commit()
        return [r.id for r in registros]
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def salvar_gasto_recorrente(gasto: dict, user_id: str, username: str) -> int:
    session = Session()
    try:
        registro = GastoRecorrente(
            telegram_user_id  = str(user_id),
            telegram_username = username,
            descricao         = gasto.get("descricao"),
            estabelecimento   = gasto.get("estabelecimento"),
            valor             = gasto.get("valor"),
            moeda             = gasto.get("moeda", "BRL"),
            categoria         = gasto.get("categoria"),
            quem_gastou       = gasto.get("quem_gastou"),
            forma_pagamento   = gasto.get("forma_pagamento"),
            cartao            = gasto.get("cartao"),
            dia_cobranca      = gasto.get("dia_cobranca"),
            observacoes       = gasto.get("observacoes"),
        )
        session.add(registro)
        session.commit()
        return registro.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def deletar_gasto(tipo: str, ids: list[int]):
    session = Session()
    try:
        if tipo == "recorrente":
            session.query(GastoRecorrente).filter(GastoRecorrente.id.in_(ids)).delete(synchronize_session=False)
        else:
            session.query(Gasto).filter(Gasto.id.in_(ids)).delete(synchronize_session=False)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def adicionar_cartao(user_id: str, nome: str, dia_fechamento: int, dia_vencimento: int) -> int:
    session = Session()
    try:
        cartao = Cartao(
            telegram_user_id=str(user_id),
            nome=nome,
            dia_fechamento=dia_fechamento,
            dia_vencimento=dia_vencimento
        )
        session.add(cartao)
        session.commit()
        return cartao.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def obter_cartoes(user_id: str):
    session = Session()
    try:
        return session.query(Cartao).filter(Cartao.telegram_user_id == str(user_id)).all()
    finally:
        session.close()

def remover_cartao(cartao_id: int, user_id: str) -> bool:
    session = Session()
    try:
        resultado = session.query(Cartao).filter(
            Cartao.id == cartao_id, 
            Cartao.telegram_user_id == str(user_id)
        ).delete()
        session.commit()
        return resultado > 0
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def gerar_relatorio_mensal(user_id: str, ano: int, mes: int) -> dict:
    session = Session()
    try:
        user_id_str = str(user_id)
        
        # Obter os cartões para regras de fechamento
        cartoes = session.query(Cartao).filter(Cartao.telegram_user_id == user_id_str).all()
        cartoes_dict = {c.nome.lower(): c for c in cartoes}

        # Ampliar a janela de busca para o mês anterior e o próximo (para cobrir datas de fechamento)
        data_inicio_busca = datetime(ano, mes, 1) - relativedelta(months=1)
        data_fim_busca = datetime(ano, mes, 1) + relativedelta(months=2)
        
        gastos_brutos = session.query(Gasto).filter(
            Gasto.telegram_user_id == user_id_str,
            Gasto.data_hora >= data_inicio_busca,
            Gasto.data_hora < data_fim_busca
        ).all()
        
        gastos_mes = []
        for g in gastos_brutos:
            rm, ry = g.data_hora.month, g.data_hora.year
            if g.forma_pagamento and g.forma_pagamento.lower() in ["crédito", "credito"] and g.cartao:
                c = cartoes_dict.get(g.cartao.lower())
                if c:
                    if g.data_hora.day < c.dia_fechamento:
                        rm -= 1
                        if rm == 0:
                            rm = 12
                            ry -= 1
            
            if rm == mes and ry == ano:
                gastos_mes.append(g)
        
        # Filtrar gastos recorrentes ativos
        recorrentes = session.query(GastoRecorrente).filter(
            GastoRecorrente.telegram_user_id == user_id_str,
            GastoRecorrente.ativo == True
        ).all()
        
        relatorio = {
            "total_gasto": 0.0,
            "por_categoria": {},
            "por_cartao": {},
            "dividas": {},       # O que eu devo (categoria Terceiros/Dívidas)
            "a_receber": {}      # O que me devem (quem_gastou != Eu)
        }
        
        def processar_item(valor, categoria, cartao, forma_pagamento, estabelecimento, quem_gastou):
            if valor is None: return
            
            valor_meu = valor
            
            if quem_gastou:
                pessoas = [p.strip() for p in quem_gastou.split(",")]
                if pessoas:
                    valor_por_pessoa = valor / len(pessoas)
                    valor_meu = 0
                    for p in pessoas:
                        if p.lower() not in ["", "eu"]:
                            relatorio["a_receber"][p] = relatorio["a_receber"].get(p, 0.0) + valor_por_pessoa
                        else:
                            valor_meu += valor_por_pessoa
                            
            relatorio["total_gasto"] += valor_meu
            
            cat = categoria or "Sem Categoria"
            relatorio["por_categoria"][cat] = relatorio["por_categoria"].get(cat, 0.0) + valor_meu
            
            if forma_pagamento and forma_pagamento.lower() in ["crédito", "credito"] and cartao:
                relatorio["por_cartao"][cartao] = relatorio["por_cartao"].get(cartao, 0.0) + valor_meu
                
            if categoria == "Terceiros/Dívidas":
                pessoa = estabelecimento or "Desconhecido"
                relatorio["dividas"][pessoa] = relatorio["dividas"].get(pessoa, 0.0) + valor
                
        for g in gastos_mes:
            processar_item(g.valor_total, g.categoria, g.cartao, g.forma_pagamento, g.estabelecimento, g.quem_gastou)
            
        for r in recorrentes:
            processar_item(r.valor, r.categoria, r.cartao, r.forma_pagamento, r.estabelecimento, r.quem_gastou)
            
        return relatorio
    finally:
        session.close()

def obter_devedores_detalhado(user_id: str, ano: int, mes: int) -> dict:
    session = Session()
    try:
        user_id_str = str(user_id)
        
        cartoes = session.query(Cartao).filter(Cartao.telegram_user_id == user_id_str).all()
        cartoes_dict = {c.nome.lower(): c for c in cartoes}

        data_inicio_busca = datetime(ano, mes, 1) - relativedelta(months=1)
        data_fim_busca = datetime(ano, mes, 1) + relativedelta(months=2)
        
        gastos_brutos = session.query(Gasto).filter(
            Gasto.telegram_user_id == user_id_str,
            Gasto.data_hora >= data_inicio_busca,
            Gasto.data_hora < data_fim_busca
        ).all()
        
        gastos_mes = []
        for g in gastos_brutos:
            rm, ry = g.data_hora.month, g.data_hora.year
            if g.forma_pagamento and g.forma_pagamento.lower() in ["crédito", "credito"] and g.cartao:
                c = cartoes_dict.get(g.cartao.lower())
                if c:
                    if g.data_hora.day < c.dia_fechamento:
                        rm -= 1
                        if rm == 0:
                            rm = 12
                            ry -= 1
            
            if rm == mes and ry == ano:
                gastos_mes.append(g)
        
        recorrentes = session.query(GastoRecorrente).filter(
            GastoRecorrente.telegram_user_id == user_id_str,
            GastoRecorrente.ativo == True
        ).all()
        
        devedores = {}
        
        def add_detail(pessoa, desc, valor, data, tipo):
            if pessoa not in devedores:
                devedores[pessoa] = {"total": 0.0, "itens": []}
            devedores[pessoa]["total"] += valor
            devedores[pessoa]["itens"].append({
                "descricao": desc,
                "valor": valor,
                "data": data,
                "tipo": tipo
            })

        for g in gastos_mes:
            quem = g.quem_gastou
            if quem:
                pessoas = [p.strip() for p in quem.split(",")]
                if pessoas:
                    valor_pp = g.valor_total / len(pessoas)
                    for p in pessoas:
                        if p.lower() not in ["", "eu"]:
                            tipo = "parcelado" if g.parcelado else "unico"
                            add_detail(p, g.descricao, valor_pp, g.data_hora, tipo)
                            
        for r in recorrentes:
            quem = r.quem_gastou
            if quem:
                pessoas = [p.strip() for p in quem.split(",")]
                if pessoas:
                    valor_pp = r.valor / len(pessoas)
                    for p in pessoas:
                        if p.lower() not in ["", "eu"]:
                            add_detail(p, r.descricao, valor_pp, None, "recorrente")
                            
        return devedores
    finally:
        session.close()
def obter_gastos_parcelados_ativos(user_id: str):
    session = Session()
    try:
        user_id_str = str(user_id)
        agora = agora_br()
        mes_atual = agora.month
        ano_atual = agora.year
        
        data_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - relativedelta(months=2)
        
        cartoes = session.query(Cartao).filter(Cartao.telegram_user_id == user_id_str).all()
        cartoes_dict = {c.nome.lower(): c for c in cartoes}
        
        gastos_brutos = session.query(Gasto).filter(
            Gasto.telegram_user_id == user_id_str,
            Gasto.parcelado == True,
            Gasto.data_hora >= data_inicio,
            or_(
                Gasto.quem_gastou == None,
                Gasto.quem_gastou == "",
                Gasto.quem_gastou.ilike("eu")
            )
        ).order_by(Gasto.data_hora).all()
        
        gastos_ativos = []
        for g in gastos_brutos:
            rm, ry = g.data_hora.month, g.data_hora.year
            
            # Apenas considera a parcela pendente se for do mês atual ou futuro
            if (ry > ano_atual) or (ry == ano_atual and rm >= mes_atual):
                gastos_ativos.append(g)
                
        return gastos_ativos
    finally:
        session.close()

def obter_gastos_recorrentes_ativos(user_id: str):
    session = Session()
    try:
        return session.query(GastoRecorrente).filter(
            GastoRecorrente.telegram_user_id == str(user_id),
            GastoRecorrente.ativo == True,
            or_(
                GastoRecorrente.quem_gastou == None,
                GastoRecorrente.quem_gastou == "",
                GastoRecorrente.quem_gastou.ilike("eu")
            )
        ).all()
    finally:
        session.close()

def cancelar_gasto_recorrente(gasto_id: int, user_id: str) -> bool:
    session = Session()
    try:
        gasto = session.query(GastoRecorrente).filter(
            GastoRecorrente.id == gasto_id,
            GastoRecorrente.telegram_user_id == str(user_id)
        ).first()
        if gasto:
            gasto.ativo = False
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def liberar_acesso_usuario(user_id: str) -> bool:
    session = Session()
    try:
        usuario = session.query(Usuario).filter(Usuario.telegram_user_id == str(user_id)).first()
        if usuario:
            usuario.permitido = True
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def obter_usuarios_pendentes():
    session = Session()
    try:
        return session.query(Usuario).filter(Usuario.permitido == False).all()
    finally:
        session.close()

if __name__ == "__main__":
    init_db()
    print("Tabelas criadas com sucesso!")