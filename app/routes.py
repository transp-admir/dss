from flask import (Blueprint, render_template, request, 
                   redirect, url_for, session, flash, jsonify)
from .extensions import db
from .models import (Motorista, Conteudo, Assinatura, Checklist, 
                   ChecklistItem, Placa, Veiculo, ChecklistPreenchido, ChecklistResposta)
from datetime import datetime, date
import re
import os
from werkzeug.utils import secure_filename
from collections import defaultdict
from sqlalchemy import and_, or_

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
            return redirect(url_for('main.motorista_portal'))
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

@main_bp.route('/checklists_motorista')
def lista_checklists_motorista():
    if 'motorista_id' not in session:
        return redirect(url_for('main.motorista_login'))
    
    motorista_id = session['motorista_id']
    checklists = Checklist.query.order_by(Checklist.data.desc()).all()
    
    checklists_com_status = []
    hoje = date.today()

    for checklist in checklists:
        status = "N/A"
        if checklist.tipo == 'DIÁRIO':
            preenchido_hoje = ChecklistPreenchido.query.filter(
                and_(
                    ChecklistPreenchido.motorista_id == motorista_id,
                    ChecklistPreenchido.checklist_id == checklist.id,
                    db.func.date(ChecklistPreenchido.data_preenchimento) == hoje
                )
            ).first()

            if preenchido_hoje:
                status = "Preenchido Hoje"
            else:
                status = "Pendente"
        
        checklists_com_status.append({'checklist': checklist, 'status': status})

    return render_template('motorista_lista_checklists.html', checklists_info=checklists_com_status)

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

        novo_preenchimento = ChecklistPreenchido(
            motorista_id=motorista.id,
            veiculo_id=veiculo_do_motorista.id,
            checklist_id=checklist.id
        )
        db.session.add(novo_preenchimento)
        
        sub_itens_ids = request.form.getlist('sub_item_id')
        for sub_item_id in sub_itens_ids:
            resposta = request.form.get(f'resposta-{sub_item_id}')
            observacao = request.form.get(f'obs-{sub_item_id}')

            nova_resposta = ChecklistResposta(
                preenchimento=novo_preenchimento, 
                item_id=sub_item_id,
                resposta=resposta,
                observacao=observacao
            )
            db.session.add(nova_resposta)
        
        db.session.commit()
        flash('Checklist enviado com sucesso!', 'success')
        return redirect(url_for('main.lista_checklists_motorista'))

    itens_principais = checklist.itens.filter_by(parent_id=None).order_by(ChecklistItem.ordem).all()

    return render_template(
        'motorista_preencher_checklist.html',
        checklist=checklist,
        veiculo=veiculo_do_motorista, 
        itens_principais=itens_principais
    )


# --- BLUEPRINT DA ÁREA ADMINISTRATIVA ---
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

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
def admin_logout():
    session.pop('admin_user', None)
    flash('Você saiu da área administrativa.', 'success')
    return redirect(url_for('admin.login'))

@admin_bp.route('/dashboard')
def dashboard():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))
    return render_template('adm.html')

@admin_bp.route('/acompanhamento_diario')
def acompanhamento_diario():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    hoje = date.today()
    
    checklist_diario = Checklist.query.filter_by(tipo='DIÁRIO').order_by(Checklist.data.desc()).first()

    motoristas_status = []
    motoristas_pendentes = []

    if not checklist_diario:
        flash('Nenhum checklist do tipo "DIÁRIO" foi configurado no sistema.', 'warning')
    else:
        motoristas = Motorista.query.order_by(Motorista.nome).all()
        for motorista in motoristas:
            preenchido = ChecklistPreenchido.query.filter(
                and_(
                    ChecklistPreenchido.motorista_id == motorista.id,
                    ChecklistPreenchido.checklist_id == checklist_diario.id,
                    db.func.date(ChecklistPreenchido.data_preenchimento) == hoje
                )
            ).first()
            
            status = 'Preenchido' if preenchido else 'Pendente'
            
            info = {
                'id': motorista.id,
                'nome': motorista.nome,
                'status': status
            }
            motoristas_status.append(info)
            
            if status == 'Pendente':
                motoristas_pendentes.append(info)

    return render_template(
        'admin_acompanhamento_diario.html',
        motoristas_status=motoristas_status,
        motoristas_pendentes=motoristas_pendentes,
        checklist_diario=checklist_diario,
        data_hoje=hoje
    )

@admin_bp.route('/relatorios_consolidados', methods=['GET', 'POST'])
def relatorios_consolidados():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    motoristas = Motorista.query.order_by(Motorista.nome).all()
    resultados_agrupados = None

    if request.method == 'POST':
        tipo_checklist = request.form.get('tipo_checklist')
        motorista_id = request.form.get('motorista_id')
        data_inicio_str = request.form.get('data_inicio')
        data_fim_str = request.form.get('data_fim')

        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else None
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else None

        query = ChecklistPreenchido.query.join(Checklist).join(Motorista)

        if tipo_checklist:
            query = query.filter(Checklist.tipo == tipo_checklist)
        if motorista_id and motorista_id != 'todos':
            query = query.filter(ChecklistPreenchido.motorista_id == motorista_id)
        if data_inicio:
            query = query.filter(db.func.date(ChecklistPreenchido.data_preenchimento) >= data_inicio)
        if data_fim:
            query = query.filter(db.func.date(ChecklistPreenchido.data_preenchimento) <= data_fim)

        preenchimentos = query.order_by(Motorista.nome, ChecklistPreenchido.data_preenchimento.desc()).all()

        resultados_agrupados = defaultdict(lambda: defaultdict(list))
        for p in preenchimentos:
            data = p.data_preenchimento.date()
            resultados_agrupados[p.motorista.nome][data].append(p)
            
    return render_template('admin_relatorios_consolidados.html', 
                           motoristas=motoristas,
                           resultados=resultados_agrupados,
                           filtros=request.form)

@admin_bp.route('/motoristas')
def motoristas():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))
    lista_motoristas = Motorista.query.all()
    veiculos = Veiculo.query.all()
    return render_template('motoristas.html', motoristas=lista_motoristas, veiculos=veiculos)

@admin_bp.route('/motoristas/add', methods=['POST'])
def add_motorista():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))
    nome = request.form['nome']
    cpf = request.form['cpf']
    rg = request.form['rg']
    cnh = request.form['cnh']
    frota = request.form['frota']
    veiculo_id = request.form.get('veiculo_id')

    veiculo_id = int(veiculo_id) if veiculo_id else None

    if Motorista.query.filter_by(cpf=cpf).first():
        flash(f'Motorista com CPF {cpf} já cadastrado.', 'error')
        return redirect(url_for('admin.motoristas'))

    novo_motorista = Motorista(nome=nome, cpf=cpf, rg=rg, cnh=cnh, frota=frota, veiculo_id=veiculo_id)
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
            recurso_link = os.path.join('uploads', filename).replace('\\\\', '/')

    novo_conteudo = Conteudo(data=data_obj, assunto=assunto, pergunta=pergunta, respostas=respostas, resposta_correta=resposta_correta, tipo_recurso=tipo_recurso, recurso_link=recurso_link)
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

@admin_bp.route('/checklists', methods=['GET', 'POST'])
def gerenciar_checklists():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    if request.method == 'POST':
        tipo = request.form.get('tipo')
        codigo = request.form.get('codigo')
        revisao = request.form.get('revisao')
        data_str = request.form.get('data')

        if not all([tipo, codigo, revisao, data_str]):
            flash('Todos os campos são obrigatórios para criar um checklist.', 'danger')
            return redirect(url_for('admin.gerenciar_checklists'))

        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()

        novo_checklist = Checklist(tipo=tipo, codigo=codigo, revisao=revisao, data=data_obj)
        db.session.add(novo_checklist)
        db.session.commit()
        flash(f"Checklist '{codigo}' criado com sucesso! Agora adicione os itens.", 'success')
        return redirect(url_for('admin.checklist_detalhe', checklist_id=novo_checklist.id))

    checklists = Checklist.query.order_by(Checklist.data.desc()).all()
    return render_template('admin_checklists.html', checklists=checklists)

@admin_bp.route('/checklist/<int:checklist_id>', methods=['GET', 'POST'])
def checklist_detalhe(checklist_id):
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    checklist = Checklist.query.get_or_404(checklist_id)

    if request.method == 'POST':
        parent_id = request.form.get('parent_id')
        texto = request.form.get('texto')
        ordem = request.form.get('ordem', 0, type=int)

        if not texto:
            flash('O texto do item é obrigatório.', 'danger')
        else:
            novo_item = ChecklistItem(
                checklist_id=checklist.id,
                texto=texto,
                ordem=ordem,
                parent_id=int(parent_id) if parent_id else None
            )
            db.session.add(novo_item)
            db.session.commit()
            if parent_id:
                flash('Sub-item adicionado com sucesso.', 'success')
            else:
                flash('Item principal adicionado com sucesso.', 'success')
        
        return redirect(url_for('admin.checklist_detalhe', checklist_id=checklist_id))

    itens_principais = checklist.itens.filter_by(parent_id=None).order_by(ChecklistItem.ordem).all()

    return render_template(
        'checklist_detalhe.html', 
        checklist=checklist, 
        itens_principais=itens_principais,
        ChecklistItem=ChecklistItem  # Passa a classe para o template
    )

@admin_bp.route('/checklist/item/<int:item_id>/editar', methods=['POST'])
def editar_item(item_id):
    if 'admin_user' not in session:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403

    item = ChecklistItem.query.get_or_404(item_id)
    texto = request.form.get('texto')
    ordem = request.form.get('ordem', type=int)

    if not texto:
        return jsonify({'success': False, 'message': 'O texto não pode ser vazio.'}), 400

    item.texto = texto
    item.ordem = ordem
    db.session.commit()
    
    flash(f'Item "{item.texto}" atualizado com sucesso!', 'success')
    return jsonify({'success': True})

@admin_bp.route('/checklist/item/<int:item_id>/excluir', methods=['POST'])
def excluir_item(item_id):
    if 'admin_user' not in session:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403

    item = ChecklistItem.query.get_or_404(item_id)
    checklist_id = item.checklist_id
    db.session.delete(item)
    db.session.commit()
    flash(f'Item "{item.texto}" foi excluído.', 'info')
    return redirect(url_for('admin.checklist_detalhe', checklist_id=checklist_id))


@admin_bp.route('/veiculos')
def gerenciar_veiculos():
    if 'admin_user' not in session:
        return redirect(url_for('admin.login'))

    placas = Placa.query.all()
    veiculos = Veiculo.query.all()
    
    placas_cavalo = [p for p in placas if p.tipo == 'CAVALO']
    placas_carreta = [p for p in placas if p.tipo == 'CARRETA']

    return render_template('admin_veiculos.html', 
                           placas=placas, 
                           veiculos=veiculos, 
                           placas_cavalo=placas_cavalo,
                           placas_carreta=placas_carreta)

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
