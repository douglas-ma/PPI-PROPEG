// const sidebar = document.getElementById('sidebar');
// const toggleBtn = document.getElementById('toggle-btn');

// toggleBtn.addEventListener('click', () => {
//     sidebar.classList.toggle('collapsed');
// });

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