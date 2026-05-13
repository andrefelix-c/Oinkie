# OincOinc 🐷💰

O **OincOinc** é um assistente financeiro pessoal em formato de bot do Telegram. Ele utiliza Inteligência Artificial (OpenAI) para interpretar mensagens em linguagem natural e transformar seus textos simples em registros financeiros organizados.

Chega de planilhas manuais chatas! Apenas mande um texto para o bot dizendo *"Comprei um tênis de 200 reais no cartão Nubank em 4x"* e ele fará todo o trabalho de classificação e registro no seu banco de dados.

## 🚀 Funcionalidades

- **Processamento de Linguagem Natural**: Entende textos livres e extrai informações cruciais como: *Data, Local, Valor, Categoria, Forma de Pagamento e Quantidade de Parcelas*.
- **Controle de Gastos Únicos**: Registra gastos do dia a dia (lanches, Uber, etc).
- **Controle de Compras Parceladas (`/parceladas`)**: Gerencia gastos divididos em meses, acompanhando quantas parcelas faltam e o valor restante a pagar.
- **Despesas Recorrentes (`/recorrentes`)**: Controla suas assinaturas (Netflix, Spotify, Internet) e o dia de cobrança de cada uma.
- **Gerenciamento de Cartões de Crédito**: Adicione seus cartões com dia de fechamento e vencimento, e associe seus gastos a eles.
- **Gestão de Terceiros / Dívidas**: O bot entende se você gastou dinheiro de/com outra pessoa ou se pagou/emprestou dinheiro para alguém.
- **Relatórios Mensais (`/relatorio`)**: Gera um resumo completo do mês agrupado por categoria, cartões, e fluxo de caixa de terceiros.
- **Controle de Acesso**: Sistema de permissão integrado. Somente usuários autorizados no banco de dados podem interagir com a Inteligência Artificial.

## 🛠️ Tecnologias Utilizadas

- **Python 3.x**
- **python-telegram-bot**: Para comunicação com a API do Telegram.
- **OpenAI API (GPT-4o-mini)**: Para processamento e extração inteligente dos dados da mensagem.
- **SQLAlchemy**: ORM para gerenciamento de banco de dados.
- **PostgreSQL / Supabase**: Banco de dados relacional recomendado.

## ⚙️ Instalação e Configuração

### 1. Clonando o Repositório e Preparando o Ambiente
```bash
# Navegue até o diretório do projeto
cd OincOinc

# (Opcional) Crie e ative um ambiente virtual
python -m venv venv
venv\Scripts\activate # No Windows

# Instale as dependências
pip install -r requirements.txt
```

### 2. Configurando as Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto contendo as seguintes chaves:

```env
OPENAI_API_KEY=sk-sua-chave-aqui
TELEGRAM_TOKEN=seu-token-do-bot-do-telegram
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
```
> **Nota para Supabase**: Certifique-se de usar a URL do Connection Pooler (ex: `aws-0-...pooler.supabase.com:6543`) caso sua rede não suporte conexão IPv6 nativa.

### 3. Rodando o Banco de Dados e o Bot
O script do banco de dados cria automaticamente as tabelas necessárias quando importado ou executado.

Para iniciar o bot:
```bash
python bot.py
```
Se for o primeiro uso, as tabelas serão geradas automaticamente e o bot começará a escutar mensagens.

## 📖 Como Usar

Procure o bot no Telegram e inicie a conversa.

### Comandos Disponíveis
- `/start` - Iniciar ou reiniciar o bot.
- `/ajuda` - Ver exemplos de como enviar seus gastos.
- `/addcartao <Nome> <Dia_Fechamento> <Dia_Vencimento>` - Adicionar um cartão.
- `/cartoes` - Listar e apagar os cartões cadastrados.
- `/relatorio [MM/AAAA]` - Ver o relatório financeiro do mês (ex: `/relatorio 05/2026`).
- `/parceladas` - Ver suas compras parceladas ativas e o saldo devedor restante.
- `/recorrentes` - Ver suas assinaturas ativas e os dias de cobrança.

### Cadastrando Gastos (Exemplos)
Basta mandar uma mensagem normal para o bot!
- *"Paguei a conta de luz hoje, 120 reais no PIX."*
- *"Comprei uma TV nas Casas Bahia por 1500 no cartão Itaú parcelado em 10 vezes."*
- *"Assinei a Netflix por 45 reais no cartão Nubank. Vai cobrar todo dia 10."*
- *"Devo 50 reais pro João do almoço de ontem."*

## 🔒 Controle de Acesso (Administrador)
Para evitar que qualquer pessoa use o bot e consuma sua cota da API da OpenAI, o bot tem um sistema de permissões. A primeira vez que alguém manda mensagem, o bot avisa que o acesso está bloqueado.

**Como se tornar o administrador e gerenciar acessos:**
1. Adicione o seu ID do Telegram no arquivo `.env`:
   ```env
   ADMIN_ID=seu_telegram_id_aqui
   ```
2. Após reiniciar o bot, você terá acesso exclusivo aos comandos de administrador:
   - `/pendentes`: Lista todos os usuários que tentaram usar o bot e estão aguardando aprovação (mostra o `@username` e o `ID` deles).
   - `/liberar <ID_DO_USUARIO>`: Comando usado para aprovar e liberar o acesso do usuário no banco de dados.

---

Desenvolvido para automatizar as finanças pessoais com o poder da IA. 🐷📈
