from rest_framework import viewsets
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail, EmailMessage
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from django.conf import settings
from django.db import transaction
from django.db.models import Q, ProtectedError
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.template.loader import render_to_string
from .models import Projeto
from .forms import *
from login.forms import *
from .decorators import gestor_required, coordenador_required, aluno_required
from formtools.wizard.views import SessionWizardView
from weasyprint import HTML
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
    
    @transaction.atomic
    def done(self, form_list, form_dict, **kwargs):
        projeto_id = self.storage.extra_data.get('projeto_id')
        projeto = Projeto.objects.get(pk=projeto_id)

        dados_gerais = {}
        for form_key in ['0', '1', '2']:
            dados_gerais.update(form_dict.get(form_key, {}).cleaned_data)
        
        dados_etapa1 = form_dict.get('1', {}).cleaned_data
        grupos_pesquisa_data = dados_etapa1.get('grupos_pesquisa', [])

        dados_etapa4 = form_dict.get('4', {}).cleaned_data
        ods_data = dados_etapa4.get('ods', [])

        formset_equipe = form_dict.get('3', {})
        dados_equipe = formset_equipe.cleaned_data if formset_equipe else []

        for campo, valor in dados_gerais.items():
            if hasattr(projeto, campo) and not isinstance(getattr(projeto, campo), models.Manager):
                setattr(projeto, campo, valor)
        
        projeto.status = 'submetido'
        projeto.save()

        projeto.grupos_pesquisa.set(grupos_pesquisa_data)
        projeto.ods.set(ods_data)

        projeto.equipe.all().delete()
        for membro_data in dados_equipe:
            if membro_data and membro_data.get('membro'):
                EquipeProjeto.objects.create(
                    projeto=projeto,
                    membro=membro_data.get('membro'),
                    carga_horaria_semanal=membro_data.get('carga_horaria_semanal'),
                    carga_horaria_total=membro_data.get('carga_horaria_total')
                )

        contexto_pdf = {
            'projeto': projeto
        }
        html_string = render_to_string('projetos_institucionais/projeto_pdf.html', contexto_pdf)
        pdf_file = HTML(string=html_string).write_pdf()

        novo_anexo = Anexo(
            projeto=projeto,
            tipo_anexo='relatorio_submissao',
            descricao='Relatório de Submissão gerado automaticamente pelo sistema.',
        )
        nome_arquivo = f'submissao_projeto_{projeto.pk}.pdf'
        novo_anexo.arquivo.save(nome_arquivo, ContentFile(pdf_file), save=True)

        if 'projeto_id' in self.storage.extra_data:
            del self.storage.extra_data['projeto_id']

        return render(self.request, 'projetos_institucionais/projeto_wizard_done.html', {
            'projeto': projeto
        })

class ProjetoUpdateWizard(ProjetoCreateWizard):
    def get_form_instance(self, step):
        pk = self.kwargs.get('pk')
        self.storage.extra_data['projeto_id'] = pk
        
        return get_object_or_404(Projeto, pk=pk)
    
    @transaction.atomic
    def done(self, form_list, form_dict, **kwargs):
        response = super().done(form_list, form_dict, **kwargs)

        projeto_pk = self.kwargs.get('pk')
        if projeto_pk:
            projeto = Projeto.objects.get(pk=projeto_pk)
            if projeto.status == 'reprovado':
                projeto.status = 'submetido'
                projeto.save()
        
        return response

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
    relatorio_submissao = projeto.anexos.filter(tipo_anexo='relatorio_submissao').order_by('-data_upload').first()

    contexto = {
        'projeto': projeto,
        'comprovante': comprovante,
        'outros_anexos': outros_anexos,
        'relatorio_submissao': relatorio_submissao,
    }

    return render(request, 'projetos_institucionais/projeto_detalhe.html', contexto)

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
        'AnexoForm': AnexoForm(),
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
    projetos_aguardando_conselho = Projeto.objects.filter(status='aguardando_conselho').order_by('data_inicio')
    
    contexto = {
        'projetos_pendentes': projetos_pendentes,
        'projetos_aguardando_conselho': projetos_aguardando_conselho,
    }
    return render(request, 'projetos_institucionais/gestordashboard.html', contexto)

@gestor_required
def aprovar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    projeto.status = 'em_andamento'
    projeto.save()

    subject = f'Seu projeto "{projeto.titulo}" foi APROVADO!'
    message = (
        f'Olá, {projeto.coordenador.first_name}!\n\n'
        f'Temos boas notícias: seu projeto "{projeto.titulo}" foi aprovado e agora está em andamento. '
        f'Você pode acessar o sistema para mais detalhes.'
    )
    
    link_projeto = request.build_absolute_uri(reverse('projeto_detalhe', args=[projeto.pk]))
    enviar_email_e_notificacao(subject, message, projeto.coordenador, link=link_projeto)

    messages.success(request, f'O projeto "{projeto.titulo}" aprovado com sucesso.')
    return redirect('gestor_dashboard')
    
@gestor_required
def reprovar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    projeto.status = 'reprovado'
    projeto.save()

    subject = f'Atualização sobre seu projeto "{projeto.titulo}"'
    message = (
        f'Olá, {projeto.coordenador.first_name}.\n\n'
        f'Após análise, o projeto "{projeto.titulo}" foi reprovado. '
        f'Você pode acessar o sistema para editar e ressubmeter o projeto, se desejar.'
    )
    
    link_projeto = request.build_absolute_uri(reverse('projeto_detalhe', args=[projeto.pk]))
    enviar_email_e_notificacao(subject, message, projeto.coordenador, link=link_projeto)

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
    status_antigo = usuario_selecionado.status

    if request.method == 'POST':
        form = UsuarioEditForm(request.POST, instance=usuario_selecionado)
        if form.is_valid():
            user = form.save(commit=False)
            if user.status == 'ativo':
                user.is_active = True
            else:
                user.is_active = False
            user.save()

            status_novo = user.status
            if status_novo != status_antigo:
                subject = 'Sua conta na Plataforma PROPEG foi ativada!'
                message = (
                    f'Olá, {user.first_name}!\n\n'
                    f'Sua conta em nossa plataforma foi ativada por um gestor. '
                    f'Você já pode acessar o sistema com seu CPF e senha.\n\n'
                    f'Atenciosamente, \nEquipe PROPEG'
                )
                enviar_email_e_notificacao(subject, message, user)
                messages.success(request, f'Usuário "{user.get_full_name()}" ativado e notificado por email.')
            elif status_novo == 'inativo' and status_antigo == 'ativo':
                subject = 'Aviso: Sua conta na Plataforma PROPEG foi inativada'
                message = (
                    f'Olá, {user.first_name}.\n\n'
                    f'Sua conta em nossa plataforma foi inativada por um gestor. '
                    f'Se você acredita que isso foi um engano, por favor, entre em contato com a administração.\n\n'
                    f'Atenciosamente,\nEquipe PROPEG'
                )
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                )
                messages.warning(request, f'Usuário "{user.get_full_name()}" inativado e notificado por email.')
            else:
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

@login_required
@gestor_required
def encaminhar_para_conselho(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if projeto.status == 'submetido':
        projeto.status = 'aguardando_conselho'
        projeto.save()

        relatorio_anexo = projeto.anexos.filter(tipo_anexo='relatorio_submissao').order_by('-data_upload').first()

        if projeto.centro_lotacao and projeto.centro_lotacao.email:
            subject_conselho = f'Novo Projeto para Análise do Conselho: "{projeto.titulo}"'
            message_conselho = (
                f'Prezados membros do conselho do {projeto.centro_lotacao.nome},\n\n'
                f'O projeto "{projeto.titulo}", coordenado por {projeto.coordenador.get_full_name()}, foi encaminhado para sua análise e aprovação.\n\n'
                f'O relatório de submissão do projeto está anexado a este email para sua conveniência.\n\n'
                f'Atenciosamente,\nEquipe de Gestão PROPEG'
            )
            
            email_conselho = EmailMessage(
                subject_conselho,
                message_conselho,
                settings.DEFAULT_FROM_EMAIL,
                [projeto.centro_lotacao.email],
            )

            if relatorio_anexo and relatorio_anexo.arquivo:
                email_conselho.attach(
                    relatorio_anexo.arquivo.name.split('/')[-1],
                    relatorio_anexo.arquivo.read(),
                    'application/pdf'
                )
            
            email_conselho.send()

        subject_coordenador = f'Atualização do seu Projeto: "{projeto.titulo}"'
        message_coordenador = (
            f'Olá, {projeto.coordenador.first_name}!\n\n'
            f'Seu projeto "{projeto.titulo}" foi revisado pela gestão e encaminhado com sucesso para a análise do conselho do seu centro de lotação.\n\n'
            f'O status do seu projeto foi atualizado para "Aguardando aprovação do conselho". Você será notificado sobre as próximas etapas.\n\n'
            f'Atenciosamente,\nEquipe PROPEG'
        )
        link_projeto = request.build_absolute_uri(reverse('projeto_detalhe', args=[projeto.pk]))
        enviar_email_e_notificacao(subject_coordenador, message_coordenador, projeto.coordenador, link=link_projeto)
        messages.success(request, f'O projeto "{projeto.titulo}" foi encaminhado ao conselho e o coordenador foi notificado.')
    else:
        messages.warning(request, f'O projeto "{projeto.titulo}" não está no status "Submetido" e não pode ser encaminhado.')

    return redirect('gestor_dashboard')

@login_required
@coordenador_required
def adicionar_anexo(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if request.user != projeto.coordenador:
        return HttpResponseForbidden("Você não tem permissão para realizar esta ação.")
    
    if request.method == 'POST':
        form = AnexoForm(request.POST, request.FILES)
        if form.is_valid():
            anexo = form.save(commit=False)
            anexo.projeto = projeto
            anexo.save()
            messages.success(request, 'Anexo adicionado com sucesso!')
        else:
            messages.error(request, 'Houve um erro ao adicionar o anexo. Verifique o formulário.')
    
    return redirect(request.META.get('HTTP_REFERER', 'projeto_dashboard'))

@login_required
@coordenador_required
def deletar_anexo(request, anexo_id):
    anexo = get_object_or_404(Anexo, pk=anexo_id)
    if request.user != anexo.projeto.coordenador:
        return HttpResponseForbidden("Você não tem permissão para realizar esta ação.")
    
    if request.method == 'POST':
        anexo.arquivo.delete(save=True)
        anexo.delete()
        messages.success(request, 'Anexo excluído com sucesso.')

    return redirect(request.META.get('HTTP_REFERER', 'projeto_dashboard'))

@login_required
def projeto_equipe(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    contexto = {
        'projeto': projeto
    }
    return render(request, 'projetos_institucionais/projeto_equipe.html', contexto)

@login_required
def visualizar_perfil(request, pk):
    usuario_selecionado = get_object_or_404(Usuario, pk=pk)
    
    contexto = {
        'usuario_selecionado': usuario_selecionado,
    }
    
    return render(request, 'projetos_institucionais/usuario_detalhe.html', contexto)

@login_required
def projeto_anexos(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    relatorio_submissao = projeto.anexos.filter(tipo_anexo='relatorio_submissao').order_by('-data_upload').first()
    comprovante_aprovacao = projeto.anexos.filter(tipo_anexo='comprovante_aprovacao').first()
    anexos_gerenciaveis = projeto.anexos.exclude(tipo_anexo__in=['relatorio_submissao', 'comprovante_aprovacao'])

    
    if request.method == 'POST':
        if request.user != projeto.coordenador:
            return HttpResponseForbidden("Você não tem permissão para realizar esta ação.")
        
        form = AnexoForm(request.POST, request.FILES)
        if form.is_valid():
            anexo = form.save(commit=False)
            anexo.projeto = projeto
            anexo.save()
            messages.success(request, 'Anexo adicionado com sucesso!')
            return redirect('projeto_anexos', pk=projeto.pk)
        else:
            messages.error(request, 'Houve um erro ao adicionar o anexo.')
    else:
        form = AnexoForm()

    contexto = {
        'projeto': projeto,
        'relatorio_submissao': relatorio_submissao,
        'comprovante_aprovacao': comprovante_aprovacao,
        'anexos': anexos_gerenciaveis,
        'form': form,
    }
    return render(request, 'projetos_institucionais/projeto_anexos.html', contexto)


def enviar_email_e_notificacao(subject, message, destinatario_usuario, link=None):
    """
    Envia um email e cria uma notificação no sistema para o usuário.
    """
    # Envia o email
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [destinatario_usuario.email],
    )
    # Cria a notificação
    Notificacao.objects.create(
        destinatario=destinatario_usuario,
        mensagem=message,
        link=link
    )


@login_required
def lista_notificacoes(request):
    notificacoes = Notificacao.objects.filter(destinatario=request.user)
    notificacoes.update(lida=True)
    
    return render(request, 'projetos_institucionais/notificacoes.html', {'notificacoes': notificacoes})