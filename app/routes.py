from flask import (Blueprint, render_template, request, 
                   redirect, url_for, session, flash)
from .extensions import db
from .models import Motorista, Conteudo, Assinatura
from datetime import datetime
import re
import os
from werkzeug.utils import secure_filename

# --- Configuração de Upload ---
UPLOAD_FOLDER = 'app/static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- BLUEPRINT DA ÁREA PÚBLICA (MOTORISTAS) ---
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/login/motorista', methods=['GET', 'POST'])
def motorista_login():
    if request.method == 'POST':
        login_user = request.form['login']
        senha = request.form['senha']
        motoristas = Motorista.query.all()
        motorista_encontrado = None

        for motorista in motoristas:
            cpf_numerico = re.sub(r'[^0-9]', '', motorista.cpf)
            credencial = cpf_numerico[:6]

            if login_user == credencial and senha == credencial:
                motorista_encontrado = motorista
                break
        
        if motorista_encontrado:
            session['motorista_id'] = motorista_encontrado.id
            flash(f'Bem-vindo, {motorista_encontrado.nome}!', 'success')
            return redirect(url_for('main.motorista_portal')) # Redireciona para o novo portal
        else:
            flash('Usuário ou senha inválidos. Tente novamente.', 'error')
            return redirect(url_for('main.motorista_login'))

    return render_template('login.html')

@main_bp.route('/portal/motorista')
def motorista_portal():
    if 'motorista_id' not in session:
        return redirect(url_for('main.motorista_login'))
    
    motorista = Motorista.query.get(session['motorista_id'])
    if not motorista:
        session.pop('motorista_id', None)
        return redirect(url_for('main.motorista_login'))

    return render_template('motorista_portal.html', motorista=motorista)

@main_bp.route('/logout')
def logout():
    session.pop('motorista_id', None)
    flash('Você saiu do sistema.', 'success')
    return redirect(url_for('main.motorista_login'))

@main_bp.route('/conteudos')
def lista_conteudos():
    if 'motorista_id' not in session:
        return redirect(url_for('main.motorista_login'))
    
    motorista_id = session['motorista_id'] # CORRIGIDO AQUI
    conteudos = Conteudo.query.order_by(Conteudo.data.desc()).all()
    
    assinaturas = Assinatura.query.filter_by(motorista_id=motorista_id).all()
    assinaturas_motorista = {a.conteudo_id for a in assinaturas}

    return render_template('lista_conteudos.html', 
                           conteudos=conteudos, 
                           assinaturas_motorista=assinaturas_motorista)

@main_bp.route('/conteudo/<int:conteudo_id>/ver', methods=['GET', 'POST'])
def ver_conteudo(conteudo_id):
    if 'motorista_id' not in session:
        return redirect(url_for('main.motorista_login'))

    motorista_id = session['motorista_id']
    conteudo = Conteudo.query.get_or_404(conteudo_id)
    assinatura = Assinatura.query.filter_by(motorista_id=motorista_id, conteudo_id=conteudo_id).first()

    if request.method == 'POST':
        if not assinatura:
            resposta_usuario = request.form.get('resposta_usuario')
            tempo_leitura_segundos = request.form.get('tempo_leitura', 0, type=int)

            nova_assinatura = Assinatura(
                motorista_id=motorista_id,
                conteudo_id=conteudo_id,
                tempo_leitura=tempo_leitura_segundos,
                resposta_motorista=resposta_usuario
            )
            db.session.add(nova_assinatura)
            db.session.commit()

            if resposta_usuario and resposta_usuario.strip().lower() == conteudo.resposta_correta.strip().lower():
                flash('Conteúdo assinado! Sua resposta está correta.', 'success')
            else:
                flash('Conteúdo assinado. Sua resposta está incorreta, revise o material.', 'warning')
            
            return redirect(url_for('main.lista_conteudos'))
    
    return render_template('conteudo_motorista.html', 
                           conteudo=conteudo, 
                           assinatura=assinatura)


# --- BLUEPRINT DA ÁREA ADMINISTRATIVA ---
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ... (o restante do código do admin permanece o mesmo)

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == 'admin' and password == 'admin':
            session['admin_user'] = username
            flash('Login de administrador bem-sucedido!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Usuário ou senha inválidos.', 'error')
            return redirect(url_for('admin.login'))
            
    return render_template('admin_login.html')

@admin_bp.route('/logout')
def logout():
    session.pop('admin_user', None)
    flash('Você saiu da área administrativa.', 'success')
    return redirect(url_for('admin.login'))

@admin_bp.route('/dashboard')
def dashboard():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))
    return render_template('adm.html')

@admin_bp.route('/motoristas')
def motoristas():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))
    lista_motoristas = Motorista.query.all()
    return render_template('motoristas.html', motoristas=lista_motoristas)

@admin_bp.route('/motoristas/add', methods=['POST'])
def add_motorista():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))
    nome = request.form['nome']
    cpf = request.form['cpf']
    rg = request.form['rg']
    cnh = request.form['cnh']
    frota = request.form['frota']

    if Motorista.query.filter_by(cpf=cpf).first():
        flash(f'Motorista com CPF {cpf} já cadastrado.', 'error')
        return redirect(url_for('admin.motoristas'))

    novo_motorista = Motorista(nome=nome, cpf=cpf, rg=rg, cnh=cnh, frota=frota)
    db.session.add(novo_motorista)
    db.session.commit()
    flash(f'Motorista {nome} adicionado com sucesso!', 'success')
    return redirect(url_for('admin.motoristas'))

@admin_bp.route('/conteudo')
def conteudo():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))
    lista_conteudos = Conteudo.query.order_by(Conteudo.id.desc()).all()
    return render_template('conteudo.html', conteudos=lista_conteudos)

@admin_bp.route('/conteudo/add', methods=['POST'])
def add_conteudo():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))
    data_str = request.form['data']
    assunto = request.form['assunto']
    pergunta = request.form['pergunta']
    respostas = request.form['respostas']
    resposta_correta = request.form['resposta_correta']
    data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()

    tipo_recurso = request.form['tipo_recurso']
    recurso_link = None

    if tipo_recurso == 'link':
        recurso_link = request.form.get('link')
    elif tipo_recurso == 'arquivo':
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo enviado', 'error')
            return redirect(request.url)
        file = request.files['arquivo']
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            recurso_link = os.path.join('uploads', filename).replace('\\', '/')

    novo_conteudo = Conteudo(
        data=data_obj,
        assunto=assunto,
        pergunta=pergunta,
        respostas=respostas,
        resposta_correta=resposta_correta,
        tipo_recurso=tipo_recurso,
        recurso_link=recurso_link
    )
    db.session.add(novo_conteudo)
    db.session.commit()
    flash('Conteúdo adicionado com sucesso!', 'success')
    return redirect(url_for('admin.conteudo'))

@admin_bp.route('/conteudo/<int:conteudo_id>')
def conteudo_detalhe(conteudo_id):
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))
    conteudo = Conteudo.query.get_or_404(conteudo_id)
    relatorio = conteudo.assinaturas
    return render_template('conteudo_detalhe.html', conteudo=conteudo, relatorio=relatorio)