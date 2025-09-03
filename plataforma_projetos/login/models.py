from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model

User = get_user_model()

def login_view(request, tipo_usuario):
    if request.method == "POST":
        cpf = request.POST.get("cpf", "").replace(".", "").replace("-", "")  # remove máscara
        senha = request.POST.get("senha")

        try:
            user = User.objects.get(cpf=cpf)
        except User.DoesNotExist:
            messages.error(request, "CPF não encontrado.")
            return render(request, "login.html", {"tipo_usuario": tipo_usuario.capitalize()})

        # autenticação normal pelo Django
        user = authenticate(request, username=user.username, password=senha)
        if user is not None:
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Senha incorreta.")

    return render(request, "login.html", {"tipo_usuario": tipo_usuario.capitalize()})
