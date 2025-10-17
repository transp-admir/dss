# --- IMPORTAÇÕES DO FLASK PARA CRIAÇÃO DE ROTAS, RENDERIZAÇÃO DE TEMPLATES E MANIPULAÇÃO DE REQUISIÇÕES ---
from flask import (
    Blueprint, render_template, request, 
    redirect, url_for, session, flash, jsonify, Response
)

# --- IMPORTAÇÃO DE FUNÇÃO PARA CRIAÇÃO DE DECORADORES PERSONALIZADOS ---
from functools import wraps

# --- IMPORTAÇÃO DOS MODELS DEFINIDOS NA APLICAÇÃO (BANCO DE DADOS ORM) ---
from .models import (
    clean_cpf,Usuario, Motorista, Conteudo, Assinatura, Checklist, 
    ChecklistItem, Placa, Veiculo, ChecklistPreenchido, 
    ChecklistResposta, Pendencia, DocumentoFixo, ExtintorCheck,
    VeiculoIndisponibilidade, MotoristaIsencao, UnidadeConfig
)

# --- IMPORTAÇÃO DE FUNÇÕES DE DATA E HORA ---
from datetime import datetime, date, timedelta

# --- DEFINIÇÃO DO BLUEPRINT DA ÁREA ADMINISTRATIVA ---
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- IMPORTAÇÃO DE TIPOS NUMÉRICOS PARA TRATAMENTO DE VALORES DECIMAIS ---
from decimal import Decimal, InvalidOperation

# --- IMPORTAÇÃO DE BIBLIOTECA PARA MANIPULAÇÃO DE DADOS EM TABELAS ---
import pandas as pd

# --- IMPORTAÇÃO DE BIBLIOTECA PARA TRABALHO COM FLUXO DE DADOS EM MEMÓRIA ---
import io

# --- IMPORTAÇÃO DE FUNÇÃO PARA SERVIR ARQUIVOS ESTÁTICOS ---
from flask import send_from_directory

# --- IMPORTAÇÃO DA EXTENSÃO DO BANCO DE DADOS SQLALCHEMY ---
from .extensions import db

# --- IMPORTAÇÃO DE EXPRESSÕES REGULARES PARA VALIDAÇÃO DE DADOS ---
import re

# --- IMPORTAÇÃO DE FUNÇÕES DO SISTEMA OPERACIONAL PARA MANIPULAÇÃO DE ARQUIVOS ---
import os

# --- IMPORTAÇÃO DE FUNÇÃO PARA SEGURANÇA DE NOMES DE ARQUIVOS UPLOAD ---
from werkzeug.utils import secure_filename

# --- IMPORTAÇÃO DE ESTRUTURA DE DADOS PARA AGRUPAMENTO DE VALORES ---
from collections import defaultdict

# --- IMPORTAÇÃO DE OPERADORES LÓGICOS PARA CONSULTAS SQLALCHEMY ---
from sqlalchemy import and_, or_

# --- IMPORTAÇÃO DE BIBLIOTECA PARA GERAÇÃO DE DOCUMENTOS PDF ---
from fpdf import FPDF

import base64
import tempfile
from datetime import timezone, timedelta

# --- DEFINIÇÃO DO BLUEPRINT DA ÁREA PÚBLICA (ACESSO DE MOTORISTAS) ---
main_bp = Blueprint('main', __name__)

DOCUMENTOS_UPLOAD_FOLDER = 'app/static/uploads/documentos_fixos'
DOCUMENTOS_ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'png'}

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

#Rota para ativar/desativar opcao do motorista selecionar o conjunto
@admin_bp.route('/salvar_config_unidade', methods=['POST'])
@login_required(required_role=["master"])
def salvar_config_unidade():
    user_unidade = session.get('unidade')
    if not user_unidade:
        flash('Sua conta não está associada a uma unidade.', 'danger')
        return redirect(url_for('admin.dashboard'))

    # Captura o valor selecionado no dropdown ('NENHUMA', 'UNIDADE', 'OPERACAO')
    nova_permissao = request.form.get('motorista_pode_trocar_veiculo')
    
    # Validação para garantir que o valor é um dos esperados
    if nova_permissao not in ['NENHUMA', 'UNIDADE', 'OPERACAO']:
        flash('Valor de permissão inválido.', 'danger')
        return redirect(url_for('admin.dashboard'))

    config = UnidadeConfig.query.filter_by(unidade=user_unidade).first()
    if config:
        config.motorista_pode_trocar_veiculo = nova_permissao
        db.session.commit()
        
        # Mensagem de feedback mais descritiva
        if nova_permissao == 'NENHUMA':
            flash('Troca de veículo DESATIVADA para os motoristas da sua unidade.', 'info')
        else:
            flash(f'Permissão de troca de veículo definida como "{nova_permissao}" para a sua unidade.', 'success')
    else:
        flash('Configuração da unidade não encontrada.', 'danger')

    return redirect(url_for('admin.dashboard'))


@main_bp.route('/motorista/trocar_veiculo', methods=['POST'])
def trocar_veiculo():
    """
    Processa a troca ou a primeira vinculação de um conjunto para o motorista,
    respeitando a configuração da unidade e garantindo a integridade do banco de dados.
    """
    if 'motorista_id' not in session:
        return redirect(url_for('main.motorista_login'))

    motorista_atual = Motorista.query.get(session['motorista_id'])
    
    config_unidade = UnidadeConfig.query.filter_by(unidade=motorista_atual.unidade).first()
    permissao = config_unidade.motorista_pode_trocar_veiculo if config_unidade else 'NENHUMA'

    if permissao == 'NENHUMA':
        flash('A troca de veículo não está permitida para sua unidade. Fale com o administrador.', 'danger')
        return redirect(url_for('main.lista_checklists_motorista'))

    novo_veiculo_id = request.form.get('veiculo_id')

    if not novo_veiculo_id:
        flash('Você precisa selecionar um conjunto.', 'warning')
        return redirect(url_for('main.lista_checklists_motorista'))

    novo_veiculo = Veiculo.query.get(novo_veiculo_id)
    if not novo_veiculo:
        flash('Conjunto selecionado é inválido.', 'danger')
        return redirect(url_for('main.lista_checklists_motorista'))

    if permissao == 'UNIDADE' and motorista_atual.unidade != novo_veiculo.unidade:
        flash(f'Você só tem permissão para se vincular a conjuntos da sua unidade ({motorista_atual.unidade}).', 'danger')
        return redirect(url_for('main.lista_checklists_motorista'))
    
    if permissao == 'OPERACAO' and motorista_atual.operacao != novo_veiculo.operacao:
        flash(f'Você só tem permissão para se vincular a conjuntos da sua operação ({motorista_atual.operacao}).', 'danger')
        return redirect(url_for('main.lista_checklists_motorista'))

    # --- LÓGICA DE TROCA CORRIGIDA ---

    # 1. Libera o conjunto novo, se ele estiver ocupado por outro motorista.
    motorista_antigo = novo_veiculo.motorista
    if motorista_antigo and motorista_antigo.id != motorista_atual.id:
        motorista_antigo.veiculo_id = None
        db.session.add(motorista_antigo)
        db.session.commit() # SALVA a liberação antes de continuar.
        flash(f'O conjunto {novo_veiculo.nome_conjunto} foi desvinculado do motorista anterior.', 'info')

    # 2. Atribui o conjunto (agora livre) ao motorista atual.
    motorista_atual.veiculo_id = novo_veiculo.id
    db.session.add(motorista_atual)
    db.session.commit() # SALVA a nova atribuição.
    
    # --- FIM DA CORREÇÃO ---

    flash(f'Você agora está vinculado ao conjunto {novo_veiculo.nome_conjunto}.', 'success')
    return redirect(url_for('main.lista_checklists_motorista'))

# --- Configuração de Upload ---
UPLOAD_FOLDER = 'app/static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



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
    return render_template('motorista_portal.html', motorista=motorista)


@main_bp.route('/login/motorista', methods=['GET', 'POST'])
def motorista_login():
    """Página de login para motoristas, com tratamento para CPF."""
    if request.method == 'POST':
        cpf_digitado = request.form.get('login')
        senha = request.form.get('senha')

        if not cpf_digitado or not senha:
            flash('CPF e senha são obrigatórios.', 'warning')
            return redirect(url_for('main.motorista_login'))

        # Limpa o CPF vindo do formulário para bater com o formato do banco
        cpf_limpo = clean_cpf(cpf_digitado)
        
        # A busca no banco é feita com o CPF limpo
        motorista = Motorista.query.filter_by(_cpf=cpf_limpo).first()

        
        # A verificação de senha funciona, pois ela é gerada a partir do CPF limpo
        if motorista and motorista.check_password(senha):
            session['motorista_id'] = motorista.id
            flash(f'Bem-vindo, {motorista.nome}!', 'success')
            return redirect(url_for('main.motorista_portal'))
        else:
            flash('CPF ou senha inválidos. Tente novamente.', 'danger')
            return redirect(url_for('main.motorista_login'))
            
    return render_template('login.html')


# --- ROTAS DE GERENCIAMENTO DE VEÍCULOS E PLACAS ---

@admin_bp.route('/veiculos')
@login_required()
def veiculos():
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # Query base para veículos e placas, filtrando por unidade se necessário
    veiculos_query = Veiculo.query
    placas_query = Placa.query
    if user_role != 'admin':
        veiculos_query = veiculos_query.filter(Veiculo.unidade == user_unidade)
        placas_query = placas_query.filter(Placa.unidade == user_unidade)

    # A lista agora inclui veículos ativos e inativos. A ordenação é feita no template.
    lista_veiculos = veiculos_query.order_by(Veiculo.nome_conjunto).all()
    todas_as_placas = placas_query.order_by(Placa.numero).all()
    
    # --- LÓGICA CORRIGIDA: Identifica IDs de placas em uso APENAS em veículos ATIVOS ---
    placas_em_uso_ids = set()
    veiculos_ativos = Veiculo.query.filter_by(ativo=True).all()
    for v in veiculos_ativos:
        if v.placa_cavalo_id: placas_em_uso_ids.add(v.placa_cavalo_id)
        if v.placa_carreta1_id: placas_em_uso_ids.add(v.placa_carreta1_id)
        if v.placa_carreta2_id: placas_em_uso_ids.add(v.placa_carreta2_id)

    # Cria listas de placas disponíveis para os formulários de adição/edição
    placas_cavalo_disponiveis = [p for p in todas_as_placas if p.tipo == 'CAVALO' and p.id not in placas_em_uso_ids]
    placas_carreta_disponiveis = [p for p in todas_as_placas if p.tipo == 'CARRETA' and p.id not in placas_em_uso_ids]

    unidades_disponiveis = []
    if user_role == 'admin':
        unidades_db = db.session.query(Usuario.unidade).distinct().all()
        unidades_disponiveis = sorted([u[0] for u in unidades_db if u[0]])

    return render_template(
        'veiculos.html',
        veiculos=lista_veiculos,
        placas=todas_as_placas,
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

    # --- TRAVA DE SEGURANÇA: VERIFICA SE AS PLACAS JÁ ESTÃO EM USO ---
    placas_selecionadas_ids = {int(p_id) for p_id in [placa_cavalo_id, placa_carreta1_id, placa_carreta2_id] if p_id}
    placa_em_uso = Veiculo.query.filter(
        Veiculo.ativo == True,
        or_(
            Veiculo.placa_cavalo_id.in_(placas_selecionadas_ids),
            Veiculo.placa_carreta1_id.in_(placas_selecionadas_ids),
            Veiculo.placa_carreta2_id.in_(placas_selecionadas_ids)
        )
    ).first()

    if placa_em_uso:
        flash(f'Uma ou mais placas selecionadas já estão em uso no conjunto ativo "{placa_em_uso.nome_conjunto}".', 'danger')
        return redirect(url_for('admin.veiculos'))
    # --- FIM DA TRAVA ---

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
        
    placa_cavalo_id = request.form.get('placa_cavalo_id')
    placa_carreta1_id = request.form.get('placa_carreta1_id')
    placa_carreta2_id = request.form.get('placa_carreta2_id')

    # --- TRAVA DE SEGURANÇA: VERIFICA SE AS PLACAS JÁ ESTÃO EM USO EM OUTRO CONJUNTO ---
    placas_selecionadas_ids = {int(p_id) for p_id in [placa_cavalo_id, placa_carreta1_id, placa_carreta2_id] if p_id}
    conflito = Veiculo.query.filter(
        Veiculo.id != veiculo_id,  # Exclui o próprio veículo da verificação
        Veiculo.ativo == True,
        or_(
            Veiculo.placa_cavalo_id.in_(placas_selecionadas_ids),
            Veiculo.placa_carreta1_id.in_(placas_selecionadas_ids),
            Veiculo.placa_carreta2_id.in_(placas_selecionadas_ids)
        )
    ).first()

    if conflito:
        flash(f'Uma ou mais placas selecionadas já estão em uso no conjunto ativo "{conflito.nome_conjunto}".', 'danger')
        return redirect(url_for('admin.veiculos'))
    # --- FIM DA TRAVA ---

    veiculo.nome_conjunto = request.form.get('nome_conjunto')
    veiculo.operacao = request.form.get('operacao')
    veiculo.obs = request.form.get('obs')
    
    if user_role == 'admin':
        veiculo.unidade = request.form.get('unidade')

    veiculo.placa_cavalo_id = int(placa_cavalo_id) if placa_cavalo_id else None
    veiculo.placa_carreta1_id = int(placa_carreta1_id) if placa_carreta1_id else None
    veiculo.placa_carreta2_id = int(placa_carreta2_id) if placa_carreta2_id else None
    
    db.session.commit()
    flash(f'Conjunto "{veiculo.nome_conjunto}" atualizado com sucesso.', 'success')
    return redirect(url_for('admin.veiculos'))


@admin_bp.route('/placas/add', methods=['POST'])
@login_required()
def add_placa():
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    
    numero_placa = request.form.get('numero') 
    tipo = request.form.get('tipo')           
    unidade = request.form.get('unidade')
    operacao = request.form.get('operacao')

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
        operacao=operacao
    )
    db.session.add(nova_placa)
    db.session.commit()
    
    flash(f'Placa {numero_placa.upper()} adicionada com sucesso.', 'success')
    return redirect(url_for('admin.veiculos'))



@admin_bp.route('/veiculos/toggle_status/<int:veiculo_id>', methods=['POST'])
@login_required()
def toggle_veiculo_status(veiculo_id):
    veiculo = Veiculo.query.get_or_404(veiculo_id)
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    if user_role != 'admin' and veiculo.unidade != user_unidade:
        flash('Você não tem permissão para alterar este veículo.', 'danger')
        return redirect(url_for('admin.veiculos'))

    has_history = ChecklistPreenchido.query.filter_by(veiculo_id=veiculo.id).first()
    
    if not has_history:
        db.session.delete(veiculo)
        db.session.commit()
        flash(f'Conjunto "{veiculo.nome_conjunto}" foi excluído permanentemente, pois não possuía histórico.', 'info')
        return redirect(url_for('admin.veiculos'))

    # Se estiver DESATIVANDO (veiculo.ativo é True, será mudado para False)
    if veiculo.ativo:
        veiculo.ativo = False
        if veiculo.motorista:
            veiculo.motorista.veiculo_id = None
            flash(f'O motorista {veiculo.motorista.nome} foi desvinculado do conjunto.', 'warning')
        
        db.session.commit()
        flash(f'Conjunto "{veiculo.nome_conjunto}" foi desativado e arquivado. O histórico foi mantido.', 'success')
    
    # Se estiver REATIVANDO (veiculo.ativo é False, será mudado para True)
    else:
        # --- TRAVA DE SEGURANÇA NA REATIVAÇÃO ---
        placas_do_veiculo_ids = {p_id for p_id in [veiculo.placa_cavalo_id, veiculo.placa_carreta1_id, veiculo.placa_carreta2_id] if p_id}
        
        conflito = Veiculo.query.filter(
            Veiculo.id != veiculo.id,
            Veiculo.ativo == True,
            or_(
                Veiculo.placa_cavalo_id.in_(placas_do_veiculo_ids),
                Veiculo.placa_carreta1_id.in_(placas_do_veiculo_ids),
                Veiculo.placa_carreta2_id.in_(placas_do_veiculo_ids)
            )
        ).first()

        if conflito:
            flash(f'Não foi possível reativar o conjunto "{veiculo.nome_conjunto}". Uma ou mais de suas placas já estão em uso pelo conjunto ativo "{conflito.nome_conjunto}".', 'danger')
            return redirect(url_for('admin.veiculos'))
        # --- FIM DA TRAVA DE SEGURANÇA ---

        veiculo.ativo = True
        db.session.commit()
        flash(f'Conjunto "{veiculo.nome_conjunto}" foi reativado com sucesso.', 'success')

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
    
    flash(f'Placa {placa.numero} excluída com sucesso.', 'info')
    return redirect(url_for('admin.veiculos'))


#-----------------------------------------------------------------------
# ROTA PARA ACESSAR DOCUMENTOS FIXOS (MOTORISTA E ADMIN)
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
                assinatura_imagem=assinatura_imagem_data 
            )
            db.session.add(nova_assinatura)
            db.session.commit()

            if resposta_usuario.strip().lower() == conteudo.resposta_correta.strip().lower():
                flash('Conteúdo assinado! Sua resposta está correta.', 'success')
            else:
                flash('Conteúdo assinado. Sua resposta está incorreta, revise o material.', 'warning')
            
            return redirect(url_for('main.lista_conteudos'))
    
    return render_template('conteudo_motorista.html', 
                           conteudo=conteudo, 
                           assinatura=assinatura)



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

        # --- CORREÇÃO PRINCIPAL: CAPTURA A HORA DO DISPOSITIVO DO USUÁRIO ---
        data_preenchimento_str = request.form.get('data_preenchimento_local')
        if data_preenchimento_str:
            # Converte a string ISO 8601 enviada pelo navegador para um objeto datetime
            data_preenchimento = datetime.fromisoformat(data_preenchimento_str.replace('Z', '+00:00'))
        else:
            # Fallback para a hora do servidor, caso o javascript falhe
            data_preenchimento = datetime.utcnow()

        assinatura_motorista_data = request.form.get('assinatura_motorista')
        assinatura_responsavel_data = request.form.get('assinatura_responsavel')
        outros_problemas = request.form.get('outros_problemas')
        solucoes_adotadas = request.form.get('solucoes_adotadas')
        pendencias_gerais = request.form.get('pendencias_gerais')

        if not assinatura_motorista_data:
            flash('A assinatura do motorista é obrigatória.', 'danger')
            return redirect(url_for('main.preencher_checklist', checklist_id=checklist_id))

        novo_preenchimento = ChecklistPreenchido(
            motorista_id=motorista.id,
            veiculo_id=veiculo_do_motorista.id,
            checklist_id=checklist.id,
            data_preenchimento=data_preenchimento,  # <-- USA A DATA/HORA CORRETA
            assinatura_motorista=assinatura_motorista_data,
            assinatura_responsavel=assinatura_responsavel_data,
            outros_problemas=outros_problemas,
            solucoes_adotadas=solucoes_adotadas,
            pendencias_gerais=pendencias_gerais
        )
        db.session.add(novo_preenchimento)

        # (O restante da função continua igual para salvar as respostas e pendências)
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

        for i in range(5):
            local = request.form.get(f'extintor-{i}-local')
            tipo = request.form.get(f'extintor-{i}-tipo')
            peso = request.form.get(f'extintor-{i}-peso')
            vencimento_str = request.form.get(f'extintor-{i}-vencimento')
            trocado = request.form.get(f'extintor-{i}-trocado')
            motivo_troca = request.form.get(f'extintor-{i}-motivo')

            if peso or vencimento_str or motivo_troca:
                vencimento_data = None
                if vencimento_str:
                    try:
                        vencimento_data = datetime.strptime(vencimento_str, '%d/%m/%Y').date()
                    except ValueError:
                        pass
                novo_extintor = ExtintorCheck(
                    preenchimento=novo_preenchimento,
                    local=local, tipo=tipo, peso=peso,
                    vencimento=vencimento_data, trocado=trocado, motivo_troca=motivo_troca
                )
                db.session.add(novo_extintor)

        db.session.flush()

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
            session['setor'] = user.setor
            flash('Login bem-sucedido!', 'success')
            session.permanent = True  # ⏱️ ativa limite de tempo de sessão
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
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    
    config_unidade = None
    if user_role == 'master' and user_unidade:
        config_unidade = UnidadeConfig.query.filter_by(unidade=user_unidade).first()
        if not config_unidade:
            config_unidade = UnidadeConfig(unidade=user_unidade, motorista_pode_trocar_veiculo=False)
            db.session.add(config_unidade)
            db.session.commit()

    return render_template('adm.html', config_unidade=config_unidade)




# --- ROTAS DE GERENCIAMENTO DE USUÁRIOS ---

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
    unidade = request.form.get('unidade_usuario') 

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

    # Filtra por um veículo específico, se solicitado
    veiculo_id_str = request.args.get('veiculo_id')
    veiculo_id = int(veiculo_id_str) if veiculo_id_str else None
    if veiculo_id:
        query = query.filter(Pendencia.veiculo_id == veiculo_id)

    pendencias = query.order_by(Pendencia.data_criacao.desc()).all()

    # Agrupa as pendências pelo veículo
    pendencias_agrupadas = defaultdict(list)
    for pendencia in pendencias:
        pendencias_agrupadas[pendencia.veiculo].append(pendencia)

    # Busca veículos para popular o filtro da página
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

    # Atualiza a pendência
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

    brt_tz = timezone(timedelta(hours=-3))
    utc_tz = timezone.utc

    # --- 1. BUSCA OS CHECKLISTS ATIVOS (DIÁRIO E MENSAL) ---
    def get_active_checklist(tipo):
        query = Checklist.query.filter(Checklist.tipo == tipo, Checklist.ativo == True)
        if user_role != 'admin':
            query = query.filter(or_(Checklist.unidade == user_unidade, Checklist.unidade == None))
        return query.order_by(Checklist.data.desc()).first()

    checklist_diario = get_active_checklist('DIÁRIO')
    checklist_mensal = get_active_checklist('MENSAL')

    # --- 2. BUSCA OS VEÍCULOS (ATIVOS E INATIVOS COM REGISTRO HOJE) ---
    veiculos_query = Veiculo.query
    motoristas_query = Motorista.query
    if user_role != 'admin':
        veiculos_query = veiculos_query.filter(Veiculo.unidade == user_unidade)
        motoristas_query = motoristas_query.filter(Motorista.unidade == user_unidade)

    start_of_today_utc = datetime.combine(hoje, datetime.min.time(), tzinfo=brt_tz).astimezone(utc_tz)
    end_of_today_utc = datetime.combine(hoje, datetime.max.time(), tzinfo=brt_tz).astimezone(utc_tz)
    
    veiculo_ids_com_preenchimento_diario = set()
    if checklist_diario:
        veiculo_ids_com_preenchimento_diario = {p.veiculo_id for p in ChecklistPreenchido.query.filter(
            ChecklistPreenchido.checklist_id == checklist_diario.id,
            ChecklistPreenchido.data_preenchimento.between(start_of_today_utc, end_of_today_utc)
        ).all()}

    veiculos_ativos = veiculos_query.filter(Veiculo.ativo == True).all()
    veiculos_inativos_com_registro = veiculos_query.filter(
        Veiculo.ativo == False,
        Veiculo.id.in_(veiculo_ids_com_preenchimento_diario)
    ).all()

    veiculos_para_exibir_map = {v.id: v for v in veiculos_ativos}
    for v in veiculos_inativos_com_registro:
        if v.id not in veiculos_para_exibir_map:
            veiculos_para_exibir_map[v.id] = v
    veiculos_para_exibir = sorted(veiculos_para_exibir_map.values(), key=lambda v: v.nome_conjunto)

    # --- 3. COLETA DADOS DE STATUS (DIÁRIO, MENSAL, INDISPONIBILIDADE, ISENÇÃO) ---
    # <<< INÍCIO DA ALTERAÇÃO >>>
    indisponibilidades_hoje_query = VeiculoIndisponibilidade.query.filter(
        VeiculoIndisponibilidade.data_inicio <= hoje, 
        or_(VeiculoIndisponibilidade.data_fim >= hoje, VeiculoIndisponibilidade.data_fim == None)
    ).all()
    
    indisponibilidades_hoje = {}
    for ind in indisponibilidades_hoje_query:
        # Se tipo_checklist for None (ou vazio), afeta ambos. Se tiver valor, afeta só o tipo específico.
        afeta_diario = not ind.tipo_checklist or ind.tipo_checklist == 'DIÁRIO'
        afeta_mensal = not ind.tipo_checklist or ind.tipo_checklist == 'MENSAL'
        indisponibilidades_hoje[ind.veiculo_id] = {
            'motivo': ind.motivo,
            'afeta_diario': afeta_diario,
            'afeta_mensal': afeta_mensal
        }
    # <<< FIM DA ALTERAÇÃO >>>

    preenchimentos_diarios_agrupados = defaultdict(list)
    if checklist_diario:
        preenchimentos_diarios_brutos = ChecklistPreenchido.query.filter(
            ChecklistPreenchido.checklist_id == checklist_diario.id,
            ChecklistPreenchido.data_preenchimento.between(start_of_today_utc, end_of_today_utc)
        ).order_by(ChecklistPreenchido.data_preenchimento.asc()).all()
        for p in preenchimentos_diarios_brutos:
            preenchimentos_diarios_agrupados[p.veiculo_id].append(p)

    preenchimentos_mensais_agrupados = defaultdict(list)
    if checklist_mensal:
        start_of_month = hoje.replace(day=1)
        next_month = start_of_month.replace(day=28) + timedelta(days=4)
        end_of_month = next_month - timedelta(days=next_month.day)
        start_of_month_utc = datetime.combine(start_of_month, datetime.min.time(), tzinfo=brt_tz).astimezone(utc_tz)
        end_of_month_utc = datetime.combine(end_of_month, datetime.max.time(), tzinfo=brt_tz).astimezone(utc_tz)

        preenchimentos_mensais_brutos = ChecklistPreenchido.query.filter(
            ChecklistPreenchido.checklist_id == checklist_mensal.id,
            ChecklistPreenchido.data_preenchimento.between(start_of_month_utc, end_of_month_utc)
        ).order_by(ChecklistPreenchido.data_preenchimento.asc()).all()
        for p in preenchimentos_mensais_brutos:
            preenchimentos_mensais_agrupados[p.veiculo_id].append(p)

    isencoes_diario = {i.motorista_id: i.motivo for i in MotoristaIsencao.query.filter_by(data=hoje, tipo_checklist='DIÁRIO').all()}
    isencoes_mensal = {i.motorista_id: i.motivo for i in MotoristaIsencao.query.filter(
        db.func.extract('year', MotoristaIsencao.data) == hoje.year,
        db.func.extract('month', MotoristaIsencao.data) == hoje.month,
        MotoristaIsencao.tipo_checklist == 'MENSAL'
    ).all()}

    # --- 4. MONTA A ESTRUTURA DE DADOS CORRETA PARA O TEMPLATE ---
    veiculos_status = []
    for veiculo in veiculos_para_exibir:
        info = {
            'veiculo': veiculo,
            'status_diario': {'status': 'N/A', 'detalhe': 'Não aplicável', 'classe_css': 'table-secondary'},
            'status_mensal': {'status': 'N/A', 'detalhe': 'Não aplicável', 'classe_css': 'table-secondary'}
        }

        motorista_atual = veiculo.motorista
        detalhe_motorista = f"Motorista: {motorista_atual.nome}" if motorista_atual else "Sem motorista"

        # <<< INÍCIO DA ALTERAÇÃO >>>
        indisponibilidade = indisponibilidades_hoje.get(veiculo.id)

        # Status DIÁRIO
        if checklist_diario:
            if indisponibilidade and indisponibilidade['afeta_diario']:
                info['status_diario'] = {'status': 'Indisponível', 'detalhe': indisponibilidade['motivo'], 'classe_css': 'table-secondary'}
            elif veiculo.id in preenchimentos_diarios_agrupados:
                regs = preenchimentos_diarios_agrupados[veiculo.id]
                ultimo_reg = regs[-1]
                hora_local = ultimo_reg.data_preenchimento.replace(tzinfo=utc_tz).astimezone(brt_tz).strftime('%H:%M')
                detalhe = f"por {ultimo_reg.motorista.nome} às {hora_local}" + (f" ({len(regs)} regs)" if len(regs) > 1 else "")
                info['status_diario'] = {'status': 'Preenchido', 'detalhe': detalhe, 'classe_css': 'table-success'}
            elif motorista_atual and motorista_atual.id in isencoes_diario:
                info['status_diario'] = {'status': 'Isento', 'detalhe': f"{detalhe_motorista} ({isencoes_diario[motorista_atual.id]})", 'classe_css': 'table-light'}
            else:
                info['status_diario'] = {'status': 'Pendente', 'detalhe': detalhe_motorista, 'classe_css': 'table-danger'}
        
        # Status MENSAL
        if checklist_mensal:
            if indisponibilidade and indisponibilidade['afeta_mensal']:
                info['status_mensal'] = {'status': 'Indisponível', 'detalhe': indisponibilidade['motivo'], 'classe_css': 'table-secondary'}
            elif veiculo.id in preenchimentos_mensais_agrupados:
                regs = preenchimentos_mensais_agrupados[veiculo.id]
                ultimo_reg = regs[-1]
                data_local = ultimo_reg.data_preenchimento.replace(tzinfo=utc_tz).astimezone(brt_tz).strftime('%d/%m')
                detalhe = f"por {ultimo_reg.motorista.nome} em {data_local}" + (f" ({len(regs)} regs)" if len(regs) > 1 else "")
                info['status_mensal'] = {'status': 'Preenchido', 'detalhe': detalhe, 'classe_css': 'table-success'}
            elif motorista_atual and motorista_atual.id in isencoes_mensal:
                info['status_mensal'] = {'status': 'Isento', 'detalhe': f"{detalhe_motorista} ({isencoes_mensal[motorista_atual.id]})", 'classe_css': 'table-light'}
            else:
                info['status_mensal'] = {'status': 'Pendente', 'detalhe': detalhe_motorista, 'classe_css': 'table-danger'}
        # <<< FIM DA ALTERAÇÃO >>>
        
        veiculos_status.append(info)

    # --- 5. PREPARA DADOS PARA FORMULÁRIOS E RENDERIZA ---
    veiculos_para_formulario = veiculos_query.order_by(Veiculo.nome_conjunto).all()
    motoristas_para_formulario = motoristas_query.order_by(Motorista.nome).all()

    tipos_checklist_query = db.session.query(Checklist.tipo).distinct().all()
    tipos_checklist = sorted([tipo[0] for tipo in tipos_checklist_query])

    return render_template(
        'admin_acompanhamento_diario.html',
        veiculos_status=veiculos_status,
        checklist_diario=checklist_diario,
        checklist_mensal=checklist_mensal,
        data_hoje=hoje,
        veiculos_para_formulario=veiculos_para_formulario,
        motoristas_para_formulario=motoristas_para_formulario,
        tipos_checklist=tipos_checklist
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
    tipo_checklist = request.form.get('tipo_checklist')


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
        usuario_id=user_id,
        tipo_checklist=tipo_checklist if tipo_checklist else None
    )
    db.session.add(nova_indisponibilidade)
    db.session.commit()
    
    flash('Indisponibilidade do veículo registrada com sucesso!', 'success')
    return redirect(url_for('admin.acompanhamento_diario'))

# ROTA PARA REGISTRAR ISENÇÃO DE MOTORISTA (COM PERÍODO)

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
@login_required() # Usando o decorador para segurança
def relatorios_consolidados():
    # --- DEFINIÇÃO DOS FUSOS HORÁRIOS ---
    brt_tz = timezone(timedelta(hours=-3))
    utc_tz = timezone.utc

    # --- LÓGICA DE FILTRO CORRIGIDA ---
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    veiculos_query = Veiculo.query
    if user_role != 'admin':
        veiculos_query = veiculos_query.filter(Veiculo.unidade == user_unidade)
    
    veiculos = veiculos_query.order_by(Veiculo.nome_conjunto).all()
    # --- FIM DA CORREÇÃO ---
    
    resultados_agrupados = None
    filtros = request.form if request.method == 'POST' else {}

    if request.method == 'POST':
        tipo_checklist = request.form.get('tipo_checklist')
        veiculo_id = request.form.get('veiculo_id')
        data_inicio_str = request.form.get('data_inicio')
        data_fim_str = request.form.get('data_fim')
        
        query = ChecklistPreenchido.query.join(Checklist).join(Veiculo)

        # Filtra pela unidade do usuário se não for admin (camada extra de segurança)
        if user_role != 'admin':
            query = query.filter(Veiculo.unidade == user_unidade)

        if data_inicio_str:
            data_inicio_brt = datetime.strptime(data_inicio_str, '%Y-%m-%d').replace(tzinfo=brt_tz)
            data_inicio_utc = data_inicio_brt.astimezone(utc_tz)
            query = query.filter(ChecklistPreenchido.data_preenchimento >= data_inicio_utc)
        if data_fim_str:
            data_fim_brt = datetime.combine(datetime.strptime(data_fim_str, '%Y-%m-%d'), datetime.max.time()).replace(tzinfo=brt_tz)
            data_fim_utc = data_fim_brt.astimezone(utc_tz)
            query = query.filter(ChecklistPreenchido.data_preenchimento <= data_fim_utc)

        if tipo_checklist:
            query = query.filter(Checklist.tipo == tipo_checklist)
        if veiculo_id and veiculo_id != 'todos':
            query = query.filter(ChecklistPreenchido.veiculo_id == veiculo_id)

        preenchimentos = query.order_by(Veiculo.nome_conjunto, ChecklistPreenchido.data_preenchimento.desc()).all()

        for p in preenchimentos:
            p.data_preenchimento_local = p.data_preenchimento.replace(tzinfo=utc_tz).astimezone(brt_tz)
        
        resultados_agrupados = defaultdict(lambda: defaultdict(list))
        for p in preenchimentos:
            if p.veiculo:
                data_local = p.data_preenchimento_local.date()
                resultados_agrupados[p.veiculo.nome_conjunto][data_local].append(p)
            
    return render_template('admin_relatorios_consolidados.html', 
                           veiculos=veiculos,
                           resultados=resultados_agrupados,
                           filtros=filtros)





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

    # CORREÇÃO: Verifica a existência usando o CPF limpo
    cpf_limpo = clean_cpf(cpf)
    if Motorista.query.filter_by(_cpf=cpf_limpo).first():
        flash('Já existe um motorista com este CPF.', 'danger')
        return redirect(url_for('admin.motoristas'))

    # A criação funciona, pois o modelo `Motorista` já limpa o CPF automaticamente
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

    
    cpf_antigo = motorista.cpf
    cpf_novo = request.form.get('cpf')

    # Atualiza todos os outros campos primeiro
    motorista.nome = request.form.get('nome')
    motorista.rg = request.form.get('rg')
    motorista.cnh = request.form.get('cnh')
    motorista.frota = request.form.get('frota')
    motorista.veiculo_id = int(request.form.get('veiculo_id')) if request.form.get('veiculo_id') else None
    motorista.operacao = request.form.get('operacao')
    
    if user_role == 'admin':
        motorista.unidade = request.form.get('unidade')
    
    # Agora, lida com a alteração do CPF
    motorista.cpf = cpf_novo

    # Se o CPF foi realmente alterado, redefine a senha para o novo padrão.
    if cpf_novo != cpf_antigo:
        motorista.set_password(None) # O método já usa o CPF do próprio objeto para gerar a senha
        flash('O CPF foi alterado. A senha do motorista foi redefinida para os 6 primeiros dígitos do novo CPF.', 'info')
    

    db.session.commit()
    flash(f'Dados do motorista {motorista.nome} atualizados com sucesso!', 'success')
    return redirect(url_for('admin.motoristas'))



@admin_bp.route('/motoristas/toggle/<int:motorista_id>', methods=['POST'])
@login_required()
def toggle_motorista_status(motorista_id):
    """
    Ativa ou desativa um motorista. Esta função substitui a exclusão.
    """
    motorista = Motorista.query.get_or_404(motorista_id)
    
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # Verificação de segurança: Apenas admin ou master da mesma unidade podem alterar.
    if user_role != 'admin' and motorista.unidade != user_unidade:
        flash('Você não tem permissão para alterar o status deste motorista.', 'danger')
        return redirect(url_for('admin.motoristas'))

    # Inverte o status do motorista (True -> False, False -> True)
    motorista.ativo = not motorista.ativo
    
    # REGRA DE NEGÓCIO: Se estiver desativando, desvincule o veículo.
    if not motorista.ativo and motorista.veiculo:
        motorista.veiculo_id = None
        
    db.session.commit()
    
    status = "ativado" if motorista.ativo else "desativado"
    flash(f'Motorista {motorista.nome} foi {status} com sucesso.', 'success')
    
    return redirect(url_for('admin.motoristas'))




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
            return redirect(url_for('admin.conteudo'))

        file = request.files['arquivo']
        
        # Verifica se um arquivo foi realmente selecionado
        if file.filename == '':
            flash('Nenhum arquivo selecionado. Por favor, escolha um arquivo para enviar.', 'error')
            return redirect(url_for('admin.conteudo')) 

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            # Armazena o caminho relativo para ser usado no template
            recurso_link = os.path.join('uploads', filename).replace('\\', '/')
        else:
            flash('Tipo de arquivo não permitido.', 'danger')
            return redirect(url_for('admin.conteudo')) 

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



@admin_bp.route('/checklists/add', methods=['POST'])
@login_required(required_role=["admin"])
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
    
    motorista = Motorista.query.get(session['motorista_id'])
    if not motorista:
        flash('Seus dados de motorista não foram encontrados.', 'danger')
        return redirect(url_for('main.motorista_login'))
        
    motorista_unidade = motorista.unidade
    
    config = UnidadeConfig.query.filter_by(unidade=motorista_unidade).first()
    permissao_troca = config.motorista_pode_trocar_veiculo if config else 'NENHUMA'
    
    veiculos_para_troca = []
    if permissao_troca != 'NENHUMA':
        query_veiculos = Veiculo.query.filter_by(ativo=True)
        
        if permissao_troca == 'UNIDADE':
            query_veiculos = query_veiculos.filter(Veiculo.unidade == motorista.unidade)
        elif permissao_troca == 'OPERACAO':
            if motorista.operacao:
                query_veiculos = query_veiculos.filter(Veiculo.operacao == motorista.operacao)
            else:
                query_veiculos = query_veiculos.filter(Veiculo.id == -1)

        if motorista.veiculo:
            query_veiculos = query_veiculos.filter(Veiculo.id != motorista.veiculo.id)
            
        veiculos_para_troca = query_veiculos.order_by(Veiculo.nome_conjunto).all()

    if not motorista.veiculo:
        return render_template(
            'motorista_lista_checklists.html', 
            motorista_sem_veiculo=True,
            veiculos_disponiveis=veiculos_para_troca,
            troca_permitida=permissao_troca 
        )

    checklists = Checklist.query.filter(
        Checklist.ativo == True,
        Checklist.itens.any(),
        or_(Checklist.unidade == motorista_unidade, Checklist.unidade == None)
    ).order_by(Checklist.tipo, Checklist.codigo).all()
    
    checklists_com_status = []
    hoje = date.today()

    for checklist in checklists:
        preenchido_no_periodo = False
        status_texto = "Pendente"
        
        if motorista.veiculo:
            q = ChecklistPreenchido.query.filter(
                and_(
                    ChecklistPreenchido.motorista_id == motorista.id,
                    ChecklistPreenchido.checklist_id == checklist.id,
                    ChecklistPreenchido.veiculo_id == motorista.veiculo.id
                )
            )
            
            if checklist.tipo == 'DIÁRIO':
                preenchimento = q.filter(db.func.date(ChecklistPreenchido.data_preenchimento) == hoje).first()
                # --- CORREÇÃO DO ERRO DE DIGITAÇÃO APLICADA AQUI ---
                if preenchimento:
                    preenchido_no_periodo = True
                    status_texto = "Preenchido Hoje"
            
            elif checklist.tipo == 'MENSAL':
                preenchimento = q.filter(
                    db.func.extract('year', ChecklistPreenchido.data_preenchimento) == hoje.year,
                    db.func.extract('month', ChecklistPreenchido.data_preenchimento) == hoje.month
                ).first()
                # --- CORREÇÃO DO ERRO DE DIGITAÇÃO APLICADA AQUI ---
                if preenchimento:
                    preenchido_no_periodo = True
                    status_texto = "Preenchido este Mês"

        checklists_com_status.append({
            'checklist': checklist, 
            'preenchido': preenchido_no_periodo,
            'status': status_texto
        })

    return render_template(
        'motorista_lista_checklists.html', 
        checklists_info=checklists_com_status,
        motorista_sem_veiculo=False,
        veiculo_atual=motorista.veiculo,
        veiculos_disponiveis=veiculos_para_troca, 
        troca_permitida=permissao_troca
    )



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
@login_required(required_role=["admin"])
def add_checklist_item(checklist_id):
    """
    Adiciona um novo item ou sub-item a um checklist.
     Salva a ordem como texto para permitir "1.1", "1.2", etc.
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
    # Captura a ordem como string e substitui vírgula por ponto
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
        ordem=ordem_str,  
        parent_id=int(parent_id) if parent_id else None,
        setor_responsavel=setor_responsavel if setor_responsavel else None
    )
    db.session.add(novo_item)
    db.session.commit()
    
    flash('Item adicionado com sucesso!', 'success')
    return redirect(url_for('admin.view_checklist', checklist_id=checklist_id))





@admin_bp.route('/checklists/delete_item/<int:item_id>', methods=['POST'])
@login_required(required_role=["admin"])
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
@login_required(required_role=["admin"])
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


@admin_bp.route('/checklist/item/<int:item_id>/json', methods=['GET'])
@login_required()
def get_checklist_item_json(item_id):
    """
    Retorna os dados de um item de checklist em formato JSON para o modal de edição.
    """
    item = ChecklistItem.query.get_or_404(item_id)
    
    # Validação de segurança
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    if user_role != 'admin' and item.checklist.unidade is not None and item.checklist.unidade != user_unidade:
        return jsonify({'error': 'Permissão negada'}), 403

    return jsonify({
        'id': item.id,
        'texto': item.texto,
        'ordem': item.ordem or '', # Garante que não seja None
        'setor_responsavel': item.setor_responsavel or '' # Retorna string vazia se for None
    })


@admin_bp.route('/checklist/item/update/<int:item_id>', methods=['POST'])
@login_required(required_role=["admin"])
def update_checklist_item(item_id):
    """
    Atualiza um item de checklist (principal ou sub-item) a partir dos dados do formulário modal.
    """
    item = ChecklistItem.query.get_or_404(item_id)
    
    # Validação de segurança
    user_role = session.get('role')
    user_unidade = session.get('unidade')
    if user_role != 'admin' and item.checklist.unidade is not None and item.checklist.unidade != user_unidade:
        flash('Você não tem permissão para modificar este item.', 'danger')
        return redirect(url_for('admin.checklists'))

    # Captura os dados do formulário
    novo_texto = request.form.get('texto')
    # Substitui vírgula por ponto para consistência na ordem
    nova_ordem = request.form.get('ordem', '').replace(',', '.')
    novo_setor = request.form.get('setor_responsavel')

    if not novo_texto:
        flash('O texto do item não pode ser vazio.', 'danger')
    else:
        item.texto = novo_texto
        item.ordem = nova_ordem
        # Salva o setor, ou None se a opção "Nenhum" for selecionada (valor vazio)
        item.setor_responsavel = novo_setor if novo_setor else None
        
        db.session.commit()
        flash('Item atualizado com sucesso!', 'success')

    return redirect(url_for('admin.view_checklist', checklist_id=item.checklist_id))



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


#relatorio de status diario

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
    
    if not preenchimentos:
        flash('Nenhum checklist preenchido encontrado para os filtros selecionados.', 'warning')
        return redirect(url_for('admin.relatorios_consolidados'))

    checklist_base = Checklist.query.get(preenchimentos[0].checklist_id)
    itens_principais = checklist_base.itens.filter_by(parent_id=None).order_by(ChecklistItem.ordem).all()

    titulo = f"Relatório - {veiculo_obj.nome_conjunto if veiculo_obj else 'Geral'}"
    pdf = PDF(title=titulo, orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- DEFINIÇÃO DOS FUSOS HORÁRIOS ---
    brt_tz = timezone(timedelta(hours=-3))
    utc_tz = timezone.utc

    dados_agrupados = defaultdict(list)
    for p in preenchimentos:
        # Agrupa pela data local correta
        data_local = p.data_preenchimento.replace(tzinfo=utc_tz).astimezone(brt_tz)
        dados_agrupados[data_local.date()].append(p)

    laudo_count = 0
    for data, preenchs in sorted(dados_agrupados.items()):
        for p in preenchs:
            laudo_count += 1
            if laudo_count > 1:
                pdf.add_page()
            
            # --- CORREÇÃO: CONVERTE A HORA DE UTC (DO BANCO) PARA BRT (EXIBIÇÃO) ---
            hora_utc = p.data_preenchimento.replace(tzinfo=utc_tz)
            hora_local_obj = hora_utc.astimezone(brt_tz)
            data_local_str = hora_local_obj.strftime('%d/%m/%Y')
            hora_local_str = hora_local_obj.strftime('%H:%M')

            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, f"Data do Checklist: {data_local_str}", 0, 1, 'L')
            pdf.set_font('Arial', 'I', 10)
            pdf.cell(0, 8, f"Preenchido por: {p.motorista.nome} às {hora_local_str}", 0, 1, 'L')
            pdf.ln(2)

            # (O restante do código para renderizar os itens e assinaturas continua o mesmo)
            item_counter = 1
            for item_principal in itens_principais:
                pdf.set_font('Arial', 'B', 10)
                pdf.set_fill_color(224, 224, 224)
                pdf.cell(0, 7, item_principal.texto.encode('latin-1', 'replace').decode('latin-1'), 1, 1, 'C', 1)
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(10, 7, 'Nº', 1, 0, 'C', 1)
                pdf.cell(120, 7, 'Descrição', 1, 0, 'C', 1)
                pdf.cell(60, 7, 'Resposta', 1, 1, 'C', 1)
                pdf.set_font('Arial', '', 9)

                def natural_sort_key(text):
                    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', str(text or '0'))]

                sub_itens_sorted = sorted(item_principal.sub_itens, key=lambda si: natural_sort_key(si.ordem))
                for sub_item in sub_itens_sorted:
                    resposta_obj = next((r for r in p.respostas if r.item_id == sub_item.id), None)
                    h = 6
                    x_start = pdf.get_x()
                    y_start = pdf.get_y()
                    pdf.cell(10, h, str(item_counter), 1, 0, 'C')
                    pdf.multi_cell(120, h, sub_item.texto.encode('latin-1', 'replace').decode('latin-1'), 1, 'L')
                    y_end = pdf.get_y()
                    pdf.set_xy(x_start + 130, y_start)
                    pdf.cell(60, y_end - y_start, resposta_obj.resposta if resposta_obj else '-', 1, 1, 'C')
                    if resposta_obj and resposta_obj.observacao:
                        pdf.set_font('Arial', 'I', 8)
                        pdf.set_fill_color(245, 245, 245)
                        pdf.multi_cell(0, 5, f"Obs: {resposta_obj.observacao.encode('latin-1', 'replace').decode('latin-1')}", 1, 'L', 1)
                        pdf.set_font('Arial', '', 9)
                    item_counter += 1

            # --- INÍCIO DA SEÇÃO DE EXTINTORES PARA O PDF ---
            extintores_preenchidos = p.extintores_check.all()
            if extintores_preenchidos:
                pdf.ln(5) # Espaçamento
                pdf.set_font('Arial', 'B', 10)
                pdf.set_fill_color(224, 224, 224)
                pdf.cell(0, 7, "Controle de Extintores", 1, 1, 'C', 1)

                # Cabeçalho da tabela
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(40, 7, 'Local', 1, 0, 'C', 1)
                pdf.cell(20, 7, 'Tipo', 1, 0, 'C', 1)
                pdf.cell(20, 7, 'Peso (KG)', 1, 0, 'C', 1)
                pdf.cell(30, 7, 'Vencimento', 1, 0, 'C', 1)
                pdf.cell(20, 7, 'Trocado?', 1, 0, 'C', 1)
                pdf.cell(60, 7, 'Motivo da Troca', 1, 1, 'C', 1)
                
                # Corpo da tabela
                pdf.set_font('Arial', '', 9)
                for ext in extintores_preenchidos:
                    pdf.cell(40, 6, (ext.local or '').encode('latin-1', 'replace').decode('latin-1'), 1, 0, 'L')
                    pdf.cell(20, 6, (ext.tipo or '').encode('latin-1', 'replace').decode('latin-1'), 1, 0, 'C')
                    pdf.cell(20, 6, str(ext.peso or ''), 1, 0, 'C')
                    pdf.cell(30, 6, ext.vencimento.strftime('%d/%m/%Y') if ext.vencimento else '', 1, 0, 'C')
                    pdf.cell(20, 6, (ext.trocado or '').encode('latin-1', 'replace').decode('latin-1'), 1, 0, 'C')
                    pdf.cell(60, 6, (ext.motivo_troca or '').encode('latin-1', 'replace').decode('latin-1'), 1, 1, 'L')
            # --- FIM DA SEÇÃO DE EXTINTORES PARA O PDF ---
            
            altura_bloco_assinatura = 60
            if pdf.get_y() + altura_bloco_assinatura > pdf.page_break_trigger:
                pdf.add_page()

            pdf.ln(5)
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(0, 8, 'Observações Gerais e Assinaturas', 0, 1, 'L')
            
            obs_text = []
            if p.outros_problemas: obs_text.append(f"Outros Problemas: {p.outros_problemas}")
            if p.solucoes_adotadas: obs_text.append(f"Soluções Adotadas: {p.solucoes_adotadas}")
            if p.pendencias_gerais: obs_text.append(f"Pendências Gerais: {p.pendencias_gerais}")
            
            pdf.set_font('Arial', '', 9)
            if obs_text:
                full_obs_text = "\\n".join(obs_text)
                pdf.multi_cell(0, 5, full_obs_text.encode('latin-1', 'replace').decode('latin-1'), 1, 'L')
            else:
                pdf.cell(0, 8, "Nenhuma observação geral registrada.", 1, 1, 'C')
            
            pdf.ln(10)
            
            y_signatures = pdf.get_y()
            x_motorista = pdf.get_x()
            x_responsavel = x_motorista + 95

            def render_signature(signature_data, x_pos, y_pos):
                temp_file = None
                try:
                    img_data = re.sub('^data:image/.+;base64,', '', signature_data)
                    img_bytes = base64.b64decode(img_data)
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                    temp_file.write(img_bytes)
                    temp_file.close()
                    pdf.image(temp_file.name, x=x_pos, y=y_pos, w=80, h=30)
                except Exception:
                    pdf.text(x_pos + 5, y_pos + 15, "(Erro ao carregar assinatura)")
                finally:
                    if temp_file and os.path.exists(temp_file.name):
                        os.remove(temp_file.name)

            if p.assinatura_motorista:
                render_signature(p.assinatura_motorista, x_motorista + 5, y_signatures)
            
            if p.assinatura_responsavel:
                render_signature(p.assinatura_responsavel, x_responsavel, y_signatures)
            
            pdf.line(x_motorista + 5, y_signatures + 32, x_motorista + 85, y_signatures + 32)
            pdf.set_xy(x_motorista + 5, y_signatures + 33)
            pdf.set_font('Arial', 'I', 8)
            pdf.cell(80, 5, 'Motorista', 0, 0, 'C')
            
            if p.assinatura_responsavel:
                pdf.line(x_responsavel, y_signatures + 32, x_responsavel + 80, y_signatures + 32)
                pdf.set_xy(x_responsavel, y_signatures + 33)
                pdf.cell(80, 5, 'Responsável', 0, 0, 'C')

    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        response_bytes = pdf_output.encode('latin-1')
    else:
        response_bytes = bytes(pdf_output)

    return Response(response_bytes,
                    mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment;filename=relatorio_consolidado.pdf'})



@admin_bp.route('/relatorio/status_diario')
@login_required()
def gerar_relatorio_status_diario():
    """
    Gera um relatório diário de status de preenchimento, corrigido para não usar o motorista atual em datas passadas.
    """
    user_role = session.get('role')
    user_unidade = session.get('unidade')

    # --- 1. Captura e Validação de Filtros ---
    veiculo_id_str = request.args.get('veiculo_id')
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    if not data_inicio_str or not data_fim_str:
        hoje = date.today()
        data_inicio = hoje.replace(day=1)
        proximo_mes = hoje.replace(day=28) + timedelta(days=4)
        data_fim = proximo_mes - timedelta(days=proximo_mes.day)
    else:
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de data inválido.', 'danger')
            return "Erro: Formato de data inválido.", 400

    if (data_fim - data_inicio).days > 93:
        flash('O intervalo para este relatório não pode exceder 3 meses.', 'danger')
        return "Erro: O intervalo não pode exceder 3 meses.", 400

    # --- 2. Seleção de Veículos ---
    veiculos_query = Veiculo.query
    if user_role != 'admin':
        veiculos_query = veiculos_query.filter(Veiculo.unidade == user_unidade)
    if veiculo_id_str and veiculo_id_str != 'todos':
        veiculos_query = veiculos_query.filter(Veiculo.id == int(veiculo_id_str))
    
    veiculos = veiculos_query.order_by(Veiculo.nome_conjunto).all()
    veiculos_selecionados_nomes = ", ".join([v.nome_conjunto for v in veiculos]) if veiculo_id_str != 'todos' else "Todos da Unidade"

    # --- 3. Coleta de Dados Históricos ---
    veiculo_ids = [v.id for v in veiculos]
    
    checklist_diario_query = Checklist.query.filter(Checklist.tipo == 'DIÁRIO', Checklist.ativo == True)
    if user_role != 'admin':
        checklist_diario_query = checklist_diario_query.filter(or_(Checklist.unidade == user_unidade, Checklist.unidade == None))
    
    checklist_diario_ids = [c.id for c in checklist_diario_query.all()]

    preenchimentos = {
        (p.veiculo_id, p.data_preenchimento.date()): p
        for p in ChecklistPreenchido.query.filter(
            ChecklistPreenchido.checklist_id.in_(checklist_diario_ids),
            ChecklistPreenchido.veiculo_id.in_(veiculo_ids),
            db.func.date(ChecklistPreenchido.data_preenchimento).between(data_inicio, data_fim)
        ).all()
    }

    indisponibilidades = {
        (i.veiculo_id, dia.date()): i.motivo
        for i in VeiculoIndisponibilidade.query.filter(VeiculoIndisponibilidade.veiculo_id.in_(veiculo_ids))
        for dia in pd.date_range(i.data_inicio, i.data_fim or data_fim)
        if data_inicio <= dia.date() <= data_fim
    }
    
    # --- 4. Processamento e Geração do Relatório ---
    report_data = []
    dias_no_periodo = [data_inicio + timedelta(days=i) for i in range((data_fim - data_inicio).days + 1)]

    for dia_atual in dias_no_periodo:
        for veiculo in veiculos:
            status_info = {}
            chave_busca = (veiculo.id, dia_atual)

            # 1. Verifica se há um registro de preenchimento. Esta é a fonte de verdade.
            if chave_busca in preenchimentos:
                p = preenchimentos[chave_busca]
                status_info = {
                    'status': 'Preenchido',
                    'detalhe': f"por {p.motorista.nome} às {p.data_preenchimento.strftime('%H:%M')}",
                    'classe_css': 'status-preenchido',
                    'assinatura': p.assinatura_motorista
                }
            # 2. Se não preencheu, verifica indisponibilidade do VEÍCULO.
            elif chave_busca in indisponibilidades:
                status_info = {
                    'status': 'Indisponível',
                    'detalhe': indisponibilidades[chave_busca],
                    'classe_css': 'status-indisponivel',
                    'assinatura': None
                }
            # 3. Se nenhuma das anteriores, o status é 'Não Preenchido'.
            else:
                 status_info = {
                    'status': 'Não Preenchido',
                    'detalhe': 'Nenhum registro de preenchimento ou indisponibilidade para esta data.',
                    'classe_css': 'status-nao-preenchido',
                    'assinatura': None
                }
            
            report_data.append({
                'data': dia_atual,
                'veiculo': veiculo,
                **status_info
            })

    return render_template(
        'admin_relatorio_status_diario.html',
        report_data=report_data,
        data_inicio=data_inicio,
        data_fim=data_fim,
        veiculos_selecionados_nomes=veiculos_selecionados_nomes
    )
