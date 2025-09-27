from rest_framework import viewsets
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from django.db import transaction
from django.db.models import Q, ProtectedError
from .models import Projeto
from .forms import *
from login.forms import *
from .decorators import gestor_required, coordenador_required, aluno_required
from formtools.wizard.views import SessionWizardView
import re
import datetime

ETAPAS_NOMES = [
    ("0", "Tipo de Projeto"),
    ("1", "Informações Gerais"),
    ("2", "Detalhes do Projeto"),
    ("3", "Equipe de Trabalho"),
    ("4", "Vínculo com ODS"),
    ("5", "Revisão e Submissão"),
]

# Requisições
def request_home(request):
    return render(request, 'home/home.html')

# Projeto
class ProjetoCreateWizard(SessionWizardView):
    template_name = 'projetos_institucionais/projeto_wizard_form.html'

    form_list = [
        ('0', Etapa1_TipoFinanciamentoForm),
        ('1', Etapa2_InfoGeraisForm),
        ('2', Etapa3_DetalhesProjetoForm),
        ('3', EquipeProjetoFormSet),
        ('4', Etapa5_ODSForm),
        ('5', Etapa6_RevisaoForm),
    ]

    def get_template_names(self):
        if self.steps.current == '5':
            return 'projetos_institucionais/projeto_wizard_review.html'
        return 'projetos_institucionais/projeto_wizard_form.html'

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        context['etapas_nomes'] = ETAPAS_NOMES

        if self.steps.current == '5':
            context['todos_os_dados'] = self.get_all_cleaned_data()
            context['formset_equipe'] = self.get_cleaned_data_for_step('3')
            ods_data = self.get_cleaned_data_for_step('4')
            context['ods_selecionados'] = ods_data.get('ods') if ods_data else []

        return context

    def get_form(self, step=None, data=None, files=None):
        form = super().get_form(step, data, files)
        
        if step is None:
            step = self.steps.current
        
        try:
            step_title = ETAPAS_NOMES[int(step)][1]
        except (IndexError, ValueError):
            step_title = f"Etapa {int(step) + 1}"
        
        form.step_title = step_title
        return form

    def get_form_initial(self, step):
        initial = super().get_form_initial(step)
        if step == '1':
            user = self.request.user
            initial.update({
                'eh_docente': getattr(user, 'eh_docente', False),
                'eh_pesquisador': getattr(user, 'eh_pesquisador', False),
            })
        return initial
    
    def get_form_instance(self, step):
        projeto_id = self.storage.extra_data.get('projeto_id', None)
        if projeto_id:
            return Projeto.objects.get(pk=projeto_id)
        
        instance = Projeto.objects.create(coordenador=self.request.user, status='rascunho')
        self.storage.extra_data['projeto_id'] = instance.id
        return instance
    
    def process_step(self, form):
        projeto = self.get_form_instance(self.steps.current)

        if self.steps.current in ['1', '2']:
            form.instance = projeto
            form.save()
        elif self.steps.current == '3':
            if form.is_valid():
                instances = form.save(commit=False)
                for obj in instances:
                    obj.projeto = projeto
                    obj.save()
                for obj in form.deleted_objects:
                    obj.delete()
        elif self.steps.current == '4':
            if form.is_valid():
                ods_selecionados = form.cleaned_data.get('ods')
                if ods_selecionados:
                    projeto.ods.set(ods_selecionados)

        return self.get_form_step_data(form)

    @transaction.atomic
    def done(self, form_list, form_dict, **kwargs):
        projeto_id = self.storage.extra_data.get('projeto_id')
        projeto = Projeto.objects.get(pk=projeto_id)

        dados_etapa2 = form_dict.get('1', {}).cleaned_data
        dados_etapa3 = form_dict.get('2', {}).cleaned_data
        dados_etapa5 = form_dict.get('4', {}).cleaned_data

        grupos_pesquisa_data = dados_etapa2.pop('grupos_pesquisa', None)
        ods_data = dados_etapa5.get('ods')

        for campo, valor in {**dados_etapa2, **dados_etapa3}.items():
            setattr(projeto, campo, valor)
        
        projeto.status = 'submetido'
        projeto.save()

        if grupos_pesquisa_data:
            projeto.grupos_pesquisa.set(grupos_pesquisa_data)
        if ods_data:
            projeto.ods.set(ods_data)

        dados_equipe = form_dict['3'].cleaned_data
        
        projeto.equipe.all().delete()
        
        for membro_data in dados_equipe:
            if membro_data and membro_data.get('membro'):
                EquipeProjeto.objects.create(
                    projeto=projeto,
                    membro=membro_data.get('membro'),
                    carga_horaria_semanal=membro_data.get('carga_horaria_semanal'),
                    carga_horaria_total=membro_data.get('carga_horaria_total')
                )

        if 'projeto_id' in self.storage.extra_data:
            del self.storage.extra_data['projeto_id']

        return render(self.request, 'projetos_institucionais/projeto_wizard_done.html', {
            'projeto': projeto
        })

@login_required
def tela_principal(request):
    user = request.user
    contexto = {}

    hora_atual = datetime.datetime.now().hour
    if 5 <= hora_atual < 12:
        saudacao = "Bom dia"
    elif 12 <= hora_atual < 18:
        saudacao = "Boa tarde"
    else:
        saudacao = "Boa noite"
    
    contexto['saudacao'] = saudacao

    if user.perfil == 'gestor':
        contexto['usuarios_pendentes'] = Usuario.objects.filter(is_active=False, status='pendente').count()
        contexto['projetos_pendentes'] = Projeto.objects.filter(status='submetido').count()

    elif user.perfil == 'coordenador':
        projetos_do_coordenador = Projeto.objects.filter(coordenador=user)
        contexto['projetos_em_andamento'] = projetos_do_coordenador.filter(status='em_andamento').count()
        contexto['projetos_em_revisao'] = projetos_do_coordenador.filter(status='submetido').count()

    elif user.perfil == 'aluno':
        contexto['projetos_participando'] = EquipeProjeto.objects.filter(membro=user).count()
        contexto['endereco_preenchido'] = hasattr(user, 'endereco') and user.endereco is not None

    return render(request, 'projetos_institucionais/tela_principal.html', contexto)

def projeto_listar(request):
    projetos = Projeto.objects.all()
    return render(request, 'projetos_institucionais/projeto_listar.html', {'projeto': projetos})

def projeto_detalhe(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    comprovante = projeto.anexos.filter(tipo_anexo='comprovante_aprovacao').first()
    outros_anexos = projeto.anexos.exclude(tipo_anexo='comprovante_aprovacao')

    contexto = {
        'projeto': projeto,
        'comprovante': comprovante,
        'outros_anexos': outros_anexos,
    }

    return render(request, 'projetos_institucionais/projeto_detalhe.html', contexto)

def projeto_editar(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    # if request.method == 'POST':
    #     form = ProjetoForm(request.POST, instance=projeto)
    #     if form.is_valid():
    #         form.save()
    #         return redirect('projeto_detalhe', pk=projeto.pk)
    # else:
    #     form = ProjetoForm(instance=projeto)
    return render(request, 'projetos_institucionais/projeto_form.html')

def projeto_deletar(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if request.method == 'POST':
        projeto.delete()
        return redirect('projeto_listar')
    return render(request, 'projetos_institucionais/projeto_confirmar_delete.html', {'projeto': projeto})

@login_required
@coordenador_required
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

@login_required
@aluno_required
def aluno_projeto_dashboard(request):
    participacoes = EquipeProjeto.objects.filter(membro=request.user).select_related('projeto', 'projeto__coordenador')

    contexto = {
        'participacoes': participacoes,
    }

    return render(request, 'projetos_institucionais/aluno_projeto_dashboard.html', contexto)

@gestor_required
def gestor_dashboard(request):
    projetos_pendentes = Projeto.objects.filter(status='submetido').order_by('data_inicio')
    
    contexto = {
        'projetos_pendentes': projetos_pendentes
    }
    return render(request, 'projetos_institucionais/gestordashboard.html', contexto)

@gestor_required
def aprovar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    projeto.status = 'em_andamento'
    projeto.save()

    send_mail(
        subject=f'Seu projeto "{projeto.titulo}" foi APROVADO!',
        message=f'Olá, {projeto.coordenador.first_name}!\n\nTemos boas notícias: seu projeto "{projeto.titulo}" foi aprovado e agora está em andamento. Você pode acessar o sistema para mais detalhes.\n\nAtenciosamente,\nEquipe PROPEG',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[projeto.coordenador.email],
    )

    messages.success(request, f'O projeto "{projeto.titulo}" aprovado com sucesso.')
    return redirect('gestor_dashboard')
    
@gestor_required
def reprovar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    projeto.status = 'reprovado'
    projeto.save()

    send_mail(
        subject=f'Atualização sobre seu projeto "{projeto.titulo}"',
        message=f'Olá, {projeto.coordenador.first_name}.\n\nApós análise, o projeto "{projeto.titulo}" foi reprovado. Para mais informações, por favor, entre em contato com a equipe responsável.\n\nAtenciosamente,\nEquipe PROPEG',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[projeto.coordenador.email],
    )

    messages.error(request, f'O projeto "{projeto.titulo}" reprovado.')
    return redirect('gestor_dashboard')

@gestor_required
def anexar_comprovante(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    if request.method == 'POST':
        form = AnexoComprovanteForm(request.POST, request.FILES)
        if form.is_valid():
            anexo = form.save(commit=False)
            anexo.projeto = projeto
            anexo.tipo_anexo = 'comprovante_aprovacao'
            anexo.save()
            messages.success(request, f'Comprovante anexado com sucesso ao projeto "{projeto.titulo}".')
            return redirect('gestor_dashboard')
    else:
        form = AnexoComprovanteForm()
    
    contexto = {
        'form': form,
        'projeto': projeto,
    }
    return render(request, 'projetos_institucionais/anexar_comprovante.html', contexto)

@gestor_required
def gerenciar_usuarios(request):
    queryset = Usuario.objects.exclude(pk=request.user.pk).order_by('first_name')
    
    query = request.GET.get('q', '')
    if query:
        queryset = queryset.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(cpf__icontains=query)
        )

    perfil_filter = request.GET.get('perfil', '')
    if perfil_filter in ['aluno', 'coordenador', 'gestor']:
        queryset = queryset.filter(perfil=perfil_filter)

    sort_by = request.GET.get('sort', 'first_name')
    if sort_by in ['first_name', '-first_name', 'email', '-email']:
        queryset = queryset.order_by(sort_by)
    
    paginator = Paginator(queryset, 10)
    page_number = request.GET.get('page')
    pagina_de_usuarios = paginator.get_page(page_number)

    contexto = {
        'pagina_de_usuarios': pagina_de_usuarios,
        'query': query,
        'perfil_filter': perfil_filter,
        'sort_by': sort_by,
        'perfil_choices': Usuario.PERFIL_CHOICES,
    }

    return render(request, 'projetos_institucionais/gerenciar_usuarios.html', contexto)

@gestor_required
def usuario_detalhe(request, pk):
    usuario_selecionado = get_object_or_404(Usuario, pk=pk)
    contexto = {
        'usuario_selecionado': usuario_selecionado,
    }
    return render(request, 'projetos_institucionais/usuario_detalhe.html', contexto)

@gestor_required
def usuario_editar(request, pk):
    usuario_selecionado = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        form = UsuarioEditForm(request.POST, instance=usuario_selecionado)
        if form.is_valid():
            user = form.save(commit=False)
            if user.status == 'ativo':
                user.is_active = True
            else:
                user.is_active = False
            user.save()
            messages.success(request, 'Usuário atualizado com sucesso!')
            return redirect('gerenciar_usuarios')
    else:
        form = UsuarioEditForm(instance=usuario_selecionado)
    
    contexto = {
        'form': form,
        'usuario_selecionado': usuario_selecionado,
    }

    return render(request, 'projetos_institucionais/usuario_form.html', contexto)

@gestor_required
def usuario_deletar(request, pk):
    usuario_selecionado = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        try:
            usuario_selecionado.delete()
            messages.success(request, 'Usuário excluído com sucesso!')
        except ProtectedError:
            messages.error(request, 'Este usuário não pode ser excluído pois está vinculado como coordenador de um ou mais projetos.')
        return redirect('gerenciar_usuarios')
    
    contexto = {
        'usuario_selecionado': usuario_selecionado,
    }

    return render(request, 'projetos_institucionais/usuario_confirmar_delete.html', contexto)

@gestor_required
def historico_projetos(request):
    queryset = Projeto.objects.exclude(status='rascunho').select_related('coordenador').order_by('-data_inicio')
    
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    ano_filter = request.GET.get('ano', '')

    if query:
        queryset = queryset.filter(
            Q(titulo__icontains=query) |
            Q(coordenador__first_name__icontains=query) |
            Q(coordenador__last_name__icontains=query)
        )
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if ano_filter:
        queryset = queryset.filter(data_inicio__year=ano_filter)
    
    sort_by = request.GET.get('sort', 'data_inicio')
    allowed_sort_fields = ['titulo', '-titulo', 'coordenador__first_name', '-coordenador__first_name', 'data_inicio', '-data_inicio', 'data_fim', '-data_fim']
    if sort_by in allowed_sort_fields:
        queryset = queryset.order_by(sort_by)

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get('page')
    pagina_de_projetos = paginator.get_page(page_number)

    anos_disponiveis = Projeto.objects.exclude(data_inicio__isnull=True).dates('data_inicio', 'year', order='DESC')

    contexto = {
        'pagina_de_projetos': pagina_de_projetos,
        'status_choices': [choice for choice in Projeto.STATUS_CHOICES if choice[0] != 'rascunho'],
        'anos_disponiveis': anos_disponiveis,
        'query': query,
        'status_filter': status_filter,
        'ano_filter': ano_filter,
        'sort_by': sort_by,
    }

    return render(request, 'projetos_institucionais/historico_projetos.html', contexto)