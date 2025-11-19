document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('checklist-form');
    if (!form) return;

    // --- INICIALIZAÇÃO DO MODAL E ASSINATURAS ---
    const signatureModalEl = document.getElementById('signature-modal');
    const signatureModal = bootstrap.Modal.getOrCreateInstance(signatureModalEl);
    
    const canvasMotorista = document.getElementById('signature-canvas-motorista');
    const canvasResponsavel = document.getElementById('signature-canvas-responsavel');
    
    const signaturePadMotorista = new SignaturePad(canvasMotorista);
    const signaturePadResponsavel = new SignaturePad(canvasResponsavel);

    // --- FUNÇÕES E EVENTOS DO MODAL (VERSÃO FINAL E CORRIGIDA) ---

    // Função para carregar assinaturas existentes nos pads quando o modal é aberto
    function loadSignatures() {
        signaturePadMotorista.clear();
        const motoristaData = document.getElementById('assinatura_motorista_input').value;
        if (motoristaData) {
            signaturePadMotorista.fromDataURL(motoristaData);
        }
        
        signaturePadResponsavel.clear();
        const responsavelData = document.getElementById('assinatura_responsavel_input').value;
        if (responsavelData) {
            signaturePadResponsavel.fromDataURL(responsavelData);
        }
    }

    // Aciona o carregamento das assinaturas quando o modal é aberto
    signatureModalEl.addEventListener('shown.bs.modal', loadSignatures);

    // Botão de SALVAR do modal
    document.getElementById('signature-modal-save').addEventListener('click', function () {
        if (signaturePadMotorista.isEmpty()) {
            alert('A assinatura do motorista é obrigatória.');
            return;
        }

        // Salva os dados da assinatura na página principal
        const motoristaDataURL = signaturePadMotorista.toDataURL('image/png');
        document.getElementById('assinatura_motorista_input').value = motoristaDataURL;
        document.getElementById('signature-motorista-img').src = motoristaDataURL;
        document.getElementById('signature-motorista-img').style.display = 'block';
        document.getElementById('signature-motorista-text').style.display = 'none';
        document.getElementById('signature-motorista-display').classList.remove('is-invalid');

        if (!signaturePadResponsavel.isEmpty()) {
            const responsavelDataURL = signaturePadResponsavel.toDataURL('image/png');
            document.getElementById('assinatura_responsavel_input').value = responsavelDataURL;
            document.getElementById('signature-responsavel-img').src = responsavelDataURL;
            document.getElementById('signature-responsavel-img').style.display = 'block';
            document.getElementById('signature-responsavel-text').style.display = 'none';
        } else {
            document.getElementById('assinatura_responsavel_input').value = '';
            document.getElementById('signature-responsavel-img').src = '';
            document.getElementById('signature-responsavel-img').style.display = 'none';
            document.getElementById('signature-responsavel-text').style.display = 'block';
        }
        
        // Apenas esconde o modal. O evento 'hidden.bs.modal' cuidará do resto.
        signatureModal.hide();
    });

    // Botões que apenas fecham o modal
    document.getElementById('modal-cancel-btn').addEventListener('click', () => signatureModal.hide());
    document.getElementById('modal-close-x').addEventListener('click', () => signatureModal.hide());

    // ***** A SOLUÇÃO DEFINITIVA PARA A TELA TRAVADA *****
    // Este evento é disparado pelo Bootstrap APÓS o modal ter sido completamente escondido
    signatureModalEl.addEventListener('hidden.bs.modal', function (event) {
        // Este código de limpeza agora só roda no momento certo.
        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) {
            backdrop.remove();
        }
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    });

    // Botões de limpar assinaturas dentro do modal
    document.getElementById('clear-motorista').addEventListener('click', () => signaturePadMotorista.clear());
    document.getElementById('clear-responsavel').addEventListener('click', () => signaturePadResponsavel.clear());

    // --- VALIDAÇÃO DO FORMULÁRIO E MÁSCARAS (Sem alterações) ---

    document.querySelectorAll('.date-mask').forEach(input => {
        input.addEventListener('input', e => {
            let v = e.target.value.toUpperCase();
            if ('N/A'.startsWith(v)) { e.target.value = 'N/A'; return; }
            v = v.replace(/\D/g, '');
            v = v.replace(/(\d{2})(\d)/, '$1/$2');
            v = v.replace(/(\d{2})\/(\d{2})(\d)/, '$1/$2/$3');
            e.target.value = v.slice(0, 10);
        });
    });

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        let primeiroItemInvalido = null;
        let isValid = true;

        document.querySelectorAll('.sub-item, .single-item').forEach(item => {
            const radios = item.querySelectorAll('input[type="radio"]');
            if (!Array.from(radios).some(radio => radio.checked)) {
                isValid = false;
                item.classList.add('is-invalid');
                if (!primeiroItemInvalido) primeiroItemInvalido = item;
            }
        });

        document.querySelectorAll('.extintor-required').forEach(input => {
            if (!input.value.trim()) {
                isValid = false;
                input.classList.add('is-invalid');
                if (!primeiroItemInvalido) primeiroItemInvalido = input;
            }
        });

        if (!document.getElementById('assinatura_motorista_input').value) {
            isValid = false;
            const placeholder = document.getElementById('signature-motorista-display');
            placeholder.classList.add('is-invalid');
            if (!primeiroItemInvalido) primeiroItemInvalido = placeholder;
        }

        if (!isValid) {
            alert('Por favor, preencha todos os campos obrigatórios em vermelho.');
            if (primeiroItemInvalido) {
                primeiroItemInvalido.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            return;
        }

        document.getElementById('data_preenchimento_local_input').value = new Date().toISOString();
        form.submit();
    });
});