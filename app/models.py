# Conteúdo completo para o arquivo app/models.py

from .extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

# --- MODELO DE USUÁRIO (ADMIN, MASTER, COMUM) ---
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    setor = db.Column(db.String(50))
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), nullable=False, default='comum') # admin, master, comum
    unidade = db.Column(db.String(100))

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Usuario {self.nome}>'

# --- MODELO DE VEÍCULOS E PLACAS ---
class Placa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), unique=True, nullable=False)
    tipo = db.Column(db.String(20), nullable=False) # CAVALO, CARRETA
    unidade = db.Column(db.String(100))
    operacao = db.Column(db.String(100))

    def __repr__(self):
        return f'<Placa {self.numero}>'

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_conjunto = db.Column(db.String(100), unique=True, nullable=False)
    unidade = db.Column(db.String(100))
    operacao = db.Column(db.String(100))
    obs = db.Column(db.Text)
    
    placa_cavalo_id = db.Column(db.Integer, db.ForeignKey('placa.id'), unique=True)
    placa_carreta1_id = db.Column(db.Integer, db.ForeignKey('placa.id'), unique=True)
    placa_carreta2_id = db.Column(db.Integer, db.ForeignKey('placa.id'), unique=True)
    
    placa_cavalo = db.relationship('Placa', foreign_keys=[placa_cavalo_id])
    placa_carreta1 = db.relationship('Placa', foreign_keys=[placa_carreta1_id])
    placa_carreta2 = db.relationship('Placa', foreign_keys=[placa_carreta2_id])

    motorista = db.relationship('Motorista', back_populates='veiculo', uselist=False)
    indisponibilidades = db.relationship('VeiculoIndisponibilidade', backref='veiculo', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Veiculo {self.nome_conjunto}>'

# --- MODELO DE MOTORISTA ---
class Motorista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    rg = db.Column(db.String(20))
    cnh = db.Column(db.String(20))
    frota = db.Column(db.String(50))
    unidade = db.Column(db.String(100))
    operacao = db.Column(db.String(100))
    password_hash = db.Column(db.String(256))
    
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=True, unique=True)
    veiculo = db.relationship('Veiculo', back_populates='motorista')
    
    assinaturas = db.relationship('Assinatura', backref='motorista', lazy=True)
    checklists_preenchidos = db.relationship('ChecklistPreenchido', backref='motorista', lazy='dynamic')

    def set_password(self, password):
        if not password:
            password = self.cpf[:6]
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            self.set_password(None)
            db.session.commit()
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Motorista {self.nome}>'

# --- MODELOS DE CONTEÚDO E ASSINATURA ---
class Conteudo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    assunto = db.Column(db.String(200), nullable=False)
    pergunta = db.Column(db.String(500))
    respostas = db.Column(db.Text)
    resposta_correta = db.Column(db.String(100))
    tipo_recurso = db.Column(db.String(20))
    recurso_link = db.Column(db.String(500))
    assinaturas = db.relationship('Assinatura', backref='conteudo', lazy=True)

class Assinatura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_assinatura = db.Column(db.DateTime, default=datetime.utcnow)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    conteudo_id = db.Column(db.Integer, db.ForeignKey('conteudo.id'), nullable=False)
    tempo_leitura = db.Column(db.Integer)
    resposta_motorista = db.Column(db.String(100))
    assinatura_imagem = db.Column(db.Text)

# --- MODELOS DE CHECKLIST ---
class Checklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    codigo = db.Column(db.String(50))
    revisao = db.Column(db.String(20))
    data = db.Column(db.Date)
    tipo = db.Column(db.String(50), nullable=False) # DIÁRIO, SEMANAL, MENSAL, OUTRO
    unidade = db.Column(db.String(100), nullable=True) # Se nulo, é global
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    itens = db.relationship('ChecklistItem', backref='checklist', lazy='dynamic', cascade="all, delete-orphan")

class ChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.Text, nullable=False)
    ordem = db.Column(db.String(10)) 
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=True)
    sub_itens = db.relationship('ChecklistItem', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade="all, delete-orphan")
    setor_responsavel = db.Column(db.String(100), nullable=True) # CAMPO ADICIONADO

class ChecklistPreenchido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_preenchimento = db.Column(db.DateTime, default=datetime.utcnow)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'), nullable=False)
    assinatura_motorista = db.Column(db.Text)
    assinatura_responsavel = db.Column(db.Text, nullable=True)
    outros_problemas = db.Column(db.Text)
    solucoes_adotadas = db.Column(db.Text)
    pendencias_gerais = db.Column(db.Text)
    
    checklist = db.relationship('Checklist')
    veiculo = db.relationship('Veiculo')
    respostas = db.relationship('ChecklistResposta', backref='preenchimento', lazy='dynamic', cascade="all, delete-orphan")
    extintores_check = db.relationship('ExtintorCheck', backref='preenchimento', lazy='dynamic', cascade="all, delete-orphan")

class ChecklistResposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    checklist_preenchido_id = db.Column(db.Integer, db.ForeignKey('checklist_preenchido.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=False)
    resposta = db.Column(db.String(50)) # 'CONFORME', 'NAO CONFORME', 'N/A'
    observacao = db.Column(db.Text)
    item = db.relationship('ChecklistItem')

class Pendencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    item_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=False)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    resposta_abertura_id = db.Column(db.Integer, db.ForeignKey('checklist_resposta.id'), nullable=False)
    status = db.Column(db.String(50), default='PENDENTE') # PENDENTE, RESOLVIDO
    data_resolucao = db.Column(db.DateTime, nullable=True)
    observacao_admin = db.Column(db.Text)
    numero_os = db.Column(db.String(100))
    
    item = db.relationship('ChecklistItem')
    veiculo = db.relationship('Veiculo')
    resposta_abertura = db.relationship('ChecklistResposta')

class ExtintorCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    checklist_preenchido_id = db.Column(db.Integer, db.ForeignKey('checklist_preenchido.id'), nullable=False)
    local = db.Column(db.String(100))
    tipo = db.Column(db.String(50))
    peso = db.Column(db.String(20))
    vencimento = db.Column(db.Date)
    trocado = db.Column(db.String(10))
    motivo_troca = db.Column(db.Text)

class DocumentoFixo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)


# --- NOVOS MODELOS E MODELOS RESTAURADOS ---

class VeiculoIndisponibilidade(db.Model):
    """Registra um período em que um veículo está indisponível para operação (e, portanto, para checklists)."""
    __tablename__ = 'veiculo_indisponibilidade'
    id = db.Column(db.Integer, primary_key=True)
    data_inicio = db.Column(db.Date, nullable=False, default=date.today)
    data_fim = db.Column(db.Date, nullable=True) # Se nulo, a indisponibilidade é por tempo indeterminado.
    motivo = db.Column(db.Text, nullable=False) # Ex: "Em manutenção", "Vendido", "Aguardando documentação"
    
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', backref='indisponibilidades_criadas')

    def __repr__(self):
        return f'<Indisponibilidade para Veiculo {self.veiculo_id} a partir de {self.data_inicio}>'

# Para a funcionalidade de isentar um motorista individualmente do preenchimento
class MotoristaIsencao(db.Model):
    __tablename__ = 'motorista_isencao'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    motivo = db.Column(db.String(255), nullable=False)
    tipo_checklist = db.Column(db.String(50), nullable=False) # DIÁRIO, MENSAL, etc.

    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    motorista = db.relationship('Motorista', backref='isencoes')
    usuario = db.relationship('Usuario', backref='isencoes_criadas')

    __table_args__ = (db.UniqueConstraint('data', 'motorista_id', 'tipo_checklist', name='_data_motorista_tipo_uc'),)

    def __repr__(self):
        return f'<Isenção para {self.motorista.nome} em {self.data} do checklist {self.tipo_checklist}>'
