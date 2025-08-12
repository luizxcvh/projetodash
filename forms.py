# Em forms.py
from flask_wtf import FlaskForm
from wtforms import (StringField, TextAreaField, FloatField, SubmitField, 
                     SelectField, DateField, HiddenField, RadioField)
from wtforms.validators import DataRequired, Length
from wtforms.form import Form
from wtforms.fields import FieldList, FormField
from datetime import datetime

# --- Formulários Principais ---

class SecretariaForm(FlaskForm):
    nome = StringField('Nome da Secretaria', validators=[DataRequired(), Length(min=3, max=100)])
    submit = SubmitField('Cadastrar Secretaria')

class ObraForm(FlaskForm):
    nome = StringField('Nome da Obra', validators=[DataRequired(), Length(min=5, max=200)])
    objeto = TextAreaField('Objeto')
    municipio = StringField('Município')
    n_contrato = StringField('Nº do Contrato')
    contrato_fonte = StringField('Contrato Fonte')
    ordem_servico = StringField('Ordem de Serviço')
    periodo = StringField('Período')
    endereco = StringField('Endereço')
    secretaria_id = SelectField('Secretaria Responsável', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Cadastrar Obra')

class GastoForm(FlaskForm):
    descricao = StringField('Descrição do Gasto', validators=[DataRequired(), Length(min=3, max=200)])
    valor = FloatField('Valor (R$)', validators=[DataRequired()])
    data = DateField('Data do Gasto', format='%Y-%m-%d', default=datetime.today, validators=[DataRequired()])
    submit = SubmitField('Registrar Gasto')

# --- Formulários para a Nova Lógica de Medição ---

class MedicaoForm(FlaskForm):
    """Formulário simplificado para criar uma medição (período)."""
    nome = StringField('Nome/Referência da Medição', validators=[DataRequired(), Length(min=5, max=150)],
                       render_kw={"placeholder": "Ex: Medição de Agosto/2025"})
    data_inicio = DateField('Data de Início', format='%Y-%m-%d', validators=[DataRequired()])
    data_fim = DateField('Data de Fim', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Criar Período de Medição')

class OrcamentoObraSubForm(Form):
    """Sub-formulário para uma única linha de obra na página de medição."""
    obra_id = HiddenField()
    
    # ADICIONE ESTE CAMPO (será apenas para leitura no template)
    nome = StringField('Nome da Obra') 
    
    os_inicial_secretaria = FloatField('OS Inicial (Secretaria)')
    os_qualitech = FloatField('OS QUALITECH')
    fonte_orcamento_selecionada = RadioField(
        'Fonte',
        choices=[('inicial', 'OS Inicial'), ('qualitech', 'OS Qualitech')],
        default='inicial'
    )

class DetalhesMedicaoForm(FlaskForm):
    """Formulário principal que contém uma lista de sub-formulários de obras."""
    obras = FieldList(FormField(OrcamentoObraSubForm))
    submit = SubmitField('Salvar Orçamentos da Medição')
