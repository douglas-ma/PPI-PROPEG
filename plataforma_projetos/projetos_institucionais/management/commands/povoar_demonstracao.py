from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from projetos_institucionais.catalogo_ufac import criar_catalogo_ufac
from projetos_institucionais.ods_catalogo import normalizar_ods_padrao
from projetos_institucionais.models import (
    AdendoEdital,
    AgenciaFinanciadora,
    CentroLotacao,
    CursoGraduacao,
    Edital,
    Endereco,
    EquipeProjeto,
    GrupoPesquisa,
    Notificacao,
    ProgramaPos,
    Projeto,
    SolicitacaoAprovacaoCentro,
    TipoEtico,
    Titulacao,
    Usuario,
)


SENHAS_DEMO = {
    'coordenador': 'Coord@2026',
    'aluno': 'Aluno@2026',
    'gestor': 'Gestor@2026',
}

USUARIOS_DEMO = (
    ('10000000108', 'Ana', 'Souza', 'coordenador', 'ana.souza@example.com'),
    ('10000000280', 'Bruno', 'Lima', 'coordenador', 'bruno.lima@example.com'),
    ('10000000361', 'Carla', 'Mendes', 'coordenador', 'carla.mendes@example.com'),
    ('10000000442', 'Diego', 'Alves', 'aluno', 'diego.alves@example.com'),
    ('10000000523', 'Elisa', 'Rocha', 'aluno', 'elisa.rocha@example.com'),
    ('10000000604', 'Felipe', 'Nunes', 'aluno', 'felipe.nunes@example.com'),
    ('10000000795', 'Gabriela', 'Costa', 'gestor', 'gabriela.costa@example.com'),
    ('10000000876', 'Henrique', 'Silva', 'gestor', 'henrique.silva@example.com'),
    ('10000000957', 'Isabela', 'Martins', 'gestor', 'isabela.martins@example.com'),
)

def formatar_cpf(cpf):
    return f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'


class Command(BaseCommand):
    help = (
        'Exclui usuários e projetos existentes e cria uma base local de demonstração. '
        'Use somente em ambiente de desenvolvimento ou homologação.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma a exclusão dos usuários e projetos existentes.',
        )

    def _salvar_usuario(self, cpf, nome, sobrenome, perfil, email, **campos):
        usuario = Usuario.objects.filter(cpf=cpf).first() or Usuario(cpf=cpf)
        usuario.username = cpf
        usuario.first_name = nome
        usuario.last_name = sobrenome
        usuario.email = email
        usuario.perfil = perfil
        usuario.status = 'ativo'
        usuario.is_active = True
        usuario.is_staff = perfil == 'gestor'
        usuario.is_superuser = False
        for campo, valor in campos.items():
            setattr(usuario, campo, valor)
        usuario.set_password(SENHAS_DEMO[perfil])
        usuario.save()
        return usuario

    @transaction.atomic
    def handle(self, *args, **options):
        if not options['confirmar']:
            raise CommandError(
                'Operação destrutiva não confirmada. Execute novamente com --confirmar.'
            )

        hoje = timezone.localdate()
        agora = timezone.now()

        # Projetos carregam a maior parte dos registros transacionais por CASCADE.
        Projeto.objects.all().delete()

        # Mantém editais históricos, mas transfere sua autoria antes de remover usuários.
        dados_gestor = USUARIOS_DEMO[6]
        gestor_principal = self._salvar_usuario(*dados_gestor)
        Edital.objects.all().update(criado_por=gestor_principal)
        AdendoEdital.objects.all().update(criado_por=gestor_principal)

        Usuario.objects.filter(is_superuser=False).exclude(pk=gestor_principal.pk).delete()
        gestor_principal.endereco = None
        gestor_principal.curso = None
        gestor_principal.centro_lotacao = None
        gestor_principal.titulacao = None
        gestor_principal.save(update_fields=[
            'endereco', 'curso', 'centro_lotacao', 'titulacao',
        ])
        Endereco.objects.all().delete()

        # Recria os catálogos solicitados sem manter centros ou cursos de teste.
        ProgramaPos.objects.all().delete()
        CursoGraduacao.objects.all().delete()
        CentroLotacao.objects.all().delete()
        centros = criar_catalogo_ufac(CentroLotacao, CursoGraduacao)
        ProgramaPos.objects.create(
            nome='Programa de Pós-Graduação em Ciência da Computação (PPGCC)',
            centro_lotacao=centros['CCET'],
        )

        titulacao_doutorado, _ = Titulacao.objects.get_or_create(nome='Doutorado')
        titulacao_mestrado, _ = Titulacao.objects.get_or_create(nome='Mestrado')

        cursos = {
            curso.nome: curso
            for curso in CursoGraduacao.objects.select_related('centro_lotacao')
        }

        usuarios = {gestor_principal.cpf: gestor_principal}
        configuracoes = {
            '10000000108': {
                'centro_lotacao': centros['CCET'],
                'titulacao': titulacao_doutorado,
                'regime_trabalho': 'DE',
                'siape': '1000001',
            },
            '10000000280': {
                'centro_lotacao': centros['CFCH'],
                'titulacao': titulacao_mestrado,
                'regime_trabalho': '40h',
                'siape': '1000002',
            },
            '10000000361': {
                'centro_lotacao': centros['CCBN'],
                'titulacao': titulacao_doutorado,
                'regime_trabalho': '20h',
                'siape': '1000003',
            },
            '10000000442': {
                'curso': cursos['Bacharelado em Sistemas de Informação'],
                'centro_lotacao': centros['CCET'],
                'matricula': '202600001',
            },
            '10000000523': {
                'curso': cursos['Bacharelado em Psicologia'],
                'centro_lotacao': centros['CFCH'],
                'matricula': '202600002',
            },
            '10000000604': {
                'curso': cursos['Bacharelado em Engenharia Agronômica'],
                'centro_lotacao': centros['CCBN'],
                'matricula': '202600003',
            },
        }

        for dados in USUARIOS_DEMO:
            cpf = dados[0]
            if cpf == gestor_principal.cpf:
                continue
            usuarios[cpf] = self._salvar_usuario(
                *dados,
                **configuracoes.get(cpf, {}),
            )

        gestores = [usuarios[cpf] for cpf in ('10000000795', '10000000876', '10000000957')]
        coordenadores = [usuarios[cpf] for cpf in ('10000000108', '10000000280', '10000000361')]
        alunos = [usuarios[cpf] for cpf in ('10000000442', '10000000523', '10000000604')]

        edital_aberto, _ = Edital.objects.update_or_create(
            tipo='DEMO',
            numero=1,
            ano=hoje.year,
            defaults={
                'titulo': 'Apoio a Projetos Institucionais de Demonstração',
                'descricao': 'Edital aberto destinado aos testes do fluxo UFAC com financiamento.',
                'data_inicio_submissoes': hoje - timedelta(days=30),
                'data_fim_submissoes': hoje + timedelta(days=120),
                'status': 'aberto',
                'criado_por': gestores[0],
            },
        )
        Edital.objects.update_or_create(
            tipo='DEMO',
            numero=2,
            ano=hoje.year - 1,
            defaults={
                'titulo': 'Edital Encerrado para Consulta Histórica',
                'descricao': 'Edital de demonstração utilizado nos testes de histórico.',
                'data_inicio_submissoes': hoje - timedelta(days=400),
                'data_fim_submissoes': hoje - timedelta(days=300),
                'status': 'fechado',
                'criado_por': gestores[1],
            },
        )

        agencia_cnpq, _ = AgenciaFinanciadora.objects.get_or_create(nome='CNPq')
        grupo_inovacao, _ = GrupoPesquisa.objects.get_or_create(nome='Tecnologia e Inovação na Amazônia')
        tipo_etico, _ = TipoEtico.objects.get_or_create(nome='Comitê de Ética em Pesquisa com Seres Humanos')
        ods, _ = normalizar_ods_padrao()

        definicoes = (
            {
                'coordenador': coordenadores[0],
                'titulo': 'Plataforma Aberta de Indicadores Acadêmicos',
                'tipo_projeto': Projeto.TIPO_PROJETO_AGENCIA_FOMENTO,
                'status': 'rascunho',
                'centro_lotacao': centros['CCET'],
                'curso': cursos['Bacharelado em Sistemas de Informação'],
                'agencia_financiadora': agencia_cnpq,
                'valor_fomento': Decimal('45000.00'),
            },
            {
                'coordenador': coordenadores[0],
                'titulo': 'Inclusão Digital para Comunidades do Acre',
                'tipo_projeto': Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
                'status': 'aguardando_conselho',
                'centro_lotacao': centros['CCET'],
                'curso': cursos['Bacharelado em Sistemas de Informação'],
            },
            {
                'coordenador': coordenadores[0],
                'titulo': 'Laboratório de Dados para Gestão Universitária',
                'tipo_projeto': Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
                'status': 'submetido',
                'centro_lotacao': centros['CCET'],
                'curso': cursos['Bacharelado em Sistemas de Informação'],
                'edital': edital_aberto,
            },
            {
                'coordenador': coordenadores[1],
                'titulo': 'Saúde Mental e Permanência Estudantil',
                'tipo_projeto': Projeto.TIPO_PROJETO_AGENCIA_FOMENTO,
                'status': 'aprovado',
                'centro_lotacao': centros['CFCH'],
                'curso': cursos['Bacharelado em Psicologia'],
                'agencia_financiadora': agencia_cnpq,
                'valor_fomento': Decimal('30000.00'),
                'etica_obrigatoria': True,
                'situacao_etica': 'submetido',
                'tipo_etica': tipo_etico,
                'etica_submetida_em': hoje - timedelta(days=60),
                'prazo_aprovacao_etica': hoje + timedelta(days=30),
            },
            {
                'coordenador': coordenadores[1],
                'titulo': 'Memória Social e Patrimônio Cultural Acreano',
                'tipo_projeto': Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
                'status': 'em_andamento',
                'centro_lotacao': centros['CFCH'],
                'curso': cursos['Bacharelado em História'],
                'edital': edital_aberto,
            },
            {
                'coordenador': coordenadores[1],
                'titulo': 'Cartografia Participativa em Comunidades Urbanas',
                'tipo_projeto': Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
                'status': 'reprovado',
                'centro_lotacao': centros['CFCH'],
                'curso': cursos['Bacharelado em Geografia'],
            },
            {
                'coordenador': coordenadores[2],
                'titulo': 'Manejo Sustentável de Sistemas Agroflorestais',
                'tipo_projeto': Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
                'status': 'aguardando_encerramento',
                'centro_lotacao': centros['CCBN'],
                'curso': cursos['Bacharelado em Engenharia Agronômica'],
            },
            {
                'coordenador': coordenadores[2],
                'titulo': 'Monitoramento da Biodiversidade no Campus',
                'tipo_projeto': Projeto.TIPO_PROJETO_AGENCIA_FOMENTO,
                'status': 'finalizado',
                'centro_lotacao': centros['CCBN'],
                'curso': cursos['Licenciatura em Ciências Biológicas'],
                'agencia_financiadora': agencia_cnpq,
                'valor_fomento': Decimal('25000.00'),
                'finalizado_em': agora - timedelta(days=15),
            },
            {
                'coordenador': coordenadores[2],
                'titulo': 'Educação Ambiental em Escolas Públicas',
                'tipo_projeto': Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
                'status': 'encerrado',
                'centro_lotacao': centros['CCBN'],
                'curso': cursos['Licenciatura em Ciências Biológicas'],
                'edital': edital_aberto,
                'encerrado_em': agora - timedelta(days=10),
                'encerrado_por': gestores[2],
                'motivo_encerramento': 'Projeto encerrado antecipadamente para demonstrar o fluxo excepcional.',
            },
        )

        projetos = []
        equipes_alunos = (
            (alunos[0], alunos[1]),
            (alunos[1], alunos[2]),
            (alunos[0], alunos[2]),
        )
        for indice, definicao in enumerate(definicoes):
            projeto = Projeto.objects.create(
                descricao='Projeto de demonstração criado para validar as funcionalidades da plataforma.',
                resumo='Exemplo de projeto institucional com dados suficientes para testes de navegação e fluxo.',
                introducao='Contextualização e justificativa do projeto de demonstração.',
                objetivo_geral='Validar o fluxo completo de gestão de projetos institucionais.',
                objetivos_especificos='Cadastrar dados; acompanhar tramitação; verificar permissões e relatórios.',
                metodologia='Execução organizada em etapas de planejamento, acompanhamento e avaliação.',
                resultados='Fluxo validado e registros disponíveis para consulta pelos perfis autorizados.',
                referencias='UNIVERSIDADE FEDERAL DO ACRE. Documentos institucionais.',
                palavras_chave='UFAC, projeto institucional, demonstração',
                parcerias='Unidades acadêmicas da UFAC',
                data_inicio=hoje - timedelta(days=180 - indice * 15),
                data_fim=hoje + timedelta(days=180 - indice * 10),
                eh_docente=True,
                eh_pesquisador=True,
                ultima_alteracao_gestor_em=agora if definicao['status'] != 'rascunho' else None,
                ultima_alteracao_gestor_por=(
                    gestores[indice % len(gestores)]
                    if definicao['status'] != 'rascunho'
                    else None
                ),
                **definicao,
            )
            projeto.ods.add(ods[indice % len(ods)], ods[(indice + 3) % len(ods)])
            projeto.grupos_pesquisa.add(grupo_inovacao)
            EquipeProjeto.objects.create(
                projeto=projeto,
                membro=projeto.coordenador,
                origem_membro=EquipeProjeto.ORIGEM_SISTEMA,
                funcao='coordenador',
                carga_horaria_semanal=10,
                carga_horaria_total=240,
            )
            for aluno in equipes_alunos[indice % len(equipes_alunos)]:
                EquipeProjeto.objects.create(
                    projeto=projeto,
                    membro=aluno,
                    origem_membro=EquipeProjeto.ORIGEM_SISTEMA,
                    funcao='estudante_graduacao',
                    carga_horaria_semanal=8,
                    carga_horaria_total=192,
                )
            projetos.append(projeto)

        token_centro = 'demo-centro-ufac-2026'
        SolicitacaoAprovacaoCentro.objects.create(
            projeto=projetos[1],
            token_hash=SolicitacaoAprovacaoCentro.calcular_hash(token_centro),
            email_destinatario=projetos[1].centro_lotacao.email,
            expira_em=agora + timedelta(days=30),
        )

        Notificacao.objects.bulk_create([
            Notificacao(
                destinatario=usuario,
                mensagem='Conta de demonstração criada e pronta para os testes da plataforma.',
                link='/projetos/telaprincipal/',
            )
            for usuario in usuarios.values()
        ])

        self.stdout.write(self.style.SUCCESS(
            f'Base de demonstração criada: {len(usuarios)} usuários, '
            f'{len(projetos)} projetos, {CentroLotacao.objects.count()} centros e '
            f'{CursoGraduacao.objects.count()} cursos.'
        ))
        self.stdout.write('Credenciais de demonstração:')
        for cpf, nome, sobrenome, perfil, _email in USUARIOS_DEMO:
            self.stdout.write(
                f'- {perfil}: {nome} {sobrenome} | CPF {formatar_cpf(cpf)} '
                f'| senha {SENHAS_DEMO[perfil]}'
            )
        self.stdout.write(
            f'Link de uso único do Centro: /projetos/centro/aprovacao/{token_centro}/'
        )
