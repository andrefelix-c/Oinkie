import os
import json
import uuid
from datetime import datetime
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import re
from openai import OpenAI
from database import init_db, salvar_gasto_unico, salvar_gasto_parcelado, salvar_gasto_recorrente, deletar_gasto, obter_ou_criar_usuario, obter_cartoes, adicionar_cartao, remover_cartao, gerar_relatorio_mensal, obter_gastos_parcelados_ativos, obter_gastos_recorrentes_ativos, cancelar_gasto_recorrente, liberar_acesso_usuario, obter_usuarios_pendentes, agora_br
from dotenv import load_dotenv

from dotenv import load_dotenv
load_dotenv()

# TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
# OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

client = OpenAI(api_key=OPENAI_API_KEY)

init_db()

SYSTEM_PROMPT = """
Você é um assistente financeiro pessoal. O usuário vai te contar sobre gastos de forma natural.

Sua tarefa é extrair as informações e retornar APENAS um JSON válido, sem texto adicional, sem markdown, sem explicações.

Classifique o tipo do gasto:
- "unico": gasto comum, aconteceu uma vez
- "parcelado": foi dividido em parcelas
- "recorrente": é uma cobrança que se repete todo mês (assinatura, aluguel, mensalidade, etc)

Regras específicas:
- Estabelecimento vs Pessoa: Nomes de lojas, apps e empresas (ex: iFood, Uber, Mercado) sempre vão no campo "estabelecimento". Nomes de pessoas só vão em "estabelecimento" se for um pagamento de dívida direto para elas.
- Quem gastou: Preste muita atenção! Se a mensagem disser que a compra foi feita "por [nome]", "pelo/pela [nome]", ou que "[nome] gastou", o campo "quem_gastou" DEVE ser preenchido com esse nome (ex: "Letícia"). Se o usuário fez a compra para ele mesmo, use "Eu".
- Terceiros: Se o usuário disser que deve ou pagou algo para outra pessoa (ex: "devo 30 para leticia", "paguei o joão"), coloque o nome dessa pessoa no campo "estabelecimento" e use a categoria "Terceiros/Dívidas".
- Recorrentes: Se a forma de pagamento não for explicitamente informada, preencha como "Crédito". O campo "estabelecimento" deve ser o nome da marca da assinatura ou do serviço (ex: Netflix, Spotify, Academia), caso esteja disponível.
- Compras compartilhadas/divididas: Se o usuário informar que dividiu um gasto com outras pessoas, divida o valor matematicamente pelo número de pessoas (o campo "Valor" deve ser o valor total dividido por pessoa) e retorne objetos separados dentro da lista "gastos", um para cada pessoa (colocando o nome dela no campo "quem_gastou"). Se ele não se incluir na divisão, coloque apenas o nome das outras pessoas.

JSON esperado:
{
  "entendido": true,
  "mensagem": "mensagem amigável confirmando o que entendeu, em português",
  "gastos": [
    {
      "tipo": "unico | parcelado | recorrente",
      "data_hora": "YYYY-MM-DD HH:MM:SS ou null se não souber a hora",
      "descricao": "o que foi comprado / onde foi gasto",
      "estabelecimento": "nome do lugar (ou nome da pessoa recebedora, se for pagamento a terceiros) ou null",
      "valor": 0.00,
      "valor_parcela": 0.00,
      "moeda": "BRL",
      "categoria": "uma dessas: Alimentação | Vestuário | Transporte | Saúde | Lazer | Moradia | Educação | Assinatura | Terceiros/Dívidas | Outro",
      "quem_gastou": "nome da pessoa mencionada ou 'Eu' se for o próprio usuário",
      "forma_pagamento": "Dinheiro | Pix | Débito | Crédito | Outro",
      "cartao": "nome do cartão utilizado, ou null se não foi usado cartão",
      "parcelado": false,
      "num_parcelas": null,
      "dia_cobranca": null,
      "observacoes": "qualquer detalhe extra relevante ou null"
    }
  ]
}

Se a mensagem não for sobre um gasto, retorne:
{
  "entendido": false,
  "mensagem": "resposta amigável explicando que só processa gastos por enquanto"
}

Hoje é: {data_hoje}
Cartões cadastrados pelo usuário: {lista_cartoes}
"""

async def configurar_comandos(app):
    comandos_basicos = [
        BotCommand("start", "Iniciar o bot"),
        BotCommand("ajuda", "Ver exemplos de uso"),
        BotCommand("addcartao", "Adicionar um novo cartão"),
        BotCommand("cartoes", "Listar e gerenciar cartões"),
        BotCommand("relatorio", "Ver o relatório de gastos do mês"),
        BotCommand("parceladas", "Ver contas parceladas ativas"),
        BotCommand("recorrentes", "Ver contas recorrentes ativas"),
    ]
    
    await app.bot.set_my_commands(comandos_basicos)
    
    admin_id = os.getenv('ADMIN_ID')
    if admin_id:
        from telegram import BotCommandScopeChat
        comandos_admin = comandos_basicos + [
            BotCommand("pendentes", "👨‍💼 (Admin) Ver usuários pendentes"),
            BotCommand("liberar", "👨‍💼 (Admin) Aprovar acesso"),
        ]
        try:
            await app.bot.set_my_commands(comandos_admin, scope=BotCommandScopeChat(chat_id=int(admin_id)))
        except Exception as e:
            print(f"Aviso: Não foi possível definir comandos do admin: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    permitido = obter_ou_criar_usuario(user.id, user.username)
    
    if not permitido:
        await update.message.reply_text(
            "Olá! 🐷 Sou o *Oinkie*, seu porquinho assistente financeiro.\n\n"
            "⚠️ *Acesso Restrito*\n"
            "Seu usuário foi registrado, mas você ainda não tem permissão para usar o bot. "
            "Peça ao administrador para liberar seu acesso (mudar `permitido` para `true` no banco).",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "Olá! 🐷 Sou o *Oinkie*, seu porquinho assistente financeiro.\n\n"
        "Me conta seus gastos de forma natural e eu coloco tudo no cofrinho pra você!\n\n"
        "Digite /ajuda para ver exemplos e o que eu consigo registrar.",
        parse_mode="Markdown"
    )

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Como usar:*\n\n"
        "Me conta seus gastos de forma natural! Quanto mais detalhes, melhor. Veja o que eu consigo extrair:\n\n"
        "🛒 *Gasto simples:*\n"
        "_'Hoje gastei 45 reais no Burger King no débito'_\n"
        "→ data, valor, local, cartão\n\n"
        "💳 *Compra parcelada:*\n"
        "_'Comprei um tênis na Centauro por 320 reais no Nubank em 4x'_\n"
        "→ cria uma linha por parcela com a data de cada vencimento\n\n"
        "🔁 *Gasto recorrente:*\n"
        "_'Pago o Spotify todo mês, 21 reais no cartão Inter, todo dia 15'_\n"
        "→ salvo como recorrente com o dia da cobrança\n\n"
        "👥 *Dividindo contas:*\n"
        "_'Comprei uma pizza de 80 reais no Nubank e dividi com a Cecilia e o Thales'_\n"
        "→ calculo a parte de cada um e separo pra você cobrar depois\n\n"
        "👤 *Gasto de outra pessoa:*\n"
        "_'Minha filha gastou 80 reais na farmácia ontem'_\n"
        "→ registro quem fez o gasto para separar do seu\n\n"
        "💸 *Pagando dívidas ou terceiros:*\n"
        "_'Paguei 50 reais que devia ao João'_\n"
        "→ registro no fechamento de contas a receber/pagar\n\n"
        "📋 *Campos que eu entendo:*\n"
        "Data • Valor • Local • Categoria • Quem gastou • Cartão • Parcelas • Dia de cobrança • Observações\n\n"
        "💡 Quanto mais você informar, mais completo fica o registro!",
        parse_mode="Markdown"
    )

async def cmd_addcartao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not obter_ou_criar_usuario(user.id, user.username):
        await update.message.reply_text("⚠️ Acesso restrito.")
        return

    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("⚠️ Uso correto: /addcartao <Nome> <Dia_Vira> <Dia_Paga>\nExemplo: /addcartao Nubank 25 2")
            return
        
        nome = " ".join(args[:-2])
        dia_vira = int(args[-2])
        dia_paga = int(args[-1])

        adicionar_cartao(user.id, nome, dia_vira, dia_paga)
        await update.message.reply_text(f"✅ Cartão *{nome}* adicionado com sucesso!\nDia que vira: {dia_vira}\nDia do pagamento: {dia_paga}", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("⚠️ Os dias devem ser números. Ex: /addcartao Nubank 25 2")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao salvar cartão: {str(e)}")

async def cmd_cartoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not obter_ou_criar_usuario(user.id, user.username):
        await update.message.reply_text("⚠️ Acesso restrito.")
        return

    cartoes = obter_cartoes(user.id)
    if not cartoes:
        await update.message.reply_text("💳 Você não tem cartões cadastrados.\nUse /addcartao <Nome> <Dia_Vira> <Dia_Paga> para cadastrar.")
        return

    botoes = []
    texto = "💳 *Seus Cartões Cadastrados:*\n\n"
    for c in cartoes:
        texto += f"• *{c.nome}* (Vira: {c.dia_fechamento}, Paga: {c.dia_vencimento})\n"
        botoes.append([InlineKeyboardButton(f"🗑️ Apagar {c.nome}", callback_data=f"delcartao|{c.id}")])

    teclado = InlineKeyboardMarkup(botoes)
    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=teclado)

async def delcartao_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, cartao_id = query.data.split("|")
    user = update.effective_user
    
    sucesso = remover_cartao(int(cartao_id), user.id)
    if sucesso:
        await query.edit_message_text(f"{query.message.text}\n\n✅ _Cartão apagado com sucesso!_", parse_mode="Markdown")
    else:
        await query.edit_message_text(f"⚠️ Não foi possível apagar o cartão.")

async def desfazer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, tipo, ids_str = query.data.split("|")
    ids = [int(i) for i in ids_str.split(",")]

    try:
        deletar_gasto(tipo, ids)
        await query.edit_message_text(
            query.message.text + "\n\n✅ _Inserção desfeita com sucesso!_",
            parse_mode="Markdown"
        )
    except Exception as e:
        await query.edit_message_text(f"⚠️ Erro ao desfazer: {str(e)}")

async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, pendencia_id = query.data.split("|")
    dados = context.user_data.get(pendencia_id)

    if not dados:
        await query.edit_message_text(
            query.message.text + "\n\n⚠️ _Tempo expirado ou gasto já processado._",
            parse_mode="Markdown"
        )
        return

    gastos = dados.get("gastos", [])
    if not gastos and "gasto" in dados:
        gastos = [dados["gasto"]]
    
    resposta_original = dados.get("resposta_original", query.message.text)
    user = update.effective_user

    ids_salvos = {"unico": [], "parcelado": [], "recorrente": []}

    try:
        for gasto in gastos:
            tipo = gasto.get("tipo", dados.get("tipo", "unico"))
            if tipo == "recorrente":
                gasto_id = salvar_gasto_recorrente(gasto, user.id, user.username)
                ids_salvos["recorrente"].append(gasto_id)
            elif tipo == "parcelado":
                ids = salvar_gasto_parcelado(gasto, user.id, user.username)
                ids_salvos["parcelado"].extend(ids)
            else:
                gasto_id = salvar_gasto_unico(gasto, user.id, user.username)
                ids_salvos["unico"].append(gasto_id)

        context.user_data[pendencia_id]["ids_salvos"] = ids_salvos

        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Desfazer inserção", callback_data=f"desfazermulti|{pendencia_id}")]
        ])

        await query.edit_message_text(
            resposta_original + "\n\n✅ _Gasto(s) salvo(s) com sucesso!_",
            parse_mode="Markdown",
            reply_markup=teclado
        )
    except Exception as e:
        await query.edit_message_text(f"⚠️ Erro ao salvar no banco: {str(e)}")

async def desfazer_multi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, pendencia_id = query.data.split("|")
    dados = context.user_data.get(pendencia_id)

    if not dados or "ids_salvos" not in dados:
        await query.edit_message_text(
            query.message.text + "\n\n⚠️ _Tempo expirado ou já desfeito._",
            parse_mode="Markdown"
        )
        return

    ids_salvos = dados["ids_salvos"]

    try:
        if ids_salvos.get("unico"):
            deletar_gasto("unico", ids_salvos["unico"])
        if ids_salvos.get("parcelado"):
            deletar_gasto("unico", ids_salvos["parcelado"])
        if ids_salvos.get("recorrente"):
            deletar_gasto("recorrente", ids_salvos["recorrente"])

        del context.user_data[pendencia_id]
        
        await query.edit_message_text(
            query.message.text + "\n\n✅ _Inserção desfeita com sucesso!_",
            parse_mode="Markdown"
        )
    except Exception as e:
        await query.edit_message_text(f"⚠️ Erro ao desfazer: {str(e)}")

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, pendencia_id = query.data.split("|")
    dados = context.user_data.get(pendencia_id)

    if dados:
        resposta_original = dados.get("resposta_original", query.message.text)
        del context.user_data[pendencia_id]
    else:
        resposta_original = query.message.text

    await query.edit_message_text(
        resposta_original + "\n\n❌ _Gasto cancelado._",
        parse_mode="Markdown"
    )

async def processar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    permitido = obter_ou_criar_usuario(user.id, user.username)
    
    if not permitido:
        await update.message.reply_text("⚠️ Você não tem permissão para usar a IA e registrar gastos. Peça ao administrador para liberar seu acesso.")
        return

    mensagem = update.message.text
    agora = agora_br().strftime("%Y-%m-%d %H:%M:%S")

    cartoes = obter_cartoes(user.id)
    if cartoes:
        lista_cartoes = ", ".join([c.nome for c in cartoes])
    else:
        lista_cartoes = "Nenhum cartão cadastrado"

    system = SYSTEM_PROMPT.replace("{data_hoje}", agora).replace("{lista_cartoes}", lista_cartoes)

    await update.message.reply_chat_action("typing")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": mensagem}
            ],
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()
        dados = json.loads(raw)

    except json.JSONDecodeError:
        await update.message.reply_text("⚠️ Não consegui processar isso. Tente descrever o gasto de outra forma.")
        return
    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao chamar a IA: {str(e)}")
        return

    if not dados.get("entendido"):
        await update.message.reply_text("🐷 *Oink!* Sou um porquinho faminto apenas por dados financeiros.\n\nPor favor, me conte sobre um gasto, dívida ou assinatura para eu guardar no cofre. Exemplo:\n_'Gastei 45 no Burger King'_\n\nOu digite /ajuda para ver todos os comandos.", parse_mode="Markdown")
        return

    lista_gastos = dados.get("gastos") or ([dados["gasto"]] if "gasto" in dados else [])
    
    if not lista_gastos:
        await update.message.reply_text("Não encontrei os dados do gasto.")
        return

    cartoes_db = obter_cartoes(user.id)
    nomes_cartoes = [c.nome.lower() for c in cartoes_db]

    for gasto in lista_gastos:
        cartao_gasto = gasto.get("cartao")
        if cartao_gasto and cartao_gasto.lower() not in nomes_cartoes:
            await update.message.reply_text(
                f"⚠️ *Oink!* Você mencionou o cartão *{cartao_gasto}*, mas ele ainda não está no meu cofrinho.\n\n"
                "Para eu registrar certinho na sua fatura, adicione ele primeiro usando o comando:\n"
                "`/addcartao NomeDoCartao DiaQueVira DiaQuePaga`\n\n"
                "Exemplo: `/addcartao Nubank 14 20`\n\n"
                "Depois de adicionar, é só me mandar o gasto de novo!",
                parse_mode="Markdown"
            )
            return

    resposta = f"{dados.get('mensagem', 'Entendido!')}\n\n*Resumo dos Gastos:*"

    for gasto in lista_gastos:
        tipo = gasto.get("tipo", dados.get("tipo", "unico"))
        gasto["tipo"] = tipo
        
        if gasto.get("data_hora"):
            dt = datetime.fromisoformat(gasto["data_hora"])
            if dt.hour == 0 and dt.minute == 0:
                gasto["data_hora"] = dt.strftime("%Y-%m-%d") + " " + agora_br().strftime("%H:%M:%S")
        else:
            gasto["data_hora"] = agora

        parcelas = f" em {gasto['num_parcelas']}x" if gasto.get("parcelado") else ""
        cartao   = f" ({gasto['cartao']})" if gasto.get("cartao") else ""
        forma_pagamento = gasto.get("forma_pagamento", "Não informada")
        icone    = "🔁" if tipo == "recorrente" else "💳" if tipo == "parcelado" else "💸"

        resposta += f"\n\n{icone} *{gasto.get('descricao') or 'Gasto'}*"
        
        try:
            dt_obj = datetime.fromisoformat(gasto["data_hora"])
            data_formatada = dt_obj.strftime("%d/%m/%Y às %H:%M")
        except:
            data_formatada = str(gasto["data_hora"])
            
        resposta += f"\n• 📅 Data: {data_formatada}"
        resposta += f"\n• 🏪 Local: {gasto.get('estabelecimento') or '-'}"
        resposta += f"\n• 💰 Valor: R$ {gasto.get('valor', 0):.2f}{parcelas}"
        resposta += f"\n• 💳 Pagamento: {forma_pagamento}{cartao}"
        resposta += f"\n• 🏷️ Categoria: {gasto.get('categoria', 'Outro')}"
        resposta += f"\n• 👤 Quem: {gasto.get('quem_gastou', 'Eu')}"

        if tipo == "recorrente" and gasto.get("dia_cobranca"):
            resposta += f"\n• 📆 Todo dia: {gasto['dia_cobranca']}"

        if tipo == "parcelado" and gasto.get("num_parcelas"):
            valor_parcela = gasto.get("valor_parcela") or round(gasto.get("valor", 0) / gasto["num_parcelas"], 2)
            resposta += f"\n• 🔢 Parcela: R$ {valor_parcela:.2f}/mês"

        if gasto.get("observacoes"):
            resposta += f"\n• 📝 Obs: {gasto['observacoes']}"

    pendencia_id = str(uuid.uuid4())[:8]
    context.user_data[pendencia_id] = {
        "gastos": lista_gastos,
        "resposta_original": resposta
    }

    resposta_exibicao = resposta + "\n_Gasto pendente de confirmação._"

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar|{pendencia_id}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"cancelar|{pendencia_id}")
        ]
    ])

    await update.message.reply_text(resposta_exibicao, parse_mode="Markdown", reply_markup=teclado)

async def cmd_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not obter_ou_criar_usuario(user.id, user.username):
        await update.message.reply_text("⚠️ Acesso restrito.")
        return

    agora = agora_br()
    ano = agora.year
    mes = agora.month
    
    if context.args:
        try:
            mes_ano = context.args[0].split("/")
            mes = int(mes_ano[0])
            if len(mes_ano) > 1:
                ano = int(mes_ano[1])
        except (ValueError, IndexError):
            await update.message.reply_text("⚠️ Formato inválido. Use: /relatorio ou /relatorio MM/AAAA")
            return
            
    dados = gerar_relatorio_mensal(user.id, ano, mes)
    
    texto = f"📊 *Relatório de Gastos - {mes:02d}/{ano}*\n\n"
    texto += f"💰 *Total Gasto:* R$ {dados['total_gasto']:.2f}\n\n"
    
    if dados["por_categoria"]:
        texto += "🏷️ *Por Categoria:*\n"
        for cat, val in sorted(dados["por_categoria"].items(), key=lambda item: item[1], reverse=True):
            texto += f"• {cat}: R$ {val:.2f}\n"
        texto += "\n"
        
    if dados["por_cartao"]:
        texto += "💳 *Por Cartão de Crédito:*\n"
        for cartao, val in sorted(dados["por_cartao"].items(), key=lambda item: item[1], reverse=True):
            texto += f"• {cartao}: R$ {val:.2f}\n"
        texto += "\n"
        
    if dados["dividas"]:
        texto += "🛑 *O que eu devo (Dívidas a pagar):*\n"
        for pessoa, val in dados["dividas"].items():
            texto += f"• Para {pessoa}: R$ {val:.2f}\n"
        texto += "\n"
        
    if dados["a_receber"]:
        texto += "🤑 *O que me devem (A receber):*\n"
        for pessoa, val in dados["a_receber"].items():
            texto += f"• {pessoa} gastou: R$ {val:.2f}\n"
            
    if not dados["por_categoria"] and dados["total_gasto"] == 0:
        texto += "Nenhum gasto registrado neste mês."
        
    await update.message.reply_text(texto, parse_mode="Markdown")

async def cmd_parceladas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not obter_ou_criar_usuario(user.id, user.username):
        await update.message.reply_text("⚠️ Acesso restrito.")
        return

    gastos = obter_gastos_parcelados_ativos(user.id)
    if not gastos:
        await update.message.reply_text("Você não tem contas parceladas ativas no momento. 🎉")
        return

    compras = {}
    
    for g in gastos:
        base_desc = g.descricao
        match = re.search(r"(.+) \(\d+/(\d+)\)$", g.descricao)
        total_parcelas = g.num_parcelas or 1
        
        if match:
            base_desc = match.group(1).strip()
            total_parcelas = int(match.group(2))
        elif g.num_parcelas:
            total_parcelas = g.num_parcelas

        chave = (base_desc, g.estabelecimento, total_parcelas)
        
        if chave not in compras:
            compras[chave] = {
                "valor_restante": 0.0,
                "parcelas_restantes": 0,
                "total_parcelas": total_parcelas
            }
        
        compras[chave]["valor_restante"] += g.valor_total
        compras[chave]["parcelas_restantes"] += 1

    texto = "💳 *Suas Contas Parceladas Ativas:*\n\n"
    
    for chave, info in compras.items():
        base_desc, estabelecimento, total_parcelas = chave
        local = f" ({estabelecimento})" if estabelecimento else ""
        texto += f"• *{base_desc}*{local}\n"
        texto += f"  Faltam: {info['parcelas_restantes']} de {info['total_parcelas']} parcelas\n"
        texto += f"  Valor total restante: R$ {info['valor_restante']:.2f}\n\n"
        
    await update.message.reply_text(texto, parse_mode="Markdown")


async def cmd_recorrentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not obter_ou_criar_usuario(user.id, user.username):
        await update.message.reply_text("⚠️ Acesso restrito.")
        return

    gastos = obter_gastos_recorrentes_ativos(user.id)
    if not gastos:
        await update.message.reply_text("Você não tem contas recorrentes ativas. ✅")
        return

    texto = "🔁 *Suas Contas Recorrentes Ativas:*\n\n"
    botoes = []
    
    for g in gastos:
        local = f" ({g.estabelecimento})" if g.estabelecimento else ""
        dia = f"Todo dia {g.dia_cobranca}" if g.dia_cobranca else "Dia não informado"
        texto += f"• *{g.descricao}*{local}\n"
        texto += f"  Valor: R$ {g.valor:.2f}\n"
        texto += f"  Cobrança: {dia}\n\n"
        
        botoes.append([InlineKeyboardButton(f"❌ Cancelar {g.descricao}", callback_data=f"cancelrec|{g.id}")])

    teclado = InlineKeyboardMarkup(botoes)
    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=teclado)

async def cancelrec_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, gasto_id = query.data.split("|")
    user = update.effective_user
    
    sucesso = cancelar_gasto_recorrente(int(gasto_id), user.id)
    if sucesso:
        await query.edit_message_text(f"{query.message.text}\n\n✅ _Assinatura cancelada com sucesso!_", parse_mode="Markdown")
    else:
        await query.edit_message_text(f"{query.message.text}\n\n⚠️ _Não foi possível cancelar a assinatura._", parse_mode="Markdown")

async def ignorar_nao_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("⚠️ Por enquanto, eu só entendo mensagens de texto. Por favor, digite o seu gasto!")

async def cmd_pendentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = os.getenv('ADMIN_ID')
    user = update.effective_user
    
    if not admin_id or str(user.id) != str(admin_id):
        await update.message.reply_text("⛔ Você não tem permissão para usar este comando.")
        return

    pendentes = obter_usuarios_pendentes()
    if not pendentes:
        await update.message.reply_text("🎉 Nenhum usuário pendente de aprovação no momento.")
        return

    texto = "👥 *Usuários Pendentes de Aprovação:*\n\n"
    for p in pendentes:
        nome = p.telegram_username if p.telegram_username else "Sem Username"
        texto += f"• @{nome} (ID: `{p.telegram_user_id}`)\n"
    
    texto += "\n_Use `/liberar <ID>` para aprovar um usuário._"
    await update.message.reply_text(texto, parse_mode="Markdown")

async def cmd_liberar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = os.getenv('ADMIN_ID')
    user = update.effective_user
    
    if not admin_id or str(user.id) != str(admin_id):
        await update.message.reply_text("⛔ Você não tem permissão para usar este comando.")
        return
        
    if not context.args:
        await update.message.reply_text("⚠️ Uso correto: /liberar <telegram_user_id>")
        return
        
    target_id = context.args[0]
    sucesso = liberar_acesso_usuario(target_id)
    if sucesso:
        await update.message.reply_text(f"✅ Acesso liberado para o usuário `{target_id}` com sucesso!", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ Usuário `{target_id}` não encontrado no banco de dados.", parse_mode="Markdown")

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ajuda", ajuda))
app.add_handler(CommandHandler("addcartao", cmd_addcartao))
app.add_handler(CommandHandler("cartoes", cmd_cartoes))
app.add_handler(CommandHandler("relatorio", cmd_relatorio))
app.add_handler(CommandHandler("parceladas", cmd_parceladas))
app.add_handler(CommandHandler("recorrentes", cmd_recorrentes))
app.add_handler(CommandHandler("pendentes", cmd_pendentes))
app.add_handler(CommandHandler("liberar", cmd_liberar))
app.add_handler(CallbackQueryHandler(delcartao_callback, pattern="^delcartao"))
app.add_handler(CallbackQueryHandler(desfazer_multi, pattern="^desfazermulti"))
app.add_handler(CallbackQueryHandler(desfazer, pattern=r"^desfazer\|"))
app.add_handler(CallbackQueryHandler(confirmar, pattern="^confirmar"))
app.add_handler(CallbackQueryHandler(cancelar, pattern="^cancelar"))
app.add_handler(CallbackQueryHandler(cancelrec_callback, pattern=r"^cancelrec\|"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_gasto))
app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, ignorar_nao_texto))

app.post_init = configurar_comandos

app.run_polling()