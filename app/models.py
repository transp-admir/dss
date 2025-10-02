from .extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# --- TABELAS PRINCIPAIS ---

class Motorista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unidade = db.Column(db.String(100), nullable=True)
    operacao = db.Column(db.String(100), nullable=True) # NOVO CAMPO
    nome = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    rg = db.Column(db.String(20))
    cnh = db.Column(db.String(20))
    frota = db.Column(db.String(50))
    password_hash = db.Column(db.String(256), nullable=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=True)
    
    assinaturas = db.relationship('Assinatura', backref='motorista', lazy=True)
    checklists_preenchidos = db.relationship('ChecklistPreenchido', backref='motorista', lazy=True)

    def set_password(self, password):
        if password:
            self.password_hash = generate_password_hash(password)
        else:
            # Se nenhuma senha for fornecida, use os 6 primeiros dígitos do CPF como padrão.
            if self.cpf:
                self.password_hash = generate_password_hash(self.cpf[:6])

    def check_password(self, password):
        # Se o hash da senha existir no banco, use a verificação segura.
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        # Fallback para motoristas antigos: se não houver hash, compare diretamente.
        elif self.cpf:
            return password == self.cpf[:6]
        # Se não houver nem hash nem CPF, a senha é inválida.
        return False

class Conteudo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unidade = db.Column(db.String(100), nullable=True) # NOVO CAMPO
    data = db.Column(db.Date, nullable=False)
    assunto = db.Column(db.String(200), nullable=False)
    pergunta = db.Column(db.String(500), nullable=False)
    respostas = db.Column(db.Text)  # Armazena as opções de resposta, separadas por vírgula
    resposta_correta = db.Column(db.String(100), nullable=False)
    tipo_recurso = db.Column(db.String(10), nullable=False, default='link') # 'link' ou 'arquivo'
    recurso_link = db.Column(db.String(500)) # URL do vídeo, caminho do arquivo, etc.
    
    assinaturas = db.relationship('Assinatura', backref='conteudo', lazy=True)

# --- TABELAS DE RELACIONAMENTO ---

class Assinatura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    conteudo_id = db.Column(db.Integer, db.ForeignKey('conteudo.id'), nullable=False)
    data_assinatura = db.Column(db.DateTime, default=datetime.utcnow)
    tempo_leitura = db.Column(db.Integer) # Tempo em segundos
    resposta_motorista = db.Column(db.String(100))
    assinatura_imagem = db.Column(db.Text, nullable=True) # NOVO CAMPO PARA ASSINATURA DSS

# --- ESTRUTURA PARA VEÍCULOS ---

class Placa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unidade = db.Column(db.String(100), nullable=True)
    operacao = db.Column(db.String(100), nullable=True) # NOVO CAMPO
    numero = db.Column(db.String(8), unique=True, nullable=False)
    tipo = db.Column(db.String(20), nullable=False) # Ex: CAVALO, CARRETA

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unidade = db.Column(db.String(100), nullable=True)
    operacao = db.Column(db.String(100), nullable=True) # NOVO CAMPO
    nome_conjunto = db.Column(db.String(100), unique=True, nullable=False)
    placa_cavalo_id = db.Column(db.Integer, db.ForeignKey('placa.id'), nullable=False)
    placa_carreta1_id = db.Column(db.Integer, db.ForeignKey('placa.id'), nullable=True)
    placa_carreta2_id = db.Column(db.Integer, db.ForeignKey('placa.id'), nullable=True)
    obs = db.Column(db.Text)

    # Relacionamentos para acessar os objetos Placa diretamente
    placa_cavalo = db.relationship('Placa', foreign_keys=[placa_cavalo_id])
    placa_carreta1 = db.relationship('Placa', foreign_keys=[placa_carreta1_id])
    placa_carreta2 = db.relationship('Placa', foreign_keys=[placa_carreta2_id])
    motoristas = db.relationship('Motorista', backref='veiculo', lazy=True)
    checklists_preenchidos = db.relationship('ChecklistPreenchido', backref='veiculo', lazy=True)

# --- ESTRUTURA PARA CHECKLISTS ---

class Checklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unidade = db.Column(db.String(100), nullable=True) # NOVO CAMPO
    tipo = db.Column(db.String(50), nullable=False) # DIÁRIO, SEMANAL, etc.
    codigo = db.Column(db.String(50), nullable=False)
    revisao = db.Column(db.String(20), nullable=False)
    data = db.Column(db.Date, nullable=False)

    itens = db.relationship('ChecklistItem', backref='checklist', lazy='dynamic', cascade="all, delete-orphan")
    preenchimentos = db.relationship('ChecklistPreenchido', backref='checklist', lazy=True)

class ChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'), nullable=False)
    texto = db.Column(db.String(500), nullable=False)
    ordem = db.Column(db.Integer, default=0) # Para ordenar os itens
    
    # Relacionamento de auto-referência para hierarquia
    parent_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=True)
    sub_itens = db.relationship('ChecklistItem', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade="all, delete-orphan")

class ChecklistPreenchido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklist.id'), nullable=False)
    data_preenchimento = db.Column(db.DateTime, default=datetime.utcnow)
    
    # --- NOVO CAMPO DE ASSINATURA ---
    assinatura_motorista = db.Column(db.Text, nullable=True)

    # --- CAMPOS DE TEXTO LIVRE ---
    outros_problemas = db.Column(db.Text, nullable=True)
    solucoes_adotadas = db.Column(db.Text, nullable=True)
    pendencias_gerais = db.Column(db.Text, nullable=True)

    respostas = db.relationship('ChecklistResposta', backref='preenchimento', lazy='dynamic', cascade="all, delete-orphan")

class ChecklistResposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    preenchimento_id = db.Column(db.Integer, db.ForeignKey('checklist_preenchido.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('checklist_item.id'), nullable=False)
    resposta = db.Column(db.String(50)) # Ex: 'CONFORME', 'NAO CONFORME'
    observacao = db.Column(db.Text)

    item = db.relationship('ChecklistItem')

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

    item = db.relationship('ChecklistItem')
    veiculo = db.relationship('Veiculo')
    resposta_abertura = db.relationship('ChecklistResposta')

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
    role = db.Column(db.String(50), nullable=False, default='comum') # Pode ser 'admin', 'master', ou 'comum'

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
