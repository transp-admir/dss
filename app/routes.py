from flask import (Blueprint, render_template, request, 
                   redirect, url_for, session, flash, jsonify, Response)
from functools import wraps

from .models import (Usuario, Motorista, Conteudo, Assinatura, Checklist, 
                   ChecklistItem, Placa, Veiculo, ChecklistPreenchido, 
                   ChecklistResposta, Pendencia, DocumentoFixo, ExtintorCheck,
                   VeiculoIndisponibilidade, MotoristaIsencao)



# No topo de app/routes.py
from datetime import datetime, date, timedelta



# --- BLUEPRINT DA ÁREA ADMINISTRATIVA ---
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

from decimal import Decimal, InvalidOperation
import pandas as pd
import io
from flask import send_from_directory
from .extensions import db
from datetime import datetime, date
import re
import os
from werkzeug.utils import secure_filename
from collections import defaultdict
from sqlalchemy import and_, or_
from fpdf import FPDF

# --- Classe Auxiliar para gerar o PDF com Cabeçalho e Rodapé ---
class PDF(FPDF):
    def __init__(self, title, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report_title = title

    def header(self):
        # Define a fonte para o cabeçalho
        self.set_font('Arial', 'B', 14)
        # Título
        self.cell(0, 10, self.report_title, 0, 1, 'C')
        # Quebra de linha
        self.ln(5)

    def footer(self):
        # Posiciona o cursor a 1.5 cm do fim da página
        self.set_y(-15)
        # Define a fonte para o rodapé
        self.set_font('Arial', 'I', 8)
        # Número da página
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

# --- DECORADOR DE VERIFICAÇÃO DE LOGIN E ROLE ---
def login_required(required_role=["admin", "master", "comum"]):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor, faça login para acessar esta página.', 'warning')
                return redirect(url_for('admin.login'))
            
            user_role = session.get('role')
            if user_role not in required_role:
                flash('Você não tem permissão para acessar esta página.', 'danger')
                return redirect(url_for('admin.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


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




@main_bp.route('/portal/motorista')
def motorista_portal():
    """Portal principal do motorista após o login."""
    if 'motorista_id' not in session:
        return redirect(url_for('main.motorista_login'))
    
    motorista = Motorista.query.get(session['motorista_id'])
    if not motorista:
        session.pop('motorista_id', None)
        flash('Não foi possível encontrar seus dados. Faça login novamente.', 'warning')
        return redirect(url_for('main.motorista_login'))

    # Assumindo que você tenha um template 'motorista_portal.html'
    return render_template('motorista_portal.html', motorista=motorista)

@main_bp.route('/login/motorista', methods=['GET', 'POST'])
def motorista_login():
    """Página de login para motoristas."""
    if request.method == 'POST':
        login_user = request.form.get('login') # Pode ser o CPF
        senha = request.form.get('senha')
        motorista = Motorista.query.filter_by(cpf=login_user).first()
        
        if motorista and motorista.check_password(senha):
            session['motorista_id'] = motorista.id
            flash(f'Bem-vindo, {motorista.nome}!', 'success')
            return redirect(url_for('main.motorista_portal'))
        else:
            flash('CPF ou senha inválidos. Tente novamente.', 'error')
            return redirect(url_for('main.motorista_login'))
            
    return render_template('login.html')
#-----------------------------------------------------------------------
# ROTA PARA LISTAR E BAIXAR DOCUMENTOS FIXOS (MOTORISTA)
#-----------------------------------------------------------------------




# --- ROTAS DE GERENCIAMENTO DE VEÍCULOS E PLACAS ---

@admin_bp.route('/veiculos')
@login_required()
def veiculos():
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # Filtra os veículos e placas com base na unidade do usuário
    veiculos_query = Veiculo.query
    placas_query = Placa.query
    if user_role != 'admin':
        veiculos_query = veiculos_query.filter(Veiculo.unidade == user_unidade)
        placas_query = placas_query.filter(Placa.unidade == user_unidade)

    lista_veiculos = veiculos_query.order_by(Veiculo.nome_conjunto).all()
    todas_as_placas = placas_query.order_by(Placa.numero).all()
    
    # Identifica os IDs de todas as placas que já estão em uso
    placas_em_uso_ids = set()
    for v in Veiculo.query.all(): # Precisamos checar todos os veículos, não apenas os filtrados
        if v.placa_cavalo_id: placas_em_uso_ids.add(v.placa_cavalo_id)
        if v.placa_carreta1_id: placas_em_uso_ids.add(v.placa_carreta1_id)
        if v.placa_carreta2_id: placas_em_uso_ids.add(v.placa_carreta2_id)

    # Cria listas de placas disponíveis para os formulários
    placas_cavalo_disponiveis = [p for p in todas_as_placas if p.tipo == 'CAVALO' and p.id not in placas_em_uso_ids]
    placas_carreta_disponiveis = [p for p in todas_as_placas if p.tipo == 'CARRETA' and p.id not in placas_em_uso_ids]

    unidades_disponiveis = []
    if user_role == 'admin':
        unidades_db = db.session.query(Usuario.unidade).distinct().all()
        unidades_disponiveis = sorted([u[0] for u in unidades_db if u[0]])

    return render_template(
        'veiculos.html',
        veiculos=lista_veiculos,
        placas=todas_as_placas, # Lista de todas as placas para a coluna da direita
        placas_cavalo_disponiveis=placas_cavalo_disponiveis,
        placas_carreta_disponiveis=placas_carreta_disponiveis,
        unidades_disponiveis=unidades_disponiveis
    )

@admin_bp.route('/veiculos/add', methods=['POST'])
@login_required()
def add_veiculo():
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    
    nome_conjunto = request.form.get('nome_conjunto')
    unidade = request.form.get('unidade')
    operacao = request.form.get('operacao')
    placa_cavalo_id = request.form.get('placa_cavalo_id')
    placa_carreta1_id = request.form.get('placa_carreta1_id')
    placa_carreta2_id = request.form.get('placa_carreta2_id')

    if not nome_conjunto or not placa_cavalo_id:
        flash('Nome do conjunto e Placa do Cavalo são obrigatórios.', 'danger')
        return redirect(url_for('admin.veiculos'))

    if user_role != 'admin':
        unidade = user_unidade

    if not unidade:
        flash('A unidade é obrigatória.', 'danger')
        return redirect(url_for('admin.veiculos'))

    if Veiculo.query.filter_by(nome_conjunto=nome_conjunto).first():
        flash(f'Já existe um conjunto com o nome "{nome_conjunto}".', 'danger')
        return redirect(url_for('admin.veiculos'))

    novo_veiculo = Veiculo(
        nome_conjunto=nome_conjunto, 
        unidade=unidade,
        operacao=operacao,
        placa_cavalo_id=int(placa_cavalo_id) if placa_cavalo_id else None,
        placa_carreta1_id=int(placa_carreta1_id) if placa_carreta1_id else None,
        placa_carreta2_id=int(placa_carreta2_id) if placa_carreta2_id else None
    )
    db.session.add(novo_veiculo)
    db.session.commit()
    flash(f'Conjunto "{nome_conjunto}" adicionado com sucesso.', 'success')
    return redirect(url_for('admin.veiculos'))

@admin_bp.route('/veiculos/edit/<int:veiculo_id>', methods=['POST'])
@login_required()
def edit_veiculo(veiculo_id):
    veiculo = Veiculo.query.get_or_404(veiculo_id)
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    if user_role != 'admin' and veiculo.unidade != user_unidade:
        flash('Você não tem permissão para editar este veículo.', 'danger')
        return redirect(url_for('admin.veiculos'))

    veiculo.nome_conjunto = request.form.get('nome_conjunto')
    veiculo.operacao = request.form.get('operacao')
    veiculo.obs = request.form.get('obs')
    
    if user_role == 'admin':
        veiculo.unidade = request.form.get('unidade')

    veiculo.placa_cavalo_id = int(request.form.get('placa_cavalo_id')) if request.form.get('placa_cavalo_id') else None
    veiculo.placa_carreta1_id = int(request.form.get('placa_carreta1_id')) if request.form.get('placa_carreta1_id') else None
    veiculo.placa_carreta2_id = int(request.form.get('placa_carreta2_id')) if request.form.get('placa_carreta2_id') else None
    
    db.session.commit()
    flash(f'Conjunto "{veiculo.nome_conjunto}" atualizado com sucesso.', 'success')
    return redirect(url_for('admin.veiculos'))

@admin_bp.route('/placas/add', methods=['POST'])
@login_required()
def add_placa():
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    
    numero_placa = request.form.get('numero') # Corrigido para 'numero'
    tipo = request.form.get('tipo')           # Corrigido para 'tipo'
    unidade = request.form.get('unidade')
    operacao = request.form.get('operacao')   # NOVO CAMPO

    if not numero_placa or not tipo:
        flash('Número da placa e tipo são obrigatórios.', 'danger')
        return redirect(url_for('admin.veiculos'))

    if user_role != 'admin':
        unidade = user_unidade
    
    if not unidade:
        flash('A unidade é obrigatória para cadastrar a placa.', 'danger')
        return redirect(url_for('admin.veiculos'))

    if Placa.query.filter_by(numero=numero_placa.upper()).first():
        flash(f'A placa {numero_placa.upper()} já está cadastrada.', 'warning')
        return redirect(url_for('admin.veiculos'))

    nova_placa = Placa(
        numero=numero_placa.upper(), 
        tipo=tipo,
        unidade=unidade,
        operacao=operacao # NOVO CAMPO
    )
    db.session.add(nova_placa)
    db.session.commit()
    
    flash(f'Placa {numero_placa.upper()} adicionada com sucesso.', 'success')
    return redirect(url_for('admin.veiculos'))



@admin_bp.route('/veiculos/delete/<int:veiculo_id>', methods=['POST'])
@login_required()
def delete_veiculo(veiculo_id):
    veiculo = Veiculo.query.get_or_404(veiculo_id)
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    if user_role != 'admin' and veiculo.unidade != user_unidade:
        flash('Você não tem permissão para excluir este veículo.', 'danger')
        return redirect(url_for('admin.veiculos'))

    # Apenas deletamos o veículo. O banco de dados cuida do resto.
    # A lógica de "desvincular" não é necessária aqui.
    db.session.delete(veiculo)
    db.session.commit()
    flash(f'Conjunto "{veiculo.nome_conjunto}" foi excluído.', 'info')
    return redirect(url_for('admin.veiculos'))



@admin_bp.route('/placas/delete/<int:placa_id>', methods=['POST'])
@login_required()
def delete_placa(placa_id):
    placa = Placa.query.get_or_404(placa_id)
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # Adiciona verificação de permissão explícita
    if user_role != 'admin' and placa.unidade != user_unidade:
        flash('Você não tem permissão para excluir esta placa.', 'danger')
        return redirect(url_for('admin.veiculos'))
    
    # Verifica se a placa está em uso antes de excluir
    veiculo_usando = Veiculo.query.filter(
        (Veiculo.placa_cavalo_id == placa.id) |
        (Veiculo.placa_carreta1_id == placa.id) |
        (Veiculo.placa_carreta2_id == placa.id)
    ).first()

    if veiculo_usando:
        flash(f'A placa {placa.numero} não pode ser excluída pois está em uso no conjunto "{veiculo_usando.nome_conjunto}".', 'danger')
        return redirect(url_for('admin.veiculos'))

    db.session.delete(placa)
    db.session.commit()
    
    # CORRIGIDO: Usa placa.numero
    flash(f'Placa {placa.numero} excluída com sucesso.', 'info')
    return redirect(url_for('admin.veiculos'))


#-----------------------------------------------------------------------
# ROTA PARA ACESSAR DOCUMENTOS FIXOS (MOTORISTA E ADMIN)
#-----------------------------------------------------------------------
from flask import send_from_directory


#-----------------------------------------------------------------------


@main_bp.route('/logout')
def logout():
    session.pop('motorista_id', None)
    session.pop('admin_user', None)
    flash('Você saiu do sistema.', 'success')
    return redirect(url_for('main.index'))

@main_bp.route('/conteudos')
def lista_conteudos():
    if 'motorista_id' not in session:
        return redirect(url_for('main.motorista_login'))
    
    motorista_id = session['motorista_id']
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
    # Verifica se já existe uma assinatura para este motorista e conteúdo
    assinatura = Assinatura.query.filter_by(motorista_id=motorista_id, conteudo_id=conteudo_id).first()

    # Se a requisição for POST (envio do formulário)
    if request.method == 'POST':
        # E se ainda não houver uma assinatura registrada
        if not assinatura:
            # Captura todos os dados do formulário
            resposta_usuario = request.form.get('resposta_usuario')
            tempo_leitura_segundos = request.form.get('tempo_leitura', 0, type=int)
            assinatura_imagem_data = request.form.get('assinatura_imagem')

            # Validação para garantir que a resposta e a assinatura foram enviadas
            if not resposta_usuario or not assinatura_imagem_data:
                flash('É obrigatório selecionar uma resposta e assinar para confirmar.', 'danger')
                return redirect(url_for('main.ver_conteudo', conteudo_id=conteudo_id))

            # Cria o novo registro de assinatura com todos os dados
            nova_assinatura = Assinatura(
                motorista_id=motorista_id,
                conteudo_id=conteudo_id,
                tempo_leitura=tempo_leitura_segundos,
                resposta_motorista=resposta_usuario,
                assinatura_imagem=assinatura_imagem_data  # Incluindo a assinatura
            )
            db.session.add(nova_assinatura)
            db.session.commit()

            # LÓGICA ANTIGA RESTAURADA: Verifica se a resposta está correta e envia a mensagem
            if resposta_usuario.strip().lower() == conteudo.resposta_correta.strip().lower():
                flash('Conteúdo assinado! Sua resposta está correta.', 'success')
            else:
                flash('Conteúdo assinado. Sua resposta está incorreta, revise o material.', 'warning')
            
            return redirect(url_for('main.lista_conteudos'))
    
    # Se a requisição for GET, apenas exibe a página
    return render_template('conteudo_motorista.html', 
                           conteudo=conteudo, 
                           assinatura=assinatura)




# Adicione esta importação no topo do seu arquivo app/routes.py,
# junto com as outras importações de models.
from .models import ExtintorCheck 

# ... (restante do seu código)

@main_bp.route('/checklist/preencher/<int:checklist_id>', methods=['GET', 'POST'])
def preencher_checklist(checklist_id):
    if 'motorista_id' not in session:
        return redirect(url_for('main.motorista_login'))

    checklist = Checklist.query.get_or_404(checklist_id)
    motorista = Motorista.query.get(session['motorista_id'])
    veiculo_do_motorista = motorista.veiculo

    if request.method == 'POST':
        if not veiculo_do_motorista:
            flash('Você não está vinculado a um veículo. Contate o administrador.', 'danger')
            return redirect(url_for('main.lista_checklists_motorista'))

        # Captura as assinaturas e outros campos
        assinatura_motorista_data = request.form.get('assinatura_motorista')
        assinatura_responsavel_data = request.form.get('assinatura_responsavel')
        outros_problemas = request.form.get('outros_problemas')
        solucoes_adotadas = request.form.get('solucoes_adotadas')
        pendencias_gerais = request.form.get('pendencias_gerais')

        # Validação da assinatura obrigatória do motorista
        if not assinatura_motorista_data:
            flash('A assinatura do motorista é obrigatória.', 'danger')
            return redirect(url_for('main.preencher_checklist', checklist_id=checklist_id))

        # Cria o objeto ChecklistPreenchido
        novo_preenchimento = ChecklistPreenchido(
            motorista_id=motorista.id,
            veiculo_id=veiculo_do_motorista.id,
            checklist_id=checklist.id,
            assinatura_motorista=assinatura_motorista_data,
            assinatura_responsavel=assinatura_responsavel_data, # Salva a assinatura opcional
            outros_problemas=outros_problemas,
            solucoes_adotadas=solucoes_adotadas,
            pendencias_gerais=pendencias_gerais
        )
        db.session.add(novo_preenchimento)

        # Salva as respostas dos itens normais
        respostas_adicionadas = []
        for key in request.form:
            if key.startswith('resposta-'):
                item_id = int(key.split('-')[-1])
                resposta_texto = request.form.get(key)
                observacao = request.form.get(f'obs-{item_id}', '')

                nova_resposta = ChecklistResposta(
                    preenchimento=novo_preenchimento,
                    item_id=item_id,
                    resposta=resposta_texto,
                    observacao=observacao
                )
                db.session.add(nova_resposta)
                respostas_adicionadas.append(nova_resposta)

        # --- NOVA LÓGICA PARA SALVAR DADOS DOS EXTINTORES ---
        for i in range(5): # Loop para os 5 blocos de extintores
            local = request.form.get(f'extintor-{i}-local')
            tipo = request.form.get(f'extintor-{i}-tipo')
            peso = request.form.get(f'extintor-{i}-peso')
            vencimento_str = request.form.get(f'extintor-{i}-vencimento')
            trocado = request.form.get(f'extintor-{i}-trocado')
            motivo_troca = request.form.get(f'extintor-{i}-motivo')

            # Só salva se houver algum dado preenchido (além do tipo padrão)
            if peso or vencimento_str or motivo_troca:
                vencimento_data = None
                if vencimento_str:
                    try:
                        # Converte a data do formato DD/MM/AAAA para o formato do banco
                        vencimento_data = datetime.strptime(vencimento_str, '%d/%m/%Y').date()
                    except ValueError:
                        # Ignora data inválida, mas continua salvando o resto
                        pass

                novo_extintor = ExtintorCheck(
                    preenchimento=novo_preenchimento,
                    local=local,
                    tipo=tipo,
                    peso=peso,
                    vencimento=vencimento_data,
                    trocado=trocado,
                    motivo_troca=motivo_troca
                )
                db.session.add(novo_extintor)

        db.session.flush()

        # Lógica para criar pendências (permanece a mesma)
        for resposta in respostas_adicionadas:
            if resposta.resposta == 'NAO CONFORME':
                pendencia_existente = Pendencia.query.filter_by(
                    item_id=resposta.item_id,
                    veiculo_id=veiculo_do_motorista.id,
                    status='PENDENTE'
                ).first()
                if not pendencia_existente:
                    nova_pendencia = Pendencia(
                        item_id=resposta.item_id,
                        veiculo_id=veiculo_do_motorista.id,
                        resposta_abertura_id=resposta.id
                    )
                    db.session.add(nova_pendencia)
        
        db.session.commit()
        flash('Checklist enviado com sucesso!', 'success')
        return redirect(url_for('main.lista_checklists_motorista'))

    # A parte 'GET' da função permanece a mesma
    itens_principais = checklist.itens.filter_by(parent_id=None).order_by(ChecklistItem.ordem).all()
    pendencias_abertas = set()
    if veiculo_do_motorista:
        lista_pendencias = Pendencia.query.filter_by(veiculo_id=veiculo_do_motorista.id, status='PENDENTE').all()
        pendencias_abertas = {p.item_id for p in lista_pendencias}

    return render_template(
        'motorista_preencher_checklist.html',
        checklist=checklist,
        veiculo=veiculo_do_motorista,
        itens_principais=itens_principais,
        pendencias_abertas=pendencias_abertas
    )


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login para usuários administrativos (admin, master, comum)."""
    if request.method == 'POST':
        nome = request.form.get('username')
        password = request.form.get('password')
        user = Usuario.query.filter_by(nome=nome).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['admin_user'] = user.nome
            session['role'] = user.role
            session['unidade'] = user.unidade
            # --- LINHA CRÍTICA ADICIONADA ---
            session['setor'] = user.setor  # Salva o setor do usuário na sessão
            # --- FIM DA CORREÇÃO ---
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Nome de usuário ou senha inválidos.', 'danger')
            
    return render_template('admin_login.html')




@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin_user', None)
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('unidade', None)
    flash('Você saiu da área administrativa.', 'success')
    return redirect(url_for('admin.login'))


@admin_bp.route('/dashboard')
@login_required()
def dashboard():
    return render_template('adm.html')



# --- ROTAS DE GERENCIAMENTO DE USUÁRIOS (COM NOVAS REGRAS) ---

@admin_bp.route('/usuarios', methods=['GET'])
@login_required(required_role=["admin", "master"])
def gerenciar_usuarios():
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    
    query = Usuario.query
    
    if user_role == 'master':
        # Usuário master só vê usuários de sua própria unidade
        query = query.filter(Usuario.unidade == user_unidade)
        
    usuarios = query.order_by(Usuario.nome).all()
    # Para o formulário, precisamos de uma lista de unidades (apenas o admin pode ver todas)
    unidades_disponiveis = []
    if user_role == 'admin':
        # O admin pode ver e atribuir qualquer unidade. Vamos pegar todas as unidades distintas dos usuários.
        unidades_disponiveis = db.session.query(Usuario.unidade).distinct().all()
        unidades_disponiveis = sorted([u[0] for u in unidades_disponiveis if u[0]]) # Limpa e ordena

    return render_template('admin_usuarios.html', usuarios=usuarios, unidades_disponiveis=unidades_disponiveis)

@admin_bp.route('/usuarios/add', methods=['POST'])
@login_required(required_role=["admin", "master"])
def add_usuario():
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    
    nome = request.form.get('nome')
    cpf = request.form.get('cpf')
    setor = request.form.get('setor')
    password = request.form.get('password')
    role = request.form.get('role')
    unidade = request.form.get('unidade_usuario') # Nome do campo do formulário

    # Validação
    if not all([nome, cpf, password, role, unidade]):
        flash('Todos os campos são obrigatórios.', 'danger')
        return redirect(url_for('admin.gerenciar_usuarios'))

    if user_role == 'master':
        # Master não pode criar admin
        if role == 'admin':
            flash('Você não tem permissão para criar usuários administradores.', 'danger')
            return redirect(url_for('admin.gerenciar_usuarios'))
        # Master só pode criar usuários na sua própria unidade
        unidade = user_unidade # Força a unidade do master

    if Usuario.query.filter(or_(Usuario.nome == nome, Usuario.cpf == cpf)).first():
        flash('Nome de usuário ou CPF já cadastrado.', 'danger')
        return redirect(url_for('admin.gerenciar_usuarios'))

    novo_usuario = Usuario(
        nome=nome,
        cpf=cpf,
        setor=setor,
        unidade=unidade,
        role=role
    )
    novo_usuario.password = password
    
    db.session.add(novo_usuario)
    db.session.commit()
    flash(f'Usuário {nome} adicionado com sucesso!', 'success')
    return redirect(url_for('admin.gerenciar_usuarios'))

@admin_bp.route('/usuarios/edit/<int:usuario_id>', methods=['POST'])
@login_required(required_role=["admin", "master"])
def edit_usuario(usuario_id):
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    
    usuario_a_editar = Usuario.query.get_or_404(usuario_id)

    # Regras de segurança para Master
    if user_role == 'master':
        # Master não pode editar usuários de outra unidade
        if usuario_a_editar.unidade != user_unidade:
            flash('Você não tem permissão para editar usuários de outra unidade.', 'danger')
            return redirect(url_for('admin.gerenciar_usuarios'))
        # Master não pode promover ninguém a admin
        if request.form.get('role') == 'admin':
            flash('Você não tem permissão para definir usuários como administradores.', 'danger')
            return redirect(url_for('admin.gerenciar_usuarios'))
    
    # Regra para Admin: não pode rebaixar a si mesmo se for o único admin
    if usuario_a_editar.id == session.get('user_id') and request.form.get('role') != 'admin':
        admins_count = Usuario.query.filter_by(role='admin').count()
        if admins_count <= 1:
            flash('Você não pode remover seu próprio status de administrador, pois é o único existente.', 'danger')
            return redirect(url_for('admin.gerenciar_usuarios'))

    usuario_a_editar.nome = request.form.get('nome')
    usuario_a_editar.cpf = request.form.get('cpf')
    usuario_a_editar.setor = request.form.get('setor')
    usuario_a_editar.role = request.form.get('role')
    
    # Um Master não pode alterar a unidade de um usuário, um Admin pode.
    if user_role == 'admin':
        usuario_a_editar.unidade = request.form.get('unidade_usuario')
    
    password = request.form.get('password')
    if password:
        usuario_a_editar.password = password
        
    db.session.commit()
    flash(f'Usuário {usuario_a_editar.nome} atualizado com sucesso!', 'success')
    return redirect(url_for('admin.gerenciar_usuarios'))

@admin_bp.route('/usuarios/delete/<int:usuario_id>', methods=['POST'])
@login_required(required_role=["admin", "master"])
def delete_usuario(usuario_id):
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # Prevenir que o usuário se auto-delete
    if usuario_id == session.get('user_id'):
        flash('Você não pode excluir seu próprio usuário enquanto estiver logado.', 'danger')
        return redirect(url_for('admin.gerenciar_usuarios'))

    usuario_a_excluir = Usuario.query.get_or_404(usuario_id)

    # Regras de segurança para Master
    if user_role == 'master':
        # Master só pode excluir usuários da sua unidade
        if usuario_a_excluir.unidade != user_unidade:
            flash('Você não tem permissão para excluir usuários de outra unidade.', 'danger')
            return redirect(url_for('admin.gerenciar_usuarios'))
        # Master não pode excluir admins
        if usuario_a_excluir.role == 'admin':
            flash('Você não tem permissão para excluir usuários administradores.', 'danger')
            return redirect(url_for('admin.gerenciar_usuarios'))
    
    db.session.delete(usuario_a_excluir)
    db.session.commit()
    flash(f'Usuário {usuario_a_excluir.nome} excluído com sucesso.', 'info')
    return redirect(url_for('admin.gerenciar_usuarios'))



#-----------------------------------------------------------------------
# ROTA PARA GERENCIAR DOCUMENTOS FIXOS (ADMIN)
#-----------------------------------------------------------------------

# Defina esta constante no início do arquivo, junto com as outras configurações
DOCUMENTOS_UPLOAD_FOLDER = 'app/static/uploads/documentos_fixos'
DOCUMENTOS_ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'png'}

def allowed_document_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in DOCUMENTOS_ALLOWED_EXTENSIONS

@admin_bp.route('/documentos', methods=['GET', 'POST'])
def gerenciar_documentos():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')

        if not titulo or 'arquivo' not in request.files:
            flash('Título e arquivo são obrigatórios.', 'danger')
            return redirect(request.url)

        file = request.files['arquivo']

        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'danger')
            return redirect(request.url)

        if file and allowed_document_file(file.filename):
            # Cria um nome de arquivo seguro e único para evitar conflitos
            original_filename = secure_filename(file.filename)
            unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{original_filename}"
            
            # Cria o diretório se ele não existir
            if not os.path.exists(DOCUMENTOS_UPLOAD_FOLDER):
                os.makedirs(DOCUMENTOS_UPLOAD_FOLDER)
            
            # Salva o arquivo
            file.path = os.path.join(DOCUMENTOS_UPLOAD_FOLDER, unique_filename)
            file.save(file.path)

            # Salva no banco de dados
            novo_documento = DocumentoFixo(
                titulo=titulo,
                descricao=descricao,
                nome_arquivo=unique_filename
            )
            db.session.add(novo_documento)
            db.session.commit()

            flash('Documento enviado com sucesso!', 'success')
            return redirect(url_for('admin.gerenciar_documentos'))
        else:
            flash('Tipo de arquivo não permitido.', 'danger')

    documentos = DocumentoFixo.query.order_by(DocumentoFixo.data_upload.desc()).all()
    return render_template('admin_documentos.html', documentos=documentos)


@admin_bp.route('/documentos/excluir/<int:documento_id>', methods=['POST'])
def excluir_documento(documento_id):
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    documento = DocumentoFixo.query.get_or_404(documento_id)
    
    # Tenta excluir o arquivo físico
    try:
        os.remove(os.path.join(DOCUMENTOS_UPLOAD_FOLDER, documento.nome_arquivo))
    except OSError as e:
        flash(f'Erro ao excluir o arquivo físico: {e}', 'danger')

    # Exclui o registro do banco de dados
    db.session.delete(documento)
    db.session.commit()

    flash('Documento excluído com sucesso.', 'success')
    return redirect(url_for('admin.gerenciar_documentos'))

#-----------------------------------------------------------------------

# --- ROTAS DE GERENCIAMENTO DE PENDÊNCIAS (COM FILTRO DE UNIDADE) ---

@admin_bp.route('/pendencias', methods=['GET'])
@login_required()
def gerenciar_pendencias():
    user_role = session.get('role')
    # --- CORREÇÃO: Usar o 'setor' salvo na sessão ---
    user_setor = session.get('setor')

    # Query base que busca apenas pendências com status 'PENDENTE'
    query = Pendencia.query.filter(Pendencia.status == 'PENDENTE')

    # Se o usuário NÃO for 'admin', filtra as pendências pelo setor responsável
    if user_role != 'admin':
        # A consulta agora junta com ChecklistItem e compara o setor_responsavel
        query = query.join(ChecklistItem, Pendencia.item_id == ChecklistItem.id)\
                     .filter(ChecklistItem.setor_responsavel == user_setor)

    # Filtra por um veículo específico, se solicitado (funcionalidade mantida)
    veiculo_id_str = request.args.get('veiculo_id')
    veiculo_id = int(veiculo_id_str) if veiculo_id_str else None
    if veiculo_id:
        query = query.filter(Pendencia.veiculo_id == veiculo_id)

    pendencias = query.order_by(Pendencia.data_criacao.desc()).all()

    # Agrupa as pendências pelo veículo
    pendencias_agrupadas = defaultdict(list)
    for pendencia in pendencias:
        pendencias_agrupadas[pendencia.veiculo].append(pendencia)

    # Busca veículos para popular o filtro da página (lógica de unidade aqui está correta)
    user_unidade = session.get('unidade')
    veiculos_query = Veiculo.query
    if user_role != 'admin':
        veiculos_query = veiculos_query.filter(Veiculo.unidade == user_unidade)
    
    todos_veiculos = veiculos_query.order_by(Veiculo.nome_conjunto).all()

    return render_template(
        'admin_pendencias.html',
        pendencias_agrupadas=pendencias_agrupadas,
        todos_veiculos=todos_veiculos,
        veiculo_selecionado_id=veiculo_id
    )




@admin_bp.route('/pendencias/resolver', methods=['POST'])
@login_required()
def resolver_pendencia():
    user_role = session.get('role')
    # --- CORREÇÃO: Usar o 'setor' salvo na sessão ---
    user_setor = session.get('setor')

    pendencia_id = request.form.get('pendencia_id')
    pendencia = Pendencia.query.get(pendencia_id)

    if not pendencia:
        flash('Pendência não encontrada.', 'danger')
        return redirect(url_for('admin.gerenciar_pendencias'))

    # --- VERIFICAÇÃO DE SEGURANÇA CORRIGIDA ---
    # Se não for admin, verifica se o setor responsável do item é o mesmo do usuário
    if user_role != 'admin':
        if not pendencia.item or pendencia.item.setor_responsavel != user_setor:
            flash('Você não tem permissão para resolver pendências deste setor.', 'danger')
            return redirect(url_for('admin.gerenciar_pendencias'))

    if pendencia.status != 'PENDENTE':
        flash('Esta pendência já foi resolvida ou finalizada.', 'warning')
        return redirect(url_for('admin.gerenciar_pendencias'))

    # Atualiza a pendência (código inalterado)
    pendencia.status = request.form.get('status')
    pendencia.observacao_admin = request.form.get('observacao_admin')
    pendencia.numero_os = request.form.get('numero_os')
    pendencia.data_resolucao = datetime.utcnow()
    db.session.commit()

    flash(f'Pendência atualizada com sucesso.', 'success')
    return redirect(url_for('admin.gerenciar_pendencias'))



@admin_bp.route('/acompanhamento_diario')
@login_required()
def acompanhamento_diario():
    hoje = date.today()
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # --- Lógica de busca e status (permanece a mesma) ---
    checklist_diario_query = Checklist.query.filter(Checklist.tipo == 'DIÁRIO', Checklist.ativo == True)
    if user_role != 'admin':
        checklist_diario_query = checklist_diario_query.filter(or_(Checklist.unidade == user_unidade, Checklist.unidade == None))
    checklist_diario = checklist_diario_query.order_by(Checklist.data.desc()).first()

    veiculos_query = Veiculo.query
    motoristas_query = Motorista.query
    if user_role != 'admin':
        veiculos_query = veiculos_query.filter(Veiculo.unidade == user_unidade)
        motoristas_query = motoristas_query.filter(Motorista.unidade == user_unidade)
    
    veiculos = veiculos_query.order_by(Veiculo.nome_conjunto).all()
    
    veiculos_status = []
    if checklist_diario:
        indisponibilidades_hoje = {ind.veiculo_id: ind.motivo for ind in VeiculoIndisponibilidade.query.filter(VeiculoIndisponibilidade.data_inicio <= hoje, or_(VeiculoIndisponibilidade.data_fim >= hoje, VeiculoIndisponibilidade.data_fim == None)).all()}
        isencoes_hoje = {isen.motorista_id: isen.motivo for isen in MotoristaIsencao.query.filter(MotoristaIsencao.data == hoje, MotoristaIsencao.tipo_checklist == 'DIÁRIO').all()}
        preenchimentos_hoje = {p.veiculo_id: p for p in ChecklistPreenchido.query.filter(ChecklistPreenchido.checklist_id == checklist_diario.id, db.func.date(ChecklistPreenchido.data_preenchimento) == hoje).all()}

        for veiculo in veiculos:
            status_info = {'veiculo': veiculo, 'status': 'Pendente', 'detalhe': '', 'classe_css': 'table-warning'}
            if veiculo.id in indisponibilidades_hoje:
                status_info.update({'status': 'Indisponível', 'detalhe': indisponibilidades_hoje[veiculo.id], 'classe_css': 'table-secondary'})
            elif not veiculo.motorista:
                status_info.update({'status': 'Sem Motorista', 'detalhe': 'Vincule um motorista ao veículo', 'classe_css': 'table-info'})
            elif veiculo.id in preenchimentos_hoje:
                preenchimento = preenchimentos_hoje[veiculo.id]
                status_info.update({'status': 'Preenchido', 'detalhe': f"por {preenchimento.motorista.nome} às {preenchimento.data_preenchimento.strftime('%H:%M')}", 'classe_css': 'table-success'})
            elif veiculo.motorista and veiculo.motorista.id in isencoes_hoje:
                status_info.update({'status': 'Isento', 'detalhe': f"Motorista isento: {isencoes_hoje[veiculo.motorista.id]}", 'classe_css': 'table-light'})
            else:
                status_info.update({'status': 'Pendente', 'detalhe': f"Motorista: {veiculo.motorista.nome}", 'classe_css': 'table-danger'})
            veiculos_status.append(status_info)
    else:
        flash('Nenhum checklist "DIÁRIO" ativo foi configurado para sua unidade.', 'warning')

    # --- NOVA LÓGICA ---
    # Busca veículos e motoristas para popular os formulários dos modais
    veiculos_para_formulario = veiculos_query.order_by(Veiculo.nome_conjunto).all()
    motoristas_para_formulario = motoristas_query.order_by(Motorista.nome).all()

    return render_template(
        'admin_acompanhamento_diario.html',
        veiculos_status=veiculos_status,
        checklist_diario=checklist_diario,
        data_hoje=hoje,
        # NOVAS VARIÁVEIS ENVIADAS AO TEMPLATE:
        veiculos_para_formulario=veiculos_para_formulario,
        motoristas_para_formulario=motoristas_para_formulario
    )


# ROTA PARA REGISTRAR INDISPONIBILIDADE DE VEÍCULO
@admin_bp.route('/indisponibilidade/registrar', methods=['POST'])
@login_required()
def registrar_indisponibilidade():
    user_id = session.get('user_id')
    
    veiculo_id = request.form.get('veiculo_id')
    data_inicio_str = request.form.get('data_inicio')
    data_fim_str = request.form.get('data_fim')
    motivo = request.form.get('motivo')

    if not all([veiculo_id, data_inicio_str, motivo]):
        flash('Veículo, data de início e motivo são obrigatórios.', 'danger')
        return redirect(url_for('admin.acompanhamento_diario'))

    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else None

    if data_fim and data_fim < data_inicio:
        flash('A data final não pode ser anterior à data de início.', 'danger')
        return redirect(url_for('admin.acompanhamento_diario'))

    # Remove qualquer registro conflitante antes de adicionar o novo
    VeiculoIndisponibilidade.query.filter(
        VeiculoIndisponibilidade.veiculo_id == veiculo_id,
        VeiculoIndisponibilidade.data_fim >= data_inicio
    ).delete(synchronize_session=False)

    nova_indisponibilidade = VeiculoIndisponibilidade(
        veiculo_id=veiculo_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
        motivo=motivo,
        usuario_id=user_id
    )
    db.session.add(nova_indisponibilidade)
    db.session.commit()
    
    flash('Indisponibilidade do veículo registrada com sucesso!', 'success')
    return redirect(url_for('admin.acompanhamento_diario'))


# ROTA PARA REGISTRAR ISENÇÃO DE MOTORISTA (COM PERÍODO)
@admin_bp.route('/isencao/registrar', methods=['POST'])
@login_required()
def registrar_isencao_motorista():
    user_id = session.get('user_id')
    
    motorista_id = request.form.get('motorista_id')
    data_inicio_str = request.form.get('data_inicio')
    data_fim_str = request.form.get('data_fim') # Campo novo
    motivo = request.form.get('motivo')

    if not all([motorista_id, data_inicio_str, motivo]):
        flash('Motorista, data de início e motivo são obrigatórios.', 'danger')
        return redirect(url_for('admin.acompanhamento_diario'))

    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    # Se a data fim não for preenchida, usa a data de início
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else data_inicio

    if data_fim < data_inicio:
        flash('A data final não pode ser anterior à data inicial.', 'danger')
        return redirect(url_for('admin.acompanhamento_diario'))
        
    delta = data_fim - data_inicio
    dias_a_isentar = [data_inicio + timedelta(days=i) for i in range(delta.days + 1)]

    adicionadas = 0
    ignoradas = 0
    for dia in dias_a_isentar:
        isencao_existente = MotoristaIsencao.query.filter_by(
            motorista_id=motorista_id,
            data=dia,
            tipo_checklist='DIÁRIO'
        ).first()

        if not isencao_existente:
            nova_isencao = MotoristaIsencao(
                motorista_id=motorista_id,
                data=dia,
                motivo=motivo,
                tipo_checklist='DIÁRIO',
                usuario_id=user_id
            )
            db.session.add(nova_isencao)
            adicionadas += 1
        else:
            ignoradas += 1

    db.session.commit()
    
    if adicionadas > 0:
        flash(f'{adicionadas} dia(s) de isenção registrados com sucesso para o motorista.', 'success')
    if ignoradas > 0:
        flash(f'{ignoradas} dia(s) de isenção já existiam e foram ignorados.', 'info')

    return redirect(url_for('admin.acompanhamento_diario'))




@admin_bp.route('/isencoes/registrar_periodo', methods=['POST'])
@login_required(required_role=["admin", "master"])
def registrar_isencao_periodo():
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    usuario_id = session.get('user_id')

    motorista_id_str = request.form.get('motorista_id')
    data_inicio_str = request.form.get('data_inicio')
    data_fim_str = request.form.get('data_fim')
    tipo_checklist = request.form.get('tipo_checklist')
    motivo = request.form.get('motivo')

    if not all([motorista_id_str, data_inicio_str, data_fim_str, tipo_checklist, motivo]):
        flash('Todos os campos são obrigatórios para registrar uma liberação.', 'danger')
        return redirect(url_for('admin.acompanhamento_diario'))

    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Formato de data inválido.', 'danger')
        return redirect(url_for('admin.acompanhamento_diario'))

    if data_fim < data_inicio:
        flash('A data final não pode ser anterior à data inicial.', 'danger')
        return redirect(url_for('admin.acompanhamento_diario'))

    motoristas_a_isentar = []
    if motorista_id_str == 'todos':
        query = Motorista.query
        if user_role == 'master':
            query = query.filter(Motorista.unidade == user_unidade)
        motoristas_a_isentar = query.all()
    else:
        motorista = Motorista.query.get(motorista_id_str)
        if motorista:
            if user_role == 'master' and motorista.unidade != user_unidade:
                 flash('Você só pode registrar liberações para motoristas da sua unidade.', 'danger')
                 return redirect(url_for('admin.acompanhamento_diario'))
            motoristas_a_isentar.append(motorista)

    if not motoristas_a_isentar:
        flash('Nenhum motorista encontrado para registrar a liberação.', 'warning')
        return redirect(url_for('admin.acompanhamento_diario'))

    adicionadas = 0
    ignoradas = 0
    delta = data_fim - data_inicio
    
    for motorista in motoristas_a_isentar:
        for i in range(delta.days + 1):
            dia = data_inicio + timedelta(days=i)
            
            isencao_existente = MotoristaIsencao.query.filter_by(
                motorista_id=motorista.id,
                data=dia,
                tipo_checklist=tipo_checklist
            ).first()

            if not isencao_existente:
                nova_isencao = MotoristaIsencao(
                    motorista_id=motorista.id,
                    data=dia,
                    motivo=motivo,
                    tipo_checklist=tipo_checklist,
                    usuario_id=usuario_id
                )
                db.session.add(nova_isencao)
                adicionadas += 1
            else:
                ignoradas += 1

    db.session.commit()

    if adicionadas > 0:
        flash(f'{adicionadas} isenção(ões) registrada(s) com sucesso. {ignoradas} já existiam e foram ignoradas.', 'success')
    else:
        flash('Nenhuma nova isenção foi registrada (provavelmente já existiam).', 'info')

    return redirect(url_for('admin.acompanhamento_diario'))


@admin_bp.route('/relatorios_consolidados', methods=['GET', 'POST'])
def relatorios_consolidados():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    veiculos = Veiculo.query.order_by(Veiculo.nome_conjunto).all()
    resultados_agrupados = None

    if request.method == 'POST':
        tipo_checklist = request.form.get('tipo_checklist')
        veiculo_id = request.form.get('veiculo_id')
        data_inicio_str = request.form.get('data_inicio')
        data_fim_str = request.form.get('data_fim')

        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else None
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else None

        query = ChecklistPreenchido.query.join(Checklist).join(Veiculo)

        if tipo_checklist:
            query = query.filter(Checklist.tipo == tipo_checklist)
        
        if veiculo_id and veiculo_id != 'todos':
            query = query.filter(ChecklistPreenchido.veiculo_id == veiculo_id)

        if data_inicio:
            query = query.filter(db.func.date(ChecklistPreenchido.data_preenchimento) >= data_inicio)
        if data_fim:
            query = query.filter(db.func.date(ChecklistPreenchido.data_preenchimento) <= data_fim)

        preenchimentos = query.order_by(Veiculo.nome_conjunto, ChecklistPreenchido.data_preenchimento.desc()).all()

        resultados_agrupados = defaultdict(lambda: defaultdict(list))
        for p in preenchimentos:
            if p.veiculo:
                data = p.data_preenchimento.date()
                resultados_agrupados[p.veiculo.nome_conjunto][data].append(p)
            
    return render_template('admin_relatorios_consolidados.html', 
                           veiculos=veiculos,
                           resultados=resultados_agrupados,
                           filtros=request.form)


@admin_bp.route('/gerar_relatorio_pdf')
def gerar_relatorio_pdf():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    # 1. Captura e processa filtros
    tipo_checklist = request.args.get('tipo_checklist')
    veiculo_id = request.args.get('veiculo_id')
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    query = ChecklistPreenchido.query.join(Checklist).join(Veiculo)

    if data_inicio_str:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        query = query.filter(db.func.date(ChecklistPreenchido.data_preenchimento) >= data_inicio)
    if data_fim_str:
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        query = query.filter(db.func.date(ChecklistPreenchido.data_preenchimento) <= data_fim)
    if tipo_checklist:
        query = query.filter(Checklist.tipo == tipo_checklist)
    
    veiculo_obj = None
    if veiculo_id and veiculo_id != 'todos':
        query = query.filter(ChecklistPreenchido.veiculo_id == veiculo_id)
        veiculo_obj = Veiculo.query.get(veiculo_id)

    preenchimentos = query.order_by(ChecklistPreenchido.data_preenchimento.desc()).all()
    
    # Estrutura de itens do primeiro checklist (base para o layout)
    itens_principais = []
    if preenchimentos:
        checklist_base = Checklist.query.get(preenchimentos[0].checklist_id)
        if checklist_base:
            itens_principais = checklist_base.itens.filter_by(parent_id=None).order_by(ChecklistItem.ordem).all()

    # Inicia a construção do PDF
    titulo = f"Relatório - {veiculo_obj.nome_conjunto if veiculo_obj else 'Geral'}"
    pdf = PDF(title=titulo, orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Agrupa preenchimentos por data
    dados_agrupados = defaultdict(list)
    for p in preenchimentos:
        dados_agrupados[p.data_preenchimento.date()].append(p)

    for data, preenchs in sorted(dados_agrupados.items()):
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f"Data do Checklist: {data.strftime('%d/%m/%Y')}", 0, 1, 'L')

        for p in preenchs:
            pdf.set_font('Arial', 'I', 10)
            pdf.cell(0, 8, f"Preenchido por: {p.motorista.nome} às {p.data_preenchimento.strftime('%H:%M')}", 0, 1, 'L')
            pdf.ln(2) # Pequeno espaço

            item_counter = 1 # Inicia o contador sequencial de itens

            for item_principal in itens_principais:
                # Renderiza o cabeçalho da categoria (Item Principal)
                pdf.set_font('Arial', 'B', 10)
                pdf.set_fill_color(224, 224, 224) # Cinza claro
                pdf.cell(0, 7, item_principal.texto.encode('latin-1', 'replace').decode('latin-1'), 1, 1, 'C', 1)

                # Renderiza o cabeçalho da tabela
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(15, 7, 'Item', 1, 0, 'C', 1)
                pdf.cell(135, 7, 'Descrição', 1, 0, 'C', 1)
                pdf.cell(40, 7, 'Resposta', 1, 1, 'C', 1)

                pdf.set_font('Arial', '', 9)
                if not item_principal.sub_itens:
                    continue # Se não houver sub-itens, apenas o cabeçalho é mostrado

                for sub_item in item_principal.sub_itens:
                    resposta_obj = next((r for r in p.respostas if r.item_id == sub_item.id), None)
                    
                    h = 6 # Altura base da célula
                    x_start = pdf.get_x()
                    y_start = pdf.get_y()

                    # Célula do Item (com contador)
                    pdf.cell(15, h, str(item_counter), 1, 0, 'C')

                    # Célula da Descrição (com multi_cell para quebra de linha)
                    pdf.multi_cell(135, h, sub_item.texto.encode('latin-1', 'replace').decode('latin-1'), 1, 'L')
                    
                    # Armazena a posição Y final após a descrição
                    y_end = pdf.get_y()

                    # Reposiciona para a mesma linha da descrição para desenhar a resposta
                    pdf.set_xy(x_start + 150, y_start)
                    pdf.cell(40, y_end - y_start, resposta_obj.resposta if resposta_obj else '-', 1, 1, 'C')

                    # Se houver observação, renderiza abaixo
                    if resposta_obj and resposta_obj.observacao:
                        pdf.set_font('Arial', 'I', 8)
                        pdf.set_fill_color(245, 245, 245)
                        pdf.multi_cell(0, 5, f"Obs: {resposta_obj.observacao.encode('latin-1', 'replace').decode('latin-1')}", 1, 'L', 1)
                        pdf.set_font('Arial', '', 9)

                    item_counter += 1
            pdf.ln(10) # Espaço entre os preenchimentos de um mesmo dia

    # Gera e retorna o PDF para download
    return Response(bytes(pdf.output(dest='S')),
                    mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment;filename=relatorio_consolidado.pdf'})



@admin_bp.route('/motoristas')
@login_required()
def motoristas():
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    motoristas_query = Motorista.query
    veiculos_query = Veiculo.query

    # Se o usuário não for admin, filtre tudo pela unidade dele
    if user_role != 'admin':
        motoristas_query = motoristas_query.filter(Motorista.unidade == user_unidade)
        veiculos_query = veiculos_query.filter(Veiculo.unidade == user_unidade)

    lista_motoristas = motoristas_query.order_by(Motorista.nome).all()
    
    # Pega os IDs de todos os conjuntos que já estão vinculados a algum motorista
    veiculos_vinculados_ids = {m.veiculo_id for m in Motorista.query.filter(Motorista.veiculo_id.isnot(None)).all()}

    # Busca apenas os veículos (conjuntos) que NÃO estão na lista de vinculados
    veiculos_disponiveis = veiculos_query.filter(Veiculo.id.notin_(veiculos_vinculados_ids)).order_by(Veiculo.nome_conjunto).all()
    
    # Pega a lista de unidades para o formulário (apenas para admin)
    unidades_disponiveis = []
    if user_role == 'admin':
        unidades_db = db.session.query(Usuario.unidade).distinct().all()
        unidades_disponiveis = sorted([u[0] for u in unidades_db if u[0]])

    return render_template('motoristas.html', 
                           motoristas=lista_motoristas, 
                           veiculos_disponiveis=veiculos_disponiveis,
                           unidades_disponiveis=unidades_disponiveis)

@admin_bp.route('/motoristas/add', methods=['POST'])
@login_required()
def add_motorista():
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    nome = request.form.get('nome')
    cpf = request.form.get('cpf')
    rg = request.form.get('rg')
    cnh = request.form.get('cnh')
    frota = request.form.get('frota')
    veiculo_id = request.form.get('veiculo_id')
    unidade = request.form.get('unidade')
    operacao = request.form.get('operacao')

    if not nome or not cpf:
        flash('Nome e CPF são obrigatórios.', 'danger')
        return redirect(url_for('admin.motoristas'))

    if user_role != 'admin':
        unidade = user_unidade
    
    if not unidade:
        flash('A unidade é obrigatória.', 'danger')
        return redirect(url_for('admin.motoristas'))

    if Motorista.query.filter_by(cpf=cpf).first():
        flash('Já existe um motorista com este CPF.', 'danger')
        return redirect(url_for('admin.motoristas'))

    novo_motorista = Motorista(
        nome=nome, 
        cpf=cpf, 
        rg=rg, 
        cnh=cnh, 
        frota=frota, 
        unidade=unidade,
        operacao=operacao,
        veiculo_id=int(veiculo_id) if veiculo_id else None
    )
    
    # LINHA ADICIONADA: Define a senha padrão (6 primeiros dígitos do CPF)
    novo_motorista.set_password(None)
    
    db.session.add(novo_motorista)
    db.session.commit()
    flash(f'Motorista {nome} adicionado com sucesso!', 'success')
    return redirect(url_for('admin.motoristas'))



@admin_bp.route('/motoristas/edit/<int:motorista_id>', methods=['POST'])
@login_required()
def edit_motorista(motorista_id):
    motorista = Motorista.query.get_or_404(motorista_id)
    
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    if user_role != 'admin' and motorista.unidade != user_unidade:
        flash('Você não tem permissão para editar este motorista.', 'danger')
        return redirect(url_for('admin.motoristas'))

    motorista.nome = request.form.get('nome')
    motorista.cpf = request.form.get('cpf')
    motorista.rg = request.form.get('rg')
    motorista.cnh = request.form.get('cnh')
    motorista.frota = request.form.get('frota')
    motorista.veiculo_id = int(request.form.get('veiculo_id')) if request.form.get('veiculo_id') else None
    motorista.operacao = request.form.get('operacao') # LINHA ADICIONADA
    
    if user_role == 'admin':
        motorista.unidade = request.form.get('unidade')

    db.session.commit()
    flash(f'Dados do motorista {motorista.nome} atualizados com sucesso!', 'success')
    return redirect(url_for('admin.motoristas'))



@admin_bp.route('/motoristas/delete/<int:motorista_id>', methods=['POST'])
@login_required()
def delete_motorista(motorista_id):
    motorista = Motorista.query.get_or_404(motorista_id)

    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # Se não for admin, verifica se o motorista pertence à sua unidade
    if user_role != 'admin' and motorista.unidade != user_unidade:
        flash('Você não tem permissão para excluir este motorista.', 'danger')
        return redirect(url_for('admin.motoristas'))

    # (Lógica futura opcional: verificar se o motorista tem assinaturas antes de excluir)
    
    db.session.delete(motorista)
    db.session.commit()
    flash(f'Motorista {motorista.nome} excluído com sucesso.', 'info')
    return redirect(url_for('admin.motoristas'))

# Em app/routes.py, ADICIONE esta nova função:

@admin_bp.route('/motoristas/desvincular/<int:motorista_id>', methods=['POST'])
@login_required()
def desvincular_conjunto(motorista_id):
    motorista = Motorista.query.get_or_404(motorista_id)

    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # Verificação de segurança: Apenas admin ou master da mesma unidade podem desvincular
    if user_role != 'admin' and motorista.unidade != user_unidade:
        flash('Você não tem permissão para modificar este motorista.', 'danger')
        return redirect(url_for('admin.motoristas'))

    if motorista.veiculo:
        veiculo_nome = motorista.veiculo.nome_conjunto
        motorista.veiculo_id = None
        db.session.commit()
        flash(f'O conjunto "{veiculo_nome}" foi desvinculado do motorista {motorista.nome}.', 'success')
    else:
        flash(f'O motorista {motorista.nome} já não possui um conjunto vinculado.', 'info')

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

    tipo_recurso = request.form.get('tipo_recurso')
    recurso_link = None

    if tipo_recurso == 'link':
        recurso_link = request.form.get('link')
    elif tipo_recurso == 'arquivo':
        # Verifica se a parte do arquivo está na requisição
        if 'arquivo' not in request.files:
            flash('Nenhum campo de arquivo encontrado no formulário.', 'error')
            return redirect(url_for('admin.conteudo')) # CORRIGIDO

        file = request.files['arquivo']
        
        # Verifica se um arquivo foi realmente selecionado
        if file.filename == '':
            flash('Nenhum arquivo selecionado. Por favor, escolha um arquivo para enviar.', 'error')
            return redirect(url_for('admin.conteudo')) # CORRIGIDO

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            # Armazena o caminho relativo para ser usado no template
            recurso_link = os.path.join('uploads', filename).replace('\\', '/')
        else:
            flash('Tipo de arquivo não permitido.', 'danger')
            return redirect(url_for('admin.conteudo')) # CORRIGIDO

    # Cria o novo conteúdo se tudo estiver OK
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


@admin_bp.route('/checklists')
@login_required()
def checklists():
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    query = Checklist.query

    # Admin não tem filtro de unidade. Master/outros veem sua unidade ou globais.
    if user_role != 'admin':
        query = query.filter(or_(
            Checklist.unidade == user_unidade,
            Checklist.unidade == None  # Permite ver checklists globais
        ))
    
    # A lista é ordenada para mostrar os ativos primeiro. 
    # O template decide como exibir (ex: checklists inativos com cor diferente).
    lista_checklists = query.order_by(Checklist.ativo.desc(), Checklist.codigo).all()

    unidades_disponiveis = []
    if user_role == 'admin':
        unidades_disponiveis = db.session.query(Motorista.unidade).distinct().all()
        unidades_disponiveis = sorted([u[0] for u in unidades_disponiveis if u[0]])

    return render_template(
        'checklists.html', 
        checklists=lista_checklists, 
        unidades_disponiveis=unidades_disponiveis
    )


# 1. FUNÇÃO CORRIGIDA PARA ADICIONAR CHECKLISTS (ADMIN)
@admin_bp.route('/checklists/add', methods=['POST'])
@login_required()
def add_checklist():
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    
    # Coleta todos os dados do formulário
    titulo = request.form.get('titulo')
    codigo = request.form.get('codigo')
    revisao = request.form.get('revisao')
    data_str = request.form.get('data')
    tipo = request.form.get('tipo')
    unidade = request.form.get('unidade') # Pode vir vazio para o admin

    # Validação dos campos obrigatórios que sempre devem existir
    if not all([titulo, codigo, revisao, data_str, tipo]):
        flash('Os campos Título, Código, Revisão, Data e Tipo são obrigatórios.', 'danger')
        return redirect(url_for('admin.checklists'))

    # Regra para não-admins: a unidade é obrigatória e travada
    if user_role != 'admin':
        unidade = user_unidade
        if not unidade:
            flash('Sua conta de usuário não está vinculada a uma unidade. Contate o administrador.', 'danger')
            return redirect(url_for('admin.checklists'))

    # Converte a data e define a unidade como Nula se o admin a deixou em branco
    data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
    unidade_para_salvar = unidade if unidade else None

    novo_checklist = Checklist(
        titulo=titulo,
        codigo=codigo,
        revisao=revisao,
        data=data_obj,
        tipo=tipo,
        unidade=unidade_para_salvar # Salva None se for global
    )
    db.session.add(novo_checklist)
    db.session.commit()
    
    if unidade_para_salvar:
        flash(f'Checklist "{titulo}" criado para a unidade {unidade_para_salvar}.', 'success')
    else:
        flash(f'Checklist Global "{titulo}" criado com sucesso para todas as unidades.', 'success')
        
    return redirect(url_for('admin.checklists'))


@main_bp.route('/checklists_motorista')
def lista_checklists_motorista():
    if 'motorista_id' not in session:
        return redirect(url_for('main.motorista_login'))
    
    motorista_id = session['motorista_id']
    motorista = Motorista.query.get(motorista_id)

    if not motorista:
        flash('Seus dados de motorista não foram encontrados.', 'danger')
        return redirect(url_for('main.motorista_login'))
        
    motorista_unidade = motorista.unidade
    
    # FILTRO ATUALIZADO: Adiciona a condição 'Checklist.ativo == True'.
    checklists = Checklist.query.filter(
        Checklist.ativo == True,  # <-- Garante que apenas checklists ativos apareçam.
        Checklist.itens.any(),
        or_(
            Checklist.unidade == motorista_unidade,
            Checklist.unidade == None
        )
    ).order_by(Checklist.tipo, Checklist.codigo).all()
    
    checklists_com_status = []
    hoje = date.today()

    for checklist in checklists:
        preenchido_no_periodo = False
        status_texto = "Pendente"

        # Lógica para verificar o status (Diário)
        if checklist.tipo == 'DIÁRIO':
            preenchimento = ChecklistPreenchido.query.filter(
                and_(
                    ChecklistPreenchido.motorista_id == motorista_id,
                    ChecklistPreenchido.checklist_id == checklist.id,
                    db.func.date(ChecklistPreenchido.data_preenchimento) == hoje
                )
            ).first()
            if preenchimento:
                preenchido_no_periodo = True
                status_texto = "Preenchido Hoje"

        # Lógica para verificar o status (Mensal)
        elif checklist.tipo == 'MENSAL':
            preenchimento = ChecklistPreenchido.query.filter(
                and_(
                    ChecklistPreenchido.motorista_id == motorista_id,
                    ChecklistPreenchido.checklist_id == checklist.id,
                    db.func.extract('year', ChecklistPreenchido.data_preenchimento) == hoje.year,
                    db.func.extract('month', ChecklistPreenchido.data_preenchimento) == hoje.month
                )
            ).first()
            if preenchimento:
                preenchido_no_periodo = True
                status_texto = "Preenchido este Mês"
        
        checklists_com_status.append({
            'checklist': checklist, 
            'preenchido': preenchido_no_periodo,
            'status': status_texto
        })

    return render_template('motorista_lista_checklists.html', checklists_info=checklists_com_status)



@admin_bp.route('/checklists/<int:checklist_id>', methods=['GET'])
@login_required()
def view_checklist(checklist_id):
    """
    Exibe e gerencia os itens de um checklist, unificando as lógicas anteriores.
    """
    checklist = Checklist.query.get_or_404(checklist_id)
    
    # Validação de segurança
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    if user_role != 'admin' and checklist.unidade != user_unidade and checklist.unidade is not None:
        flash('Você não tem permissão para ver este checklist.', 'danger')
        return redirect(url_for('admin.checklists'))

    # --- LÓGICA DE ORDENAÇÃO "NATURAL" ---
    def natural_sort_key(s):
        s_str = str(s or '0')
        try:
            return [int(c) for c in s_str.split('.')]
        except ValueError:
            return [s_str]

    itens_principais_unsorted = checklist.itens.filter_by(parent_id=None).all()
    itens_principais_sorted = sorted(itens_principais_unsorted, key=lambda item: natural_sort_key(item.ordem))
    
    # Prepara a lista final com sub-itens também ordenados
    itens_com_subitens = []
    for item in itens_principais_sorted:
        sub_itens_unsorted = item.sub_itens.all()
        sub_itens_sorted = sorted(sub_itens_unsorted, key=lambda sub: natural_sort_key(sub.ordem))
        itens_com_subitens.append((item, sub_itens_sorted))

    # --- LÓGICA PARA BUSCAR SETORES ---
    setores_query = db.session.query(Usuario.setor).distinct().filter(Usuario.setor.isnot(None))
    setores_disponiveis = sorted([s[0] for s in setores_query.all()])

    return render_template(
        'checklist_detalhe.html', # Renderiza o template correto
        checklist=checklist, 
        itens_com_subitens=itens_com_subitens,
        setores_disponiveis=setores_disponiveis
    )


@admin_bp.route('/checklists/add_item/<int:checklist_id>', methods=['POST'])
@login_required()
def add_checklist_item(checklist_id):
    """
    Adiciona um novo item ou sub-item a um checklist.
    CORRIGIDO: Salva a ordem como texto para permitir "1.1", "1.2", etc.
    """
    checklist = Checklist.query.get_or_404(checklist_id)
    
    # Validação de segurança
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    if user_role != 'admin' and checklist.unidade != user_unidade and checklist.unidade is not None:
        flash('Você não tem permissão para modificar este checklist.', 'danger')
        return redirect(url_for('admin.checklists'))

    # Captura os dados do formulário
    texto = request.form.get('texto')
    parent_id = request.form.get('parent_id')
    # CORREÇÃO: Captura a ordem como string e substitui vírgula por ponto
    ordem_str = request.form.get('ordem', '').replace(',', '.')
    setor_responsavel = request.form.get('setor_responsavel')

    if not texto:
        flash('O texto do item não pode ser vazio.', 'warning')
        return redirect(url_for('admin.view_checklist', checklist_id=checklist_id))

    # Lógica para evitar duplicar o bloco de extintores (inalterada)
    if texto == '__BLOCO_EXTINTORES__':
        item_existente = ChecklistItem.query.filter_by(checklist_id=checklist.id, texto='__BLOCO_EXTINTORES__').first()
        if item_existente:
            flash('O bloco de extintores já foi adicionado a este checklist.', 'warning')
            return redirect(url_for('admin.view_checklist', checklist_id=checklist_id))

    novo_item = ChecklistItem(
        texto=texto, 
        checklist_id=checklist.id,
        ordem=ordem_str,  # CORREÇÃO: Salva a string diretamente
        parent_id=int(parent_id) if parent_id else None,
        setor_responsavel=setor_responsavel if setor_responsavel else None
    )
    db.session.add(novo_item)
    db.session.commit()
    
    flash('Item adicionado com sucesso!', 'success')
    return redirect(url_for('admin.view_checklist', checklist_id=checklist_id))



@admin_bp.route('/checklists/edit_item/<int:item_id>', methods=['POST'])
@login_required()
def edit_checklist_item(item_id):
    """
    Edita o texto ou a ordem de um item de checklist.
    """
    item = ChecklistItem.query.get_or_404(item_id)
    
    # Validação de segurança
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    if user_role != 'admin' and item.checklist.unidade != user_unidade:
        flash('Você não tem permissão para modificar este item.', 'danger')
        return redirect(url_for('admin.checklists'))
    
    novo_texto = request.form.get('texto')
    nova_ordem = request.form.get('ordem', type=int)

    if not novo_texto:
        flash('O texto do item não pode ser vazio.', 'warning')
    else:
        item.texto = novo_texto
        if nova_ordem is not None and not item.parent_id:
            item.ordem = nova_ordem
        db.session.commit()
        flash('Item atualizado com sucesso.', 'success')

    return redirect(url_for('admin.view_checklist', checklist_id=item.checklist_id))

@admin_bp.route('/checklists/delete_item/<int:item_id>', methods=['POST'])
@login_required()
def delete_checklist_item(item_id):
    """
    Exclui um item ou sub-item de um checklist.
    """
    item = ChecklistItem.query.get_or_404(item_id)
    checklist_id = item.checklist_id # Salva o ID antes de deletar
    
    # Validação de segurança
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    if user_role != 'admin' and item.checklist.unidade != user_unidade:
        flash('Você não tem permissão para excluir este item.', 'danger')
        return redirect(url_for('admin.checklists'))
    
    db.session.delete(item)
    db.session.commit()
    
    flash('Item removido com sucesso.', 'info')
    return redirect(url_for('admin.view_checklist', checklist_id=checklist_id))



@admin_bp.route('/checklists/toggle_status/<int:checklist_id>', methods=['POST'])
@login_required(required_role=["admin", "master"])
def toggle_checklist_status(checklist_id):
    """
    Desativa/Reativa um checklist se ele tiver histórico, ou o exclui se nunca foi usado.
    """
    checklist = Checklist.query.get_or_404(checklist_id)
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # Validação de permissão
    if user_role != 'admin' and checklist.unidade is not None and checklist.unidade != user_unidade:
        flash('Você não tem permissão para alterar este checklist.', 'danger')
        return redirect(url_for('admin.checklists'))

    has_preenchimentos = ChecklistPreenchido.query.filter_by(checklist_id=checklist.id).first()

    # Se NUNCA foi preenchido, a ação é de exclusão permanente.
    if not has_preenchimentos:
        db.session.delete(checklist)
        db.session.commit()
        flash(f'Checklist "{checklist.titulo}" foi excluído permanentemente, pois não possuía histórico.', 'info')
    else:
        # Se JÁ FOI preenchido, apenas inativa ou reativa
        checklist.ativo = not checklist.ativo
        db.session.commit()
        if checklist.ativo:
            flash(f'Checklist "{checklist.titulo}" foi reativado com sucesso.', 'success')
        else:
            flash(f'Checklist "{checklist.titulo}" foi desativado. Ele não aparecerá para os motoristas, mas seu histórico foi mantido.', 'info')

    return redirect(url_for('admin.checklists'))



@admin_bp.route('/conteudo/<int:conteudo_id>')
def conteudo_detalhe(conteudo_id):
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))
    conteudo = Conteudo.query.get_or_404(conteudo_id)
    relatorio = conteudo.assinaturas
    return render_template('conteudo_detalhe.html', conteudo=conteudo, relatorio=relatorio)



@admin_bp.route('/checklist/edit/<int:checklist_id>', methods=['POST'])
def edit_checklist(checklist_id):
    """
    Rota para editar os dados de um checklist mestre.
    """
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    checklist = Checklist.query.get_or_404(checklist_id)

    # Coleta os dados do formulário de edição
    codigo = request.form.get('codigo')
    revisao = request.form.get('revisao')
    data_str = request.form.get('data')
    tipo = request.form.get('tipo')

    # Validação dos dados recebidos
    if not all([codigo, revisao, data_str, tipo]):
        flash('Todos os campos são obrigatórios para editar o checklist.', 'danger')
        return redirect(url_for('admin.gerenciar_checklists'))

    # Atualiza o objeto checklist com os novos dados
    checklist.codigo = codigo
    checklist.revisao = revisao
    checklist.data = datetime.strptime(data_str, '%Y-%m-%d').date()
    checklist.tipo = tipo

    # Salva as alterações no banco de dados
    db.session.commit()
    flash(f'Checklist "{checklist.codigo}" atualizado com sucesso!', 'success')
    return redirect(url_for('admin.gerenciar_checklists'))









@admin_bp.route('/checklists/preenchidos')
@login_required()
def checklists_preenchidos():
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    query = ChecklistPreenchido.query
    if user_role != 'admin':
        # Junta com a tabela Motorista para filtrar pela unidade do motorista
        query = query.join(Motorista, ChecklistPreenchido.motorista_id == Motorista.id)\
                     .filter(Motorista.unidade == user_unidade)
    
    # Ordena os checklists do mais recente para o mais antigo
    preenchidos = query.order_by(ChecklistPreenchido.data_preenchimento.desc()).all()
    
    return render_template('checklists_preenchidos.html', preenchidos=preenchidos)
@admin_bp.route('/checklist/preenchido/<int:preenchido_id>')
@login_required()
def view_checklist_preenchido(preenchido_id):
    preenchido = ChecklistPreenchido.query.get_or_404(preenchido_id)
    
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # Verifica se a unidade do motorista do checklist é a mesma do usuário logado
    if user_role != 'admin' and preenchido.motorista.unidade != user_unidade:
        flash('Você não tem permissão para visualizar este registro.', 'danger')
        return redirect(url_for('admin.checklists_preenchidos'))

    return render_template('checklist_preenchido_detail.html', preenchido=preenchido)


@admin_bp.route('/pendencias')
@login_required()
def pendencias():
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    query = Pendencia.query.filter_by(resolvida=False)
    if user_role != 'admin':
        # Junta as tabelas para chegar na unidade do motorista
        query = query.join(ChecklistResposta, Pendencia.resposta_id == ChecklistResposta.id)\
                     .join(ChecklistPreenchido, ChecklistResposta.checklist_preenchido_id == ChecklistPreenchido.id)\
                     .join(Motorista, ChecklistPreenchido.motorista_id == Motorista.id)\
                     .filter(Motorista.unidade == user_unidade)

    lista_pendencias = query.order_by(Pendencia.data_criacao.desc()).all()
    
    return render_template('pendencias.html', pendencias=lista_pendencias)


@admin_bp.route('/checklist/item/<int:item_id>/editar', methods=['POST'])
@login_required()
def editar_item(item_id):
    """
    Atualiza um item existente, salvando a ordem como texto.
    """
    item = ChecklistItem.query.get_or_404(item_id)
    texto = request.form.get('texto')
    ordem_str = request.form.get('ordem', '0').replace(',', '.')

    if not texto:
        flash('O texto do item não pode ser vazio.', 'danger')
        return redirect(url_for('admin.checklist_detalhe', checklist_id=item.checklist_id))

    item.texto = texto
    item.ordem = ordem_str
    db.session.commit()
    
    flash(f'Item "{item.texto}" foi atualizado com sucesso!', 'success')
    return redirect(url_for('admin.checklist_detalhe', checklist_id=item.checklist_id))


@admin_bp.route('/checklist/item/<int:item_id>/excluir', methods=['POST'])
@login_required()
def excluir_item(item_id):
    """
    CORRIGIDO: Exclui um item ou sub-item e redireciona de volta para a
    página de detalhes do checklist.
    """
    item = ChecklistItem.query.get_or_404(item_id)
    checklist_id = item.checklist_id # Guarda o ID para o redirect

    # A relação cascade no modelo deve cuidar da exclusão dos sub-itens
    db.session.delete(item)
    db.session.commit()
    
    flash(f'O item "{item.texto}" foi excluído.', 'info')
    # Redireciona de volta para a página de gerenciamento de itens
    return redirect(url_for('admin.checklist_detalhe', checklist_id=checklist_id))



@admin_bp.route('/veiculos/adicionar_placa', methods=['POST'])
def adicionar_placa():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    numero = request.form.get('numero_placa').upper()
    tipo = request.form.get('tipo_placa')

    if not numero:
        flash('O número da placa é obrigatório.', 'danger')
        return redirect(url_for('admin.gerenciar_veiculos'))

    if Placa.query.filter_by(numero=numero).first():
        flash(f'A placa {numero} já está cadastrada.', 'warning')
    else:
        nova_placa = Placa(numero=numero, tipo=tipo)
        db.session.add(nova_placa)
        db.session.commit()
        flash(f'Placa {numero} adicionada com sucesso.', 'success')

    return redirect(url_for('admin.gerenciar_veiculos'))

@admin_bp.route('/veiculos/montar_conjunto', methods=['POST'])
def montar_conjunto():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    nome_conjunto = request.form.get('nome_conjunto')
    placa_cavalo_id = request.form.get('placa_cavalo_id')
    placa_carreta1_id = request.form.get('placa_carreta1_id')
    placa_carreta2_id = request.form.get('placa_carreta2_id')
    obs = request.form.get('obs')

    if not nome_conjunto or not placa_cavalo_id:
        flash('Nome do conjunto e placa do cavalo são obrigatórios.', 'danger')
        return redirect(url_for('admin.gerenciar_veiculos'))

    placa_carreta1_id = int(placa_carreta1_id) if placa_carreta1_id else None
    placa_carreta2_id = int(placa_carreta2_id) if placa_carreta2_id else None

    novo_veiculo = Veiculo(nome_conjunto=nome_conjunto, placa_cavalo_id=int(placa_cavalo_id), placa_carreta1_id=placa_carreta1_id, placa_carreta2_id=placa_carreta2_id, obs=obs)
    db.session.add(novo_veiculo)
    db.session.commit()
    flash(f"Conjunto \\'{nome_conjunto}\\' montado com sucesso.', 'success")
    
    return redirect(url_for('admin.gerenciar_veiculos'))


# --- ROTAS PARA IMPORTAÇÃO EM MASSA ---

@admin_bp.route('/importacao')
@login_required(required_role=["admin"])
def importacao_pagina():
    """Exibe a página de importação de dados em massa."""
    return render_template('admin_importacao.html')


# Substitua a sua função 'importar_dados' por esta versão corrigida

# Substitua a sua função 'importar_dados' por esta versão melhorada

# Substitua a sua função 'importar_dados' por esta versão COMPLETA e CORRIGIDA

@admin_bp.route('/importacao/<string:tipo>', methods=['POST'])
@login_required(required_role=["admin"])
def importar_dados(tipo):
    """
    Processa o upload de arquivos para importação em massa com lógica de "upsert".
    - Se um registro não existe, ele é criado.
    - Se um registro já existe, ele é atualizado caso os dados do arquivo sejam diferentes.
    - CORRIGIDO: Mapeia a coluna 'frota' da planilha para o campo 'operacao' do banco de dados.
    """
    if 'arquivo' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('admin.importacao_pagina'))

    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('admin.importacao_pagina'))

    if not (arquivo.filename.endswith('.csv') or arquivo.filename.endswith('.xlsx')):
        flash('Formato de arquivo inválido. Use .csv ou .xlsx.', 'danger')
        return redirect(url_for('admin.importacao_pagina'))

    try:
        in_memory_file = io.BytesIO(arquivo.read())
        
        if arquivo.filename.endswith('.csv'):
            df = pd.read_csv(in_memory_file, sep=';', dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(in_memory_file, dtype=str, keep_default_na=False)
        
        df.columns = df.columns.str.strip().str.lower()
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        adicionados = 0
        atualizados = 0
        ignorados = 0
        erros = []

        if tipo == 'motoristas':
            required_cols = ['nome', 'cpf', 'unidade']
            if not all(col in df.columns for col in required_cols):
                flash(f'Arquivo de motoristas deve conter as colunas: {", ".join(required_cols)}.', 'danger')
                return redirect(url_for('admin.importacao_pagina'))

            for index, row in df.iterrows():
                if not row.get('cpf') or not row.get('nome') or not row.get('unidade'):
                    erros.append(f'Linha {index + 2}: Faltando dados obrigatórios (nome, cpf, unidade).')
                    ignorados += 1
                    continue
                
                motorista = Motorista.query.filter_by(cpf=row['cpf']).first()
                
                # Pega o valor da coluna 'frota' para usar nos campos 'operacao' e 'frota' do banco
                valor_operacao_frota = row.get('frota', '')

                if motorista:
                    # UPDATE: Motorista existe, verifica por mudanças
                    changes = []
                    if motorista.nome != row.get('nome'): motorista.nome = row.get('nome'); changes.append('nome')
                    if motorista.unidade != row.get('unidade'): motorista.unidade = row.get('unidade'); changes.append('unidade')
                    if motorista.rg != row.get('rg', ''): motorista.rg = row.get('rg', ''); changes.append('rg')
                    if motorista.cnh != row.get('cnh', ''): motorista.cnh = row.get('cnh', ''); changes.append('cnh')
                    
                    if (motorista.operacao or '') != valor_operacao_frota: motorista.operacao = valor_operacao_frota; changes.append('operacao')
                    if (motorista.frota or '') != valor_operacao_frota: motorista.frota = valor_operacao_frota; changes.append('frota')
                    
                    if changes:
                        atualizados += 1
                    else:
                        ignorados += 1
                else:
                    # INSERT: Motorista não existe, cria um novo
                    novo_motorista = Motorista(
                        nome=row['nome'],
                        cpf=row['cpf'],
                        unidade=row['unidade'],
                        operacao=valor_operacao_frota,
                        frota=valor_operacao_frota,
                        rg=row.get('rg', ''),
                        cnh=row.get('cnh', '')
                    )
                    novo_motorista.set_password(None)
                    db.session.add(novo_motorista)
                    adicionados += 1

        elif tipo == 'placas':
            required_cols = ['numero', 'tipo', 'unidade']
            if not all(col in df.columns for col in required_cols):
                flash(f'Arquivo de placas deve conter as colunas: {", ".join(required_cols)}.', 'danger')
                return redirect(url_for('admin.importacao_pagina'))

            for index, row in df.iterrows():
                numero_placa = row.get('numero', '').upper()
                tipo_placa = row.get('tipo', '').upper()

                if not numero_placa or not tipo_placa or not row.get('unidade'):
                    erros.append(f'Linha {index + 2}: Faltando dados obrigatórios (numero, tipo, unidade).')
                    ignorados += 1
                    continue

                if tipo_placa not in ['CAVALO', 'CARRETA']:
                    erros.append(f"Linha {index + 2}: Tipo de placa '{row.get('tipo')}' inválido. Use 'CAVALO' ou 'CARRETA'.")
                    ignorados += 1
                    continue
                
                placa = Placa.query.filter_by(numero=numero_placa).first()

                if placa:
                    changes = []
                    if (placa.tipo or '') != tipo_placa: placa.tipo = tipo_placa; changes.append('tipo')
                    if (placa.unidade or '') != row.get('unidade'): placa.unidade = row.get('unidade'); changes.append('unidade')
                    if (placa.operacao or '') != row.get('operacao', ''): placa.operacao = row.get('operacao', ''); changes.append('operacao')
                    if changes: atualizados += 1
                    else: ignorados += 1
                else:
                    nova_placa = Placa(numero=numero_placa, tipo=tipo_placa, unidade=row['unidade'], operacao=row.get('operacao', ''))
                    db.session.add(nova_placa)
                    adicionados += 1
        
        elif tipo == 'conjuntos':
            required_cols = ['nome_conjunto', 'unidade', 'placa_cavalo']
            if not all(col in df.columns for col in required_cols):
                flash(f'Arquivo de conjuntos deve conter as colunas: {", ".join(required_cols)}.', 'danger')
                return redirect(url_for('admin.importacao_pagina'))

            for index, row in df.iterrows():
                nome_conjunto = row.get('nome_conjunto')
                if not nome_conjunto or not row.get('unidade') or not row.get('placa_cavalo'):
                    erros.append(f'Linha {index + 2}: Faltando dados obrigatórios (nome_conjunto, unidade, placa_cavalo).')
                    ignorados += 1
                    continue
                
                placa_cavalo_num = row.get('placa_cavalo').upper()
                cavalo = Placa.query.filter_by(numero=placa_cavalo_num).first()
                if not cavalo:
                    erros.append(f"Linha {index + 2}: Placa cavalo '{placa_cavalo_num}' não encontrada no banco.")
                    ignorados += 1
                    continue
                
                carreta1_id = None
                placa_carreta1_num = row.get('placa_carreta1', '').upper()
                if placa_carreta1_num:
                    carreta1 = Placa.query.filter_by(numero=placa_carreta1_num).first()
                    if carreta1: carreta1_id = carreta1.id
                    else: erros.append(f"Linha {index + 2}: Placa carreta 1 '{placa_carreta1_num}' não encontrada.")
                
                carreta2_id = None
                placa_carreta2_num = row.get('placa_carreta2', '').upper()
                if placa_carreta2_num:
                    carreta2 = Placa.query.filter_by(numero=placa_carreta2_num).first()
                    if carreta2: carreta2_id = carreta2.id
                    else: erros.append(f"Linha {index + 2}: Placa carreta 2 '{placa_carreta2_num}' não encontrada.")

                veiculo = Veiculo.query.filter_by(nome_conjunto=nome_conjunto).first()

                if veiculo:
                    changes = []
                    if veiculo.unidade != row.get('unidade'): veiculo.unidade = row.get('unidade'); changes.append('unidade')
                    if veiculo.operacao != row.get('operacao', ''): veiculo.operacao = row.get('operacao', ''); changes.append('operacao')
                    if veiculo.obs != row.get('obs', ''): veiculo.obs = row.get('obs', ''); changes.append('obs')
                    if veiculo.placa_cavalo_id != cavalo.id: veiculo.placa_cavalo_id = cavalo.id; changes.append('placa_cavalo')
                    if veiculo.placa_carreta1_id != carreta1_id: veiculo.placa_carreta1_id = carreta1_id; changes.append('placa_carreta1')
                    if veiculo.placa_carreta2_id != carreta2_id: veiculo.placa_carreta2_id = carreta2_id; changes.append('placa_carreta2')
                    if changes: atualizados += 1
                    else: ignorados += 1
                else:
                    novo_veiculo = Veiculo(
                        nome_conjunto=nome_conjunto, unidade=row.get('unidade'), operacao=row.get('operacao', ''),
                        obs=row.get('obs', ''), placa_cavalo_id=cavalo.id, placa_carreta1_id=carreta1_id,
                        placa_carreta2_id=carreta2_id)
                    db.session.add(novo_veiculo)
                    adicionados += 1

        db.session.commit()

        flash(f'Importação de {tipo} concluída! Adicionados: {adicionados}, Atualizados: {atualizados}, Ignorados (sem alterações): {ignorados}.', 'success')
        if erros:
            for erro in erros[:5]:
                flash(erro, 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro inesperado ao processar o arquivo: {e}', 'danger')

    return redirect(url_for('admin.importacao_pagina'))


# --- ROTAS DE DOCUMENTOS PARA MOTORISTA ---

@main_bp.route('/documentos')
def lista_documentos_motorista():
    """Exibe a lista de documentos fixos para o motorista logado."""
    if 'motorista_id' not in session:
        flash('Por favor, faça login para acessar os documentos.', 'warning')
        return redirect(url_for('main.motorista_login'))
    
    documentos = DocumentoFixo.query.order_by(DocumentoFixo.data_upload.desc()).all()
    
    return render_template('motorista_documentos.html', documentos=documentos)

@main_bp.route('/documentos/acessar/<int:documento_id>')
def acessar_documento(documento_id):
    if 'motorista_id' not in session and 'user_id' not in session:
        flash('Acesso negado. Por favor, faça login.', 'danger')
        return redirect(url_for('main.index'))
        
    documento = DocumentoFixo.query.get_or_404(documento_id)
    directory = os.path.abspath(DOCUMENTOS_UPLOAD_FOLDER)
    
    action = request.args.get('action', 'view') 
    as_attachment = (action == 'download')

    return send_from_directory(
        directory=directory, 
        path=documento.nome_arquivo, 
        as_attachment=as_attachment
    )