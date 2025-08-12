from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from forms import (SecretariaForm, ObraForm, GastoForm, MedicaoForm, 
                     DetalhesMedicaoForm) # Adicione DetalhesMedicaoForm
from models import (db, Secretaria, Obra, Andamento, Gasto, Medicao, 
                    OrcamentoMedicaoObra) # Adicione OrcamentoMedicaoObraimport openpyxl
from io import BytesIO
from sqlalchemy import extract
from datetime import datetime
import calendar
import os
from dotenv import load_dotenv
import telegram
#
from sqlalchemy import or_, desc, asc, func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from datetime import timedelta

# Carrega as variáveis do ficheiro .env para o ambiente
load_dotenv()

app = Flask(__name__)
# --- ADICIONE ESTE BLOCO DE CÓDIGO ---
def format_currency(value):
    """Formata um número para o padrão de moeda brasileiro (BRL)."""
    if value is None:
        return "R$ 0,00"
    # Esta é uma forma inteligente de trocar pontos por vírgulas e vice-versa.
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Regista a função como um filtro no ambiente Jinja2
app.jinja_env.filters['currency'] = format_currency
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
# ADICIONE ESTE NOVO BLOCO
@app.cli.command("init-db")
def init_db_command():
    """Cria as tabelas do banco de dados."""
    with app.app_context():
        db.create_all()
    print("Banco de dados inicializado.")
    
@app.route('/')
def index():
    # MODIFICADO: Usa options(joinedload(...)) para garantir que as medições sejam carregadas
    secretarias = Secretaria.query.options(joinedload(Secretaria.medicoes)).all()

    return render_template('dashboard_telegram.html', secretarias=secretarias, active_page='painel')

@app.route('/secretarias')
def listar_secretarias():
    secretarias = Secretaria.query.all()
    # Adicione active_page='secretarias'
    return render_template('secretarias.html', secretarias=secretarias, active_page='secretarias')

@app.route('/secretaria/adicionar', methods=['GET', 'POST'])
def adicionar_secretaria():
    form = SecretariaForm()
    if form.validate_on_submit():
        nova_secretaria = Secretaria(nome=form.nome.data)
        db.session.add(nova_secretaria)
        
        try:
            # Tenta salvar na base de dados
            db.session.commit()
            flash('Secretaria criada com sucesso! Agora adicione a primeira medição financeira.', 'success')
            return redirect(url_for('detalhes_secretaria', secretaria_id=nova_secretaria.id))
        
        except IntegrityError:
            # Se ocorrer um erro de integridade (nome duplicado)
            db.session.rollback()  # Desfaz a tentativa de adição
            flash(f'Erro: Já existe uma secretaria com o nome "{form.nome.data}". Por favor, escolha outro nome.', 'danger')
            # Redireciona de volta para o formulário de adição
            return redirect(url_for('adicionar_secretaria'))

    return render_template('adicionar_secretaria.html', form=form, active_page='secretarias')

@app.route('/secretaria/<int:secretaria_id>/editar', methods=['GET', 'POST'])
def editar_secretaria(secretaria_id):
    secretaria = Secretaria.query.get_or_404(secretaria_id)
    form = SecretariaForm(obj=secretaria)
    if form.validate_on_submit():
        secretaria.nome = form.nome.data
        db.session.commit()
        flash('Secretaria atualizada com sucesso!', 'success')
        return redirect(url_for('listar_secretarias'))
    return render_template('editar_secretaria.html', form=form, active_page='secretarias')

@app.route('/secretaria/<int:secretaria_id>/remover', methods=['POST'])
def remover_secretaria(secretaria_id):
    secretaria = Secretaria.query.get_or_404(secretaria_id)
    db.session.delete(secretaria)
    db.session.commit()
    flash('Secretaria e todas as suas obras foram removidas com sucesso.', 'success')
    return redirect(url_for('listar_secretarias'))

# Em app.py

@app.route('/api/gastos_diarios/secretaria/<int:secretaria_id>')
def api_gastos_diarios(secretaria_id):
    """Retorna dados diários para o gráfico de linha avançado, incluindo marcadores de medição."""
    with app.app_context():
        # Carrega a secretaria e todos os seus dados relacionados de forma otimizada (eager loading)
        secretaria = db.session.query(Secretaria).options(
            joinedload(Secretaria.medicoes).joinedload(Medicao.orcamentos_obras),
            joinedload(Secretaria.obras).joinedload(Obra.gastos)
        ).filter_by(id=secretaria_id).first_or_404()

        medicoes = secretaria.medicoes

        # Se não houver medições, retorna dados vazios para o gráfico não quebrar
        if not medicoes:
            return jsonify({'labels': [], 'gastos': [], 'saldos': [], 'teto_orcamento': 0, 'medicoes': []})

        # 1. Encontrar o intervalo de datas completo de todas as medições
        min_data = min(m.data_inicio for m in medicoes)
        max_data = max(m.data_fim for m in medicoes)

        # 2. Preparar as estruturas de dados para cada dia no intervalo
        delta = max_data - min_data
        datas_range = [min_data + timedelta(days=i) for i in range(delta.days + 1)]
        
        labels = [d.strftime('%d/%m') for d in datas_range]
        gastos_diarios = {d: 0.0 for d in datas_range}
        orcamentos_diarios = {d: 0.0 for d in datas_range}

        # 3. Processar orçamentos e gastos
        for medicao in medicoes:
            if medicao.data_inicio in orcamentos_diarios:
                orcamentos_diarios[medicao.data_inicio] += medicao.orcamento_total

        todos_gastos = [gasto for obra in secretaria.obras for gasto in obra.gastos if min_data <= gasto.data <= max_data]
        for gasto in todos_gastos:
            if gasto.data in gastos_diarios:
                gastos_diarios[gasto.data] += gasto.valor

        # 4. Calcular as listas de dados para o gráfico
        lista_gastos = [gastos_diarios[d] for d in datas_range]
        
        lista_saldos_acumulados = []
        saldo_acumulado = 0
        for d in datas_range:
            saldo_acumulado += orcamentos_diarios[d]
            saldo_acumulado -= gastos_diarios[d]
            lista_saldos_acumulados.append(saldo_acumulado)

        # 5. Preparar os dados para os marcadores
        dados_medicoes = [
            {
                'nome': medicao.nome,
                'data': medicao.data_inicio.strftime('%d/%m'),
                'valor': medicao.orcamento_total
            } for medicao in medicoes if medicao.orcamento_total > 0
        ]

        # 6. Montar a resposta final
        response_data = {
            'labels': labels,
            'gastos': lista_gastos,
            'saldos': lista_saldos_acumulados,
            'teto_orcamento': secretaria.orcamento_consolidado,
            'medicoes': dados_medicoes
        }

    return jsonify(response_data)

@app.route('/api/orcamento/obra/<int:obra_id>')
def api_orcamento_obra(obra_id):
    """
    Retorna os dados para o gráfico da obra:
    - O total gasto na obra.
    - O saldo restante de TODA a secretaria.
    """
    with app.app_context():
        obra = Obra.query.get_or_404(obra_id)
        dados = {
            'gasto_da_obra': obra.total_gasto,
            'saldo_da_secretaria': obra.secretaria.orcamento_restante
        }
    return jsonify(dados)

@app.route('/secretaria/<int:secretaria_id>')
def detalhes_secretaria(secretaria_id):
    """Página de detalhes de uma secretaria, mostrando suas obras e medições."""
    secretaria = Secretaria.query.get_or_404(secretaria_id)
    form_medicao = MedicaoForm() # Cria uma instância do novo formulário
    return render_template('detalhes_secretaria.html', 
                           secretaria=secretaria, 
                           form_medicao=form_medicao, # Passa o formulário para o template
                           active_page='secretarias')

@app.route('/secretaria/<int:secretaria_id>/adicionar_medicao', methods=['POST'])
def adicionar_medicao(secretaria_id):
    secretaria = Secretaria.query.get_or_404(secretaria_id)
    form = MedicaoForm()
    if form.validate_on_submit():
        nova_medicao = Medicao(
            nome=form.nome.data,
            data_inicio=form.data_inicio.data,
            data_fim=form.data_fim.data,
            secretaria_id=secretaria.id
        )
        db.session.add(nova_medicao)
        db.session.commit()
        flash('Período de Medição criado! Agora, defina os orçamentos das obras.', 'success')
        # Redireciona para a nova página de detalhes da medição
        return redirect(url_for('detalhes_medicao', medicao_id=nova_medicao.id))
    else:
        flash('Erro ao criar a medição.', 'danger')
    return redirect(url_for('detalhes_secretaria', secretaria_id=secretaria_id))

@app.route('/medicao/<int:medicao_id>', methods=['GET', 'POST'])
def detalhes_medicao(medicao_id):
    medicao = Medicao.query.get_or_404(medicao_id)
    # Busca todas as obras da secretaria-mãe desta medição
    obras_da_secretaria = medicao.secretaria.obras

    form = DetalhesMedicaoForm()

    if form.validate_on_submit():
        # Lógica para salvar os dados
        for obra_form in form.obras:
            obra_id = int(obra_form.obra_id.data)

            # Procura se já existe um orçamento para esta obra nesta medição
            orcamento = OrcamentoMedicaoObra.query.filter_by(
                medicao_id=medicao.id,
                obra_id=obra_id
            ).first()

            if not orcamento:
                # Se não existir, cria um novo
                orcamento = OrcamentoMedicaoObra(medicao_id=medicao.id, obra_id=obra_id)
                db.session.add(orcamento)

            # Atualiza os dados
            orcamento.os_inicial_secretaria = obra_form.os_inicial_secretaria.data or 0.0
            orcamento.os_qualitech = obra_form.os_qualitech.data or 0.0
            orcamento.fonte_orcamento_selecionada = obra_form.fonte_orcamento_selecionada.data

        db.session.commit()
        flash('Orçamentos da medição salvos com sucesso!', 'success')
        return redirect(url_for('detalhes_medicao', medicao_id=medicao_id))

     # --- LÓGICA GET MODIFICADA ---
    orcamentos_existentes = {orc.obra_id: orc for orc in medicao.orcamentos_obras}
    
    for obra in obras_da_secretaria:
        orcamento_existente = orcamentos_existentes.get(obra.id)
        dados_obra = {'obra_id': obra.id, 'nome': obra.nome} # Passa o nome da obra
        
        if orcamento_existente:
            dados_obra.update({
                'os_inicial_secretaria': orcamento_existente.os_inicial_secretaria,
                'os_qualitech': orcamento_existente.os_qualitech,
                'fonte_orcamento_selecionada': orcamento_existente.fonte_orcamento_selecionada
            })
        
        form.obras.append_entry(dados_obra)

    # Já não precisamos de passar 'obras_da_secretaria' separadamente
    return render_template('detalhes_medicao.html', 
                           medicao=medicao, 
                           form=form,
                           active_page='secretarias')

# Em app.py

@app.route('/obras')
def listar_obras():
    # Captura os parâmetros de pesquisa da URL
    query_search = request.args.get('q', '')
    secretaria_id_filter = request.args.get('secretaria_id', '')
    order_by_filter = request.args.get('ordenar_por', '')

    # Começa a construir a consulta à base de dados
    query = Obra.query

    # 1. Filtro de Pesquisa por Texto (Nome ou Contrato)
    if query_search:
        search_term = f"%{query_search}%"
        query = query.filter(
            or_(
                Obra.nome.ilike(search_term),
                Obra.n_contrato.ilike(search_term)
            )
        )

    # 2. Filtro por Secretaria
    if secretaria_id_filter:
        query = query.filter(Obra.secretaria_id == int(secretaria_id_filter))

    # 3. Lógica de Ordenação
    if order_by_filter == 'maior_gasto':
        # Esta consulta continua correta
        query = query.outerjoin(Gasto).group_by(Obra.id).order_by(desc(func.sum(Gasto.valor)))
    elif order_by_filter == 'menor_gasto':
        # MODIFICADO AQUI: removemos o .nulls_last()
        query = query.outerjoin(Gasto).group_by(Obra.id).order_by(asc(func.sum(Gasto.valor)))
    else:
        # Ordenação padrão por nome
        query = query.order_by(Obra.nome)
        
    obras_filtradas = query.all()

    # Busca todas as secretarias para popular o menu de filtro
    todas_secretarias = Secretaria.query.order_by(Secretaria.nome).all()

    return render_template('obras.html', 
                           obras=obras_filtradas, 
                           todas_secretarias=todas_secretarias,
                           active_page='obras')

@app.route('/obra/adicionar', methods=['GET', 'POST'])
def adicionar_obra():
    form = ObraForm()
    form.secretaria_id.choices = [(s.id, s.nome) for s in Secretaria.query.all()]
    if form.validate_on_submit():
        nova_obra = Obra()
        # A função populate_obj agora só preenche os campos existentes no formulário
        form.populate_obj(nova_obra)

        # Adiciona o andamento inicial
        novo_andamento = Andamento(obra=nova_obra, data_inicio=datetime.utcnow().date())
        db.session.add(nova_obra)
        db.session.add(novo_andamento)

        db.session.commit()
        flash('Obra cadastrada com sucesso!', 'success')
        return redirect(url_for('listar_obras'))
    return render_template('adicionar_obra.html', form=form, active_page='obras')

@app.route('/obra/<int:obra_id>/editar', methods=['GET', 'POST'])
def editar_obra(obra_id):
    obra = Obra.query.get_or_404(obra_id)
    form = ObraForm(obj=obra)
    form.secretaria_id.choices = [(s.id, s.nome) for s in Secretaria.query.all()]
    if form.validate_on_submit():
        form.populate_obj(obra)
        db.session.commit()
        flash('Obra atualizada com sucesso!', 'success')
        return redirect(url_for('listar_obras'))
    form.secretaria_id.data = obra.secretaria_id # Garante que a secretaria correta está selecionada
    return render_template('editar_obra.html', form=form, active_page='obras')

@app.route('/obra/<int:obra_id>/remover', methods=['POST'])
def remover_obra(obra_id):
    obra = Obra.query.get_or_404(obra_id)
    db.session.delete(obra)
    db.session.commit()
    flash('Obra removida com sucesso!', 'success')
    return redirect(url_for('listar_obras'))

# Em app.py

@app.route('/obra/<int:obra_id>')
def detalhes_obra(obra_id):
    obra = Obra.query.get_or_404(obra_id)
    form_gasto = GastoForm()
    
    # Esta linha carrega a lista de gastos da base de dados
    gastos_ordenados = obra.gastos 
    
    return render_template(
        'detalhes_obra.html', 
        obra=obra, 
        form_gasto=form_gasto, 
        gastos=gastos_ordenados,
        active_page='obras'
    )

@app.route('/obra/<int:obra_id>/adicionar_gasto', methods=['POST'])
def adicionar_gasto(obra_id):
    obra = Obra.query.get_or_404(obra_id)
    form = GastoForm()
    
    if form.validate_on_submit():
        valor_gasto_novo = form.valor.data

        # Validação opcional: avisa se o gasto vai deixar a secretaria negativa
        if valor_gasto_novo > obra.secretaria.orcamento_restante:
            flash(f'Atenção! Este gasto deixará o saldo geral da secretaria ({obra.secretaria.nome}) negativo.', 'warning')

        # Cria o novo objeto de gasto
        novo_gasto = Gasto(
            descricao=form.descricao.data,
            valor=valor_gasto_novo,
            data=form.data.data,
            obra_id=obra.id
        )
        
        # Adiciona o novo gasto à "sessão" (uma área de preparação)
        db.session.add(novo_gasto)
        
        # Grava (commit) permanentemente todas as alterações da sessão na base de dados
        db.session.commit()
        
        flash('Gasto registrado com sucesso!', 'success')
    else:
        flash('Erro ao registrar o gasto. Verifique os dados.', 'danger')
            
    return redirect(url_for('detalhes_obra', obra_id=obra_id))

@app.route('/gasto/<int:gasto_id>/remover', methods=['POST'])
def remover_gasto(gasto_id):
    # Encontra o gasto específico no banco de dados ou retorna erro 404 se não existir.
    gasto_a_remover = Gasto.query.get_or_404(gasto_id)
    
    # Guarda o ID da obra para saber para onde redirecionar no final.
    obra_id = gasto_a_remover.obra_id
    
    # Remove o gasto da sessão do banco de dados.
    db.session.delete(gasto_a_remover)
    
    # Confirma a remoção no banco de dados.
    db.session.commit()
    
    flash('Gasto removido com sucesso!', 'success')
    
    # Redireciona o utilizador de volta para a página de detalhes da obra.
    return redirect(url_for('detalhes_obra', obra_id=obra_id))

# Em app.py

@app.route('/medicao/<int:medicao_id>/editar', methods=['GET', 'POST'])
def editar_medicao(medicao_id):
    medicao = Medicao.query.get_or_404(medicao_id)
    form = MedicaoForm(obj=medicao)

    if form.validate_on_submit():
        # Atualiza apenas os campos que existem no formulário
        medicao.nome = form.nome.data
        medicao.data_inicio = form.data_inicio.data
        medicao.data_fim = form.data_fim.data
        
        # A linha que causava o erro foi removida daqui:
        # medicao.valor_orcado = form.valor_orcado.data
        
        db.session.commit()
        flash('Medição atualizada com sucesso!', 'success')
        return redirect(url_for('detalhes_secretaria', secretaria_id=medicao.secretaria_id))

    return render_template('editar_medicao.html', form=form, active_page='secretarias')

@app.route('/medicao/<int:medicao_id>/remover', methods=['POST'])
def remover_medicao(medicao_id):
    medicao = Medicao.query.get_or_404(medicao_id)
    secretaria_id = medicao.secretaria_id # Guarda o ID para redirecionar
    
    db.session.delete(medicao)
    db.session.commit()
    
    flash('Medição removida com sucesso.', 'success')
    return redirect(url_for('detalhes_secretaria', secretaria_id=secretaria_id))

@app.route('/api/orcamento/secretaria/<int:secretaria_id>')
def api_orcamento_secretaria(secretaria_id):
    """Retorna os dados do orçamento para o gráfico de uma secretaria."""
    with app.app_context():
        # Usamos 'options(joinedload(...))' para garantir que os dados relacionados sejam pré-carregados
        secretaria = db.session.query(Secretaria).options(
            joinedload(Secretaria.medicoes).joinedload(Medicao.orcamentos_obras),
            joinedload(Secretaria.obras).joinedload(Obra.gastos)
        ).filter_by(id=secretaria_id).first_or_404()
        
        # Com os dados pré-carregados, podemos aceder às propriedades com segurança
        dados = {
            'nome': secretaria.nome,
            'orcamento_consolidado': secretaria.orcamento_consolidado, 
            'orcamento_gasto': secretaria.orcamento_gasto,
            'orcamento_restante': secretaria.orcamento_restante
        }
    return jsonify(dados)


def enviar_alerta_telegram(mensagem):
    """Envia uma mensagem de alerta para o admin via Telegram."""
    try:
        token = os.getenv('TELEGRAM_TOKEN')
        chat_id = os.getenv('TELEGRAM_ADMIN_CHAT_ID')
        if not token or not chat_id:
            print("AVISO: Token do Telegram ou Chat ID do admin não configurado no .env")
            return

        bot = telegram.Bot(token=token)
        # Usamos a função aninhada para não bloquear a aplicação web
        async def send_async():
            await bot.send_message(chat_id=chat_id, text=mensagem, parse_mode='Markdown')

        # Executa a função assíncrona
        import asyncio
        asyncio.run(send_async())
    except Exception as e:
        print(f"Erro ao enviar alerta para o Telegram: {e}")

@app.route('/relatorio/excel')
def gerar_excel():
    workbook = openpyxl.Workbook()
    
    # Aba Resumo
    sheet_resumo = workbook.active
    sheet_resumo.title = "Resumo"
    sheet_resumo.append(['Secretaria', 'Orçamento Declarado', 'Orçamento Gasto', 'Orçamento Restante'])
    for sec in Secretaria.query.all():
        sheet_resumo.append([sec.nome, sec.orcamento_declarado, sec.orcamento_gasto, sec.orcamento_restante])

    # Aba Extrato
    sheet_extrato = workbook.create_sheet(title="Extrato de Obras")
    sheet_extrato.append(['ID Obra', 'Nome da Obra', 'Secretaria', 'Custo Total', 'Status', 'Data de Início', 'Data de Entrega'])
    for obra in Obra.query.all():
        sheet_extrato.append([
            obra.id, obra.nome, obra.secretaria.nome, obra.custo_total,
            obra.andamento.status, obra.andamento.data_inicio, obra.andamento.data_entrega
        ])

    # Salva o arquivo em memória
    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name='relatorio_obras.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    app.run(debug=True)
