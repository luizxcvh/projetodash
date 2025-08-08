from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ADICIONADO: Nova tabela para registrar gastos individuais
class Gasto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)


class Secretaria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    orcamento_declarado = db.Column(db.Float, nullable=False, default=0.0)
    obras = db.relationship('Obra', backref='secretaria', lazy=True)

    @property
    def orcamento_gasto(self):
        # MODIFICADO: Agora soma o total gasto real de cada obra
        return sum(obra.total_gasto for obra in self.obras)

    @property
    def orcamento_restante(self):
        return self.orcamento_declarado - self.orcamento_gasto


class Obra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    objeto = db.Column(db.Text, nullable=True)
    municipio = db.Column(db.String(100), nullable=True)
    n_contrato = db.Column(db.String(50), nullable=True)
    contrato_fonte = db.Column(db.String(100), nullable=True)
    ordem_servico = db.Column(db.String(50), nullable=True)
    periodo = db.Column(db.String(50), nullable=True)
    endereco = db.Column(db.String(200), nullable=True)
    # MODIFICADO: Renomeado para refletir o valor planejado
    orcamento_previsto = db.Column(db.Float, nullable=False, default=0.0)
    secretaria_id = db.Column(db.Integer, db.ForeignKey('secretaria.id'), nullable=False)
    andamento = db.relationship('Andamento', backref='obra', uselist=False, cascade="all, delete-orphan")
    # ADICIONADO: Relação com a tabela de gastos
    # LINHA NOVA E CORRETA
    gastos = db.relationship('Gasto', backref='obra', order_by=Gasto.data.desc(), cascade="all, delete-orphan")

    # ADICIONADO: Propriedade que calcula o total gasto em tempo real
    @property
    def total_gasto(self):
        return sum(gasto.valor for gasto in self.gastos)


class Andamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), nullable=False, default='Não Iniciada')
    data_inicio = db.Column(db.Date, nullable=True)
    data_entrega = db.Column(db.Date, nullable=True)
    ultima_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
