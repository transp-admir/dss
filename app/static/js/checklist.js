document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('checklist-form');
    if (!form) return;

    // --- INICIALIZAÇÃO DO MODAL E ASSINATURAS (sem alterações) ---
    const signatureModalEl = document.getElementById('signature-modal');
    const signatureModal = bootstrap.Modal.getOrCreateInstance(signatureModalEl);
    
    const canvasMotorista = document.getElementById('signature-canvas-motorista');
    const canvasResponsavel = document.getElementById('signature-canvas-responsavel');
    
    const signaturePadMotorista = new SignaturePad(canvasMotorista);
    const signaturePadResponsavel = new SignaturePad(canvasResponsavel);

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

    signatureModalEl.addEventListener('shown.bs.modal', loadSignatures);

    document.getElementById('signature-modal-save').addEventListener('click', function () {
        if (signaturePadMotorista.isEmpty()) {
            alert('A assinatura do motorista é obrigatória.');
            return;
        }

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
        
        signatureModal.hide();
    });

    document.getElementById('modal-cancel-btn').addEventListener('click', () => signatureModal.hide());
    document.getElementById('modal-close-x').addEventListener('click', () => signatureModal.hide());

    signatureModalEl.addEventListener('hidden.bs.modal', function (event) {
        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) {
            backdrop.remove();
        }
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    });

    document.getElementById('clear-motorista').addEventListener('click', () => signaturePadMotorista.clear());
    document.getElementById('clear-responsavel').addEventListener('click', () => signaturePadResponsavel.clear());

    // --- VALIDAÇÃO E ENVIO DO FORMULÁRIO (COM A NOVA LÓGICA) ---

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
        // --- INÍCIO DA CORREÇÃO ---
        const submitButton = form.querySelector('button[type="submit"]');

        // Previne o envio padrão para fazermos a validação e desabilitar o botão
        event.preventDefault();

        // Se o botão já estiver desabilitado, impede um novo envio
        if (submitButton && submitButton.disabled) {
            return;
        }
        // --- FIM DA CORREÇÃO ---

        document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        let primeiroItemInvalido = null;
        let isValid = true;

        // Validação dos itens do checklist
        document.querySelectorAll('.sub-item, .single-item').forEach(item => {
            const radios = item.querySelectorAll('input[type="radio"]');
            if (!Array.from(radios).some(radio => radio.checked)) {
                isValid = false;
                item.classList.add('is-invalid');
                if (!primeiroItemInvalido) primeiroItemInvalido = item;
            }
        });

        // Validação dos extintores
        document.querySelectorAll('.extintor-required').forEach(input => {
            if (!input.value.trim()) {
                isValid = false;
                input.classList.add('is-invalid');
                if (!primeiroItemInvalido) primeiroItemInvalido = input;
            }
        });

        // Validação da assinatura do motorista
        if (!document.getElementById('assinatura_motorista_input').value) {
            isValid = false;
            const placeholder = document.getElementById('signature-motorista-display');
            placeholder.classList.add('is-invalid');
            if (!primeiroItemInvalido) primeiroItemInvalido = placeholder;
        }

        // Se a validação falhar, mostra alerta e para a execução
        if (!isValid) {
            alert('Por favor, preencha todos os campos obrigatórios em vermelho.');
            if (primeiroItemInvalido) {
                primeiroItemInvalido.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            return;
        }

        // --- INÍCIO DA CORREÇÃO ---
        // Se a validação passou, desabilita o botão para evitar clique duplo
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = `
                <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                Enviando...
            `;
        }
        // --- FIM DA CORREÇÃO ---

        // Preenche a data e envia o formulário programaticamente
        document.getElementById('data_preenchimento_local_input').value = new Date().toISOString();
        form.submit();
    });
});
