from rest_framework import viewsets
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from .models import Projeto
from .forms import ProjetoForm

# Requisições
def request_home(request):
    return render(request, 'home/home.html')


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

def projeto_dashboard(request):
    projetos = Projeto.objects.all()

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

