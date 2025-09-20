# app/models.py
from .extensions import db
from datetime import datetime

class Motorista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    rg = db.Column(db.String(20), unique=True, nullable=False)
    cnh = db.Column(db.String(20), unique=True, nullable=False)
    frota = db.Column(db.String(20))
    assinaturas = db.relationship('Assinatura', backref='motorista', lazy=True)

class Conteudo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    assunto = db.Column(db.String(200), nullable=False)
    pergunta = db.Column(db.Text, nullable=False)
    respostas = db.Column(db.Text) # CSV: "Opção A,Opção B,Opção C"
    resposta_correta = db.Column(db.String(200))
    
    tipo_recurso = db.Column(db.String(50)) # 'link' ou 'arquivo'
    recurso_link = db.Column(db.String(300)) # URL ou caminho do arquivo

    assinaturas = db.relationship('Assinatura', backref='conteudo', lazy=True)

class Assinatura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    conteudo_id = db.Column(db.Integer, db.ForeignKey('conteudo.id'), nullable=False)
    data_assinatura = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Coluna para a resposta que o motorista deu
    resposta_motorista = db.Column(db.String(200), nullable=True)
    
    # Coluna para o tempo de leitura em segundos
    tempo_leitura = db.Column(db.Integer, nullable=True)
