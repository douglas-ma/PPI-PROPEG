from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import PerfilUsuarioForm, EnderecoForm, RegistroUsuarioForm
from projetos_institucionais.forms import CoordenadorProfileForm, AlunoProfileForm
import re

def login_view(request):
    if request.method == 'POST':
        cpf = request.POST.get('cpf')
        senha = request.POST.get('senha')

        if not cpf or not senha:
            messages.error(request, 'CPF e senha são obrigatórios.')
            return render(request, 'login/login.html')
        
        cpf_limpo = re.sub(r'[^0-9]', '', cpf)
        
        user = authenticate(request, cpf=cpf_limpo, password=senha)

        if user is not None:
            if user.is_active:
                login(request, user)
                if user.perfil == 'gestor':
                    return redirect('tela_principal')
                elif user.perfil == 'coordenador':
                    return redirect('tela_principal')
                else:
                    return redirect('tela_principal')
            else:
                messages.warning(request, f'Sua conta ainda está em análise e aguarda aprovação.')
        else:
            messages.error(request, 'CPF ou senha inválidos.')
    return render(request, 'login/login.html')

def logout_view(request):
    logout(request)
    return redirect('home')

def esqueceu_senha(request):
    return render(request, 'login/esqueceusenha.html')

def registro_view(request):
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            return render(request, 'login/registro_analise.html')
    
    else:
        form = RegistroUsuarioForm()
    
    contexto = {
        'form': form
    }
    return render(request, 'login/registrar.html', contexto)

@login_required
def perfil_view(request):
    contexto = {
        'usuario': request.user
    }
    return render(request, 'login/perfilusuario.html', contexto)

@login_required
def perfil_editar_view(request):
    user = request.user
    user_form_class = None

    if user.perfil == 'coordenador':
        user_form_class = CoordenadorProfileForm
    elif user.perfil == 'aluno':
        user_form_class = AlunoProfileForm
    else:
        messages.info(request, 'Seu perfil é gerenciado pelo sistema.')
        return redirect('perfil')

    endereco_instance = user.endereco if hasattr(user, 'endereco') else None

    if request.method == 'POST':
        user_form = user_form_class(request.POST, instance=user)
        endereco_form = EnderecoForm(request.POST, instance=endereco_instance)
        
        if user_form.is_valid() and endereco_form.is_valid():
            endereco = endereco_form.save()
            usuario = user_form.save(commit=False)
            usuario.endereco = endereco
            usuario.save()

            messages.success(request, 'Seu perfil foi atualizado com sucesso!')
            return redirect('perfil')
    else:
        user_form = user_form_class(instance=user)
        endereco_form = EnderecoForm(instance=endereco_instance)

    contexto = {
        'user_form': user_form,
        'endereco_form': endereco_form,
    }
    return render(request, 'login/perfileditar.html', contexto)

@login_required
def endereco_editar_view(request):
    try:
        endereco_instance = request.user.endereco
    except AttributeError:
        endereco_instance = None
    
    if request.method == 'POST':
        form = EnderecoForm(request.POST, instance=endereco_instance)
        if form.is_valid():
            endereco = form.save()
            request.user.endereco = endereco
            request.user.save()

            messages.success(request, 'Endereço atualizado com sucesso!')
            return redirect('perfil')
    else:
        form = EnderecoForm(instance=endereco_instance)
    
    contexto = {
        'form': form
    }
    return render(request, 'login/perfilendereco.html', contexto)
