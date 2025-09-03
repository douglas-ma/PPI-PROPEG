from django.shortcuts import render
from django.http import HttpResponse

def login_view(request, tipo_usuario):
    contexto = {
        "tipo_usuario": tipo_usuario.capitalize()
    }
    return render(request, 'login/login.html', contexto)

def esqueceu_senha(request):
    return render(request, 'login/esqueceusenha.html')

def registrar(request):
    if request.method == "POST":
        # Aqui você pode tratar o formulário futuramente
        nome = request.POST.get("nome")
        sobrenome = request.POST.get("sobrenome")
        email = request.POST.get("email")
        senha = request.POST.get("senha")
        tipo_usuario = request.POST.get("tipo_usuario")

        # Exemplo: salvar no banco depois de implementar models
        print(nome, sobrenome, email, senha, tipo_usuario)

    return render(request, "login/registro.html")