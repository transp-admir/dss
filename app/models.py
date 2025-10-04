from .extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# --- TABELAS PRINCIPAIS ---

class Motorista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unidade = db.Column(db.String(100), nullable=True)
    operacao = db.Column(db.String(100), nullable=True)
    nome = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    rg = db.Column(db.String(20))
    cnh = db.Column(db.String(20))
    frota = db.Column(db.String(50))
    password_hash = db.Column(db.String(256), nullable=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=True)
    
    assinaturas = db.relationship('Assinatura', backref='motorista', lazy=True, cascade="all, delete-orphan")
    checklists_preenchidos = db.relationship('ChecklistPreenchido', backref='motorista', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        if password:
            self.password_hash = generate_password_hash(password)
        else:
            if self.cpf:
                self.password_hash = generate_password_hash(self.cpf[:6])

    def check_password(self, password):
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        elif self.cpf:
            return password == self.cpf[:6]
        return False

class Conteudo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unidade = db.Column(db.String(100), nullable=True)
    data = db.Column(db.Date, nullable=False)
    assunto = db.Column(db.String(200), nullable=False)
    pergunta = db.Column(db.String(500), nullable=False)
    respostas = db.Column(db.Text)
    resposta_correta = db.Column(db.String(100), nullable=False)
    tipo_recurso = db.Column(db.String(10), nullable=False, default='link')
    recurso_link = db.Column(db.String(500))
    
    assinaturas = db.relationship('Assinatura', backref='conteudo', lazy=True, cascade="all, delete-orphan")

# --- TABELAS DE RELACIONAMENTO ---

class Assinatura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    conteudo_id = db.Column(db.Integer, db.ForeignKey('conteudo.id'), nullable=False)
    data_assinatura = db.Column(db.DateTime, default=datetime.utcnow)
    tempo_leitura = db.Column(db.Integer)
    resposta_motorista = db.Column(db.String(100))
    assinatura_imagem = db.Column(db.Text, nullable=True)

# --- ESTRUTURA PARA VEÍCULOS ---

class Placa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unidade = db.Column(db.String(100), nullable=True)
    operacao = db.Column(db.String(100), nullable=True)
    numero = db.Column(db.String(8), unique=True, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unidade = db.Column(db.String(100), nullable=True)
    operacao = db.Column(db.String(100), nullable=True)
    nome_conjunto = db.Column(db.String(100), unique=True, nullable=False)
    placa_cavalo_id = db.Column(db.Integer, db.ForeignKey('placa.id'), nullable=False)
    placa_carreta1_id = db.Column(db.Integer, db.ForeignKey('placa.id'), nullable=True)
    placa_carreta2_id = db.Column(db.Integer, db.ForeignKey('placa.id'), nullable=True)
    obs = db.Column(db.Text)

    placa_cavalo = db.relationship('Placa', foreign_keys=[placa_cavalo_id])
    placa_carreta1 = db.relationship('Placa', foreign_keys=[placa_carreta1_id])
    placa_carreta2 = db.relationship('Placa', foreign_keys=[placa_carreta2_id])
    motoristas = db.relationship('Motorista', backref='veiculo', lazy=True)
    checklists_preenchidos = db.relationship('ChecklistPreenchido', backref='veiculo', lazy=True, cascade="all, delete-orphan")
    pendencias = db.relationship('Pendencia', backref='veiculo', lazy=True, cascade="all, delete-orphan")

# --- ESTRUTURA PARA CHECKLISTS ---

class Checklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    unidade = db.Column(db.String(100), nullable=True)
    tipo = db.Column(db.String(50), nullable=False)
    codigo = db.Column(db.String(50), nullable=False)
    revisao = db.Column(db.String(20), nullable=False)
    data = db.Column(db.Date, nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)

    itens = db.relationship('ChecklistItem', backref='checklist', lazy='dynamic', cascade="all, delete-orphan")
    preenchimentos = db.relationship('ChecklistPreenchido', backref='checklist', lazy=True, cascade="all, delete-orphan")

class ChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'), nullable=False)
    texto = db.Column(db.String(500), nullable=False)
    # CORRIGIDO: Usa String para preservar o formato exato (ex: 2.10)
    ordem = db.Column(db.String(20), nullable=False, default='0')
    
    parent_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=True)
    sub_itens = db.relationship('ChecklistItem', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade="all, delete-orphan")

class ChecklistPreenchido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'), nullable=False)
    data_preenchimento = db.Column(db.DateTime, default=datetime.utcnow)
    
    assinatura_motorista = db.Column(db.Text, nullable=True)
    assinatura_responsavel = db.Column(db.Text, nullable=True)
    outros_problemas = db.Column(db.Text, nullable=True)
    solucoes_adotadas = db.Column(db.Text, nullable=True)
    pendencias_gerais = db.Column(db.Text, nullable=True)

    respostas = db.relationship('ChecklistResposta', backref='preenchimento', lazy='dynamic', cascade="all, delete-orphan")
    extintores = db.relationship('ExtintorCheck', backref='preenchimento', lazy='dynamic', cascade="all, delete-orphan")

class ChecklistResposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    preenchimento_id = db.Column(db.Integer, db.ForeignKey('checklist_preenchido.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=False)
    resposta = db.Column(db.String(50))
    observacao = db.Column(db.Text)

    item = db.relationship('ChecklistItem')
    pendencia = db.relationship('Pendencia', backref='resposta_abertura', uselist=False, cascade="all, delete-orphan")

# --- NOVA TABELA PARA EXTINTORES ---
class ExtintorCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    preenchimento_id = db.Column(db.Integer, db.ForeignKey('checklist_preenchido.id'), nullable=False)
    local = db.Column(db.String(50), nullable=False)
    tipo = db.Column(db.String(50))
    peso = db.Column(db.String(20))
    vencimento = db.Column(db.Date, nullable=True)
    trocado = db.Column(db.String(3))
    motivo_troca = db.Column(db.Text, nullable=True)

# --- ESTRUTURA PARA PENDÊNCIAS ---

class Pendencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=False)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    resposta_abertura_id = db.Column(db.Integer, db.ForeignKey('checklist_resposta.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='PENDENTE')
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_resolucao = db.Column(db.DateTime, nullable=True)
    observacao_admin = db.Column(db.Text, nullable=True)
    numero_os = db.Column(db.String(50), nullable=True)

    item = db.relationship('ChecklistItem')

# --- ESTRUTURA PARA DOCUMENTOS FIXOS ---

class DocumentoFixo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    data_upload = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# --- ESTRUTURA PARA USUÁRIOS DO SISTEMA ---

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), unique=True, nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    setor = db.Column(db.String(100), nullable=True)
    unidade = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='comum')

    @property
    def password(self):
        raise AttributeError('A senha não é um atributo legível.')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Usuario {self.nome}>'
