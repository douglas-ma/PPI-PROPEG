from rest_framework import viewsets
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail, EmailMessage
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.db import transaction
from django.db.models import Q, ProtectedError
from django.http import HttpResponseForbidden, JsonResponse
from django.urls import reverse
from django.template.loader import render_to_string
from .models import Projeto
from .forms import *
from login.forms import *
from .decorators import gestor_required, coordenador_required, aluno_required
from formtools.wizard.views import SessionWizardView
from weasyprint import HTML
import re
from datetime import date
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

    file_storage = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'temp_wizard_files'))

    form_list = [
        ('0', Etapa1_TipoFinanciamentoForm),
        ('1', Etapa2_InfoGeraisForm),
        ('2', Etapa3_DetalhesProjetoForm),
        ('3', EquipeProjetoFormSet),
        ('4', Etapa5_ODSForm),
        ('5', Etapa6_RevisaoForm),
    ]

    def process_step(self, form):
        if self.steps.current == '1':
            files = form.cleaned_data.get('anexos_gerais', [])
            if files:
                file_names = [f.name for f in files]
                self.storage.extra_data['anexos_gerais_nomes'] = file_names
        
        return self.get_form_step_data(form)

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
            context['anexos_gerais_review'] = self.storage.extra_data.get('anexos_gerais_nomes', [])
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
    
    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        if step == '3':
            kwargs['form_kwargs'] = {'coordenador': self.request.user}
        return kwargs
    
    @transaction.atomic
    def done(self, form_list, form_dict, **kwargs):
        projeto_id = self.storage.extra_data.get('projeto_id')
        projeto = Projeto.objects.get(pk=projeto_id)

        dados_gerais = {}
        for form_key in ['0', '1', '2']:
            dados_gerais.update(form_dict.get(form_key, {}).cleaned_data)
        
        anexos_a_salvar = dados_gerais.pop('anexos_gerais', [])
        centro_lotacao_obj = dados_gerais.get('centro_lotacao')
        nome_agencia = dados_gerais.pop('agencia_financiadora', None)
        
        if nome_agencia:
            agencia_obj, _ = AgenciaFinanciadora.objects.get_or_create(nome=nome_agencia.strip())
            projeto.agencia_financiadora = agencia_obj

        nome_programa = dados_gerais.pop('programa_pos', None)
        if nome_programa and centro_lotacao_obj:
            programa_obj, _ = ProgramaPos.objects.get_or_create(nome=nome_programa.strip(), defaults={'centro_lotacao': centro_lotacao_obj})
            projeto.programa_pos = programa_obj
        
        nome_tipo_etica = dados_gerais.pop('tipo_etica', None)
        if nome_tipo_etica:
            etica_obj, _ = TipoEtico.objects.get_or_create(nome=nome_tipo_etica.strip())
            projeto.tipo_etica = etica_obj

        grupos_str = dados_gerais.pop('grupos_pesquisa', '')

        dados_etapa4 = form_dict.get('4', {}).cleaned_data
        ods_data = dados_etapa4.get('ods', [])

        formset_equipe = form_dict.get('3', {})
        dados_equipe = formset_equipe.cleaned_data if formset_equipe else []

        projeto.edital = dados_gerais.pop('edital', None)
        imagem_capa_salvar = dados_gerais.pop('imagem_capa', None)

        for campo, valor in dados_gerais.items():
            if hasattr(projeto, campo) and not isinstance(getattr(projeto, campo), models.Manager):
                setattr(projeto, campo, valor)
        
        if imagem_capa_salvar:
            projeto.imagem_capa = imagem_capa_salvar

        projeto.status = 'submetido'
        projeto.save()

        lista_de_grupos = []
        if grupos_str:
            nomes_grupos = [nome.strip() for nome in grupos_str.split(',') if nome.strip()]
            for nome in nomes_grupos:
                grupo_obj, _ = GrupoPesquisa.objects.get_or_create(nome=nome)
                lista_de_grupos.append(grupo_obj)
        projeto.grupos_pesquisa.set(lista_de_grupos)
        projeto.ods.set(ods_data)

        if anexos_a_salvar:
            anexos_nomes = self.storage.extra_data.get('anexos_gerais_nomes', [])
            
            for file_content, file_name in zip(anexos_a_salvar, anexos_nomes):
                django_file = ContentFile(file_content, name=file_name)
                
                Anexo.objects.create(
                    projeto=projeto,
                    tipo_anexo='outro',
                    arquivo=django_file,
                    descricao=f"Anexo geral: {file_name}"
                )

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

def load_cursos(request):
    centro_id = request.GET.get('centro_id')
    cursos = CursoGraduacao.objects.filter(centro_lotacao_id=centro_id).order_by('nome')
    return JsonResponse(list(cursos.values('id', 'nome')), safe=False)

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
    relatorios_enviados = projeto.relatorios.all().order_by('-data_envio')

    contexto = {
        'projeto': projeto,
        'comprovante': comprovante,
        'outros_anexos': outros_anexos,
        'relatorio_submissao': relatorio_submissao,
        'relatorios_enviados': relatorios_enviados,
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
    active_tab = request.GET.get('tab', 'visao_geral')
    contexto = {
        'active_tab': active_tab,
        'AnexoForm': AnexoForm(),
    }

    if active_tab == 'visao_geral':
        projetos_em_andamento = Projeto.objects.filter(status='em_andamento')
        projetos_em_revisao = Projeto.objects.filter(Q(status='submetido') | Q(status='aguardando_conselho'))
        projetos_rejeitados = Projeto.objects.filter(status='reprovado')

        contexto.update({
            'projetos_em_andamento': projetos_em_andamento,
            'projetos_em_revisao': projetos_em_revisao,
            'projetos_rejeitados': projetos_rejeitados,
        })
        todos_os_projetos = list(projetos_em_andamento) + list(projetos_em_revisao) + list(projetos_rejeitados)
        contexto['todos_os_projetos'] = todos_os_projetos
    else:
        status_map = {
            'em_andamento': (['em_andamento'], 'Projetos em Andamento'),
            'em_revisao': (['submetido','aguardando_conselho', 'aguardando_encerramento'], 'Projetos em Revisão'),
            'finalizados': (['encerrado'], 'Projetos Finalizados'),
            'avaliados': (['aprovado', 'reprovado'], 'Projetos Aprovados e Rejeitados'),
        }

        status_filter, table_title = status_map.get(active_tab, ([], ''))
        if status_filter:
            lista_projetos = Projeto.objects.filter(coordenador=request.user, status__in=status_filter).order_by('-data_inicio')

            paginator = Paginator(lista_projetos, 10)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)

            contexto['page_obj'] = page_obj
            contexto['table_title'] = table_title

    return render(request, 'projetos_institucionais/meusprojetos.html', contexto)

@login_required
@aluno_required
def aluno_projeto_dashboard(request):
    participacoes = EquipeProjeto.objects.filter(membro=request.user).select_related('projeto', 'projeto__coordenador')

    contexto = {
        'participacoes': participacoes,
    }

    return render(request, 'projetos_institucionais/aluno_projeto_dashboard.html', contexto)

@login_required
@gestor_required
def gestor_dashboard(request):
    projetos_pendentes = Projeto.objects.filter(status='submetido').order_by('data_inicio')
    projetos_aguardando_conselho = Projeto.objects.filter(status='aguardando_conselho').order_by('data_inicio')
    projetos_aguardando_encerramento = Projeto.objects.filter(status='aguardando_encerramento').order_by('data_fim')
    usuarios_pendentes = Usuario.objects.filter(status='pendente', is_active=False).order_by('date_joined')

    contexto = {
        'projetos_pendentes': projetos_pendentes,
        'projetos_aguardando_conselho': projetos_aguardando_conselho,
        'projetos_aguardando_encerramento': projetos_aguardando_encerramento,
        'usuarios_pendentes': usuarios_pendentes,
        'count_projetos_pendentes': projetos_pendentes.count(),
        'count_aguardando_conselho': projetos_aguardando_conselho.count(),
        'count_aguardando_encerramento': projetos_aguardando_encerramento.count(),
        'count_usuarios_pendentes': usuarios_pendentes.count(),
    }
    return render(request, 'projetos_institucionais/gestordashboard.html', contexto)

@gestor_required
def aprovar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    projeto.status = 'aprovado'
    projeto.save()

    subject = f'Seu projeto "{projeto.titulo}" foi APROVADO!'
    message = (
        f'Olá, {projeto.coordenador.first_name}!\n\n'
        f'Temos boas notícias: seu projeto "{projeto.titulo}" foi aprovado pelo gestor.'
        f'Você já pode iniciá-lo a partir do seu painel ou aguardar a data de início programada.'
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

@login_required
@coordenador_required
def iniciar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk, coordenador=request.user)

    if projeto.status == 'aprovado':
        projeto.status = 'em_andamento'
        projeto.save()

        subject = f'O projeto "{projeto.titulo}" foi iniciado!'
        message = (
            f'O projeto "{projeto.titulo}", do qual você faz parte, acaba de ser iniciado pelo coordenador. '
            f'Acesse a plataforma para acompanhar as atividades.'
        )
        link_projeto = request.build_absolute_uri(reverse('projeto_detalhe', args=[projeto.pk]))
        
        enviar_email_e_notificacao(subject, message, projeto.coordenador, link=link_projeto)

        for membro_equipe in projeto.equipe.all():
            enviar_email_e_notificacao(subject, message, membro_equipe.membro, link=link_projeto)

        messages.success(request, f'O projeto "{projeto.titulo}" foi iniciado e toda a equipe foi notificada.')
    else:
        messages.warning(request, 'Este projeto não pode ser iniciado.')

    return redirect('projeto_detalhe', pk=pk)

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

@login_required
@coordenador_required
def listar_projetos_para_relatorio(request):
    hoje = date.today()

    projetos_sem_relatorio_final = Projeto.objects.filter(
        coordenador=request.user,
        status='em_andamento'
    ).exclude(relatorios__tipo='final')

    projetos_no_prazo = projetos_sem_relatorio_final.filter(data_fim__gte=hoje).order_by('data_fim')
    projetos_atrasados = projetos_sem_relatorio_final.filter(data_fim__lt=hoje).order_by('data_fim')
    
    for p in projetos_no_prazo: p.dias_restantes = (p.data_fim - hoje).days
    for p in projetos_atrasados: p.dias_atraso = abs((p.data_fim - hoje).days)

    contexto = {
        'projetos_no_prazo': projetos_no_prazo,
        'projetos_atrasados': projetos_atrasados,
    }
    return render(request, 'projetos_institucionais/relatorio_lista_projetos.html', contexto)

@login_required
@coordenador_required
def criar_relatorio(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk, coordenador=request.user)
    if request.method == 'POST':
        form = RelatorioForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data

            contexto_pdf = {
                'projeto': projeto,
                'dados_relatorio': dados,
                'data_geracao': date.today(),
            }
            html_string = render_to_string('projetos_institucionais/relatorio_pdf_template.html', contexto_pdf)
            pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

            nome_arquivo = f'relatorio_{dados["tipo_relatorio"]}_projeto_{projeto.pk}.pdf'
            arquivo_pdf_django = ContentFile(pdf_file, name=nome_arquivo)

            novo_relatorio = Relatorio.objects.create(
                projeto=projeto,
                responsavel=request.user,
                tipo=dados['tipo_relatorio'],
                anexo_pdf=arquivo_pdf_django,
            )
            if novo_relatorio.tipo == 'final':
                projeto.status = 'aguardando_encerramento'
                projeto.save()

                gestores = Usuario.objects.filter(perfil='gestor', is_active=True)
                subject = f'Relatório Final Submetido: "{projeto.titulo}"'
                message = (
                    f'O coordenador {projeto.coordenador.get_full_name()} submeteu o relatório final para o projeto "{projeto.titulo}".\n\n'
                    f'O projeto agora está pronto para sua análise e finalização.'
                )
                link_projeto = request.build_absolute_uri(reverse('projeto_detalhe', args=[projeto.pk]))

                for gestor in gestores:
                    enviar_email_e_notificacao(subject, message, gestor, link=link_projeto)

            messages.success(request, 'Relatório enviado com sucesso e salvo no projeto.')
            return redirect('projeto_detalhe', pk=projeto.pk)
    else:
        form = RelatorioForm()
    
    contexto = {
        'form': form,
        'projeto': projeto,
    }
    return render(request, 'projetos_institucionais/relatorio_form.html', contexto)

@login_required
@gestor_required
def finalizar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    tem_relatorio_final = projeto.relatorios.filter(tipo='final').exists()

    if not tem_relatorio_final:
        messages.error(request, 'Ação não permitida: o projeto não pode ser encerrado sem a submissão do relatório final.')
        return redirect('projeto_detalhe', pk=pk)
    
    projeto.status = 'encerrado'
    projeto.save()
    messages.success(request, 'Projeto encerrado com sucesso!')
    return redirect('projeto_detalhe', pk=pk)

@login_required
@gestor_required
def encerrar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    
    if projeto.status == 'aguardando_encerramento':
        projeto.status = 'encerrado'
        projeto.save()

        subject = f'Seu projeto "{projeto.titulo}" foi oficialmente encerrado'
        message = (
            f'Olá, {projeto.coordenador.first_name}!\n\n'
            f'Informamos que o projeto "{projeto.titulo}" foi revisado e oficialmente encerrado pela gestão.\n\n'
            f'Agradecemos pelo seu trabalho e dedicação.\nEquipe PROPEG'
        )
        link_projeto = request.build_absolute_uri(reverse('projeto_detalhe', args=[projeto.pk]))
        enviar_email_e_notificacao(subject, message, projeto.coordenador, link=link_projeto)

        messages.success(request, f'O projeto "{projeto.titulo}" foi encerrado com sucesso.')
    else:
        messages.warning(request, 'Este projeto não está aguardando encerramento.')

    return redirect('gestor_dashboard')

@login_required
@gestor_required
def listar_relatorios_gestor(request):
    queryset = Relatorio.objects.select_related('projeto', 'projeto__coordenador').all().order_by('-data_envio')

    query = request.GET.get('q', '')
    ano_filter = request.GET.get('ano', '')
    tipo_filter = request.GET.get('tipo', '')
    status_filter = request.GET.get('status', '')

    if query:
        queryset = queryset.filter(
            Q(projeto__titulo__icontains=query) |
            Q(projeto__coordenador__first_name__icontains=query) |
            Q(projeto__coordenador__last_name__icontains=query)
        )
    if ano_filter:
        queryset = queryset.filter(projeto__data_inicio__year=ano_filter)
    if tipo_filter:
        queryset = queryset.filter(tipo=tipo_filter)
    if status_filter:
        queryset = queryset.filter(projeto__status=status_filter)

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    anos_disponiveis = Projeto.objects.dates('data_inicio', 'year', order='DESC')

    contexto = {
        'page_obj': page_obj,
        'anos_disponiveis': anos_disponiveis,
        'tipo_choices': Relatorio.TIPO_CHOICES,
        'status_choices': Projeto.STATUS_CHOICES,
        'query': query,
        'ano_filter': ano_filter,
        'tipo_filter': tipo_filter,
        'status_filter': status_filter,
    }
    return render(request, 'projetos_institucionais/gestor_relatorios.html', contexto)

@login_required
@gestor_required
def gestor_listar_editais(request):
    editais = Edital.objects.all()
    contexto = {
        'editais': editais
    }
    return render(request, 'projetos_institucionais/gestor_edital_lista.html', contexto)

@login_required
@gestor_required
def gestor_criar_edital(request):
    if request.method == 'POST':
        form = EditalForm(request.POST, request.FILES)
        formset = AnexoEditalFormSet(request.POST, request.FILES, instance=Edital())
        if form.is_valid() and formset.is_valid():
            edital = form.save(commit=False)
            edital.criado_por = request.user
            edital.save()
            
            formset.instance = edital
            formset.save()
            
            messages.success(request, "Edital cadastrado com sucesso!")
            return redirect('gestor_listar_editais')
    else:
        form = EditalForm(initial={'ano': date.today().year})
        formset = AnexoEditalFormSet(instance=Edital())

    contexto = {
        'form': form, 'formset': formset
    }
    return render(request, 'projetos_institucionais/gestor_edital_form.html', contexto)

@login_required
@gestor_required
def gestor_editar_edital(request, pk):
    edital = get_object_or_404(Edital, pk=pk)
    if request.method == 'POST':
        form = EditalForm(request.POST, request.FILES, instance=edital)
        formset = AnexoEditalFormSet(request.POST, request.FILES, instance=edital)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Edital atualizado com sucesso!")
            return redirect('gestor_listar_editais')
    else:
        form = EditalForm(instance=edital)
        formset = AnexoEditalFormSet(instance=edital)

    contexto = {
        'form': form, 'formset': formset, 'edital': edital
    }
    return render(request, 'projetos_institucionais/gestor_edital_form.html', contexto)

@login_required
@gestor_required
def gestor_deletar_edital(request, pk):
    edital = get_object_or_404(Edital, pk=pk)
    if request.method == 'POST':
        edital.delete()
        messages.success(request, "Edital excluído com sucesso.")
        return redirect('gestor_listar_editais')
    
    contexto = {
        'edital': edital
    }
    return render(request, 'projetos_institucionais/edital_confirm_delete.html', contexto)

@login_required
@coordenador_required
def listar_editais_abertos(request):
    hoje = date.today()
    editais_abertos = Edital.objects.filter(
        status='aberto',
        data_inicio_submissoes__lte=hoje,
        data_fim_submissoes__gte=hoje
    ).prefetch_related('anexos')

    contexto = {
        'editais': editais_abertos
    }
    return render(request, 'projetos_institucionais/editais_abertos_lista.html', contexto)