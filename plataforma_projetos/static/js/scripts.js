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