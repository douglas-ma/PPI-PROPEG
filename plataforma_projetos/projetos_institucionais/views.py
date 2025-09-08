from rest_framework import viewsets
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Projeto
from .forms import ProjetoForm
import re

# Requisições
def request_home(request):
    return render(request, 'home/home.html')

def login_coordenador_view(request):
    if request.method == 'POST':
        cpf = request.POST.get('cpf')
        senha = request.POST.get('senha')

        if not cpf or not senha:
            messages.error(request, 'Preencha os campos obrigatórios.')
            return render(request, 'login/login.html', {'tipo_usuario': 'Coordenador'})
        
        cpf_limpo = re.sub(r'[^0-9]', cpf)

        user = authenticate(request, cpf=cpf_limpo, password=senha)

        if user is not None:
            if user.perfil == 'coordenador':
                login(request, user)
                return redirect('projeto_dashboard')
            else:
                messages.error(request, 'Acesso permitido somente para coordenadores.')
        else:
            messages.error(request, 'CPF ou senha inválidos.')
    return render(request, 'login/login.html', {'tipo_usuario': 'Coordenador'})

# CRUDS
# Projeto
def projeto_listar(request):
    projetos = Projeto.objects.all()
    return render(request, 'projetos_institucionais/projeto_listar.html', {'projetos': projetos})

def projeto_detalhe(request, pk):
    projetos = get_object_or_404(Projeto, pk=pk)
    return render(request, 'projetos_institucionais/projeto_listar.html', {'projetos': projetos})

def projeto_criar(request):
    if request.method == 'POST':
        form = ProjetoForm(request.POST)
        if form.is_valid():
            projeto = form.save(commit=False)
            projeto.coordenador = request.user
            projeto.save()
            form.save_m2m()
            return redirect('projeto_detalhe', pk=projeto.pk)
    else:
        form = ProjetoForm()
    return render(request, 'projetos_institucionais/projeto_form.html', {'form': form})

def projeto_editar(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if request.method == 'POST':
        form = ProjetoForm(request.POST, instance=projeto)
        if form.is_valid():
            form.save()
            return redirect('projeto_detalhe', pk=projeto.pk)
    else:
        form = ProjetoForm(instance=projeto)
    return render(request, 'projetos_institucionais/projeto_form.html', {'form': form})

def projeto_deletar(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if request.method == 'POST':
        projeto.delete()
        return redirect('projeto_listar')
    return render(request, 'projetos_institucionais/projeto_confirmar_delete.html', {'projeto': projeto})

@login_required
def projeto_dashboard(request):
    projetos = Projeto.objects.filter(coordenador=request.user)

    projetos_em_andamento = projetos.filter(status='em_andamento')
    projetos_em_revisao = projetos.filter(Q(status='submetido') | Q(status='aguardando_conselho'))
    projetos_arquivados = projetos.filter(Q(status='encerrado') | Q(status='reprovado'))

    contexto = {
        'projetos_em_andamento': projetos_em_andamento,
        'projetos_em_revisao': projetos_em_revisao,
        'projetos_arquivados': projetos_arquivados,
    }
    return render(request, 'projetos_institucionais/meusprojetos.html', contexto)

# Criar as outras aqui depois

