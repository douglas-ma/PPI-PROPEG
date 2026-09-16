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
from django.db.models import Q, ProtectedError, Value, Count
from django.db.models.functions import Replace
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Anexo, ODS, Projeto, AdendoEdital, SolicitacaoAprovacaoCentro
from .forms import *
from login.forms import *
from .decorators import gestor_required, coordenador_required, aluno_required
from .forms import ProjetoEtapa1Form, ProjetoEtapa2Form, ProjetoEtapa2AgenciaFomentoForm, ProjetoEtapa4Form
from .document_extraction import extrair_campos_projeto
from formtools.wizard.views import SessionWizardView
from weasyprint import HTML
import re
import base64
import mimetypes
from io import BytesIO
from datetime import date
import datetime
from pathlib import Path
from pypdf import PdfReader, PdfWriter


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
    from login.forms import RegistroUsuarioForm
    form = RegistroUsuarioForm()
    return render(request, 'home/home.html', {'form_registro': form})


def _url_anexo_no_relatorio(anexo, request=None):
    """Retorna uma URL clicável para o arquivo original do anexo."""
    try:
        arquivo_url = anexo.arquivo.url
    except (AttributeError, ValueError):
        return ''

    if request and arquivo_url and not arquivo_url.startswith(('http://', 'https://', 'data:')):
        return request.build_absolute_uri(arquivo_url)
    return arquivo_url


def _preparar_anexos_do_relatorio(projeto, request=None):
    """Prepara imagens para o HTML e PDFs para incorporação posterior com pypdf."""
    anexos = list(projeto.anexos_documentais)
    pdfs_para_incorporar = []
    extensoes_imagem = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

    for anexo in anexos:
        anexo.arquivo_link = _url_anexo_no_relatorio(anexo, request)
        extensao = Path(anexo.arquivo.name or '').suffix.lower()

        if extensao in extensoes_imagem:
            try:
                with anexo.arquivo.open('rb') as arquivo:
                    conteudo = arquivo.read()
                tipo_mime = mimetypes.guess_type(anexo.arquivo.name)[0] or 'application/octet-stream'
                anexo.imagem_data_uri = (
                    f'data:{tipo_mime};base64,{base64.b64encode(conteudo).decode("ascii")}'
                )
            except Exception:
                anexo.imagem_data_uri = ''

        elif extensao == '.pdf':
            try:
                with anexo.arquivo.open('rb') as arquivo:
                    conteudo = arquivo.read()
                leitor = PdfReader(BytesIO(conteudo), strict=False)
                paginas = len(leitor.pages)
                if not paginas:
                    raise ValueError('O PDF não possui páginas.')
                anexo.pdf_incorporado = True
                anexo.pdf_paginas = paginas
                pdfs_para_incorporar.append((anexo, conteudo))
            except Exception:
                anexo.pdf_incorporado = False
                anexo.pdf_paginas = 0

    return anexos, pdfs_para_incorporar


def _gerar_relatorio_submissao(projeto, request=None):
    """Gera o dossiê com anexos visuais incorporados no PDF final."""
    anexos, pdfs_para_incorporar = _preparar_anexos_do_relatorio(projeto, request)
    logo_path = Path(settings.BASE_DIR) / 'static' / 'imagens' / 'logo_ufac.png'
    contexto_pdf = {
        'projeto': projeto,
        'data_geracao': timezone.localdate(),
        'logo_ufac_uri': logo_path.resolve().as_uri() if logo_path.exists() else '',
        'anexos_relatorio': anexos,
    }
    html_string = render_to_string(
        'projetos_institucionais/projeto_pdf.html',
        contexto_pdf,
    )
    pdf_file = HTML(string=html_string, base_url=str(settings.BASE_DIR)).write_pdf()

    # WeasyPrint não renderiza PDF dentro de uma tag <embed>. Depois de gerar
    # o relatório principal, incorporamos as páginas dos PDFs como páginas
    # reais do mesmo documento e criamos um marcador para cada anexo.
    if pdfs_para_incorporar:
        leitor_base = PdfReader(BytesIO(pdf_file), strict=False)
        escritor = PdfWriter()
        escritor.append(leitor_base)
        for anexo, conteudo in pdfs_para_incorporar:
            primeira_pagina = len(escritor.pages)
            leitor_anexo = PdfReader(BytesIO(conteudo), strict=False)
            for pagina in leitor_anexo.pages:
                escritor.add_page(pagina)
            escritor.add_outline_item(
                f'Anexo - {anexo.descricao or anexo.get_tipo_anexo_display()}',
                primeira_pagina,
            )
        pdf_final = BytesIO()
        escritor.write(pdf_final)
        pdf_file = pdf_final.getvalue()

    novo_anexo = Anexo(
        projeto=projeto,
        tipo_anexo='relatorio_submissao',
        descricao='Relatório de Submissão criado pelo sistema no envio do projeto.',
    )
    novo_anexo.arquivo.save(
        f'submissao_projeto_{projeto.pk}.pdf',
        ContentFile(pdf_file),
        save=True,
    )
    return novo_anexo


def _enviar_email_externo(destinatario_email, destinatario_nome, assunto, mensagem):
    """Envia e-mail a um destinatário sem conta, via Brevo ou backend Django."""
    brevo_key = getattr(settings, 'BREVO_API_KEY', '')
    if brevo_key:
        try:
            import sib_api_v3_sdk
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key['api-key'] = brevo_key
            api = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )
            email_obj = sib_api_v3_sdk.SendSmtpEmail(
                to=[{'email': destinatario_email, 'name': destinatario_nome}],
                sender={'email': settings.DEFAULT_FROM_EMAIL, 'name': 'PROPEG/UFAC'},
                subject=assunto,
                text_content=mensagem,
            )
            api.send_transac_email(email_obj)
            return True
        except Exception as erro:
            print(f'Erro ao enviar e-mail ao Centro via Brevo: {erro}')
            return False

    try:
        return bool(send_mail(
            assunto,
            mensagem,
            settings.DEFAULT_FROM_EMAIL,
            [destinatario_email],
            fail_silently=False,
        ))
    except Exception as erro:
        print(f'Erro ao enviar e-mail ao Centro: {erro}')
        return False


def _emitir_solicitacao_centro(request, projeto):
    validade_horas = int(getattr(settings, 'APROVACAO_CENTRO_LINK_HORAS', 168))
    solicitacao, token = SolicitacaoAprovacaoCentro.emitir(
        projeto=projeto,
        email_destinatario=projeto.centro_lotacao.email,
        validade_horas=validade_horas,
    )
    link = request.build_absolute_uri(reverse('aprovacao_centro', args=[token]))
    assunto = f'Aprovação de projeto pelo Centro: "{projeto.titulo}"'
    mensagem = (
        f'Prezados responsáveis do {projeto.centro_lotacao.nome},\n\n'
        f'O projeto "{projeto.titulo}", coordenado por '
        f'{projeto.coordenador.get_full_name()}, aguarda deliberação do Conselho do Centro.\n\n'
        f'Acesse o link restrito abaixo para consultar o projeto e anexar a ata da assembleia '
        f'que registra sua aprovação:\n{link}\n\n'
        f'O link permite somente esta tramitação, expira em {validade_horas // 24 or 1} dia(s) '
        f'e será invalidado após o envio válido da ata.\n\n'
        'Atenciosamente,\nEquipe PROPEG/UFAC'
    )
    enviado = _enviar_email_externo(
        projeto.centro_lotacao.email,
        projeto.centro_lotacao.nome,
        assunto,
        mensagem,
    )
    return solicitacao, enviado

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

        _gerar_relatorio_submissao(projeto, self.request)

        if 'projeto_id' in self.storage.extra_data:
            del self.storage.extra_data['projeto_id']

        return render(self.request, 'projetos_institucionais/projeto_wizard_done.html', {
            'projeto': projeto
        })

def load_cursos(request):
    centro_id = request.GET.get('centro_id')
    cursos = CursoGraduacao.objects.filter(centro_lotacao_id=centro_id).order_by('nome')
    return JsonResponse(list(cursos.values('id', 'nome')), safe=False)


@login_required
@coordenador_required
def buscar_membros_equipe(request):
    """Busca coordenadores e alunos por nome, curso ou CPF para a Etapa 3."""
    termo = request.GET.get('q', '').strip()
    if len(termo) < 2:
        return JsonResponse({'resultados': []})

    usuarios = Usuario.objects.filter(
        perfil__in=('coordenador', 'aluno'),
    ).exclude(pk=request.user.pk).select_related('curso').annotate(
        cpf_busca=Replace(
            Replace(Replace('cpf', Value('.'), Value('')), Value('-'), Value('')),
            Value(' '),
            Value(''),
        ),
    )

    for parte in termo.split():
        filtro = (
            Q(first_name__icontains=parte)
            | Q(last_name__icontains=parte)
            | Q(username__icontains=parte)
            | Q(cpf__icontains=parte)
            | Q(curso__nome__icontains=parte)
        )
        parte_numerica = ''.join(filter(str.isdigit, parte))
        if parte_numerica:
            filtro |= Q(cpf_busca__icontains=parte_numerica)
        usuarios = usuarios.filter(filtro)

    def cpf_mascarado(valor):
        numeros = ''.join(filter(str.isdigit, valor or ''))
        if len(numeros) == 11:
            return f'{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}'
        return valor or ''

    resultados = [
        {
            'id': usuario.pk,
            'nome': usuario.get_full_name() or usuario.username,
            'cpf': cpf_mascarado(usuario.cpf),
            'curso': str(usuario.curso) if usuario.curso_id else 'Curso não informado',
            'perfil': usuario.get_perfil_display(),
        }
        for usuario in usuarios.order_by('first_name', 'last_name')[:20]
    ]
    return JsonResponse({'resultados': resultados})

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
        contexto['usuarios_pendentes']           = Usuario.objects.filter(is_active=False, status='pendente').count()
        contexto['projetos_pendentes']           = Projeto.objects.filter(status='submetido').count()
        contexto['count_aguardando_conselho'] = Projeto.objects.filter(
            status='aguardando_conselho',
            tipo_projeto=Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
        ).count()
        contexto['count_aguardando_encerramento']= Projeto.objects.filter(status='aguardando_encerramento').count()
        contexto['total_projetos']               = Projeto.objects.exclude(status='rascunho').count()
        contexto['total_coordenadores']          = Usuario.objects.filter(perfil='coordenador', is_active=True).count()
        contexto['projetos_recentes']            = Projeto.objects.exclude(status='rascunho').order_by('-id')[:5]

    elif user.perfil == 'coordenador':
        projetos = Projeto.objects.filter(coordenador=user)
        contexto['projetos_em_andamento']  = projetos.filter(status='em_andamento').count()
        contexto['projetos_em_revisao']    = projetos.filter(status__in=['submetido','aguardando_conselho']).count()
        contexto['projetos_aprovados']     = projetos.filter(status='aprovado').count()
        contexto['projetos_rascunho']      = projetos.filter(status='rascunho').count()
        contexto['projetos_finalizados']   = projetos.filter(status='finalizado').count()
        contexto['projetos_encerrados']    = projetos.filter(status='encerrado').count()
        contexto['total_projetos']         = projetos.exclude(status='rascunho').count()
        contexto['projetos_recentes']      = projetos.exclude(status='rascunho').order_by('-id')[:5]
        contexto['editais_abertos']        = Edital.objects.filter(
            status='aberto',
            data_inicio_submissoes__lte=date.today(),
            data_fim_submissoes__gte=date.today(),
        ).count()

    elif user.perfil == 'aluno':
        participacoes = EquipeProjeto.objects.filter(membro=user).select_related('projeto')
        contexto['projetos_participando']  = participacoes.count()
        contexto['projetos_em_andamento']  = participacoes.filter(projeto__status='em_andamento').count()
        contexto['endereco_preenchido']    = hasattr(user, 'endereco') and user.endereco is not None
        contexto['participacoes_recentes'] = participacoes.order_by('-projeto__data_inicio')[:5]

    return render(request, 'projetos_institucionais/tela_principal.html', contexto)

def projeto_listar(request):
    projetos = Projeto.objects.all()
    return render(request, 'projetos_institucionais/projeto_listar.html', {'projeto': projetos})

@login_required
def projeto_detalhe(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    if projeto.status == 'rascunho' and request.user != projeto.coordenador and request.user.perfil != 'gestor':
        raise Http404

    comprovante         = projeto.anexos.filter(tipo_anexo='comprovante_aprovacao').order_by('-data_upload').first()
    comprovante_fomento = projeto.anexos.filter(tipo_anexo='comprovante_fomento').order_by('-data_upload').first()
    ata_conselho        = projeto.anexos.filter(tipo_anexo='ata_conselho').order_by('-data_upload').first()
    aprovacao_etica     = projeto.anexos.filter(tipo_anexo='comite_etica').order_by('-data_upload').first()
    submissao_etica     = projeto.anexos.filter(tipo_anexo='submissao_comite_etica').order_by('-data_upload').first()
    relatorio_submissao = projeto.anexos.filter(tipo_anexo='relatorio_submissao').order_by('-data_upload').first()
    outros_anexos       = projeto.anexos.exclude(tipo_anexo__in=[
        'comprovante_aprovacao', 'comprovante_fomento',
        'relatorio_submissao', 'ata_conselho',
        'comite_etica', 'submissao_comite_etica',
    ])
    relatorios_enviados = projeto.relatorios.all().order_by('-data_envio')
    visao_completa      = (request.user == projeto.coordenador or request.user.perfil == 'gestor')
    solicitacao_centro = projeto.solicitacoes_aprovacao_centro.filter(
        utilizada_em__isnull=True,
        invalidada_em__isnull=True,
    ).first()

    return render(request, 'projetos_institucionais/projeto_detalhe.html', {
        'projeto':             projeto,
        'comprovante':         comprovante,
        'comprovante_fomento': comprovante_fomento,
        'ata_conselho':        ata_conselho,
        'aprovacao_etica':     aprovacao_etica,
        'submissao_etica':     submissao_etica,
        'outros_anexos':       outros_anexos,
        'relatorio_submissao': relatorio_submissao,
        'relatorios_enviados': relatorios_enviados,
        'visao_completa':      visao_completa,
        'solicitacao_centro':  solicitacao_centro,
    })


@login_required
@gestor_required
def anexar_ata_conselho(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if projeto.requer_ata_conselho:
        messages.warning(
            request,
            'Neste tipo de projeto, a ata deve ser enviada pelo Centro pelo link restrito encaminhado por e-mail.',
        )
        return redirect('gestor_dashboard')
    if request.method == 'POST':
        form = AnexoComprovanteForm(request.POST, request.FILES)
        if form.is_valid():
            anexo = form.save(commit=False)
            anexo.projeto    = projeto
            anexo.tipo_anexo = 'ata_conselho'
            anexo.descricao  = form.cleaned_data.get('descricao') or 'Ata de Aprovação do Centro'
            anexo.save()
            messages.success(request, f'Ata do centro anexada ao projeto "{projeto.titulo}".')
            return redirect('gestor_dashboard')
    else:
        form = AnexoComprovanteForm()
    return render(request, 'projetos_institucionais/anexar_comprovante.html', {
        'form': form, 'projeto': projeto,
        'titulo_pagina': 'Anexar Ata de Aprovação do Centro',
    })


def _obter_solicitacao_por_token(token):
    token_hash = SolicitacaoAprovacaoCentro.calcular_hash(token)
    return SolicitacaoAprovacaoCentro.objects.select_related(
        'projeto',
        'projeto__coordenador',
        'projeto__centro_lotacao',
    ).filter(token_hash=token_hash).first()


def _motivo_link_centro_invalido(solicitacao):
    if solicitacao is None:
        return 'Este link de aprovação não existe ou está incorreto.'
    if solicitacao.utilizada_em:
        return 'Este link já foi utilizado para registrar a ata.'
    if solicitacao.invalidada_em:
        return 'Este link foi substituído por uma solicitação mais recente.'
    if solicitacao.expira_em <= timezone.now():
        return 'Este link expirou. O coordenador poderá solicitar um novo envio pela plataforma.'
    if (
        not solicitacao.projeto.requer_ata_conselho
        or solicitacao.projeto.status != 'aguardando_conselho'
    ):
        return 'Este projeto não está mais aguardando a aprovação do Centro.'
    return ''


def aprovacao_centro(request, token):
    """Página pública restrita ao registro da ata pelo Centro de Estudos."""
    solicitacao = _obter_solicitacao_por_token(token)
    motivo_invalido = _motivo_link_centro_invalido(solicitacao)
    if motivo_invalido:
        return render(
            request,
            'projetos_institucionais/aprovacao_centro.html',
            {'motivo_invalido': motivo_invalido},
            status=410,
        )

    form = AprovacaoCentroForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            solicitacao = SolicitacaoAprovacaoCentro.objects.select_for_update().select_related(
                'projeto',
                'projeto__coordenador',
                'projeto__centro_lotacao',
            ).get(pk=solicitacao.pk)
            motivo_invalido = _motivo_link_centro_invalido(solicitacao)
            if motivo_invalido:
                return render(
                    request,
                    'projetos_institucionais/aprovacao_centro.html',
                    {'motivo_invalido': motivo_invalido},
                    status=410,
                )

            projeto = Projeto.objects.select_for_update().get(pk=solicitacao.projeto_id)
            responsavel_nome = form.cleaned_data['responsavel_nome'].strip()
            responsavel_cargo = form.cleaned_data['responsavel_cargo'].strip()
            ata = Anexo.objects.create(
                projeto=projeto,
                tipo_anexo='ata_conselho',
                arquivo=form.cleaned_data['ata_assembleia'],
                descricao=(
                    f'Ata de aprovação do Centro enviada por {responsavel_nome} '
                    f'({responsavel_cargo}).'
                ),
            )
            solicitacao.ata = ata
            solicitacao.responsavel_nome = responsavel_nome
            solicitacao.responsavel_cargo = responsavel_cargo
            solicitacao.utilizada_em = timezone.now()
            solicitacao.save(update_fields=[
                'ata', 'responsavel_nome', 'responsavel_cargo', 'utilizada_em',
            ])
            projeto.status = 'submetido'
            projeto.save(update_fields=['status'])

        link_projeto = request.build_absolute_uri(reverse('projeto_detalhe', args=[projeto.pk]))
        enviar_email_e_notificacao(
            f'Projeto "{projeto.titulo}" aprovado pelo Centro',
            (
                f'Olá, {projeto.coordenador.first_name}!\n\n'
                f'O Centro de Estudos anexou a ata de aprovação do projeto "{projeto.titulo}". '
                'O projeto foi encaminhado automaticamente à PROPEG e agora aguarda a análise do gestor.\n\n'
                'Atenciosamente,\nEquipe PROPEG/UFAC'
            ),
            projeto.coordenador,
            link=link_projeto,
        )
        return render(
            request,
            'projetos_institucionais/aprovacao_centro.html',
            {'concluido': True, 'projeto': projeto},
        )

    return render(request, 'projetos_institucionais/aprovacao_centro.html', {
        'solicitacao': solicitacao,
        'projeto': solicitacao.projeto,
        'form': form,
        'token': token,
    })


def aprovacao_centro_documento(request, token):
    """Exibe somente o relatório do projeto enquanto o convite estiver ativo."""
    solicitacao = _obter_solicitacao_por_token(token)
    if _motivo_link_centro_invalido(solicitacao):
        raise Http404
    relatorio = solicitacao.projeto.anexos.filter(
        tipo_anexo='relatorio_submissao',
    ).order_by('-data_upload').first()
    if not relatorio:
        raise Http404
    arquivo = relatorio.arquivo.open('rb')
    return FileResponse(
        arquivo,
        content_type='application/pdf',
        filename=f'projeto_{solicitacao.projeto_id}.pdf',
    )


@login_required
@coordenador_required
@require_POST
def reenviar_solicitacao_centro(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk, coordenador=request.user)
    if not projeto.requer_ata_conselho or projeto.status != 'aguardando_conselho':
        messages.warning(request, 'Este projeto não está aguardando a ata do Centro.')
        return redirect('projeto_detalhe', pk=pk)
    if not projeto.centro_lotacao or not projeto.centro_lotacao.email:
        messages.error(request, 'O Centro de Lotação não possui e-mail cadastrado.')
        return redirect('projeto_detalhe', pk=pk)

    _, enviado = _emitir_solicitacao_centro(request, projeto)
    if enviado:
        messages.success(request, f'Novo link enviado para {projeto.centro_lotacao.email}.')
    else:
        messages.warning(
            request,
            'O novo link foi gerado, mas o e-mail não pôde ser enviado. Verifique a configuração de e-mail.',
        )
    return redirect('projeto_detalhe', pk=pk)


@login_required
def anexar_aprovacao_etica(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    eh_gestor = request.user.perfil == 'gestor'
    if request.user != projeto.coordenador and not eh_gestor:
        return HttpResponseForbidden('Você não tem permissão para alterar este projeto.')
    if not projeto.etica_obrigatoria:
        messages.warning(request, 'Este projeto não declarou envolvimento com aspectos éticos.')
        return redirect('projeto_detalhe', pk=pk)

    form = ComprovanteEticaAprovacaoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        Anexo.objects.create(
            projeto=projeto,
            tipo_anexo='comite_etica',
            arquivo=form.cleaned_data['comprovante'],
            descricao='Comprovante definitivo de aprovação do Comitê de Ética.',
        )
        projeto.situacao_etica = 'aprovado'
        campos = ['situacao_etica']
        if eh_gestor:
            projeto.ultima_alteracao_gestor_em = timezone.now()
            projeto.ultima_alteracao_gestor_por = request.user
            campos.extend(['ultima_alteracao_gestor_em', 'ultima_alteracao_gestor_por'])
        projeto.save(update_fields=campos)

        for gestor in Usuario.objects.filter(perfil='gestor', is_active=True):
            Notificacao.objects.create(
                destinatario=gestor,
                mensagem=f'A aprovação ética do projeto "{projeto.titulo}" foi anexada.',
                link=reverse('projeto_detalhe', args=[projeto.pk]),
            )
        messages.success(request, 'Comprovante de aprovação ética anexado com sucesso.')
        return redirect('projeto_detalhe', pk=pk)

    return render(request, 'projetos_institucionais/anexar_etica.html', {
        'projeto': projeto,
        'form': form,
    })


def _aplicar_filtro_tipo_projeto(queryset, request):
    """Aplica o filtro atual e aceita os antigos links com ?financiamento=."""
    tipo_projeto_filter = request.GET.get('tipo_projeto', '').strip()
    tipos_validos = dict(Projeto.TIPO_PROJETO_CHOICES)

    if tipo_projeto_filter in tipos_validos:
        return (
            queryset.filter(tipo_projeto=tipo_projeto_filter),
            tipo_projeto_filter,
            tipos_validos[tipo_projeto_filter],
        )

    financiamento_legacy = request.GET.get('financiamento', '').strip()
    if financiamento_legacy == 'sim':
        return (
            queryset.filter(tipo_projeto__in=[
                Projeto.TIPO_PROJETO_AGENCIA_FOMENTO,
                Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
            ]),
            '',
            'Com financiamento',
        )
    if financiamento_legacy == 'nao':
        return (
            queryset.filter(tipo_projeto=Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO),
            '',
            'Sem financiamento',
        )

    return queryset, '', ''


def _obter_filtro_ods(request):
    """Lê a seleção múltipla de ODS e normaliza o modo de combinação."""
    ods_filters = list(dict.fromkeys(
        valor for valor in request.GET.getlist('ods') if valor.isdigit()
    ))
    ods_match = request.GET.get('ods_match', 'all').strip().lower()
    if ods_match not in {'all', 'any'}:
        ods_match = 'all'
    return ods_filters, ods_match


def _aplicar_filtro_ods(queryset, ods_filters, ods_match='all'):
    """Filtra por todas as ODS selecionadas (AND) ou por qualquer uma (OR)."""
    if not ods_filters:
        return queryset
    if ods_match == 'any':
        return queryset.filter(ods__pk__in=ods_filters).distinct()

    # Filtros relacionais em chamadas separadas exigem que o mesmo projeto
    # possua cada ODS selecionada, implementando a combinação AND.
    for ods_pk in ods_filters:
        queryset = queryset.filter(ods__pk=ods_pk)
    return queryset.distinct()


def _ods_disponiveis_com_projetos():
    """Retorna as ODS usadas em projetos em ordem numérica natural."""
    ods = ODS.objects.filter(projeto__isnull=False).distinct()

    def chave_numerica(obj):
        correspondencia = re.search(r'\bODS\s*(\d+)', obj.titulo or '', re.IGNORECASE)
        numero = int(correspondencia.group(1)) if correspondencia else 999
        return numero, (obj.titulo or '').casefold()

    return sorted(ods, key=chave_numerica)


def _filtrar_consulta_publica_por_texto(queryset, consulta):
    """Busca por título, resumo ou por todos os termos do nome do coordenador."""
    if not consulta:
        return queryset

    filtro_texto = Q(titulo__icontains=consulta) | Q(resumo__icontains=consulta)
    filtro_nome = _filtro_nome_completo(
        consulta,
        'coordenador__first_name',
        'coordenador__last_name',
    )
    return queryset.filter(filtro_texto | filtro_nome)


def _filtro_nome_completo(consulta, campo_nome, campo_sobrenome):
    """Exige cada termo da busca em pelo menos uma parte do nome completo."""
    filtro = Q()
    for termo in consulta.split():
        filtro &= (
            Q(**{f'{campo_nome}__icontains': termo})
            | Q(**{f'{campo_sobrenome}__icontains': termo})
        )
    return filtro


def consulta_publica(request):
    queryset = Projeto.objects.filter(
        status__in=['aprovado', 'em_andamento', 'finalizado', 'encerrado']
    ).select_related('coordenador', 'centro_lotacao', 'curso').order_by('-data_inicio')
    q                  = request.GET.get('q', '').strip()
    centro_filter      = request.GET.get('centro', '').strip()
    curso_filter       = request.GET.get('curso', '').strip()
    status_filter      = request.GET.get('status', '').strip()
    ano_filter         = request.GET.get('ano', '').strip()
    ods_filters, ods_match = _obter_filtro_ods(request)
    queryset = _filtrar_consulta_publica_por_texto(queryset, q)
    if centro_filter:        queryset = queryset.filter(centro_lotacao__pk=centro_filter)
    if curso_filter:         queryset = queryset.filter(curso__pk=curso_filter)
    if status_filter:        queryset = queryset.filter(status=status_filter)
    if ano_filter:           queryset = queryset.filter(data_inicio__year=ano_filter)
    queryset = _aplicar_filtro_ods(queryset, ods_filters, ods_match)
    queryset, tipo_projeto_filter, tipo_projeto_filter_label = _aplicar_filtro_tipo_projeto(queryset, request)
    from projetos_institucionais.models import CentroLotacao, CursoGraduacao
    centros = CentroLotacao.objects.filter(projeto__isnull=False).distinct().order_by('nome')
    cursos  = CursoGraduacao.objects.filter(projeto__isnull=False).distinct().order_by('nome')
    ods_disponiveis = _ods_disponiveis_com_projetos()
    anos    = Projeto.objects.filter(status__in=['aprovado','em_andamento','finalizado','encerrado']).exclude(data_inicio__isnull=True).dates('data_inicio','year',order='DESC')
    paginator = Paginator(queryset, 12)
    page_obj  = paginator.get_page(request.GET.get('page'))
    return render(request, 'projetos_institucionais/consulta_publica.html', {
        'page_obj': page_obj, 'q': q, 'centro_filter': centro_filter,
        'curso_filter': curso_filter, 'status_filter': status_filter,
        'ano_filter': ano_filter,
        'ods_filters': ods_filters,
        'ods_match': ods_match,
        'tipo_projeto_filter': tipo_projeto_filter,
        'tipo_projeto_filter_label': tipo_projeto_filter_label,
        'tipo_projeto_choices': Projeto.TIPO_PROJETO_CHOICES,
        'centros': centros, 'cursos': cursos, 'ods_disponiveis': ods_disponiveis,
        'anos': anos, 'total': queryset.count(),
    })


def projeto_detalhe_publico(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk, status__in=['aprovado', 'em_andamento', 'finalizado', 'encerrado'])
    return render(request, 'projetos_institucionais/projeto_detalhe_publico.html', {'projeto': projeto})


def consulta_publica_pdf(request):
    """Gera PDF da consulta pública com os filtros ativos."""
    queryset = Projeto.objects.filter(
        status__in=['aprovado', 'em_andamento', 'finalizado', 'encerrado']
    ).select_related('coordenador', 'centro_lotacao', 'curso').order_by('-data_inicio')

    q             = request.GET.get('q', '').strip()
    centro_filter = request.GET.get('centro', '').strip()
    curso_filter  = request.GET.get('curso', '').strip()
    status_filter = request.GET.get('status', '').strip()
    ano_filter    = request.GET.get('ano', '').strip()
    ods_filters, ods_match = _obter_filtro_ods(request)

    queryset = _filtrar_consulta_publica_por_texto(queryset, q)
    if centro_filter: queryset = queryset.filter(centro_lotacao__pk=centro_filter)
    if curso_filter:  queryset = queryset.filter(curso__pk=curso_filter)
    if status_filter: queryset = queryset.filter(status=status_filter)
    if ano_filter:    queryset = queryset.filter(data_inicio__year=ano_filter)
    queryset = _aplicar_filtro_ods(queryset, ods_filters, ods_match)
    queryset, _, tipo_projeto_filter_label = _aplicar_filtro_tipo_projeto(queryset, request)

    filtros_ativos = {}
    if q:             filtros_ativos['Busca']  = q
    if status_filter: filtros_ativos['Status'] = {'aprovado': 'Aprovado', 'em_andamento': 'Em Andamento', 'finalizado': 'Finalizado', 'encerrado': 'Encerrado sem conclusão'}.get(status_filter, status_filter)
    if ano_filter:    filtros_ativos['Ano'] = ano_filter
    if tipo_projeto_filter_label:
        filtros_ativos['Tipo do Projeto'] = tipo_projeto_filter_label
    if ods_filters:
        nomes = list(ODS.objects.filter(pk__in=ods_filters).values_list('titulo', flat=True))
        filtros_ativos['Vínculo com ODS'] = ', '.join(nomes)
        filtros_ativos['Combinação ODS'] = 'Qualquer ODS (OR)' if ods_match == 'any' else 'Todas as ODS (AND)'
    if centro_filter:
        from projetos_institucionais.models import CentroLotacao
        try: filtros_ativos['Centro'] = CentroLotacao.objects.get(pk=centro_filter).nome
        except Exception: pass
    if curso_filter:
        from projetos_institucionais.models import CursoGraduacao
        try: filtros_ativos['Curso'] = CursoGraduacao.objects.get(pk=curso_filter).nome
        except Exception: pass

    html_string = render_to_string(
        'projetos_institucionais/consulta_publica_pdf.html',
        {'projetos': queryset, 'filtros_ativos': filtros_ativos,
         'data_geracao': date.today(), 'total': queryset.count()},
    )
    pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    from django.http import HttpResponse
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename="consulta_publica_projetos.pdf"'
    return resp

def projeto_deletar(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk, coordenador=request.user)
    if request.method == 'POST':
        projeto.delete()
        messages.success(request, 'Projeto excluído com sucesso.')
        return redirect(f"{reverse('projeto_dashboard')}?tab=rascunhos")
    return render(request, 'projetos_institucionais/projeto_confirmar_delete.html', {'projeto': projeto})

@login_required
@coordenador_required
def projeto_dashboard(request):
    active_tab = request.GET.get('tab', 'visao_geral')

    # Parâmetros de busca/filtro
    q            = request.GET.get('q', '').strip()
    filtro_centro = request.GET.get('centro', '').strip()
    filtro_data_inicio = request.GET.get('data_inicio', '').strip()
    filtro_data_fim    = request.GET.get('data_fim', '').strip()

    base_qs = Projeto.objects.filter(coordenador=request.user)

    projetos_em_andamento = base_qs.filter(status='em_andamento')
    projetos_em_revisao   = base_qs.filter(
        Q(status='submetido') | Q(status='aguardando_conselho') | Q(status='aguardando_encerramento')
    )
    projetos_rejeitados   = base_qs.filter(status='reprovado')
    projetos_finalizados  = base_qs.filter(status='finalizado')
    projetos_encerrados   = base_qs.filter(status='encerrado')
    projetos_avaliados    = base_qs.filter(status__in=['aprovado', 'reprovado'])
    count_rascunhos       = base_qs.filter(status='rascunho').count()

    # Dados para filtros
    todos_projetos = base_qs.exclude(status='rascunho')
    centros_disponiveis = sorted(set(
        todos_projetos.exclude(centro_lotacao=None)
                      .values_list('centro_lotacao__nome', flat=True)
    ))

    tabs = [
        ('visao_geral',  'Visão Geral',         0,                              ''),
        ('rascunhos',    'Rascunhos',            count_rascunhos,                'bg-warning text-dark'),
        ('em_andamento', 'Em Andamento',         projetos_em_andamento.count(),  'bg-primary'),
        ('em_revisao',   'Em Revisão',           projetos_em_revisao.count(),    'bg-warning text-dark'),
        ('avaliados',    'Aprovados/Rejeitados', projetos_avaliados.count(),     'bg-secondary'),
        ('finalizados',  'Finalizados',          projetos_finalizados.count(),   'bg-success'),
        ('encerrados',   'Encerrados',           projetos_encerrados.count(),    'bg-secondary'),
    ]

    visao_geral_cols = [
        ('Em Andamento',  list(projetos_em_andamento), '#0d6efd', 'bi-play-circle-fill'),
        ('Em Revisão',    list(projetos_em_revisao),   '#ffc107', 'bi-hourglass-split'),
        ('Finalizados',   list(projetos_finalizados),  '#198754', 'bi-check-circle-fill'),
    ]

    contexto = {
        'active_tab':             active_tab,
        'AnexoForm':              AnexoForm(),
        'count_rascunhos':        count_rascunhos,
        'tabs':                   tabs,
        'visao_geral_cols':       visao_geral_cols,
        'projetos_em_andamento':  projetos_em_andamento,
        'projetos_em_revisao':    projetos_em_revisao,
        'projetos_rejeitados':    projetos_rejeitados,
        'projetos_finalizados':   projetos_finalizados,
        'projetos_encerrados':    projetos_encerrados,
        'count_finalizados':      projetos_finalizados.count(),
        'count_avaliados':        projetos_avaliados.count(),
        'q':                      q,
        'filtro_centro':          filtro_centro,
        'filtro_data_inicio':     filtro_data_inicio,
        'filtro_data_fim':        filtro_data_fim,
        'centros_disponiveis':    centros_disponiveis,
    }

    if active_tab == 'rascunhos':
        rascunhos = Projeto.objects.filter(coordenador=request.user, status='rascunho').order_by('-id')
        if q:
            rascunhos = rascunhos.filter(titulo__icontains=q)
        contexto['rascunhos'] = rascunhos

    elif active_tab not in ('visao_geral', 'rascunhos'):
        status_map = {
            'em_andamento': (['em_andamento'],                                    'Projetos em Andamento'),
            'em_revisao':   (['submetido', 'aguardando_conselho',
                              'aguardando_encerramento'],                          'Projetos em Revisão'),
            'finalizados':  (['finalizado'],                                      'Projetos Finalizados'),
            'encerrados':   (['encerrado'],                                       'Projetos Encerrados sem Conclusão'),
            'avaliados':    (['aprovado', 'reprovado'],                           'Projetos Aprovados e Rejeitados'),
        }
        status_filter, table_title = status_map.get(active_tab, ([], ''))
        if status_filter:
            qs = Projeto.objects.filter(
                coordenador=request.user, status__in=status_filter
            ).order_by('-data_inicio')

            # Aplicar filtros de busca
            if q:
                qs = qs.filter(titulo__icontains=q)
            if filtro_centro:
                qs = qs.filter(centro_lotacao__nome=filtro_centro)
            if filtro_data_inicio:
                qs = qs.filter(data_inicio__gte=filtro_data_inicio)
            if filtro_data_fim:
                qs = qs.filter(data_inicio__lte=filtro_data_fim)

            paginator = Paginator(qs, 10)
            contexto['page_obj']    = paginator.get_page(request.GET.get('page'))
            contexto['table_title'] = table_title

    return render(request, 'projetos_institucionais/meusprojetos.html', contexto)

@login_required
@aluno_required
@login_required
def aluno_projeto_dashboard(request):
    from django.db.models import Q
    participacoes = EquipeProjeto.objects.filter(
        membro=request.user
    ).select_related('projeto', 'projeto__coordenador').order_by('-projeto__data_inicio')

    # Filtros
    q         = request.GET.get('q', '').strip()
    status_f  = request.GET.get('status', '').strip()

    if q:
        participacoes = participacoes.filter(projeto__titulo__icontains=q)
    if status_f:
        participacoes = participacoes.filter(projeto__status=status_f)

    total             = participacoes.count()
    em_andamento      = participacoes.filter(projeto__status='em_andamento').count()
    finalizados       = participacoes.filter(projeto__status='finalizado').count()
    encerrados        = participacoes.filter(projeto__status='encerrado').count()

    paginator = Paginator(participacoes, 10)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'projetos_institucionais/aluno_projeto_dashboard.html', {
        'page_obj':    page_obj,
        'total':       total,
        'em_andamento': em_andamento,
        'encerrados':  encerrados,
        'finalizados': finalizados,
        'q':           q,
        'status_f':    status_f,
    })

@login_required
@login_required
@gestor_required
def gestor_dashboard(request):
    projetos_pendentes              = Projeto.objects.filter(status='submetido').select_related('coordenador', 'centro_lotacao').order_by('data_inicio')
    projetos_aguardando_centro = Projeto.objects.filter(
        status='aguardando_conselho',
        tipo_projeto=Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
    ).select_related('coordenador', 'centro_lotacao').order_by('data_inicio')
    projetos_aguardando_encerramento = Projeto.objects.filter(status='aguardando_encerramento').select_related('coordenador', 'centro_lotacao').order_by('data_fim')

    # Aba ativa
    aba = request.GET.get('aba', 'submetidos')

    contexto = {
        'projetos_pendentes':              projetos_pendentes,
        'projetos_aguardando_centro':    projetos_aguardando_centro,
        'projetos_aguardando_encerramento': projetos_aguardando_encerramento,
        'count_submetidos':      projetos_pendentes.count(),
        'count_aguardando_centro':        projetos_aguardando_centro.count(),
        'count_encerramento':    projetos_aguardando_encerramento.count(),
        'aba':                   aba,
    }
    return render(request, 'projetos_institucionais/gestordashboard.html', contexto)

@gestor_required
def aprovar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    if projeto.etica_pendente:
        messages.error(
            request,
            'O projeto não pode ser aprovado enquanto o comprovante definitivo de aprovação ética estiver pendente.',
        )
        return redirect('projeto_detalhe', pk=pk)

    pode_avaliar = (
        projeto.status == 'submetido'
        or (projeto.status == 'aguardando_conselho' and projeto.requer_tramitacao_centro)
    )
    if not pode_avaliar:
        messages.warning(request, 'Este projeto ainda não está disponível para aprovação pela PROPEG.')
        return redirect('gestor_dashboard')

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

    pode_avaliar = (
        projeto.status == 'submetido'
        or (projeto.status == 'aguardando_conselho' and projeto.requer_tramitacao_centro)
    )
    if not pode_avaliar:
        messages.warning(request, 'Este projeto ainda não está disponível para avaliação pela PROPEG.')
        return redirect('gestor_dashboard')

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

    if projeto.etica_pendente:
        messages.error(
            request,
            'Anexe o comprovante definitivo de aprovação ética antes de iniciar o projeto.',
        )
        return redirect('projeto_detalhe', pk=pk)

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

        for membro_equipe in projeto.equipe.select_related('membro'):
            if membro_equipe.membro_id:
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

@login_required
@gestor_required
def gerenciar_usuarios(request):
    queryset = Usuario.objects.exclude(pk=request.user.pk).order_by('first_name')

    query         = request.GET.get('q', '').strip()
    perfil_filter = request.GET.get('perfil', '').strip()
    status_filter = request.GET.get('status', '').strip()
    sort_by       = request.GET.get('sort', 'first_name')

    if query:
        filtro_nome = _filtro_nome_completo(query, 'first_name', 'last_name')
        queryset = queryset.filter(
            filtro_nome |
            Q(cpf__icontains=query)        |
            Q(email__icontains=query)
        )
    if perfil_filter in ['aluno', 'coordenador', 'gestor']:
        queryset = queryset.filter(perfil=perfil_filter)
    if status_filter == 'ativo':
        queryset = queryset.filter(is_active=True)
    elif status_filter == 'inativo':
        queryset = queryset.filter(is_active=False)

    sortable = ['first_name', '-first_name', 'email', '-email',
                'perfil', '-perfil', 'date_joined', '-date_joined']
    if sort_by in sortable:
        queryset = queryset.order_by(sort_by)

    try:
        per_page = int(request.GET.get('per_page', 10))
        if per_page not in [5, 7, 10, 15, 20]:
            per_page = 10
    except (ValueError, TypeError):
        per_page = 10

    todos = Usuario.objects.exclude(pk=request.user.pk)
    contadores = {
        'total':         todos.count(),
        'ativos':        todos.filter(is_active=True).count(),
        'inativos':      todos.filter(is_active=False).count(),
        'coordenadores': todos.filter(perfil='coordenador', is_active=True).count(),
        'alunos':        todos.filter(perfil='aluno', is_active=True).count(),
        'gestores':      todos.filter(perfil='gestor', is_active=True).count(),
    }

    paginator = Paginator(queryset, per_page)
    pagina_de_usuarios = paginator.get_page(request.GET.get('page'))

    return render(request, 'projetos_institucionais/gerenciar_usuarios.html', {
        'pagina_de_usuarios': pagina_de_usuarios,
        'query':         query,
        'perfil_filter': perfil_filter,
        'status_filter': status_filter,
        'sort_by':       sort_by,
        'per_page':      per_page,
        'perfil_choices': Usuario.PERFIL_CHOICES,
        'contadores':    contadores,
    })


@login_required
@gestor_required
def toggle_usuario_status(request, pk):
    """Ativa ou inativa um usuário via POST (toggle rápido)."""
    if request.method == 'POST':
        usuario = get_object_or_404(Usuario, pk=pk)
        if usuario == request.user:
            messages.error(request, 'Você não pode alterar seu próprio status.')
            return redirect('gerenciar_usuarios')

        usuario.is_active = not usuario.is_active
        usuario.status    = 'ativo' if usuario.is_active else 'inativo'
        usuario.save()

        if usuario.is_active:
            subject = 'Sua conta na Plataforma PROPEG foi ativada!'
            message = (
                f'Olá, {usuario.first_name}!\n\n'
                f'Sua conta foi reativada. Você já pode acessar o sistema.\n\n'
                f'Atenciosamente,\nEquipe PROPEG'
            )
            enviar_email_e_notificacao(subject, message, usuario)
            messages.success(request, f'Usuário "{usuario.get_full_name()}" ativado com sucesso.')
        else:
            subject = 'Aviso: Sua conta na Plataforma PROPEG foi inativada'
            message = (
                f'Olá, {usuario.first_name}.\n\n'
                f'Sua conta foi inativada. Entre em contato com a administração se acreditar que houve engano.\n\n'
                f'Atenciosamente,\nEquipe PROPEG'
            )
            enviar_email_e_notificacao(subject, message, usuario)
            messages.warning(request, f'Usuário "{usuario.get_full_name()}" inativado.')

    # Preserva os filtros ao redirecionar
    params = request.POST.get('next', '')
    return redirect(params or 'gerenciar_usuarios')

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
                enviar_email_e_notificacao(subject, message, user)
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

@login_required
@gestor_required
def historico_projetos(request):
    queryset = Projeto.objects.exclude(status="rascunho")\
        .select_related("coordenador", "centro_lotacao", "curso")\
        .order_by("-data_inicio")

    query          = request.GET.get("q", "").strip()
    status_filters = request.GET.getlist("status")
    data_inicio_filter = request.GET.get("data_inicio", "").strip()
    data_fim_filter    = request.GET.get("data_fim", "").strip()
    centro_filters = request.GET.getlist("centro")
    curso_filters  = request.GET.getlist("curso")
    ods_filters, ods_match = _obter_filtro_ods(request)
    sort_by        = request.GET.get("sort", "-data_inicio")
    try:
        per_page = int(request.GET.get("per_page", 10))
        if per_page not in [5, 7, 10, 15, 20]:
            per_page = 10
    except (ValueError, TypeError):
        per_page = 10

    if query:
        queryset = queryset.filter(
            Q(titulo__icontains=query) |
            Q(coordenador__first_name__icontains=query) |
            Q(coordenador__last_name__icontains=query)
        )
    if status_filters:
        queryset = queryset.filter(status__in=status_filters)
    if data_inicio_filter:
        queryset = queryset.filter(data_inicio__gte=data_inicio_filter)
    if data_fim_filter:
        queryset = queryset.filter(data_inicio__lte=data_fim_filter)
    if centro_filters:
        queryset = queryset.filter(centro_lotacao__pk__in=centro_filters)
    if curso_filters:
        queryset = queryset.filter(curso__pk__in=curso_filters)
    queryset = _aplicar_filtro_ods(queryset, ods_filters, ods_match)
    queryset, tipo_projeto_filter, tipo_projeto_filter_label = _aplicar_filtro_tipo_projeto(queryset, request)

    allowed_sort = [
        "titulo", "-titulo",
        "coordenador__first_name", "-coordenador__first_name",
        "data_inicio", "-data_inicio",
        "data_fim", "-data_fim",
        "status", "-status",
        "centro_lotacao__nome", "-centro_lotacao__nome",
    ]
    if sort_by in allowed_sort:
        queryset = queryset.order_by(sort_by)

    from projetos_institucionais.models import CentroLotacao, CursoGraduacao
    anos_disponiveis    = Projeto.objects.exclude(data_inicio__isnull=True)\
        .dates("data_inicio", "year", order="DESC")
    centros_disponiveis = CentroLotacao.objects.filter(
        projeto__isnull=False).distinct().order_by("nome")
    try:
        cursos_disponiveis = CursoGraduacao.objects.filter(
            projeto__isnull=False).distinct().order_by("nome")
    except Exception:
        cursos_disponiveis = []
    ods_disponiveis = _ods_disponiveis_com_projetos()

    todos = Projeto.objects.exclude(status="rascunho")
    contadores = {
        "total":      todos.count(),
        "andamento":  todos.filter(status="em_andamento").count(),
        "finalizados": todos.filter(status="finalizado").count(),
        "encerrados": todos.filter(status="encerrado").count(),
        "submetidos": todos.filter(status="submetido").count(),
    }

    paginator          = Paginator(queryset, per_page)
    pagina_de_projetos = paginator.get_page(request.GET.get("page"))

    return render(request, "projetos_institucionais/historico_projetos.html", {
        "pagina_de_projetos":  pagina_de_projetos,
        "status_choices":      [c for c in Projeto.STATUS_CHOICES if c[0] != "rascunho"],
        "anos_disponiveis":    anos_disponiveis,
        "centros_disponiveis": centros_disponiveis,
        "cursos_disponiveis":  cursos_disponiveis,
        "ods_disponiveis":     ods_disponiveis,
        "query":          query,
        "status_filters": status_filters,
        "data_inicio_filter": data_inicio_filter,
        "data_fim_filter":    data_fim_filter,
        "centro_filters": centro_filters,
        "curso_filters":  curso_filters,
        "ods_filters":    ods_filters,
        "ods_match":      ods_match,
        "tipo_projeto_filter": tipo_projeto_filter,
        "tipo_projeto_filter_label": tipo_projeto_filter_label,
        "tipo_projeto_choices": Projeto.TIPO_PROJETO_CHOICES,
        "sort_by":       sort_by,
        "per_page":      per_page,
        "contadores":    contadores,
    })


@login_required
@gestor_required
def historico_projetos_pdf(request):
    queryset = Projeto.objects.exclude(status="rascunho")\
        .select_related("coordenador", "centro_lotacao", "curso")\
        .order_by("-data_inicio")
    query          = request.GET.get("q", "").strip()
    status_filters = request.GET.getlist("status")
    data_inicio_filter = request.GET.get("data_inicio", "").strip()
    data_fim_filter    = request.GET.get("data_fim", "").strip()
    centro_filters = request.GET.getlist("centro")
    curso_filters  = request.GET.getlist("curso")
    ods_filters, ods_match = _obter_filtro_ods(request)
    if query:
        queryset = queryset.filter(
            Q(titulo__icontains=query) |
            Q(coordenador__first_name__icontains=query) |
            Q(coordenador__last_name__icontains=query)
        )
    if status_filters: queryset = queryset.filter(status__in=status_filters)
    if data_inicio_filter: queryset = queryset.filter(data_inicio__gte=data_inicio_filter)
    if data_fim_filter:    queryset = queryset.filter(data_inicio__lte=data_fim_filter)
    if centro_filters: queryset = queryset.filter(centro_lotacao__pk__in=centro_filters)
    if curso_filters:  queryset = queryset.filter(curso__pk__in=curso_filters)
    queryset = _aplicar_filtro_ods(queryset, ods_filters, ods_match)
    queryset, _, tipo_projeto_filter_label = _aplicar_filtro_tipo_projeto(queryset, request)

    filtros_ativos = {}
    if query:          filtros_ativos["Busca"]        = query
    if status_filters:
        sd = dict(Projeto.STATUS_CHOICES)
        filtros_ativos["Status"] = ", ".join(sd.get(s, s) for s in status_filters)
    if data_inicio_filter: filtros_ativos["Data Início"] = data_inicio_filter
    if data_fim_filter:    filtros_ativos["Data Fim"]    = data_fim_filter
    if tipo_projeto_filter_label:
        filtros_ativos["Tipo do Projeto"] = tipo_projeto_filter_label
    if centro_filters:
        from projetos_institucionais.models import CentroLotacao
        nomes = list(CentroLotacao.objects.filter(pk__in=centro_filters).values_list("nome", flat=True))
        filtros_ativos["Centro"] = ", ".join(nomes)
    if curso_filters:
        from projetos_institucionais.models import CursoGraduacao
        nomes = list(CursoGraduacao.objects.filter(pk__in=curso_filters).values_list("nome", flat=True))
        filtros_ativos["Curso"]  = ", ".join(nomes)
    if ods_filters:
        nomes = list(ODS.objects.filter(pk__in=ods_filters).values_list('titulo', flat=True))
        filtros_ativos['Vínculo com ODS'] = ', '.join(nomes)
        filtros_ativos['Combinação ODS'] = 'Qualquer ODS (OR)' if ods_match == 'any' else 'Todas as ODS (AND)'

    html_string = render_to_string(
        "projetos_institucionais/historico_pdf.html",
        {"projetos": queryset, "filtros_ativos": filtros_ativos,
         "data_geracao": date.today(), "total": queryset.count()},
    )
    pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri("/")).write_pdf()
    from django.http import HttpResponse
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = "attachment; filename=\"historico_projetos.pdf\""
    return resp
@login_required
@gestor_required
def encaminhar_para_conselho(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    eh_encerramento = projeto.status == 'aguardando_encerramento'

    # Agência de fomento já possui aprovação externa e o fluxo contínuo já traz a ata.
    if not projeto.requer_tramitacao_centro:
        messages.warning(
            request,
            f'O tipo do projeto "{projeto.titulo}" não requer novo encaminhamento ao Centro. '
            f'Utilize a opção de Aprovar ou Encerrar diretamente.'
        )
        return redirect('gestor_dashboard')

    if projeto.status in ('submetido', 'aguardando_encerramento'):
        projeto.status = 'aguardando_conselho'
        projeto.save()

        # Busca o documento mais relevante para anexar
        relatorio_anexo = (
            projeto.relatorios.order_by('-data_envio').first()
            if eh_encerramento
            else projeto.anexos.filter(tipo_anexo='relatorio_submissao').order_by('-data_upload').first()
        )

        if projeto.centro_lotacao and projeto.centro_lotacao.email:
            if eh_encerramento:
                subject_conselho = f'Projeto para Aprovação de Encerramento pelo Centro: "{projeto.titulo}"'
                message_conselho = (
                    f'Prezados responsáveis do centro {projeto.centro_lotacao.nome},\n\n'
                    f'O projeto "{projeto.titulo}", coordenado por {projeto.coordenador.get_full_name()}, '
                    f'concluiu suas atividades e foi encaminhado para aprovação de encerramento.\n\n'
                    f'O relatório final de atividades está disponível para análise.\n\n'
                    f'Atenciosamente,\nEquipe de Gestão PROPEG'
                )
            else:
                subject_conselho = f'Novo Projeto para Análise do Centro: "{projeto.titulo}"'
                message_conselho = (
                    f'Prezados responsáveis do centro {projeto.centro_lotacao.nome},\n\n'
                    f'O projeto "{projeto.titulo}", coordenado por {projeto.coordenador.get_full_name()}, foi encaminhado para sua análise e aprovação.\n\n'
                    f'O relatório de submissão do projeto está anexado a este email para sua conveniência.\n\n'
                    f'Atenciosamente,\nEquipe de Gestão PROPEG'
                )

            brevo_key = getattr(settings, 'BREVO_API_KEY', '')
            if brevo_key:
                try:
                    import sib_api_v3_sdk
                    configuration = sib_api_v3_sdk.Configuration()
                    configuration.api_key['api-key'] = brevo_key
                    api = sib_api_v3_sdk.TransactionalEmailsApi(
                        sib_api_v3_sdk.ApiClient(configuration)
                    )
                    params = {
                        'to': [{"email": projeto.centro_lotacao.email,
                                "name": projeto.centro_lotacao.nome}],
                        'sender': {"email": settings.DEFAULT_FROM_EMAIL, "name": "PROPEG/UFAC"},
                        'subject': subject_conselho,
                        'text_content': message_conselho,
                    }
                    if relatorio_anexo:
                        arquivo = relatorio_anexo.anexo_pdf if eh_encerramento else relatorio_anexo.arquivo
                        if arquivo:
                            import base64
                            try:
                                pdf_bytes = arquivo.read()
                                params['attachment'] = [{
                                    'content': base64.b64encode(pdf_bytes).decode('utf-8'),
                                    'name': arquivo.name.split('/')[-1],
                                }]
                            except Exception as e:
                                print(f'Erro ao anexar PDF: {e}')
                    api.send_transac_email(sib_api_v3_sdk.SendSmtpEmail(**params))
                except Exception as e:
                    print(f'Erro Brevo centro: {e}')
            else:
                try:
                    email_conselho = EmailMessage(
                        subject_conselho, message_conselho,
                        settings.DEFAULT_FROM_EMAIL,
                        [projeto.centro_lotacao.email],
                    )
                    if relatorio_anexo:
                        arquivo = relatorio_anexo.anexo_pdf if eh_encerramento else relatorio_anexo.arquivo
                        if arquivo:
                            email_conselho.attach(arquivo.name.split('/')[-1], arquivo.read(), 'application/pdf')
                    email_conselho.send()
                except Exception as e:
                    print(f'Erro email conselho: {e}')

        if eh_encerramento:
            msg_coord = (
                f'Olá, {projeto.coordenador.first_name}!\n\n'
                f'Seu projeto "{projeto.titulo}" foi encaminhado para aprovação de encerramento pelo centro do seu centro.\n\n'
                f'Você será notificado assim que houver uma decisão.\n\n'
                f'Atenciosamente,\nEquipe PROPEG'
            )
            msg_sucesso = f'O projeto "{projeto.titulo}" foi encaminhado ao centro para aprovação de encerramento.'
        else:
            msg_coord = (
                f'Olá, {projeto.coordenador.first_name}!\n\n'
                f'Seu projeto "{projeto.titulo}" foi encaminhado para análise do centro do seu centro de lotação.\n\n'
                f'O status foi atualizado para "Aguardando aprovação do centro". Você será notificado sobre as próximas etapas.\n\n'
                f'Atenciosamente,\nEquipe PROPEG'
            )
            msg_sucesso = f'O projeto "{projeto.titulo}" foi encaminhado ao centro e o coordenador foi notificado.'

        link_projeto = request.build_absolute_uri(reverse('projeto_detalhe', args=[projeto.pk]))
        enviar_email_e_notificacao(msg_sucesso.split('"')[0], msg_coord, projeto.coordenador, link=link_projeto)
        messages.success(request, msg_sucesso)
    else:
        messages.warning(request, f'O projeto "{projeto.titulo}" não pode ser encaminhado ao centro no status atual.')

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
def deletar_anexo(request, anexo_id):
    anexo = get_object_or_404(Anexo, pk=anexo_id)
    if request.user != anexo.projeto.coordenador and request.user.perfil != 'gestor':
        return HttpResponseForbidden("Você não tem permissão para realizar esta ação.")
    
    if request.method == 'POST':
        anexo.arquivo.delete(save=True)
        projeto = anexo.projeto
        anexo.delete()
        if request.user.perfil == 'gestor':
            _registrar_alteracao_gestor(projeto, request.user)
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
        if request.user != projeto.coordenador and request.user.perfil != 'gestor':
            return HttpResponseForbidden("Você não tem permissão para realizar esta ação.")
        
        form = AnexoForm(request.POST, request.FILES)
        if form.is_valid():
            anexo = form.save(commit=False)
            anexo.projeto = projeto
            anexo.save()
            if request.user.perfil == 'gestor':
                _registrar_alteracao_gestor(projeto, request.user)
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
    Envia um email (via Brevo API ou SMTP) e cria uma notificação no sistema.
    """
    brevo_key = getattr(settings, 'BREVO_API_KEY', '')
    if brevo_key:
        # Produção: usa API HTTP do Brevo (funciona no Render free)
        try:
            import sib_api_v3_sdk
            from sib_api_v3_sdk.rest import ApiException
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key['api-key'] = brevo_key
            api = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )
            nome = destinatario_usuario.get_full_name() or destinatario_usuario.username
            email_obj = sib_api_v3_sdk.SendSmtpEmail(
                to=[{"email": destinatario_usuario.email, "name": nome}],
                sender={"email": settings.DEFAULT_FROM_EMAIL, "name": "PROPEG/UFAC"},
                subject=subject,
                text_content=message,
            )
            api.send_transac_email(email_obj)
        except Exception as e:
            print(f"Erro Brevo: {e}")
    else:
        # Desenvolvimento: usa backend configurado no settings (console ou SMTP)
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL,
                      [destinatario_usuario.email], fail_silently=True)
        except Exception as e:
            print(f"Erro send_mail: {e}")

    # Cria a notificação no sistema independentemente do e-mail
    Notificacao.objects.create(
        destinatario=destinatario_usuario,
        mensagem=message,
        link=link
    )


@login_required
def lista_notificacoes(request):
    qs = Notificacao.objects.filter(destinatario=request.user).order_by('-data_criacao')

    # Marca todas como lidas ao acessar
    qs.filter(lida=False).update(lida=True)

    # Busca por conteúdo
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(mensagem__icontains=q)

    # Filtro por data
    data_de  = request.GET.get('data_de', '')
    data_ate = request.GET.get('data_ate', '')
    if data_de:
        qs = qs.filter(data_criacao__date__gte=data_de)
    if data_ate:
        qs = qs.filter(data_criacao__date__lte=data_ate)

    # Paginação: 50 por página
    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'projetos_institucionais/notificacoes.html', {
        'page_obj':  page_obj,
        'q':         q,
        'data_de':   data_de,
        'data_ate':  data_ate,
        'total':     qs.count(),
    })


@login_required
def excluir_notificacao(request, pk):
    notificacao = get_object_or_404(Notificacao, pk=pk, destinatario=request.user)
    if request.method == 'POST':
        notificacao.delete()
    return redirect('lista_notificacoes')


@login_required
def excluir_notificacoes_em_massa(request):
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        if ids:
            Notificacao.objects.filter(
                pk__in=ids, destinatario=request.user
            ).delete()
        elif request.POST.get('excluir_todas'):
            Notificacao.objects.filter(destinatario=request.user).delete()
    return redirect('lista_notificacoes')

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
        form = RelatorioForm(request.POST, request.FILES)
        if form.is_valid():
            dados = form.cleaned_data

            contexto_pdf = {
                'projeto':        projeto,
                'dados':          dados,
                'data_geracao':   date.today(),
            }
            html_string = render_to_string(
                'projetos_institucionais/relatorio_pdf_template.html',
                contexto_pdf,
            )
            pdf_file = HTML(
                string=html_string,
                base_url=request.build_absolute_uri(),
            ).write_pdf()

            tipo = dados['tipo_relatorio']
            nome_arquivo = f'relatorio_{tipo}_projeto_{projeto.pk}.pdf'
            arquivo_pdf_django = ContentFile(pdf_file, name=nome_arquivo)

            novo_relatorio = Relatorio.objects.create(
                projeto=projeto,
                responsavel=request.user,
                tipo=tipo,
                anexo_pdf=arquivo_pdf_django,
            )

            # Salvar evidências
            from .models import EvidenciaRelatorio
            for arq in request.FILES.getlist('evidencias'):
                EvidenciaRelatorio.objects.create(
                    relatorio=novo_relatorio,
                    arquivo=arq,
                    descricao=arq.name,
                )

            if novo_relatorio.tipo == 'final':
                projeto.status = 'aguardando_encerramento'
                projeto.save()

                gestores = Usuario.objects.filter(perfil='gestor', is_active=True)
                subject = f'Relatório Final Submetido: "{projeto.titulo}"'
                message = (
                    f'O coordenador {projeto.coordenador.get_full_name()} submeteu o '
                    f'relatório final para o projeto "{projeto.titulo}".\n\n'
                    f'O projeto agora está pronto para sua análise e finalização.'
                )
                link_projeto = request.build_absolute_uri(
                    reverse('projeto_detalhe', args=[projeto.pk])
                )
                for gestor in gestores:
                    enviar_email_e_notificacao(subject, message, gestor, link=link_projeto)

            messages.success(request, 'Relatório enviado com sucesso e salvo no projeto.')
            return redirect('projeto_detalhe', pk=projeto.pk)
    else:
        # Pré-preenche apenas objetivos e período (metodologia deve ser preenchida pelo usuário)
        form = RelatorioForm(initial={
            'objetivo_geral':        projeto.objetivo_geral or '',
            'objetivos_especificos': projeto.objetivos_especificos or '',
            'periodo_inicio':        projeto.data_inicio,
            'periodo_fim':           projeto.data_fim,
        })

    contexto = {
        'form':    form,
        'projeto': projeto,
    }
    return render(request, 'projetos_institucionais/relatorio_form.html', contexto)

@login_required
@gestor_required
def finalizar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    tem_relatorio_final = projeto.relatorios.filter(tipo='final').exists()

    if not tem_relatorio_final:
        messages.error(request, 'Ação não permitida: o projeto não pode ser finalizado sem a submissão do relatório final.')
        return redirect('projeto_detalhe', pk=pk)
    
    projeto.status = 'finalizado'
    projeto.finalizado_em = timezone.now()
    projeto.save(update_fields=['status', 'finalizado_em'])
    messages.success(request, 'Projeto finalizado com sucesso!')
    return redirect('projeto_detalhe', pk=pk)

@login_required
@gestor_required
def encerrar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    
    if projeto.status == 'aguardando_encerramento':
        projeto.status = 'finalizado'
        projeto.finalizado_em = timezone.now()
        projeto.save(update_fields=['status', 'finalizado_em'])

        subject = f'Seu projeto "{projeto.titulo}" foi finalizado com êxito'
        message = (
            f'Olá, {projeto.coordenador.first_name}!\n\n'
            f'Informamos que o projeto "{projeto.titulo}" foi revisado e finalizado com êxito pela gestão.\n\n'
            f'Agradecemos pelo seu trabalho e dedicação.\nEquipe PROPEG'
        )
        link_projeto = request.build_absolute_uri(reverse('projeto_detalhe', args=[projeto.pk]))
        enviar_email_e_notificacao(subject, message, projeto.coordenador, link=link_projeto)

        messages.success(request, f'O projeto "{projeto.titulo}" foi finalizado com sucesso.')
    else:
        messages.warning(request, 'Este projeto não está aguardando finalização.')

    return redirect('gestor_dashboard')


@login_required
@gestor_required
def encerrar_projeto_sem_conclusao(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if projeto.status in ('rascunho', 'finalizado', 'encerrado'):
        messages.warning(request, 'Este projeto não pode ser encerrado sem conclusão no status atual.')
        return redirect('projeto_detalhe', pk=pk)

    form = EncerramentoSemConclusaoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        projeto.status = 'encerrado'
        projeto.motivo_encerramento = form.cleaned_data['motivo'].strip()
        projeto.encerrado_em = timezone.now()
        projeto.encerrado_por = request.user
        projeto.ultima_alteracao_gestor_em = timezone.now()
        projeto.ultima_alteracao_gestor_por = request.user
        projeto.save(update_fields=[
            'status', 'motivo_encerramento', 'encerrado_em', 'encerrado_por',
            'ultima_alteracao_gestor_em', 'ultima_alteracao_gestor_por',
        ])
        link = request.build_absolute_uri(reverse('projeto_detalhe', args=[projeto.pk]))
        enviar_email_e_notificacao(
            f'Projeto "{projeto.titulo}" encerrado sem conclusão',
            (
                f'Olá, {projeto.coordenador.first_name}.\n\n'
                f'O projeto "{projeto.titulo}" foi encerrado sem conclusão pela gestão.\n'
                f'Motivo: {projeto.motivo_encerramento}\n\nEquipe PROPEG/UFAC'
            ),
            projeto.coordenador,
            link=link,
        )
        messages.success(request, 'Projeto encerrado sem conclusão.')
        return redirect('projeto_detalhe', pk=pk)

    return render(request, 'projetos_institucionais/encerrar_sem_conclusao.html', {
        'projeto': projeto,
        'form': form,
    })

@login_required
@gestor_required
@login_required
@gestor_required
def listar_relatorios_gestor(request):
    queryset = Relatorio.objects.select_related(
        'projeto', 'projeto__coordenador', 'projeto__centro_lotacao'
    ).all().order_by('-data_envio')

    query        = request.GET.get('q', '').strip()
    data_inicio_filter = request.GET.get('data_inicio', '').strip()
    data_fim_filter    = request.GET.get('data_fim', '').strip()
    tipo_filter  = request.GET.get('tipo', '').strip()
    status_filter = request.GET.get('status', '').strip()
    try:
        per_page = int(request.GET.get('per_page', 10))
        if per_page not in [5, 7, 10, 15, 20]: per_page = 10
    except (ValueError, TypeError):
        per_page = 10

    if query:
        queryset = queryset.filter(
            Q(projeto__titulo__icontains=query) |
            Q(projeto__coordenador__first_name__icontains=query) |
            Q(projeto__coordenador__last_name__icontains=query)
        )
    if data_inicio_filter: queryset = queryset.filter(projeto__data_inicio__gte=data_inicio_filter)
    if data_fim_filter:    queryset = queryset.filter(projeto__data_inicio__lte=data_fim_filter)
    if tipo_filter:   queryset = queryset.filter(tipo=tipo_filter)
    if status_filter: queryset = queryset.filter(projeto__status=status_filter)

    # Contadores (sem filtros)
    todos = Relatorio.objects.all()
    contadores = {
        'total':   todos.count(),
        'parciais': todos.filter(tipo='parcial').count(),
        'finais':  todos.filter(tipo='final').count(),
        'projetos_com_relatorio': todos.values('projeto').distinct().count(),
    }

    paginator = Paginator(queryset, per_page)
    page_obj  = paginator.get_page(request.GET.get('page'))
    anos_disponiveis = Projeto.objects.exclude(data_inicio__isnull=True).dates('data_inicio', 'year', order='DESC')

    return render(request, 'projetos_institucionais/gestor_relatorios.html', {
        'page_obj':        page_obj,
        'anos_disponiveis': anos_disponiveis,
        'tipo_choices':    Relatorio.TIPO_CHOICES,
        'status_choices':  [(k, v) for k, v in Projeto.STATUS_CHOICES if k not in ('rascunho',)],
        'query':           query,
        'data_inicio_filter': data_inicio_filter,
        'data_fim_filter':    data_fim_filter,
        'tipo_filter':     tipo_filter,
        'status_filter':   status_filter,
        'per_page':        per_page,
        'contadores':      contadores,
    })

@login_required
@gestor_required
def gestor_listar_editais(request):
    filtro_submissoes = (
        Q(projetos__tipo_projeto=Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO)
        & ~Q(projetos__status='rascunho')
    )
    editais = Edital.objects.annotate(
        total_submissoes=Count('projetos', filter=filtro_submissoes, distinct=True),
    ).order_by('-ano', '-numero')
    rascunhos = editais.filter(status='rascunho')
    abertos   = editais.filter(status='aberto')
    fechados  = editais.filter(status='fechado')
    grupos = [
        ('abertos',   'Editais Abertos',   'bg-success bg-opacity-10 text-success', abertos),
        ('rascunhos', 'Rascunhos',          'bg-warning text-dark',                  rascunhos),
        ('fechados',  'Editais Fechados',   'bg-secondary bg-opacity-10 text-secondary', fechados),
    ]
    return render(request, 'projetos_institucionais/gestor_edital_lista.html', {
        'rascunhos': rascunhos, 'abertos': abertos, 'fechados': fechados, 'grupos': grupos,
    })


@login_required
@gestor_required
def gestor_detalhe_edital(request, pk):
    edital = get_object_or_404(Edital, pk=pk)
    projetos = edital.projetos.filter(
        tipo_projeto=Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
    ).exclude(status='rascunho').select_related('coordenador', 'centro_lotacao')
    total_submissoes = projetos.count()
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    if q:
        projetos = projetos.filter(
            Q(titulo__icontains=q)
            | Q(coordenador__first_name__icontains=q)
            | Q(coordenador__last_name__icontains=q)
            | Q(coordenador__cpf__icontains=q)
        )
    if status in dict(Projeto.STATUS_CHOICES):
        projetos = projetos.filter(status=status)

    resumo_status = {
        chave: edital.projetos.filter(
            tipo_projeto=Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
            status=chave,
        ).count()
        for chave in ('submetido', 'aprovado', 'reprovado', 'em_andamento', 'finalizado', 'encerrado')
    }
    page_obj = Paginator(projetos.order_by('-id'), 15).get_page(request.GET.get('page'))
    return render(request, 'projetos_institucionais/gestor_edital_detalhe.html', {
        'edital': edital,
        'page_obj': page_obj,
        'total_submissoes': total_submissoes,
        'resumo_status': resumo_status,
        'status_choices': [c for c in Projeto.STATUS_CHOICES if c[0] != 'rascunho'],
        'q': q,
        'status_filter': status,
    })


@login_required
@gestor_required
def gestor_criar_edital(request):
    if request.method == 'POST':
        acao = request.POST.get('acao', 'publicar')
        is_draft = (acao == 'rascunho')
        form = EditalForm(request.POST, request.FILES, is_draft=is_draft)
        if form.is_valid():
            edital = form.save(commit=False)
            edital.criado_por = request.user
            edital.status = 'rascunho' if is_draft else 'aberto'
            edital.save()
            formset = AnexoEditalFormSet(request.POST, request.FILES, instance=edital)
            if formset.is_valid():
                formset.save()
            msg = 'Rascunho salvo! Acesse "Editais" para continuar editando.' if is_draft else 'Edital publicado com sucesso!'
            messages.success(request, msg)
            return redirect('gestor_detalhe_edital', pk=edital.pk)
    else:
        form = EditalForm(initial={'ano': date.today().year})
    formset = AnexoEditalFormSet(instance=Edital())
    return render(request, 'projetos_institucionais/gestor_edital_form.html', {
        'form': form, 'formset': formset,
    })


@login_required
@gestor_required
def gestor_editar_edital(request, pk):
    edital = get_object_or_404(Edital, pk=pk)
    if request.method == 'POST':
        acao = request.POST.get('acao', 'salvar')
        is_draft = (acao == 'rascunho')
        form = EditalForm(request.POST, request.FILES, instance=edital, is_draft=is_draft)
        formset = AnexoEditalFormSet(request.POST, request.FILES, instance=edital)
        if form.is_valid() and formset.is_valid():
            edital_salvo = form.save(commit=False)

            # Preserva o documento principal se nenhum novo arquivo foi enviado
            if not request.FILES.get('documento_principal') and edital.documento_principal:
                edital_salvo.documento_principal = edital.documento_principal

            # Status: só altera se a ação exigir — caso contrário mantém o atual
            if acao == 'publicar' and edital.status == 'rascunho':
                edital_salvo.status = 'aberto'
            elif acao == 'rascunho' and edital.status in ('aberto', 'fechado'):
                # Não rebaixa para rascunho um edital já publicado — apenas salva
                edital_salvo.status = edital.status
            else:
                edital_salvo.status = edital.status

            edital_salvo.save()
            formset.save()
            messages.success(request, 'Edital atualizado com sucesso!')
            return redirect('gestor_detalhe_edital', pk=pk)
    else:
        form = EditalForm(instance=edital)
        formset = AnexoEditalFormSet(instance=edital)
    return render(request, 'projetos_institucionais/gestor_edital_form.html', {
        'form': form, 'formset': formset, 'edital': edital,
    })


@login_required
@gestor_required
def gestor_toggle_edital(request, pk):
    """Alterna status entre aberto e fechado."""
    if request.method == 'POST':
        edital = get_object_or_404(Edital, pk=pk)
        if edital.status == 'aberto':
            edital.status = 'fechado'
            messages.success(request, f'Edital "{edital.titulo_completo}" inativado.')
        elif edital.status in ('fechado', 'rascunho'):
            edital.status = 'aberto'
            messages.success(request, f'Edital "{edital.titulo_completo}" publicado/reaberto.')
        edital.save()
    return redirect(request.POST.get('next', 'gestor_listar_editais'))


@login_required
@gestor_required
def gestor_add_adendo(request, pk):
    """Adiciona um adendo a um edital."""
    edital = get_object_or_404(Edital, pk=pk)
    if request.method == 'POST':
        titulo    = request.POST.get('titulo', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        arquivo   = request.FILES.get('arquivo')
        if titulo:
            try:
                AdendoEdital.objects.create(
                    edital=edital, titulo=titulo, descricao=descricao,
                    arquivo=arquivo, criado_por=request.user,
                )
                messages.success(request, 'Adendo publicado com sucesso!')
            except Exception as e:
                import traceback
                print('=== ERRO AO CRIAR ADENDO ===')
                print(traceback.format_exc())
                print('============================')
                messages.error(request, f'Erro ao salvar adendo: {type(e).__name__}: {e}')
        else:
            messages.error(request, 'Informe um título para o adendo.')
    return redirect('gestor_detalhe_edital', pk=pk)


@login_required
@gestor_required
def gestor_deletar_adendo(request, adendo_pk):
    adendo = get_object_or_404(AdendoEdital, pk=adendo_pk)
    edital_pk = adendo.edital.pk
    if request.method == 'POST':
        adendo.delete()
        messages.success(request, 'Adendo removido.')
    return redirect('gestor_detalhe_edital', pk=edital_pk)


@login_required
@gestor_required
def gestor_deletar_edital(request, pk):
    edital = get_object_or_404(Edital, pk=pk)
    if request.method == 'POST':
        edital.delete()
        messages.success(request, 'Edital excluído com sucesso.')
        return redirect('gestor_listar_editais')
    return render(request, 'projetos_institucionais/edital_confirm_delete.html', {'edital': edital})


@login_required
def projeto_etapa2_add_anexo(request, pk):
    """Upload de um único anexo na etapa 2 sem sair da etapa."""
    projeto = get_object_or_404(Projeto, pk=pk)
    if request.user != projeto.coordenador and request.user.perfil != 'gestor':
        return HttpResponseForbidden('Você não tem permissão para alterar este projeto.')
    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo_etapa2')
        if arquivo:
            tipo      = request.POST.get('tipo_anexo_etapa2', 'outro')
            descricao = request.POST.get('descricao_anexo_etapa2', '').strip()
            Anexo.objects.create(
                projeto=projeto, tipo_anexo=tipo,
                arquivo=arquivo, descricao=descricao or arquivo.name,
            )
            messages.success(request, f'Anexo "{arquivo.name}" adicionado com sucesso!')
        else:
            messages.warning(request, 'Selecione um arquivo para enviar.')
    return redirect('projeto_etapa', pk=pk, step=2)

@login_required
@coordenador_required
def listar_editais_abertos(request):
    hoje = date.today()
    editais_abertos = Edital.objects.filter(
        status='aberto',
    ).prefetch_related('anexos', 'adendos').order_by('-ano', '-numero')
    return render(request, 'projetos_institucionais/editais_abertos_lista.html', {
        'editais': editais_abertos,
        'hoje': hoje,
    })


@login_required
def edital_detalhe_coordenador(request, pk):
    edital = get_object_or_404(Edital, pk=pk, status='aberto')
    return render(request, 'projetos_institucionais/edital_detalhe_coordenador.html', {
        'edital': edital,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Novo fluxo de criação/edição por etapas (substitui o SessionWizardView)
# ─────────────────────────────────────────────────────────────────────────────

ETAPAS_INFO = [
    {'num': 1, 'nome': 'Informações Gerais',    'icon': 'bi-info-circle-fill'},
    {'num': 2, 'nome': 'Detalhes do Projeto',   'icon': 'bi-file-text-fill'},
    {'num': 3, 'nome': 'Equipe de Trabalho',    'icon': 'bi-people-fill'},
    {'num': 4, 'nome': 'Vínculo com ODS',       'icon': 'bi-globe2'},
    {'num': 5, 'nome': 'Revisão e Submissão',   'icon': 'bi-check-circle-fill'},
]

ETAPAS_INFO_AGENCIA_FOMENTO = [
    {'num': 1, 'nome': 'Informações Gerais',       'icon': 'bi-info-circle-fill'},
    {'num': 2, 'nome': 'Documentação e Submissão', 'icon': 'bi-file-earmark-check-fill'},
]


@login_required
@coordenador_required
def projeto_criar_iniciar(request):
    """
    Se não há rascunhos: cria um novo imediatamente.
    Se há 1 rascunho: exibe página intermediária com modal de decisão.
    Se há 2+ rascunhos: exibe página intermediária indicando aba de rascunhos.
    POST com acao='novo': força criação de novo rascunho.
    """
    if request.method == 'POST':
        if request.POST.get('acao') == 'novo':
            projeto = Projeto.objects.create(coordenador=request.user, status='rascunho')
            messages.info(request, 'Novo rascunho iniciado. Preencha as etapas abaixo.')
            return redirect('projeto_etapa', pk=projeto.pk, step=1)

    rascunhos = Projeto.objects.filter(
        coordenador=request.user, status='rascunho'
    ).order_by('-id')

    if not rascunhos.exists():
        # Nenhum rascunho: cria direto
        projeto = Projeto.objects.create(coordenador=request.user, status='rascunho')
        messages.info(request, 'Rascunho iniciado. Preencha as etapas abaixo.')
        return redirect('projeto_etapa', pk=projeto.pk, step=1)

    # Há rascunhos: exibe página intermediária
    return render(request, 'projetos_institucionais/projeto_criar_confirmar.html', {
        'rascunho_recente': rascunhos.first(),
        'total_rascunhos':  rascunhos.count(),
    })


@login_required
def projeto_editar_iniciar(request, pk):
    """Redireciona para a etapa 1 de edição de um projeto existente."""
    projeto = get_object_or_404(Projeto, pk=pk)
    eh_gestor = request.user.perfil == 'gestor'
    if not eh_gestor and projeto.coordenador_id != request.user.id:
        return HttpResponseForbidden('Você não tem permissão para editar este projeto.')
    if not eh_gestor and projeto.status not in ('rascunho', 'reprovado'):
        messages.warning(request, 'Este projeto não pode ser editado no momento.')
        return redirect('projeto_detalhe', pk=pk)
    return redirect('projeto_etapa', pk=pk, step=1)


@login_required
@gestor_required
def gestor_projeto_criar(request):
    """Inicia o cadastro completo de um projeto anterior à implantação do sistema."""
    form = GestorProjetoNovoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        projeto = Projeto.objects.create(
            coordenador=form.cleaned_data['coordenador'],
            status='rascunho',
            importado_legado=True,
            ultima_alteracao_gestor_em=timezone.now(),
            ultima_alteracao_gestor_por=request.user,
        )
        messages.info(request, 'Cadastro histórico iniciado. Preencha todas as etapas do projeto.')
        return redirect('projeto_etapa', pk=projeto.pk, step=1)
    return render(request, 'projetos_institucionais/gestor_projeto_novo.html', {'form': form})


def _registrar_alteracao_gestor(projeto, usuario):
    projeto.ultima_alteracao_gestor_em = timezone.now()
    projeto.ultima_alteracao_gestor_por = usuario
    projeto.save(update_fields=['ultima_alteracao_gestor_em', 'ultima_alteracao_gestor_por'])


def _preparar_prazo_etica(projeto):
    if projeto.etica_obrigatoria and projeto.situacao_etica == 'submetido' and projeto.etica_pendente:
        if not projeto.etica_submetida_em:
            projeto.etica_submetida_em = timezone.localdate()
        projeto.prazo_aprovacao_etica = projeto.etica_submetida_em + datetime.timedelta(days=90)
        projeto.save(update_fields=['etica_submetida_em', 'prazo_aprovacao_etica'])


def _checar_etapas(projeto):
    """
    Retorna um dict indicando quais etapas estão completas.
    Para projetos aprovados por agência de fomento o fluxo é de 2 etapas
    e a etapa 2 é validada no momento do POST.
    """
    etapa_1_base = bool(
        projeto.tipo_projeto and projeto.titulo and projeto.data_inicio and
        projeto.data_fim and projeto.centro_lotacao
    )

    if projeto.eh_agencia_fomento:
        tem_comprovante = projeto.anexos.filter(tipo_anexo='comprovante_fomento').exists()
        return {
            1: bool(etapa_1_base and projeto.agencia_financiadora_id and tem_comprovante),
            2: bool(projeto.resumo and projeto.palavras_chave),
        }

    if projeto.requer_ata_conselho:
        etapa_1_base = bool(
            etapa_1_base and projeto.centro_lotacao and projeto.centro_lotacao.email
        )
    elif projeto.requer_edital_ufac:
        hoje = date.today()
        etapa_1_base = bool(
            etapa_1_base and projeto.edital_id and
            projeto.edital.status == 'aberto' and
            projeto.edital.data_inicio_submissoes <= hoje <= projeto.edital.data_fim_submissoes
        )

    return {
        1: etapa_1_base,
        2: bool(projeto.resumo and projeto.objetivo_geral and projeto.metodologia),
        3: True,
        4: True,
    }


@login_required
def projeto_etapa_view(request, pk, step):
    """
    View única que trata todas as etapas do formulário de criação/edição de projeto.
    Cada etapa salva diretamente no banco de dados, permitindo rascunhos confiáveis.
    """
    projeto = get_object_or_404(Projeto, pk=pk)
    modo_gestor = request.user.perfil == 'gestor'
    if not modo_gestor and projeto.coordenador_id != request.user.id:
        return HttpResponseForbidden('Você não tem permissão para editar este projeto.')
    step = int(step)
    is_agencia_fomento = projeto.eh_agencia_fomento
    fluxo_curto_agencia = is_agencia_fomento and not modo_gestor
    cadastro_historico = modo_gestor and projeto.importado_legado and projeto.status == 'rascunho'

    # Projetos já aprovados por agência de fomento têm apenas 2 etapas
    etapas_info = ETAPAS_INFO_AGENCIA_FOMENTO if fluxo_curto_agencia else ETAPAS_INFO
    step_total  = 2 if fluxo_curto_agencia else 5

    if fluxo_curto_agencia and step not in range(1, 3):
        return redirect('projeto_etapa', pk=pk, step=1)
    elif not fluxo_curto_agencia and step not in range(1, 6):
        return redirect('projeto_etapa', pk=pk, step=1)

    if not modo_gestor and projeto.status not in ('rascunho', 'reprovado'):
        messages.warning(request, 'Este projeto não pode ser editado no momento.')
        return redirect('projeto_detalhe', pk=pk)

    form = None
    formset = None

    if request.method == 'POST':
        acao = request.POST.get('acao', 'proximo')
        is_draft = acao in ('rascunho', 'anexar_documento', 'preencher_documento')

        # ── Etapa 1 ──────────────────────────────────────────────────────────
        if step == 1:
            form = ProjetoEtapa1Form(
                request.POST, request.FILES,
                instance=projeto, is_draft=is_draft, allow_closed_edital=modo_gestor,
                modo_gestor=modo_gestor,
            )
            if request.user.perfil == 'gestor':
                _registrar_alteracao_gestor(projeto, request.user)
            if form.is_valid():
                projeto_salvo = form.save()
                if modo_gestor:
                    _registrar_alteracao_gestor(projeto_salvo, request.user)
                # Documento obrigatório conforme o tipo do projeto
                if projeto_salvo.eh_agencia_fomento:
                    comprovante_fomento = request.FILES.get('comprovante_fomento')
                    if comprovante_fomento:
                        Anexo.objects.create(
                            projeto=projeto_salvo,
                            tipo_anexo='comprovante_fomento',
                            arquivo=comprovante_fomento,
                            descricao='Comprovante de aprovação da agência de fomento.',
                        )
                # Comprovante do comitê de ética
                comprovante = request.FILES.get('comprovante_etica')
                if comprovante:
                    tipo_comprovante = (
                        'comite_etica'
                        if projeto_salvo.situacao_etica == 'aprovado'
                        else 'submissao_comite_etica'
                    )
                    Anexo.objects.create(
                        projeto=projeto_salvo,
                        tipo_anexo=tipo_comprovante,
                        arquivo=comprovante,
                        descricao=(
                            'Comprovante de aprovação do comitê de ética.'
                            if tipo_comprovante == 'comite_etica'
                            else 'Comprovante de submissão ao comitê de ética.'
                        ),
                    )
                # Upload de múltiplos anexos gerais
                for arquivo in request.FILES.getlist('anexos_gerais'):
                    Anexo.objects.create(
                        projeto=projeto_salvo,
                        tipo_anexo='outro',
                        arquivo=arquivo,
                        descricao=f'Anexo: {arquivo.name}',
                    )
                if is_draft:
                    messages.success(request, 'Rascunho salvo com sucesso!')
                    return redirect('projeto_etapa', pk=pk, step=1)
                return redirect('projeto_etapa', pk=pk, step=2)

        # ── Etapa 2 ──────────────────────────────────────────────────────────
        elif step == 2:
            form_class = ProjetoEtapa2AgenciaFomentoForm if is_agencia_fomento else ProjetoEtapa2Form
            form = form_class(
                request.POST,
                request.FILES,
                instance=projeto,
                is_draft=is_draft,
            )
            if form.is_valid():
                doc_projeto = form.cleaned_data.get('documento_projeto')
                if acao in ('anexar_documento', 'preencher_documento') and not doc_projeto:
                    form.add_error('documento_projeto', 'Selecione um documento PDF para continuar.')
                elif doc_projeto and acao not in ('anexar_documento', 'preencher_documento'):
                    form.add_error(
                        'documento_projeto',
                        'Confirme se deseja somente anexar ou preencher os campos automaticamente.',
                    )
                else:
                    form.save()
                    if modo_gestor:
                        _registrar_alteracao_gestor(projeto, request.user)
                    if doc_projeto:
                        Anexo.objects.create(
                            projeto=projeto,
                            tipo_anexo='projeto_completo',
                            arquivo=doc_projeto,
                            descricao='Documento digital do projeto enviado na Etapa 2.',
                        )

                    if acao in ('anexar_documento', 'preencher_documento'):
                        if acao == 'preencher_documento':
                            campos_extraidos = extrair_campos_projeto(form.texto_documento_extraido)
                            if campos_extraidos:
                                campos_truncados = []
                                for campo, conteudo in campos_extraidos.items():
                                    if len(conteudo) > 4000:
                                        conteudo = conteudo[:4000]
                                        campos_truncados.append(form.fields[campo].label)
                                    setattr(projeto, campo, conteudo)
                                projeto.save(update_fields=list(campos_extraidos))
                                nomes_campos = ', '.join(
                                    form.fields[campo].label for campo in campos_extraidos
                                )
                                messages.success(
                                    request,
                                    f'Documento anexado e {len(campos_extraidos)} campo(s) preenchido(s): '
                                    f'{nomes_campos}. Revise o conteúdo antes de avançar.',
                                )
                                if campos_truncados:
                                    messages.warning(
                                        request,
                                        'Os seguintes campos foram limitados a 4.000 caracteres: '
                                        + ', '.join(campos_truncados) + '.',
                                    )
                            else:
                                messages.warning(
                                    request,
                                    'O documento foi anexado, mas não foi possível reconhecer as seções. '
                                    'Use títulos como “Resumo”, “Objetivo Geral”, “Metodologia” e '
                                    '“Resultados Esperados”, ou preencha os campos manualmente.',
                                )
                        else:
                            messages.success(request, 'Documento digital anexado sem alterar os campos.')
                        return redirect('projeto_etapa', pk=pk, step=2)

                    # Upload de anexo opcional da etapa 2
                    arquivo_etapa2 = request.FILES.get('arquivo_etapa2')
                    if arquivo_etapa2:
                        tipo = request.POST.get('tipo_anexo_etapa2', 'outro')
                        descricao = request.POST.get('descricao_anexo_etapa2', '').strip()
                        Anexo.objects.create(
                            projeto=projeto,
                            tipo_anexo=tipo,
                            arquivo=arquivo_etapa2,
                            descricao=descricao or arquivo_etapa2.name,
                        )

                    if is_draft:
                        messages.success(request, 'Rascunho salvo com sucesso!')
                        return redirect('projeto_etapa', pk=pk, step=2)

                    if fluxo_curto_agencia:
                        if not all(_checar_etapas(projeto).values()):
                            messages.error(
                                request,
                                'Não é possível submeter. Revise as informações obrigatórias.',
                            )
                            return redirect('projeto_etapa', pk=pk, step=1)
                        # Submissão direta — agência de fomento não passa pelo Centro
                        with transaction.atomic():
                            _preparar_prazo_etica(projeto)
                            projeto.status = 'submetido'
                            projeto.save(update_fields=['status'])
                            _gerar_relatorio_submissao(projeto, request)
                        Notificacao.objects.create(
                            destinatario=request.user,
                            mensagem=(
                                f'Projeto "{projeto.titulo}" submetido com sucesso. '
                                'Por já ter aprovação de agência de fomento, o projeto aguarda avaliação pela PROPEG.'
                            ),
                            link=reverse('projeto_detalhe', args=[projeto.pk]),
                        )
                        messages.success(
                            request,
                            f'Projeto "{projeto.titulo}" submetido com sucesso! '
                            f'Ele agora aguarda avaliação direta pela PROPEG.',
                        )
                        return render(
                            request,
                            'projetos_institucionais/projeto_wizard_done.html',
                            {'projeto': projeto},
                        )

                    return redirect('projeto_etapa', pk=pk, step=3)

        # ── Etapa 3 ──────────────────────────────────────────────────────────
        elif step == 3:
            formset = EquipeProjetoFormSet(
                request.POST,
                instance=projeto,
                form_kwargs={'coordenador': projeto.coordenador, 'is_draft': is_draft},
            )
            if formset.is_valid():
                formset.save()
                if modo_gestor:
                    _registrar_alteracao_gestor(projeto, request.user)
                if is_draft:
                    messages.success(request, 'Rascunho da equipe salvo com sucesso!')
                    return redirect('projeto_etapa', pk=pk, step=3)
                return redirect('projeto_etapa', pk=pk, step=4)
            elif is_draft:
                # No rascunho, salva apenas os membros válidos e segue
                for f in formset.forms:
                    if (
                        f.is_valid()
                        and (f.cleaned_data.get('membro') or f.cleaned_data.get('nome_membro_manual'))
                        and not f.cleaned_data.get('DELETE', False)
                    ):
                        inst = f.save(commit=False)
                        inst.projeto = projeto
                        try:
                            inst.save()
                        except Exception:
                            pass
                messages.success(request, 'Rascunho parcial da equipe salvo.')
                return redirect('projeto_etapa', pk=pk, step=3)

        # ── Etapa 4 ──────────────────────────────────────────────────────────
        elif step == 4:
            form = ProjetoEtapa4Form(request.POST, instance=projeto, is_draft=is_draft)
            if form.is_valid():
                form.save()
                if modo_gestor:
                    _registrar_alteracao_gestor(projeto, request.user)
                if is_draft:
                    messages.success(request, 'Rascunho salvo com sucesso!')
                    return redirect('projeto_etapa', pk=pk, step=4)
                return redirect('projeto_etapa', pk=pk, step=5)

        # ── Etapa 5 – Submissão ───────────────────────────────────────────────
        elif step == 5:
            if modo_gestor and acao == 'salvar_gestor':
                if cadastro_historico:
                    form = GestorFinalizarCadastroProjetoForm(request.POST)
                    form_valido = form.is_valid()
                    if not all(_checar_etapas(projeto).values()):
                        form.add_error(None, 'Complete as informações obrigatórias das etapas 1 e 2.')
                        form_valido = False
                    if form_valido:
                        status_novo = form.cleaned_data['status']
                        if projeto.etica_pendente and status_novo in (
                            'aprovado', 'em_andamento', 'aguardando_encerramento', 'finalizado'
                        ):
                            form.add_error(
                                'status',
                                'Projetos com aspectos éticos pendentes não podem ser cadastrados neste status.',
                            )
                        else:
                            projeto.status = status_novo
                            projeto.motivo_encerramento = form.cleaned_data.get('motivo_encerramento', '').strip()
                            agora = timezone.now()
                            if status_novo == 'finalizado':
                                projeto.finalizado_em = agora
                            elif status_novo == 'encerrado':
                                projeto.encerrado_em = agora
                                projeto.encerrado_por = request.user
                            projeto.save()
                            _preparar_prazo_etica(projeto)
                            _registrar_alteracao_gestor(projeto, request.user)
                            _gerar_relatorio_submissao(projeto, request)
                            messages.success(request, 'Projeto histórico cadastrado com sucesso.')
                            return redirect('projeto_detalhe', pk=projeto.pk)
                else:
                    _registrar_alteracao_gestor(projeto, request.user)
                    messages.success(request, 'Alterações do projeto salvas pela gestão.')
                    return redirect('projeto_detalhe', pk=projeto.pk)

            elif acao == 'submeter':
                etapas_ok = _checar_etapas(projeto)
                etapas_incompletas = [num for num, ok in etapas_ok.items() if not ok]

                if etapas_incompletas:
                    nomes = {1: 'Informações Gerais', 2: 'Detalhes do Projeto'}
                    lista = ', '.join(nomes[n] for n in etapas_incompletas)
                    messages.error(
                        request,
                        f'Não é possível submeter. Complete as etapas obrigatórias antes: {lista}.'
                    )
                else:
                    if projeto.requer_ata_conselho and (
                        not projeto.centro_lotacao or not projeto.centro_lotacao.email
                    ):
                        messages.error(
                            request,
                            'Cadastre um Centro de Lotação com e-mail válido antes de solicitar a aprovação.',
                        )
                        return redirect('projeto_etapa', pk=pk, step=1)

                    encaminhado_centro = projeto.requer_ata_conselho
                    with transaction.atomic():
                        _preparar_prazo_etica(projeto)
                        projeto.status = 'aguardando_conselho' if encaminhado_centro else 'submetido'
                        projeto.save(update_fields=['status'])
                        _gerar_relatorio_submissao(projeto, request)
                        if encaminhado_centro:
                            _, email_enviado = _emitir_solicitacao_centro(request, projeto)

                    if encaminhado_centro:
                        Notificacao.objects.create(
                            destinatario=request.user,
                            mensagem=(
                                f'O projeto "{projeto.titulo}" foi encaminhado diretamente ao '
                                f'{projeto.centro_lotacao.nome} e aguarda o envio da ata de aprovação.'
                            ),
                            link=reverse('projeto_detalhe', args=[projeto.pk]),
                        )
                        if email_enviado:
                            messages.success(
                                request,
                                f'Solicitação enviada para {projeto.centro_lotacao.email}.',
                            )
                        else:
                            messages.warning(
                                request,
                                'O projeto está aguardando o Centro, mas o e-mail não pôde ser enviado. '
                                'Use a opção de reenvio na página do projeto.',
                            )

                    return render(
                        request,
                        'projetos_institucionais/projeto_wizard_done.html',
                        {'projeto': projeto, 'encaminhado_centro': encaminhado_centro},
                    )

    # ── GET – inicializa os formulários ──────────────────────────────────────
    # Em um POST inválido, preserve o formulário vinculado para mostrar erros e
    # manter os valores que o usuário acabou de enviar.
    if request.method == 'GET':
        if step == 1:
            form = ProjetoEtapa1Form(
                instance=projeto,
                allow_closed_edital=modo_gestor,
                modo_gestor=modo_gestor,
            )
        elif step == 2:
            form = ProjetoEtapa2AgenciaFomentoForm(instance=projeto) if is_agencia_fomento else ProjetoEtapa2Form(instance=projeto)
        elif step == 3:
            formset = EquipeProjetoFormSet(
                instance=projeto,
                form_kwargs={'coordenador': projeto.coordenador},
            )
        elif step == 4:
            form = ProjetoEtapa4Form(instance=projeto)
        elif step == 5 and cadastro_historico:
            form = GestorFinalizarCadastroProjetoForm(initial={'status': 'finalizado'})
        # etapa 5 não tem form – só exibe os dados para revisão

    step_info = next(e for e in etapas_info if e['num'] == step)

    contexto = {
        'projeto':        projeto,
        'step':           step,
        'step_total':     step_total,
        'etapas_info':    etapas_info,
        'step_info':      step_info,
        'form':           form,
        'formset':        formset,
        'etapas_status':  _checar_etapas(projeto),
        'is_agencia_fomento': is_agencia_fomento,
        'fluxo_curto_agencia': fluxo_curto_agencia,
        'modo_gestor': modo_gestor,
        'cadastro_historico': cadastro_historico,
    }
    return render(request, 'projetos_institucionais/projeto_form_steps.html', contexto)

# ─────────────────────────────────────────────────────────────────────────────
# Handlers de erro personalizados
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Handlers de erro personalizados
# Retornam HTML inline para evitar dependência de templates durante erros
# ─────────────────────────────────────────────────────────────────────────────

def _pagina_erro(codigo, titulo, descricao, cor):
    from django.http import HttpResponse
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Erro {codigo} — PROPEG/UFAC</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <style>
    body {{ min-height:100vh; display:flex; align-items:center; justify-content:center;
            background:#f0f4f8; text-align:center; padding:2rem; }}
    .card {{ border-radius:16px; padding:3rem 2.5rem; max-width:520px; width:100%; }}
    .codigo {{ font-size:5rem; font-weight:800; color:{cor}; line-height:1; }}
  </style>
</head>
<body>
  <div class="card shadow">
    <div class="codigo mb-2">{codigo}</div>
    <h4 class="fw-bold mb-2">{titulo}</h4>
    <p class="text-muted mb-4">{descricao}</p>
    <div class="d-flex justify-content-center gap-2">
      <a href="javascript:history.back()" class="btn btn-outline-secondary btn-sm">
        <i class="bi bi-arrow-left me-1"></i>Voltar
      </a>
      <a href="/" class="btn btn-primary btn-sm">
        <i class="bi bi-house me-1"></i>Página Inicial
      </a>
    </div>
    <p class="mt-4 mb-0 text-muted" style="font-size:.75rem;">PROPEG — Plataforma de Projetos Institucionais · UFAC</p>
  </div>
</body>
</html>"""
    return HttpResponse(html, status=codigo)


def handler400(request, exception=None):
    return _pagina_erro(400, 'Requisição Inválida',
        'O servidor não conseguiu processar sua solicitação. Verifique os dados e tente novamente.', '#0d6efd')

def handler403(request, exception=None):
    return _pagina_erro(403, 'Acesso Negado',
        'Você não tem permissão para acessar este recurso.', '#fd7e14')

def handler404(request, exception=None):
    return _pagina_erro(404, 'Página Não Encontrada',
        'A página que você tentou acessar não existe ou foi movida.', '#6c757d')

def handler500(request):
    return _pagina_erro(500, 'Erro Interno do Servidor',
        'Ocorreu um erro inesperado. Nossa equipe foi notificada. Tente novamente em instantes.', '#dc3545')


@login_required
def ajuda(request):
    fluxo, faqs = _ajuda_dados()
    etapas_form = [
        {'titulo': 'Informações Gerais',  'badge': 'bg-primary', 'itens': [
            'Seleção de um dos três tipos de projeto e documentação correspondente',
            'Título e resumo do projeto', 'Palavras-chave', 'Datas de início e fim',
            'Centro de lotação e curso',
            'Agência de Fomento: comprovante de aprovação em PDF, PNG, JPG ou JPEG',
            'UFAC com financiamento: edital UFAC aberto obrigatório',
            'UFAC sem financiamento: centro com e-mail cadastrado para receber a solicitação',
            'Aspectos éticos: informe se o documento é aprovação definitiva ou comprovante de submissão',
            'Comprovante de submissão inicia prazo de 90 dias e alertas em 60, 30, 15, 7, 3 e 1 dia',
        ]},
        {'titulo': 'Conteúdo Científico', 'badge': 'bg-primary', 'itens': [
            'Introdução e justificativa', 'Objetivo geral e específicos',
            'Metodologia', 'Resultados esperados', 'Referências bibliográficas',
            'Parcerias (opcional)',
            'PDF nativamente digital opcional para preenchimento automático das seções',
            'Pergunta de confirmação antes de preencher os campos automaticamente',
            'Campos que se expandem durante a digitação, com limite de 4.000 caracteres',
            'Exclusão do documento digital e dos anexos já enviados',
            'Anexos adicionais em PDF, PNG, JPG ou JPEG para compor o relatório',
        ]},
        {'titulo': 'Equipe de Trabalho',  'badge': 'bg-primary', 'itens': [
            'Busque usuários por nome, curso ou CPF, ou use o preenchimento manual',
            'CPF com máscara automática no cadastro manual',
            'Funções: Coordenador, Estudante Graduação, Estudante Pós (Mestrado), Estudante Pós (Doutorado), Estudante Pós (Especialização), Estudante Ensino Médio e Estudante Ensino Fundamental',
            'Nome, CPF, função, carga horária semanal e carga horária total',
            'Equipe pode estar incompleta no rascunho',
        ]},
        {'titulo': 'ODS e Vínculos',      'badge': 'bg-primary', 'itens': [
            'Selecione os ODS relacionados ao projeto',
            'Grupos de pesquisa vinculados', 'Programa de pós-graduação',
            'Gestor pode filtrar o histórico por um ou mais ODS, usando todas (AND) ou qualquer (OR)',
        ]},
        {'titulo': 'Revisão e Submissão', 'badge': 'bg-success', 'itens': [
            'Revise o resumo de todas as etapas (1 e 2 são obrigatórias)',
            'Agência de Fomento: envio direto para análise da PROPEG',
            'UFAC sem financiamento: envio ao Centro por link restrito, temporário e de uso único',
            'UFAC com financiamento: fluxo conforme o edital UFAC selecionado',
            'Relatório de submissão em PDF com padrão ABNT, logo da UFAC e anexos incorporados',
            'Ações de confirmação exibem orientação ao passar o mouse',
            'Projetos com aprovação ética pendente não podem ser aprovados nem iniciados',
        ]},
    ]
    return render(request, 'projetos_institucionais/ajuda.html', {
        'fluxo': fluxo, 'faqs': faqs, 'etapas_form': etapas_form,
        'data_atualizacao': timezone.localdate(),
    })


def _ajuda_dados():
    fluxo = [
        {'titulo': 'Rascunho', 'desc': 'O coordenador cria o projeto, preenche as etapas e pode salvar ou retomar o rascunho a qualquer momento.', 'cor': '#6c757d'},
        {'titulo': 'Tipo e preenchimento', 'desc': 'Na Etapa 1, o coordenador escolhe o tipo do projeto e informa a documentação exigida para aquele fluxo.', 'cor': '#0d6efd'},
        {'titulo': 'Submissão por tipo', 'desc': 'Na Etapa 5, o sistema gera o relatório em PDF e direciona o projeto conforme a modalidade selecionada.', 'cor': '#0d6efd'},
        {'titulo': 'Aprovação do Centro', 'desc': 'Somente projetos UFAC sem financiamento passam primeiro pelo Centro: o responsável recebe um link restrito, válido por 7 dias e de uso único, para anexar a ata.', 'cor': '#ffc107'},
        {'titulo': 'Análise da PROPEG', 'desc': 'Agência de Fomento e UFAC com financiamento seguem para análise do gestor. O projeto UFAC sem financiamento chega à PROPEG depois da ata do Centro.', 'cor': '#fd7e14'},
        {'titulo': 'Aprovado e início', 'desc': 'Após a aprovação do gestor, o coordenador pode confirmar o início. Quando houver aspectos éticos, a aprovação definitiva deve estar anexada.', 'cor': '#198754'},
        {'titulo': 'Em andamento', 'desc': 'Durante a execução, o coordenador acompanha a equipe e envia relatórios parciais ou finais.', 'cor': '#0d6efd'},
        {'titulo': 'Finalizado ou encerrado', 'desc': 'Com relatório final e conclusão bem-sucedida, o status é Finalizado. Encerrado é reservado à interrupção sem conclusão e exige motivo registrado pelo gestor.', 'cor': '#6c757d'},
    ]
    faqs = [
        {'pergunta': 'Posso ter mais de um projeto em andamento ao mesmo tempo?',         'resposta': 'Sim. Não há limite de projetos simultâneos por coordenador.'},
        {'pergunta': 'O que acontece se meu projeto for reprovado?',                      'resposta': 'O projeto volta para status Reprovado. Você pode editá-lo e ressubmetê-lo usando o botão "Editar e Ressubmeter" na página de detalhes.'},
        {'pergunta': 'Como adiciono uma pessoa à equipe do projeto?',                     'resposta': 'Na Etapa 3, pesquise usuários cadastrados por nome, curso ou CPF. Se a pessoa ainda não possuir conta, escolha o preenchimento manual e informe nome, CPF, função e cargas horárias.'},
        {'pergunta': 'Posso enviar mais de um arquivo na etapa 2?',                       'resposta': 'Sim. Use o botão "Adicionar Anexo" quantas vezes precisar. Cada arquivo pode ser PDF, PNG, JPG ou JPEG e pode ser removido na própria lista de arquivos enviados.'},
        {'pergunta': 'Como funciona o preenchimento automático da etapa 2?',              'resposta': 'O documento é opcional. Quando enviar um PDF nativamente digital, com texto selecionável, o sistema perguntará se você deseja preencher automaticamente os campos. Ele identifica os títulos e limites das seções, preenche os campos e mantém você na Etapa 2 para revisar. PDFs digitalizados sem texto selecionável não são processados.'},
        {'pergunta': 'Existe limite nos campos da etapa 2?',                             'resposta': 'Sim. Cada campo aceita até 4.000 caracteres. A caixa de texto quebra as linhas e cresce conforme você digita, enquanto o contador mostra o total utilizado.'},
        {'pergunta': 'Qual tipo de projeto devo selecionar?',                            'resposta': 'Use "1 - Projeto Aprovado (Agência de Fomento)" para aprovação externa já obtida e anexe o comprovante; "2 - UFAC (Sem Financiamento/Fluxo Contínuo)" para o fluxo que começa no Centro; e "3 - UFAC (Com Financiamento)" para projetos vinculados a edital UFAC aberto.'},
        {'pergunta': 'Como funciona a aprovação do Centro?',                             'resposta': 'No tipo UFAC sem financiamento, o coordenador submete o projeto diretamente ao Centro. O sistema envia um link restrito ao e-mail cadastrado, válido por 7 dias e de uso único. O responsável consulta o projeto, informa seus dados, aceita a aprovação e anexa a ata em PDF ou imagem. Depois disso, o projeto é encaminhado à PROPEG.'},
        {'pergunta': 'O que acontece se o link do Centro expirar ou já tiver sido usado?', 'resposta': 'O link deixa de exibir o projeto e não aceita novos envios. O coordenador pode abrir os detalhes do projeto e usar "Reenviar solicitação" para gerar um novo link, invalidando o anterior.'},
        {'pergunta': 'Como gero o relatório de submissão?',                               'resposta': 'Ele é criado pelo sistema no envio da Etapa 5. O relatório segue a apresentação institucional em padrão ABNT, inclui a logo da UFAC na capa, incorpora imagens e páginas de PDFs válidos e mantém links para os arquivos originais.'},
        {'pergunta': 'Quem avalia cada tipo de projeto?',                                'resposta': 'Agência de Fomento e UFAC com financiamento seguem para análise da PROPEG conforme o fluxo vigente. UFAC sem financiamento só chega ao gestor depois que o Centro registrar a ata pelo link restrito.'},
        {'pergunta': 'Como funciona o prazo da aprovação ética?',                    'resposta': 'Se na Etapa 1 for anexado apenas o comprovante de submissão ao comitê, o coordenador terá 90 dias para anexar a aprovação definitiva. O sistema envia alertas internos e por e-mail quando faltarem 60, 30, 15, 7, 3 e 1 dia. Enquanto o documento definitivo estiver pendente, o gestor não pode aprovar e o coordenador não pode iniciar o projeto.'},
        {'pergunta': 'Qual a diferença entre Finalizado e Encerrado?',                    'resposta': 'Finalizado identifica o projeto concluído com êxito após o relatório final. Encerrado identifica uma interrupção sem conclusão; o gestor deve registrar o motivo.'},
        {'pergunta': 'O gestor pode corrigir um projeto?',                                'resposta': 'Sim. Nos detalhes do projeto, o gestor pode abrir as mesmas etapas para corrigir dados, equipe, ODS e documentos. A plataforma registra data, hora e o gestor responsável pela última alteração.'},
        {'pergunta': 'Como cadastrar projetos antigos?',                                  'resposta': 'O gestor usa "Cadastrar Projeto Existente", seleciona o coordenador, preenche as cinco etapas e informa a situação atual do projeto. Esses registros passam a compor o histórico.'},
        {'pergunta': 'Preciso de aprovação do gestor para acessar o sistema?',            'resposta': 'Não. O cadastro é automático e o acesso é imediato.'},
        {'pergunta': 'Como sei que o gestor avaliou meu projeto?',                        'resposta': 'Você recebe uma notificação na plataforma (sino) e um e-mail no endereço cadastrado.'},
        {'pergunta': 'Posso excluir um projeto?',                                         'resposta': 'Apenas rascunhos podem ser excluídos. Projetos submetidos ficam no histórico.'},
        {'pergunta': 'Como funciona a consulta pública?',                                 'resposta': 'Qualquer pessoa acessa pelo botão na tela de login, sem conta. Exibe projetos aprovados, em andamento, finalizados ou encerrados sem conclusão, com busca, seleção múltipla de ODS (todas as ODS por padrão ou qualquer ODS quando OR for escolhido), filtros por tipo de projeto e exportação em PDF.'},
        {'pergunta': 'Como inativar um edital sem excluir?',                              'resposta': 'No Painel de Editais, use o botão de toggle (Fechar). O edital deixa de aparecer para coordenadores, mas pode ser reaberto.'},
        {'pergunta': 'Esqueci minha senha, o que faço?',                                  'resposta': 'Clique em "Esqueceu a senha?" na tela de login, informe o CPF e você receberá um link por e-mail válido por 24 horas.'},
        {'pergunta': 'A plataforma funciona no celular?',                                 'resposta': 'Sim, a plataforma é responsiva. Para melhor experiência no preenchimento de projetos, recomenda-se uso em telas maiores.'},
    ]
    return fluxo, faqs


# ─────────────────────────────────────────────────────────────────────────────
# Certificados
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def listar_certificados(request, pk):
    """Lista todos os membros do projeto com botão para gerar certificado."""
    projeto = get_object_or_404(Projeto, pk=pk)

    # Coordenador pode gerar seus próprios e dos membros; gestor pode gerar para qualquer um
    pode_gerar = (request.user == projeto.coordenador or
                  request.user.perfil == 'gestor')
    if not pode_gerar:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    # Monta lista: coordenador principal + equipe
    membros = []
    membros.append({
        'usuario': projeto.coordenador,
        'nome': projeto.coordenador.get_full_name() or projeto.coordenador.username,
        'funcao': 'Coordenador',
        'carga_horaria_total': None,
        'pk': projeto.coordenador.pk,
    })
    for ep in projeto.equipe.select_related('membro').all():
        membros.append({
            'usuario': ep.membro,
            'nome': ep.nome_exibicao,
            'funcao': ep.get_funcao_display(),
            'carga_horaria_total': ep.carga_horaria_total,
            'pk': ep.membro_id,
        })

    return render(request, 'projetos_institucionais/certificados_lista.html', {
        'projeto': projeto,
        'membros': membros,
    })


@login_required
def gerar_certificado(request, pk, membro_pk):
    """Gera PDF de certificado para um membro do projeto."""
    import datetime as dt
    projeto = get_object_or_404(Projeto, pk=pk)

    # Verifica permissão
    pode_gerar = (request.user == projeto.coordenador or
                  request.user.perfil == 'gestor' or
                  request.user.pk == membro_pk)
    if not pode_gerar:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    # Busca o membro
    usuario_membro = get_object_or_404(
        __import__('projetos_institucionais.models', fromlist=['Usuario']).Usuario,
        pk=membro_pk
    )

    # Determina função e horas
    if usuario_membro.pk == projeto.coordenador.pk:
        funcao = 'Coordenador'
        carga_horaria = None
    else:
        ep = get_object_or_404(
            __import__('projetos_institucionais.models', fromlist=['EquipeProjeto']).EquipeProjeto,
            projeto=projeto, membro=usuario_membro
        )
        funcao = ep.get_funcao_display()
        carga_horaria = ep.carga_horaria_total

    concluido = projeto.status == 'finalizado'
    agora = dt.datetime.now()

    contexto = {
        'projeto': projeto,
        'membro': usuario_membro,
        'funcao': funcao,
        'carga_horaria': carga_horaria,
        'concluido': concluido,
        'data_geracao': agora,
    }

    html_string = render_to_string(
        'projetos_institucionais/certificado_pdf.html',
        contexto,
    )
    pdf_bytes = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/'),
    ).write_pdf()

    from django.http import HttpResponse
    tipo = 'conclusao' if concluido else 'participacao'
    nome = f'certificado_{tipo}_{usuario_membro.pk}_{projeto.pk}.pdf'
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{nome}"'
    return resp
