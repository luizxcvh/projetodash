from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from models import db, Secretaria, Obra, Andamento, Gasto # Adicione Gasto
from forms import SecretariaForm, ObraForm, GastoForm # Adicione GastoForm
import openpyxl
from io import BytesIO
from sqlalchemy import extract
from datetime import datetime
import calendar
import os
from dotenv import load_dotenv

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
    secretarias = Secretaria.query.all()
    # Adicione active_page='painel'
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
        nova_secretaria = Secretaria(nome=form.nome.data, orcamento_declarado=form.orcamento_declarado.data)
        db.session.add(nova_secretaria)
        db.session.commit()
        flash('Secretaria cadastrada com sucesso!', 'success')
        return redirect(url_for('listar_secretarias'))
    return render_template('adicionar_secretaria.html', form=form, active_page='secretarias')

# Em app.py

@app.route('/secretaria/<int:secretaria_id>/editar', methods=['GET', 'POST'])
def editar_secretaria(secretaria_id):
    secretaria = Secretaria.query.get_or_404(secretaria_id)
    form = SecretariaForm(obj=secretaria)  # Preenche o formulário com os dados existentes

    if form.validate_on_submit():
        secretaria.nome = form.nome.data
        secretaria.orcamento_declarado = form.orcamento_declarado.data
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

@app.route('/api/gastos_diarios/secretaria/<int:secretaria_id>')
def api_gastos_diarios(secretaria_id):
    """Retorna os gastos diários de uma secretaria para o mês atual."""
    hoje = datetime.utcnow()
    ano, mes = hoje.year, hoje.month
    
    # Encontra o número de dias no mês atual
    num_dias = calendar.monthrange(ano, mes)[1]
    
    # Prepara as listas de resposta (labels para os dias, dados com zeros)
    labels = [f"{i:02}" for i in range(1, num_dias + 1)]
    dados = [0.0] * num_dias
    
    with app.app_context():
        # Consulta que busca a soma dos gastos, agrupados por dia, para o mês e ano atuais
        gastos_do_mes = db.session.query(
            extract('day', Gasto.data).label('dia'),
            db.func.sum(Gasto.valor).label('total_gasto')
        ).join(Obra).filter(
            Obra.secretaria_id == secretaria_id,
            extract('month', Gasto.data) == mes,
            extract('year', Gasto.data) == ano
        ).group_by('dia').all()

        # Preenche a lista de dados com os valores encontrados
        for gasto in gastos_do_mes:
            # O índice da lista é dia - 1 (ex: dia 1 fica no índice 0)
            dados[gasto.dia - 1] = gasto.total_gasto
            
    return jsonify({'labels': labels, 'data': dados})

@app.route('/secretaria/<int:secretaria_id>')
def detalhes_secretaria(secretaria_id):
    """Página de detalhes de uma secretaria, mostrando suas obras."""
    secretaria = Secretaria.query.get_or_404(secretaria_id)
    return render_template('detalhes_secretaria.html', secretaria=secretaria, active_page='secretarias')

@app.route('/api/orcamento/obra/<int:obra_id>')
def api_orcamento_obra(obra_id):
    """Retorna os dados do orçamento para uma única obra."""
    with app.app_context():
        obra = Obra.query.get_or_404(obra_id)
        dados = {
            'nome': obra.nome,
            'orcamento_previsto': obra.orcamento_previsto,
            'total_gasto': obra.total_gasto,
            'saldo': obra.orcamento_previsto - obra.total_gasto
        }
    return jsonify(dados)


@app.route('/obras')
def listar_obras():
    obras = Obra.query.all()
    # Adicione active_page='obras'
    return render_template('obras.html', obras=obras, active_page='obras')

@app.route('/obra/adicionar', methods=['GET', 'POST'])
def adicionar_obra():
    form = ObraForm()
    form.secretaria_id.choices = [(s.id, s.nome) for s in Secretaria.query.all()]
    if form.validate_on_submit():
        nova_obra = Obra(
            nome=form.nome.data,
            objeto=form.objeto.data,
            municipio=form.municipio.data,
            n_contrato=form.n_contrato.data,
            contrato_fonte=form.contrato_fonte.data,
            ordem_servico=form.ordem_servico.data,
            periodo=form.periodo.data,
            endereco=form.endereco.data,
            orcamento_previsto=form.orcamento_previsto.data,
            secretaria_id=form.secretaria_id.data
        )
        # Cria um andamento inicial para a obra
        novo_andamento = Andamento(obra=nova_obra, data_inicio=datetime.utcnow().date())
        db.session.add(nova_obra)
        db.session.add(novo_andamento)
        db.session.commit()
        flash('Obra cadastrada com sucesso!', 'success')
        return redirect(url_for('listar_obras'))
    return render_template('adicionar_obra.html', form=form)


# Em app.py

@app.route('/obra/<int:obra_id>/editar', methods=['GET', 'POST'])
def editar_obra(obra_id):
    obra = Obra.query.get_or_404(obra_id)
    # Precisamos de popular as escolhas da secretaria no formulário
    form = ObraForm(obj=obra)
    form.secretaria_id.choices = [(s.id, s.nome) for s in Secretaria.query.all()]

    if form.validate_on_submit():
        # Atualiza os campos do objeto obra com os dados do formulário
        form.populate_obj(obra)
        db.session.commit()
        flash('Obra atualizada com sucesso!', 'success')
        return redirect(url_for('listar_obras'))

    # Garante que o valor selecionado no GET seja o correto
    form.secretaria_id.data = obra.secretaria_id
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
    
    # A lista de gastos já vem ordenada pela definição do modelo
    gastos_ordenados = obra.gastos 
    
    # NOVO: Calcula o saldo restante da secretaria
    saldo_secretaria = obra.secretaria.orcamento_restante
    
    return render_template(
        'detalhes_obra.html', 
        obra=obra, 
        form_gasto=form_gasto, 
        gastos=gastos_ordenados,
        saldo_secretaria=saldo_secretaria, # Passa o saldo para o template
        active_page='obras'
    )

# Em app.py

@app.route('/obra/<int:obra_id>/adicionar_gasto', methods=['POST'])
def adicionar_gasto(obra_id):
    obra = Obra.query.get_or_404(obra_id)
    form = GastoForm()
    
    if form.validate_on_submit():
        valor_gasto = form.valor.data
        
        # --- VALIDAÇÃO DE SALDO NO BACKEND ---
        saldo_secretaria = obra.secretaria.orcamento_restante
        
        if valor_gasto > saldo_secretaria:
            # Se o gasto for maior que o saldo, mostra uma mensagem de erro.
            flash(f'Erro: O valor do gasto (R$ {valor_gasto:,.2f}) excede o saldo disponível da secretaria (R$ {saldo_secretaria:,.2f}).', 'danger')
            # Redireciona de volta sem salvar o gasto.
            return redirect(url_for('detalhes_obra', obra_id=obra_id))
        # --- FIM DA VALIDAÇÃO ---
            
        novo_gasto = Gasto(
            descricao=form.descricao.data,
            valor=valor_gasto,
            data=form.data.data,
            obra_id=obra.id
        )
        db.session.add(novo_gasto)
        db.session.commit()
        flash('Gasto registrado com sucesso!', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Erro no campo "{getattr(form, field).label.text}": {error}', 'danger')
                
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

@app.route('/api/orcamento/secretaria/<int:secretaria_id>')
def api_orcamento_secretaria(secretaria_id):
    secretaria = Secretaria.query.get_or_404(secretaria_id)
    data = {
        'nome': secretaria.nome,
        'orcamento_declarado': secretaria.orcamento_declarado,
        'orcamento_gasto': secretaria.orcamento_gasto,
        'orcamento_restante': secretaria.orcamento_restante
    }
    return jsonify(data)

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
