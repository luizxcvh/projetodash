from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, SubmitField, SelectField, DateField
from wtforms.validators import DataRequired, Length
from datetime import datetime

class SecretariaForm(FlaskForm):
    nome = StringField('Nome da Secretaria', validators=[DataRequired(), Length(min=3, max=100)])
    orcamento_declarado = FloatField('Orçamento Declarado', validators=[DataRequired()])
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
    orcamento_previsto = FloatField('Orçamento Previsto da Obra (R$)', validators=[DataRequired()])
    secretaria_id = SelectField('Secretaria Responsável', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Cadastrar Obra')

# ADICIONADO: Formulário para lançar um novo gasto
class GastoForm(FlaskForm):
    descricao = StringField('Descrição do Gasto', validators=[DataRequired(), Length(min=3, max=200)])
    valor = FloatField('Valor (R$)', validators=[DataRequired()])
    data = DateField('Data do Gasto', format='%Y-%m-%d', default=datetime.today, validators=[DataRequired()])
    submit = SubmitField('Registrar Gasto')
