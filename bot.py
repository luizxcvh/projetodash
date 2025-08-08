import logging
from sqlalchemy.orm import joinedload
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
# LINHA NOVA E CORRETA
from telegram.ext import (Application, CommandHandler, MessageHandler, filters, 
                          ContextTypes, ConversationHandler, CallbackQueryHandler)
import matplotlib.pyplot as plt # 
from flask import Flask
from models import db, Secretaria, Obra, Gasto
from datetime import datetime
from io import BytesIO
import os
from dotenv import load_dotenv

# Configure o logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
# Carrega as variáveis do ficheiro .env para o ambiente
load_dotenv()
# --- Configuração do App e DB ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gerenciamento.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# --- Constantes do Bot ---
# Use o token que você recebeu do BotFather
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
# URL onde sua Web App do painel estará rodando (pode ser localhost com ngrok para testes)
WEB_APP_URL = "https://fd136a2eab71.ngrok-free.app" 

# --- Estados para as Conversas ---
# Conversa de Secretaria
NOME_SECRETARIA, ORCAMENTO_SECRETARIA = range(2)
# Conversa de Obra
OBRA_NOME, OBRA_ORCAMENTO, OBRA_SECRETARIA = range(2, 5) # Continua a numeração

# ==============================================================================
# FUNÇÃO AUXILIAR PARA GERAR GRÁFICOS
# ==============================================================================
# Em bot.py

def gerar_grafico_orcamento(usado, total, titulo):
    """Gera um gráfico de rosca com valores e percentagens, e retorna o buffer da imagem."""
    if total <= 0:
        return None

    restante = total - usado
    if restante < 0:
        restante = 0
        usado = total

    # --- Lógica para os rótulos ---
    def make_autopct(values):
        def my_autopct(pct):
            total_valor = sum(values)
            val = int(round(pct * total_valor / 100.0))
            # Formata o texto para incluir o valor em Reais e a percentagem
            return f'R$ {val:,.2f}\n({pct:.1f}%)'.replace(',', 'X').replace('.', ',').replace('X', '.')
        return my_autopct

    labels = ['Gasto', 'Disponível']
    sizes = [usado, restante]
    colors = ['#EF4444', '#22C55E']  # Vermelho e Verde mais modernos
    explode = (0.05, 0)

    # --- Configurações visuais do gráfico ---
    fig, ax = plt.subplots(figsize=(8, 6), facecolor='#F9FAFB') # Fundo suave
    ax.pie(
        sizes, 
        explode=explode, 
        labels=labels, 
        colors=colors, 
        autopct=make_autopct(sizes), # Usa a nossa função de rótulo personalizada
        shadow=False, 
        startangle=90, 
        pctdistance=0.8,
        textprops={'fontsize': 10, 'fontweight': 'bold', 'color': 'white'}
    )

    centre_circle = plt.Circle((0, 0), 0.65, fc='#F9FAFB')
    fig.gca().add_artist(centre_circle)

    ax.axis('equal')
    plt.title(titulo, pad=20, fontsize=16, fontweight='bold', color='#1F2937')
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150) # Aumenta a resolução
    plt.close(fig)
    buf.seek(0)
    return buf

# ==============================================================================
# HANDLERS DE COMANDOS PRINCIPAIS
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia uma mensagem de boas-vindas."""
    user = update.effective_user
    await update.message.reply_html(
        f"Olá, {user.mention_html()}!\n\n"
        "Bem-vindo ao sistema de gestão de obras. Veja os comandos disponíveis:\n\n"
        "📊  /painel - Abre o dashboard interativo\n"
        "📈  /grafico - Gera um gráfico de orçamento\n"
        "🏢  /secretarias - Lista as secretarias\n"
        "🏗️  /obras - Lista as obras\n"
        "➕  /add_secretaria - Cadastra uma nova secretaria\n"
        "➕  /add_obra - Cadastra uma nova obra\n"
        "💰  /add_gasto - Lança um novo gasto (a implementar)\n"
        "📋  /extrato - Consulta o extrato de gastos\n"
        "❌  /cancelar - Cancela qualquer operação em andamento."
    )

async def painel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Abre o painel interativo como uma Web App."""
    keyboard = [[InlineKeyboardButton("📊 Abrir Painel de Controle", web_app=WebAppInfo(url=WEB_APP_URL))]]
    await update.message.reply_text(
        "Clique no botão abaixo para abrir o painel interativo:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def listar_secretarias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista todas as secretarias cadastradas, usando eager loading."""
    with app.app_context():
        secretarias = db.session.query(Secretaria).options(
            joinedload(Secretaria.obras).joinedload(Obra.gastos)
        ).all()

    if not secretarias:
        await update.message.reply_text("Nenhuma secretaria cadastrada.")
        return

    mensagem = "📋 *Secretarias Cadastradas:*\n\n"
    for sec in secretarias:
        mensagem += f"*{sec.nome}*\n"
        mensagem += f"  - Orçamento: R$ {sec.orcamento_declarado:,.2f}\n"
        mensagem += f"  - Gasto: R$ {sec.orcamento_gasto:,.2f}\n"
        mensagem += f"  - Saldo: R$ {sec.orcamento_restante:,.2f}\n\n"
    
    await update.message.reply_text(mensagem, parse_mode='Markdown')

async def listar_obras(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista todas as obras cadastradas."""
    with app.app_context():
        obras = Obra.query.all()
    if not obras:
        await update.message.reply_text("Nenhuma obra cadastrada.")
        return

    mensagem = "🏗️ *Obras Cadastradas:*\n\n"
    for obra in obras:
         mensagem += f"*{obra.nome}* ({obra.secretaria.nome})\n"
         mensagem += f"  - Orçamento: R$ {obra.orcamento_previsto:,.2f}\n"
         mensagem += f"  - Gasto: R$ {obra.total_gasto:,.2f}\n"
         mensagem += f"  - Status: {obra.andamento.status}\n\n"
    
    await update.message.reply_text(mensagem, parse_mode='Markdown')


# ==============================================================================
# FLUXO DE GRÁFICOS E EXTRATOS (COM CALLBACKS)
# ==============================================================================
async def grafico_secretaria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra um teclado para escolher de qual secretaria ver o gráfico."""
    with app.app_context():
        secretarias = Secretaria.query.all()
    if not secretarias:
        await update.message.reply_text("Nenhuma secretaria cadastrada.")
        return

    keyboard = [[InlineKeyboardButton(sec.nome, callback_data=f"grafico_{sec.id}")] for sec in secretarias]
    await update.message.reply_text(
        "Selecione uma secretaria para ver o gráfico de orçamento:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def enviar_grafico_selecionado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback que recebe a escolha do utilizador e envia o gráfico."""
    query = update.callback_query
    await query.answer()
    secretaria_id = int(query.data.split('_')[1])
    
    with app.app_context():
        sec = db.session.get(Secretaria, secretaria_id)
        if not sec:
            await query.edit_message_text("Secretaria não encontrada.")
            return
        grafico_buffer = gerar_grafico_orcamento(sec.orcamento_gasto, sec.orcamento_declarado, f"Orçamento: {sec.nome}")

    if grafico_buffer:
        await query.message.reply_photo(photo=grafico_buffer)
        await query.edit_message_text(f"Gráfico para *{sec.nome}* gerado.", parse_mode='Markdown')
    else:
        await query.edit_message_text(f"Não há orçamento declarado para *{sec.nome}*.", parse_mode='Markdown')

async def extrato_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra o menu de opções para gerar extratos."""
    keyboard = [
        [InlineKeyboardButton("Extrato do Dia de Hoje", callback_data="extrato_dia_hoje")],
        [InlineKeyboardButton("Extrato do Mês Atual", callback_data="extrato_mes_atual")],
        [InlineKeyboardButton("Por Secretaria", callback_data="extrato_secretaria")],
        [InlineKeyboardButton("Por Obra", callback_data="extrato_obra")],
    ]
    await update.message.reply_text("Selecione o tipo de extrato:", reply_markup=InlineKeyboardMarkup(keyboard))


# ==============================================================================
# CONVERSATION HANDLERS
# ==============================================================================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela e encerra a conversa atual."""
    await update.message.reply_text("Operação cancelada.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

# --- CONVERSA: Adicionar Secretaria ---
async def add_secretaria_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Qual o nome da nova secretaria?")
    return NOME_SECRETARIA

async def get_nome_secretaria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['nome_secretaria'] = update.message.text
    await update.message.reply_text(f"Nome: {update.message.text}.\nQual o orçamento declarado? (Ex: 500000.50)")
    return ORCAMENTO_SECRETARIA

async def get_orcamento_secretaria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        orcamento = float(update.message.text)
        nome = context.user_data['nome_secretaria']
        with app.app_context():
            nova_secretaria = Secretaria(nome=nome, orcamento_declarado=orcamento)
            db.session.add(nova_secretaria)
            db.session.commit()
        await update.message.reply_text(f"✅ Sucesso! Secretaria '{nome}' cadastrada.")
    except (ValueError, KeyError):
        await update.message.reply_text("❌ Erro! Envie um número válido. Tente novamente com /add_secretaria.")
    context.user_data.clear()
    return ConversationHandler.END

# --- CONVERSA: Adicionar Obra ---
async def add_obra_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Qual o nome da nova obra?")
    return OBRA_NOME

async def get_obra_nome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['nome_obra'] = update.message.text
    await update.message.reply_text("Qual o orçamento previsto para esta obra? (Ex: 75000)")
    return OBRA_ORCAMENTO

async def get_obra_orcamento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['orcamento_obra'] = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Valor inválido. Tente novamente.")
        return OBRA_ORCAMENTO
    with app.app_context():
        secretarias = Secretaria.query.all()
    if not secretarias:
        await update.message.reply_text("Crie uma secretaria primeiro com /add_secretaria.")
        return ConversationHandler.END
    keyboard = [[sec.nome] for sec in secretarias]
    await update.message.reply_text(
        "A qual secretaria esta obra pertence?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return OBRA_SECRETARIA

async def get_obra_secretaria_e_salvar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nome_secretaria_escolhida = update.message.text
    with app.app_context():
        secretaria = Secretaria.query.filter_by(nome=nome_secretaria_escolhida).first()
        if not secretaria:
            await update.message.reply_text("Secretaria não encontrada. Tente novamente.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        nova_obra = Obra(
            nome=context.user_data['nome_obra'],
            orcamento_previsto=context.user_data['orcamento_obra'],
            secretaria_id=secretaria.id
        )
        novo_andamento = Andamento(obra=nova_obra, data_inicio=datetime.utcnow().date())
        db.session.add(nova_obra)
        db.session.add(novo_andamento)
        db.session.commit()
    await update.message.reply_text(
        f"✅ Obra '{nova_obra.nome}' cadastrada com sucesso!",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

# ==============================================================================
# FUNÇÃO PRINCIPAL (MAIN)
# ==============================================================================
def main() -> None:
    """Inicia o bot e regista todos os handlers."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- Handlers de Conversa ---
    conv_secretaria_handler = ConversationHandler(
        entry_points=[CommandHandler("add_secretaria", add_secretaria_start)],
        states={
            NOME_SECRETARIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_nome_secretaria)],
            ORCAMENTO_SECRETARIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_orcamento_secretaria)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
    )

    conv_obra_handler = ConversationHandler(
        entry_points=[CommandHandler("add_obra", add_obra_start)],
        states={
            OBRA_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_obra_nome)],
            OBRA_ORCAMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_obra_orcamento)],
            OBRA_SECRETARIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_obra_secretaria_e_salvar)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
    )

    # --- Registo dos Handlers ---
    # Comandos simples
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("painel", painel))
    application.add_handler(CommandHandler("secretarias", listar_secretarias))
    application.add_handler(CommandHandler("obras", listar_obras))
    application.add_handler(CommandHandler("grafico", grafico_secretaria))
    application.add_handler(CommandHandler("extrato", extrato_menu))
    
    # Handlers de conversa
    application.add_handler(conv_secretaria_handler)
    application.add_handler(conv_obra_handler)

    # Handler para os botões (callbacks)
    application.add_handler(CallbackQueryHandler(enviar_grafico_selecionado, pattern="^grafico_"))
    # (Aqui seriam adicionados mais CallbackQueryHandlers para o menu de extrato)

    # Inicia o bot
    print("Bot iniciado e a aguardar mensagens...")
    application.run_polling()

if __name__ == "__main__":
    main()
