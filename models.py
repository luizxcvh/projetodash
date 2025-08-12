from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.orm import joinedload

db = SQLAlchemy()

class Gasto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)

class Andamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), nullable=False, default='Não Iniciada')
    data_inicio = db.Column(db.Date, nullable=True)
    data_entrega = db.Column(db.Date, nullable=True)
    ultima_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)

# --- ESTA É A NOVA CLASSE QUE ESTAVA A FALTAR ---
class OrcamentoMedicaoObra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medicao_id = db.Column(db.Integer, db.ForeignKey('medicao.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    
    os_inicial_secretaria = db.Column(db.Float, default=0.0)
    os_qualitech = db.Column(db.Float, default=0.0)
    
    fonte_orcamento_selecionada = db.Column(db.String(20), default='inicial')

    obra = db.relationship('Obra')

    @property
    def valor_efetivo(self):
        if self.fonte_orcamento_selecionada == 'qualitech':
            return self.os_qualitech
        return self.os_inicial_secretaria

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
    secretaria_id = db.Column(db.Integer, db.ForeignKey('secretaria.id'), nullable=False)
    andamento = db.relationship('Andamento', backref='obra', uselist=False, cascade="all, delete-orphan")
    gastos = db.relationship('Gasto', backref='obra', order_by="desc(Gasto.data)", cascade="all, delete-orphan")

    @property
    def total_gasto(self):
        return db.session.query(db.func.sum(Gasto.valor)).filter(Gasto.obra_id == self.id).scalar() or 0.0


class Medicao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    secretaria_id = db.Column(db.Integer, db.ForeignKey('secretaria.id'), nullable=False)
    
    # MODIFICADO AQUI: 'lazy="dynamic"' foi removido para ser compatível com o 'joinedload'
    orcamentos_obras = db.relationship('OrcamentoMedicaoObra', backref='medicao', cascade="all, delete-orphan")

    @property
    def orcamento_total(self):
        """Soma os orçamentos efetivos de todas as obras nesta medição."""
        # A lógica agora itera sobre a lista diretamente
        return sum(orcamento_obra.valor_efetivo for orcamento_obra in self.orcamentos_obras)

    @property
    def total_gasto_no_periodo(self):
        """Soma os gastos de todas as obras da secretaria dentro do período."""
        total = db.session.query(db.func.sum(Gasto.valor)).join(Obra).filter(
            Obra.secretaria_id == self.secretaria_id,
            Gasto.data >= self.data_inicio,
            Gasto.data <= self.data_fim
        ).scalar()
        return total or 0.0

    @property
    def resultado(self):
        """Calcula o resultado: Orçamento Total da Medição - Gastos no Período."""
        return self.orcamento_total - self.total_gasto_no_periodo

class Secretaria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    obras = db.relationship('Obra', backref='secretaria', lazy=True, cascade="all, delete-orphan")
    medicoes = db.relationship('Medicao', backref='secretaria', lazy=True, cascade="all, delete-orphan", order_by="desc(Medicao.data_inicio)")

    @property
    def orcamento_consolidado(self):
        total = 0
        for medicao in self.medicoes:
            total += medicao.orcamento_total
        return total

    @property
    def orcamento_gasto(self):
        total = db.session.query(db.func.sum(Gasto.valor)).join(Obra).filter(Obra.secretaria_id == self.id).scalar()
        return total or 0.0

    @property
    def orcamento_restante(self):
        return self.orcamento_consolidado - self.orcamento_gasto

    @property
    def resultado_consolidado_percentual(self):
        """Calcula o percentual de lucro ou prejuízo consolidado (geral)."""
        # Evita divisão por zero se ainda não houver orçamento
        if not self.orcamento_consolidado:
            return 0.0
        
        # Fórmula: (Saldo Geral / Orçamento Total) * 100
        resultado_geral = self.orcamento_restante
        percentual = (resultado_geral / self.orcamento_consolidado) * 100
        return percentual
