// Garante que o script rode após o carregamento da página
document.addEventListener('DOMContentLoaded', function() {

    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggle-btn');

    // Verifica se os elementos existem antes de adicionar o evento
    if (sidebar && toggleBtn) {
        toggleBtn.addEventListener('click', function (event) {
            // Previne o comportamento padrão do link (que é navegar para '#')
            event.preventDefault();
            
            // Adiciona ou remove a classe 'collapsed' da sidebar
            sidebar.classList.toggle('collapsed');
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
        cpfInput.addEventListener("input", function (e) {
            let value = cpfInput.value.replace(/\D/g, "");
            value = value.substring(0, 11);
            value = value.replace(/(\d{3})(\d)/, "$1.$2");
            value = value.replace(/(\d{3})(\d)/, "$1.$2");
            value = value.replace(/(\d{3})(\d{1,2})$/, "$1-$2");
            cpfInput.value = value;
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