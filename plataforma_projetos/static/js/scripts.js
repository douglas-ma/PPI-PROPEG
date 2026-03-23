document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss para todos os alertas com a classe alert-dismissible
    document.querySelectorAll('.alert.alert-dismissible.fade.show').forEach(function (alertEl) {
        setTimeout(function () {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alertEl);
            if (bsAlert) bsAlert.close();
        }, 5000); // 5 segundos
    });
});

// Garante que o script rode após o carregamento da página
document.addEventListener('DOMContentLoaded', function() {

    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggle-btn');

    if (sidebar && toggleBtn) {
        // Restaura o estado salvo ao carregar a página
        if (localStorage.getItem('sidebarCollapsed') === 'true') {
            sidebar.classList.add('collapsed');
        }

        toggleBtn.addEventListener('click', function (event) {
            event.preventDefault();
            sidebar.classList.toggle('collapsed');
            // Persiste o estado atual
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
        });
    }

});

document.addEventListener("DOMContentLoaded", function () {
    
    function setupPasswordToggle(inputId, buttonId) {
        const passwordInput = document.getElementById(inputId);
        const toggleButton = document.getElementById(buttonId);

        if (passwordInput && toggleButton) {
            const eyeIcon = toggleButton.querySelector("i");
            toggleButton.addEventListener("click", function () {
                const type = passwordInput.getAttribute("type") === "password" ? "text" : "password";
                passwordInput.setAttribute("type", type);
                
                if (type === "password") {
                    eyeIcon.classList.remove("bi-eye-slash-fill");
                    eyeIcon.classList.add("bi-eye-fill");
                } else {
                    eyeIcon.classList.remove("bi-eye-fill");
                    eyeIcon.classList.add("bi-eye-slash-fill");
                }
            });
        }
    }

    setupPasswordToggle('senha', 'toggleSenha');
    setupPasswordToggle('id_password', 'toggleSenha');
    setupPasswordToggle('id_password2', 'toggleSenha2');


    const cpfInputLogin = document.getElementById("cpf");
    const cpfInputRegistro = document.getElementById("id_cpf");
    const cpfInput = cpfInputLogin || cpfInputRegistro;

    if (cpfInput) {
        cpfInput.setAttribute('maxlength', '14');
        cpfInput.addEventListener("input", function (e) {
            let value = cpfInput.value.replace(/\D/g, "");
            value = value.substring(0, 11);
            value = value.replace(/(\d{3})(\d)/, "$1.$2");
            value = value.replace(/(\d{3})(\d)/, "$1.$2");
            value = value.replace(/(\d{3})(\d{1,2})$/, "$1-$2");
            cpfInput.value = value;
        });
    }

    // Máscara SIAPE — apenas números, máximo 7 dígitos
    var siapeInput = document.getElementById('id_siape') || document.querySelector('[name="siape"]');
    if (siapeInput) {
        siapeInput.setAttribute('maxlength', '7');
        siapeInput.addEventListener('input', function () {
            this.value = this.value.replace(/\D/g, '').substring(0, 7);
        });
    }

    // Matrícula — apenas números, máximo 15 dígitos
    var matriculaInput = document.getElementById('id_matricula') || document.querySelector('[name="matricula"]');
    if (matriculaInput) {
        matriculaInput.setAttribute('maxlength', '15');
        matriculaInput.addEventListener('input', function () {
            this.value = this.value.replace(/\D/g, '').substring(0, 15);
        });
    }

    // Estado / UF — apenas letras, máximo 2, maiúsculas
    var estadoInput = document.getElementById('id_estado') || document.querySelector('[name="estado"]');
    if (estadoInput) {
        estadoInput.setAttribute('maxlength', '2');
        estadoInput.setAttribute('style', (estadoInput.getAttribute('style') || '') + ';text-transform:uppercase;');
        estadoInput.addEventListener('input', function () {
            this.value = this.value.replace(/[^a-zA-Z]/g, '').substring(0, 2).toUpperCase();
        });
    }

});

// Interatividade para o forms de criar projetos
document.addEventListener('DOMContentLoaded', function() {
    const formsetContainer = document.getElementById('equipe-formset-container');
    if (!formsetContainer) return;

    const addFormBtn = document.getElementById('add-form-btn');
    const totalFormsInput = document.querySelector('input[name="form-TOTAL_FORMS"]'); // Seletor mais robusto
    const emptyFormTemplate = document.getElementById('empty-form-template').querySelector('tr');

    // --- LÓGICA PARA ADICIONAR ---
    addFormBtn.addEventListener('click', function() {
        let formNum = parseInt(totalFormsInput.value);
        const newFormRow = emptyFormTemplate.cloneNode(true);

        newFormRow.innerHTML = newFormRow.innerHTML.replace(/__prefix__/g, formNum);
        formsetContainer.appendChild(newFormRow);
        totalFormsInput.value = formNum + 1;
    });

    // --- LÓGICA PARA REMOVER ---
    formsetContainer.addEventListener('click', function(event) {
        if (event.target && event.target.classList.contains('remove-form-row-btn')) {
            const rowToRemove = event.target.closest('.equipe-form-row');
            const deleteInput = rowToRemove.querySelector('input[type="checkbox"][name$="-DELETE"]');

            if (deleteInput) {
                deleteInput.checked = true;
                rowToRemove.style.display = 'none';
            } else {
                rowToRemove.remove();
                totalFormsInput.value = parseInt(totalFormsInput.value) - 1;
            }
        }
    });
});

document.addEventListener('DOMContentLoaded', function () {
    const confirmationModal = document.getElementById('confirmationModal');
    if (confirmationModal) {
        confirmationModal.addEventListener('show.bs.modal', function (event) {
            // Botão que acionou o modal
            const button = event.relatedTarget;

            // Extrai informações dos atributos data-*
            const actionTitle = button.getAttribute('data-action-title');
            const projetoTitulo = button.getAttribute('data-projeto-titulo');
            const actionUrl = button.getAttribute('href');

            // Atualiza o conteúdo do modal
            const modalTitle = confirmationModal.querySelector('.modal-title');
            const modalBody = confirmationModal.querySelector('.modal-body');
            const confirmBtn = confirmationModal.querySelector('#confirmActionBtn');

            modalTitle.textContent = actionTitle;
            modalBody.textContent = 'Você tem certeza que deseja ' + actionTitle.toLowerCase() + ' o projeto "' + projetoTitulo + '"?';
            confirmBtn.href = actionUrl;

            // Muda a cor do botão de confirmação
            if (actionTitle.includes('Aprovar')) {
                confirmBtn.className = 'btn btn-success';
            } else {
                confirmBtn.className = 'btn btn-danger';
            }
        });
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const odsGrid = document.getElementById('ods-selection-grid');
    const odsCounter = document.getElementById('ods-counter');
    if (odsGrid) {
        const checkboxes = odsGrid.querySelectorAll('input[type="checkbox"]');

            function updateCounter() {
                const selectedCount = odsGrid.querySelectorAll('input[type="checkbox"]:checked').length;
                odsCounter.textContent = selectedCount;
            }

            checkboxes.forEach(checkbox => {
                checkbox.addEventListener('change', updateCounter);
            });
            updateCounter();
    }

    const addFormBtn = document.getElementById('add-form-btn');
    const formsetContainer = document.getElementById('equipe-formset-container');
    const emptyFormTemplate = document.getElementById('empty-form-template').innerHTML;
    const totalFormsInput = document.querySelector('#id_form-TOTAL_FORMS');

    if (formsetContainer){
        if (addFormBtn) {
            addFormBtn.addEventListener('click', function() {
                let currentFormCount = formsetContainer.children.length;
                let newFormHtml = emptyFormTemplate.replace(/__prefix__/g, currentFormCount);
                
                formsetContainer.insertAdjacentHTML('beforeend', newFormHtml);
                totalFormsInput.value = currentFormCount + 1;
            });
        }

        formsetContainer.addEventListener('click', function(e) {
            if (e.target && e.target.classList.contains('remove-form-row-btn')) {
                const formRow = e.target.closest('.equipe-form-row');
                const deleteCheckbox = formRow.querySelector('input[type="checkbox"][name$="-DELETE"]');
                if (deleteCheckbox) {
                    deleteCheckbox.checked = true;
                }
                formRow.style.display = 'none';
            }
        });
    }
});

document.addEventListener('DOMContentLoaded', function () {

    /**
     * Função reutilizável para configurar um campo condicional.
     * @param {string} triggerName - O 'name' do campo de rádio que dispara a ação (ex: '1-etica_obrigatoria').
     * @param {string} targetId - O 'id' do DIV que envolve o campo a ser mostrado/escondido (ex: 'div_id_1-tipo_etica').
     * @param {string} showValue - O valor do rádio que deve mostrar o campo (geralmente 'True' para 'Sim').
     */
    function setupConditionalField(triggerName, targetId, showValue) {
            // O ID gerado pelo Crispy Forms geralmente é 'div_id_PREFIXO-NOME_DO_CAMPO'
        const targetElement = document.getElementById(`div_id_${targetId}`);
        const triggerRadios = document.querySelectorAll(`input[name="${triggerName}"]`);

        if (!targetElement || triggerRadios.length === 0) {
            // Se não encontrar, tenta sem o prefixo 'div_id_'
            const fallbackTarget = document.getElementById(targetId);
            if (!fallbackTarget) return; // Se ainda não encontrar, desiste
            targetElement = fallbackTarget;
        }

        function updateVisibility() {
            const selectedRadio = document.querySelector(`input[name="${triggerName}"]:checked`);
            // Se nenhum rádio estiver selecionado, esconde o campo
            if (!selectedRadio) {
                targetElement.style.display = 'none';
                return;
            }
            
            if (selectedRadio.value === showValue) {
                targetElement.style.display = 'block';
            } else {
                targetElement.style.display = 'none';
            }
        }

        triggerRadios.forEach(radio => {
            radio.addEventListener('change', updateVisibility);
        });
        
        // Força a atualização da visibilidade no carregamento da página
        updateVisibility();
    }

    // O prefixo '1-' é adicionado pelo form wizard
    setupConditionalField('1-etica_obrigatoria', '1-tipo_etica', 'True');
    setupConditionalField('1-participa_pos_graduacao', '1-programa_pos', 'True');
});