from datetime import date, timedelta
from io import BytesIO, StringIO
from unittest.mock import ANY, patch
import re
from pathlib import Path

import tinycss2
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import InMemoryStorage
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from PIL import Image
from weasyprint import HTML

from .document_extraction import extrair_campos_projeto
from .ethics_notifications import processar_alertas_etica
from .forms import (
    CoordenadorProfileForm,
    EquipeProjetoForm,
    ProjetoEtapa1Form,
    ProjetoEtapa2AgenciaFomentoForm,
)
from .management.commands.povoar_demonstracao import (
    TITULOS_PROJETOS_DEMO,
    USUARIOS_DEMO,
)
from .models import (
    Anexo, CentroLotacao, CursoGraduacao, Edital, EquipeProjeto, ODS, Projeto,
    Notificacao, NotificacaoPrazoEtica, SolicitacaoAprovacaoCentro, Usuario,
)
from .views import _gerar_relatorio_submissao


class MobileLayoutRegressionTests(SimpleTestCase):
    def test_layout_de_tela_pequena_restringe_menu_conteudo_e_tabela(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')
        regras = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
        regras_mobile = [
            regra for regra in regras
            if regra.type == 'at-rule'
            and regra.at_keyword == 'media'
            and 'max-width: 768px' in tinycss2.serialize(regra.prelude)
        ]
        self.assertTrue(regras_mobile, 'Deve existir uma regra de layout para larguras móveis.')

        regras_internas = tinycss2.parse_rule_list(
            regras_mobile[0].content,
            skip_comments=True,
            skip_whitespace=True,
        )
        estilos = {}
        for regra in regras_internas:
            if regra.type != 'qualified-rule':
                continue
            seletor = tinycss2.serialize(regra.prelude).strip()
            declaracoes = tinycss2.parse_declaration_list(
                regra.content,
                skip_comments=True,
                skip_whitespace=True,
            )
            estilos[seletor] = {
                declaracao.name: tinycss2.serialize(declaracao.value).strip()
                for declaracao in declaracoes
                if declaracao.type == 'declaration'
            }

        self.assertEqual(estilos.get('#sidebar.collapsed', {}).get('width'), '88px')
        self.assertEqual(estilos.get('#main-content', {}).get('min-width'), '0')
        self.assertEqual(estilos.get('.table-responsive', {}).get('overflow-x'), 'auto')


class CatalogoEPerfilTests(TestCase):
    def test_regime_de_trabalho_aceita_somente_opcoes_institucionais(self):
        usuario = Usuario.objects.create_user(
            cpf='52998224725',
            username='coord-regime',
            email='coord-regime@example.com',
            password='senha-segura-123',
            perfil='coordenador',
        )
        form = CoordenadorProfileForm(data={
            'first_name': 'Coordena',
            'last_name': 'Dor',
            'email': usuario.email,
            'regime_trabalho': '30h',
            'participa_pos_graduacao': 'False',
        }, instance=usuario)

        self.assertFalse(form.is_valid())
        self.assertIn('regime_trabalho', form.errors)
        opcoes = {
            valor for valor, _rotulo in form.fields['regime_trabalho'].choices if valor
        }
        self.assertEqual(opcoes, {'20h', '40h', 'DE'})

    def test_comando_cria_catalogo_usuarios_e_projetos_demonstrativos(self):
        saida = StringIO()
        call_command('povoar_demonstracao', confirmar=True, stdout=saida)

        self.assertEqual(Usuario.objects.count(), 9)
        self.assertEqual(Projeto.objects.count(), 9)
        self.assertEqual(CentroLotacao.objects.count(), 8)
        self.assertEqual(CursoGraduacao.objects.count(), 49)
        self.assertEqual(ODS.objects.count(), 17)
        self.assertTrue(all(
            usuario.check_password({
                'coordenador': 'Coord@2026',
                'aluno': 'Aluno@2026',
                'gestor': 'Gestor@2026',
            }[usuario.perfil])
            for usuario in Usuario.objects.all()
        ))
        self.assertEqual(
            set(Projeto.objects.values_list('status', flat=True)),
            {
                'rascunho', 'aguardando_conselho', 'submetido', 'aprovado',
                'em_andamento', 'reprovado', 'aguardando_encerramento',
                'finalizado', 'encerrado',
            },
        )

    def test_comando_aditivo_preserva_dados_e_pode_ser_reexecutado(self):
        usuario_existente = Usuario.objects.create_user(
            cpf='52998224725',
            username='usuario-existente',
            email='existente@ufac.br',
            password='senha-segura-123',
            perfil='coordenador',
            is_active=True,
        )
        projeto_existente = Projeto.objects.create(
            coordenador=usuario_existente,
            titulo='Projeto existente em produção',
        )

        call_command('povoar_demonstracao', adicionar=True, stdout=StringIO())
        call_command('povoar_demonstracao', adicionar=True, stdout=StringIO())

        self.assertTrue(Usuario.objects.filter(pk=usuario_existente.pk).exists())
        self.assertTrue(Projeto.objects.filter(pk=projeto_existente.pk).exists())
        self.assertEqual(
            Usuario.objects.filter(cpf__in=[dados[0] for dados in USUARIOS_DEMO]).count(),
            9,
        )
        self.assertEqual(
            Projeto.objects.filter(titulo__in=TITULOS_PROJETOS_DEMO).count(),
            9,
        )
        self.assertEqual(Projeto.objects.count(), 10)

        call_command('limpar_demonstracao', confirmar=True, stdout=StringIO())

        self.assertTrue(Usuario.objects.filter(pk=usuario_existente.pk).exists())
        self.assertTrue(Projeto.objects.filter(pk=projeto_existente.pk).exists())
        self.assertFalse(
            Usuario.objects.filter(cpf__in=[dados[0] for dados in USUARIOS_DEMO]).exists()
        )
        self.assertFalse(Projeto.objects.filter(titulo__in=TITULOS_PROJETOS_DEMO).exists())

    def test_ajuda_apresenta_secao_sobre_o_sistema(self):
        usuario = Usuario.objects.create_user(
            cpf='11144477735',
            username='usuario-ajuda',
            email='usuario-ajuda@example.com',
            password='senha-segura-123',
            perfil='aluno',
            is_active=True,
        )
        self.client.force_login(usuario)

        resposta = self.client.get(reverse('ajuda'))

        self.assertContains(resposta, 'Sobre o Sistema e os Desenvolvedores')
        self.assertContains(resposta, 'Douglas Moura Araújo')


class ProjetoTipoFluxoFormTests(TestCase):
    def setUp(self):
        self.coordenador = Usuario.objects.create_user(
            cpf='52998224725',
            username='coordenador',
            email='coordenador@example.com',
            password='senha-segura-123',
            first_name='Coordena',
            last_name='Dor',
            perfil='coordenador',
            status='ativo',
            is_active=True,
        )
        self.centro = CentroLotacao.objects.create(
            nome='Centro de Testes',
            email='centro@example.com',
        )
        self.edital = Edital.objects.create(
            tipo='PROPEG',
            numero=1,
            ano=date.today().year,
            titulo='Edital aberto para testes',
            descricao='Edital usado nos testes do fluxo por tipo.',
            data_inicio_submissoes=date.today() - timedelta(days=1),
            data_fim_submissoes=date.today() + timedelta(days=1),
            status='aberto',
            criado_por=self.coordenador,
        )

    def dados_etapa_1(self, tipo_projeto, **alteracoes):
        dados = {
            'tipo_projeto': tipo_projeto,
            'titulo': 'Projeto de Teste',
            'data_inicio': date.today().isoformat(),
            'data_fim': (date.today() + timedelta(days=30)).isoformat(),
            'edital': '',
            'centro_lotacao': str(self.centro.pk),
            'curso': '',
            'valor_fomento': '',
            'agencia_financiadora_nome': '',
            'programa_pos_nome': '',
            'tipo_etica_nome': '',
            'grupos_pesquisa_str': '',
            'eh_docente': 'False',
            'eh_pesquisador': 'False',
            'eh_pesquisador_visitante': 'False',
            'participa_pos_graduacao': 'False',
            'etica_obrigatoria': 'False',
        }
        dados.update(alteracoes)
        return dados

    def novo_projeto(self):
        return Projeto(coordenador=self.coordenador, status='rascunho')

    def criar_projeto_publico(self, tipo_projeto, titulo):
        return Projeto.objects.create(
            coordenador=self.coordenador,
            centro_lotacao=self.centro,
            tipo_projeto=tipo_projeto,
            titulo=titulo,
            status='aprovado',
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=30),
        )

    def test_agencia_exige_nome_e_comprovante(self):
        form = ProjetoEtapa1Form(
            data=self.dados_etapa_1(Projeto.TIPO_PROJETO_AGENCIA_FOMENTO),
            instance=self.novo_projeto(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn('agencia_financiadora_nome', form.errors)
        self.assertIn('comprovante_fomento', form.errors)

    def test_agencia_aceita_comprovante_pdf_ou_imagem(self):
        for nome, content_type in (
            ('comprovante.pdf', 'application/pdf'),
            ('comprovante.png', 'image/png'),
            ('comprovante.jpg', 'image/jpeg'),
        ):
            with self.subTest(nome=nome):
                arquivo = SimpleUploadedFile(nome, b'conteudo-de-teste', content_type=content_type)
                form = ProjetoEtapa1Form(
                    data=self.dados_etapa_1(
                        Projeto.TIPO_PROJETO_AGENCIA_FOMENTO,
                        agencia_financiadora_nome='CNPq',
                    ),
                    files={'comprovante_fomento': arquivo},
                    instance=self.novo_projeto(),
                )
                self.assertTrue(form.is_valid(), form.errors)

    def test_agencia_rejeita_formato_diferente(self):
        arquivo = SimpleUploadedFile('comprovante.txt', b'invalido', content_type='text/plain')
        form = ProjetoEtapa1Form(
            data=self.dados_etapa_1(
                Projeto.TIPO_PROJETO_AGENCIA_FOMENTO,
                agencia_financiadora_nome='CAPES',
            ),
            files={'comprovante_fomento': arquivo},
            instance=self.novo_projeto(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn('comprovante_fomento', form.errors)

    def test_ufac_sem_financiamento_nao_exige_ata_do_coordenador(self):
        form = ProjetoEtapa1Form(
            data=self.dados_etapa_1(Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO),
            instance=self.novo_projeto(),
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn('ata_conselho', form.fields)

    def test_ufac_sem_financiamento_exige_email_do_centro(self):
        self.centro.email = ''
        self.centro.save(update_fields=['email'])
        form = ProjetoEtapa1Form(
            data=self.dados_etapa_1(Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO),
            instance=self.novo_projeto(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn('centro_lotacao', form.errors)

    def test_ufac_com_financiamento_exige_edital_aberto(self):
        dados = self.dados_etapa_1(Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO)
        form = ProjetoEtapa1Form(data=dados, instance=self.novo_projeto())
        self.assertFalse(form.is_valid())
        self.assertIn('edital', form.errors)

        dados['edital'] = str(self.edital.pk)
        form_com_edital = ProjetoEtapa1Form(data=dados, instance=self.novo_projeto())
        self.assertTrue(form_com_edital.is_valid(), form_com_edital.errors)

    def test_aspectos_eticos_exigem_situacao_e_comprovante_correspondente(self):
        dados = self.dados_etapa_1(
            Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            etica_obrigatoria='True',
            tipo_etica_nome='CEP',
            situacao_etica='submetido',
        )
        sem_arquivo = ProjetoEtapa1Form(data=dados, instance=self.novo_projeto())
        self.assertFalse(sem_arquivo.is_valid())
        self.assertIn('comprovante_etica', sem_arquivo.errors)

        arquivo = SimpleUploadedFile(
            'submissao.pdf', b'%PDF-1.4 submissao', content_type='application/pdf'
        )
        com_arquivo = ProjetoEtapa1Form(
            data=dados,
            files={'comprovante_etica': arquivo},
            instance=self.novo_projeto(),
        )
        self.assertTrue(com_arquivo.is_valid(), com_arquivo.errors)

    def test_documento_da_etapa_2_e_opcional(self):
        projeto = self.novo_projeto()
        projeto.tipo_projeto = Projeto.TIPO_PROJETO_AGENCIA_FOMENTO

        form = ProjetoEtapa2AgenciaFomentoForm(
            data={'resumo': 'Resumo', 'palavras_chave': 'pesquisa, inovação'},
            instance=projeto,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_relatorio_incorpora_imagens_e_paginas_de_pdfs_dos_anexos(self):
        projeto = self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            'Projeto com anexos incorporados',
        )

        imagem_buffer = BytesIO()
        Image.new('RGB', (80, 50), (0, 94, 184)).save(imagem_buffer, format='PNG')
        pdf_anexo = HTML(string='<h1>Documento anexado</h1><p>Conteúdo do PDF.</p>').write_pdf()

        campo_arquivo = Anexo._meta.get_field('arquivo')
        with patch.object(campo_arquivo, 'storage', InMemoryStorage()):
            Anexo.objects.create(
                projeto=projeto,
                tipo_anexo='imagens',
                arquivo=SimpleUploadedFile(
                    'figura.png', imagem_buffer.getvalue(), content_type='image/png'
                ),
                descricao='Figura incorporada',
            )
            Anexo.objects.create(
                projeto=projeto,
                tipo_anexo='outro',
                arquivo=SimpleUploadedFile(
                    'documento-anexo.pdf', pdf_anexo, content_type='application/pdf'
                ),
                descricao='PDF incorporado',
            )

            relatorio = _gerar_relatorio_submissao(projeto)
            relatorio.arquivo.open('rb')
            resultado = relatorio.arquivo.read()

        leitor = PdfReader(BytesIO(resultado))
        texto = '\n'.join((pagina.extract_text() or '') for pagina in leitor.pages)
        self.assertIn('Documento PDF incorporado ao relatório.', texto)
        self.assertIn('PDF incorporado', texto)
        self.assertGreaterEqual(len(leitor.pages), 4)

    def test_documento_digital_da_etapa_2_e_aceito(self):
        projeto = self.novo_projeto()
        projeto.tipo_projeto = Projeto.TIPO_PROJETO_AGENCIA_FOMENTO
        pdf = HTML(string='''
            <h1>Resumo</h1>
            <p>Este documento possui texto selecionável suficiente para ser processado automaticamente.</p>
            <h1>Objetivo Geral</h1>
            <p>Analisar o funcionamento da plataforma de projetos institucionais.</p>
        ''').write_pdf()

        documento = SimpleUploadedFile('projeto.pdf', pdf, content_type='application/pdf')
        form_com_documento = ProjetoEtapa2AgenciaFomentoForm(
            data={'resumo': 'Resumo', 'palavras_chave': 'pesquisa, inovação'},
            files={'documento_projeto': documento},
            instance=projeto,
        )
        self.assertTrue(form_com_documento.is_valid(), form_com_documento.errors)

    def test_pdf_digitalizado_sem_texto_e_rejeitado(self):
        saida = BytesIO()
        escritor = PdfWriter()
        escritor.add_blank_page(width=595, height=842)
        escritor.write(saida)
        documento = SimpleUploadedFile('digitalizado.pdf', saida.getvalue(), content_type='application/pdf')

        form = ProjetoEtapa2AgenciaFomentoForm(
            data={'resumo': 'Resumo', 'palavras_chave': 'pesquisa, inovação'},
            files={'documento_projeto': documento},
            instance=self.novo_projeto(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn('documento_projeto', form.errors)
        self.assertIn('nativamente digital', str(form.errors['documento_projeto']))

    def test_extracao_identifica_todos_os_campos_da_etapa_2(self):
        texto = '''
        RESUMO
        Resumo do projeto.
        PALAVRAS-CHAVE: pesquisa, inovação, universidade
        1 INTRODUÇÃO E JUSTIFICATIVA
        Contexto e justificativa do projeto.
        2 OBJETIVOS
        2.1 OBJETIVO GERAL
        Desenvolver a solução proposta.
        2.2 OBJETIVOS ESPECÍFICOS
        Mapear o processo.
        Validar a implementação.
        3 METODOLOGIA
        Pesquisa aplicada e testes automatizados.
        4 RESULTADOS ESPERADOS
        Maior eficiência no cadastro.
        5 PARCERIAS
        Universidade e comunidade.
        6 REFERÊNCIAS BIBLIOGRÁFICAS
        AUTOR. Obra de referência. 2026.
        '''

        campos = extrair_campos_projeto(texto)

        self.assertEqual(
            set(campos),
            {
                'resumo', 'palavras_chave', 'introducao', 'objetivo_geral',
                'objetivos_especificos', 'metodologia', 'resultados',
                'parcerias', 'referencias',
            },
        )
        self.assertIn('Desenvolver a solução', campos['objetivo_geral'])
        self.assertIn('Maior eficiência', campos['resultados'])

    def test_acao_preencher_documento_salva_campos_e_mantem_na_etapa_2(self):
        projeto = self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            'Projeto para preenchimento automático',
        )
        projeto.status = 'rascunho'
        projeto.save(update_fields=['status'])
        pdf = HTML(string='''
            <h1>RESUMO</h1>
            <p>Resumo digital do projeto com conteudo selecionavel suficiente para processamento.</p>
            <h1>PALAVRAS-CHAVE</h1>
            <p>pesquisa, inovacao, universidade</p>
            <h1>INTRODUCAO E JUSTIFICATIVA</h1>
            <p>Contexto digital da proposta e sua justificativa institucional.</p>
            <h1>OBJETIVO GERAL</h1>
            <p>Automatizar o cadastro de projetos.</p>
            <h1>OBJETIVOS ESPECIFICOS</h1>
            <p>Extrair secoes e permitir revisao.</p>
            <h1>METODOLOGIA</h1>
            <p>Extracao textual e testes automatizados.</p>
            <h1>RESULTADOS ESPERADOS</h1>
            <p>Cadastro mais eficiente e consistente.</p>
        ''').write_pdf()
        documento = SimpleUploadedFile('projeto-digital.pdf', pdf, content_type='application/pdf')
        self.client.force_login(self.coordenador)

        campo_arquivo = Anexo._meta.get_field('arquivo')
        with patch.object(campo_arquivo, 'storage', InMemoryStorage()):
            resposta = self.client.post(
                reverse('projeto_etapa', kwargs={'pk': projeto.pk, 'step': 2}),
                data={
                    'acao': 'preencher_documento',
                    'documento_projeto': documento,
                },
            )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            resposta.url,
            reverse('projeto_etapa', kwargs={'pk': projeto.pk, 'step': 2}),
        )
        projeto.refresh_from_db()
        self.assertIn('Resumo digital', projeto.resumo)
        self.assertIn('Automatizar o cadastro', projeto.objetivo_geral)
        self.assertIn('Cadastro mais eficiente', projeto.resultados)
        self.assertTrue(projeto.anexos.filter(tipo_anexo='projeto_completo').exists())

    def test_consulta_publica_filtra_pelos_tres_tipos(self):
        self.criar_projeto_publico(Projeto.TIPO_PROJETO_AGENCIA_FOMENTO, 'Projeto agência')
        projeto_sem = self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            'Projeto fluxo contínuo',
        )
        self.criar_projeto_publico(Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO, 'Projeto edital UFAC')

        resposta = self.client.get(
            reverse('consulta_publica'),
            {'tipo_projeto': Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['total'], 1)
        self.assertEqual(list(resposta.context['page_obj'].object_list), [projeto_sem])

    def test_consulta_publica_busca_coordenador_pelo_nome_completo(self):
        self.coordenador.first_name = 'Bruno'
        self.coordenador.last_name = 'Lima'
        self.coordenador.save(update_fields=['first_name', 'last_name'])
        projeto = self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            'Projeto encontrado pelo coordenador',
        )

        resposta = self.client.get(reverse('consulta_publica'), {'q': 'Bruno Lima'})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['total'], 1)
        self.assertEqual(list(resposta.context['page_obj'].object_list), [projeto])

    def test_consulta_publica_mantem_links_antigos_de_financiamento(self):
        self.criar_projeto_publico(Projeto.TIPO_PROJETO_AGENCIA_FOMENTO, 'Projeto agência')
        self.criar_projeto_publico(Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO, 'Projeto fluxo contínuo')
        self.criar_projeto_publico(Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO, 'Projeto edital UFAC')

        resposta = self.client.get(reverse('consulta_publica'), {'financiamento': 'sim'})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['total'], 2)
        self.assertEqual(resposta.context['tipo_projeto_filter_label'], 'Com financiamento')

    def test_consulta_publica_filtra_por_vinculo_com_ods(self):
        ods_saude = ODS.objects.create(titulo='ODS 3 - Saúde e Bem-Estar')
        ODS.objects.create(titulo='ODS 4 - Educação de Qualidade')
        projeto_saude = self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            'Projeto vinculado à saúde',
        )
        projeto_saude.ods.add(ods_saude)
        self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_AGENCIA_FOMENTO,
            'Projeto sem o ODS pesquisado',
        )

        resposta = self.client.get(reverse('consulta_publica'), {'ods': ods_saude.pk})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['total'], 1)
        self.assertEqual(list(resposta.context['page_obj'].object_list), [projeto_saude])

    def test_consulta_publica_combina_ods_por_todas_ou_qualquer(self):
        ods_um = ODS.objects.create(titulo='ODS 1 - Erradicação da Pobreza')
        ods_dez = ODS.objects.create(titulo='ODS 10 - Redução das Desigualdades')
        projeto_duas = self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            'Projeto com as duas ODS',
        )
        projeto_duas.ods.add(ods_um, ods_dez)
        projeto_um = self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_AGENCIA_FOMENTO,
            'Projeto somente ODS 1',
        )
        projeto_um.ods.add(ods_um)
        projeto_dez = self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
            'Projeto somente ODS 10',
        )
        projeto_dez.ods.add(ods_dez)

        resposta_and = self.client.get(
            reverse('consulta_publica'),
            {'ods': [ods_um.pk, ods_dez.pk]},
        )
        self.assertEqual(resposta_and.context['ods_match'], 'all')
        self.assertEqual(list(resposta_and.context['page_obj'].object_list), [projeto_duas])

        resposta_or = self.client.get(
            reverse('consulta_publica'),
            {'ods': [ods_um.pk, ods_dez.pk], 'ods_match': 'any'},
        )
        self.assertEqual(resposta_or.context['total'], 3)
        self.assertCountEqual(
            resposta_or.context['page_obj'].object_list,
            [projeto_duas, projeto_um, projeto_dez],
        )

    def test_filtro_publico_exibe_ods_em_ordem_numerica(self):
        ods_dez = ODS.objects.create(titulo='ODS 10 - Redução das Desigualdades')
        ods_um = ODS.objects.create(titulo='ODS 1 - Erradicação da Pobreza')
        projeto = self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            'Projeto para ordenar ODS',
        )
        projeto.ods.add(ods_dez, ods_um)

        resposta = self.client.get(reverse('consulta_publica'))

        ods_ids = [ods.pk for ods in resposta.context['ods_disponiveis']]
        self.assertLess(ods_ids.index(ods_um.pk), ods_ids.index(ods_dez.pk))

    def test_detalhe_nao_quebra_quando_ods_nao_tem_imagem(self):
        ods = ODS.objects.create(titulo='ODS sem imagem')
        projeto = self.criar_projeto_publico(
            Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            'Projeto sem imagem de ODS',
        )
        projeto.ods.add(ods)
        self.client.force_login(self.coordenador)

        resposta = self.client.get(reverse('projeto_detalhe', kwargs={'pk': projeto.pk}))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'ODS sem imagem')


class AprovacaoPreviaCentroTests(TestCase):
    def setUp(self):
        self.centro = CentroLotacao.objects.create(
            nome='Centro de Ciências de Teste',
            email='conselho@example.com',
        )
        self.coordenador = Usuario.objects.create_user(
            cpf='52998224725',
            username='coordenador-centro',
            email='coordenador-centro@example.com',
            password='senha-segura-123',
            first_name='Ana',
            last_name='Coordenadora',
            perfil='coordenador',
            status='ativo',
            is_active=True,
        )
        self.gestor = Usuario.objects.create_user(
            cpf='93541134780',
            username='gestor-centro',
            email='gestor-centro@example.com',
            password='senha-segura-123',
            first_name='Gestor',
            last_name='PROPEG',
            perfil='gestor',
            status='ativo',
            is_active=True,
        )
        self.projeto = Projeto.objects.create(
            coordenador=self.coordenador,
            centro_lotacao=self.centro,
            tipo_projeto=Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            titulo='Projeto de Fluxo Contínuo',
            resumo='Resumo completo para a submissão.',
            objetivo_geral='Validar o novo fluxo institucional.',
            metodologia='Pesquisa aplicada com acompanhamento do Centro.',
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=180),
            status='rascunho',
        )

    @patch('projetos_institucionais.views._gerar_relatorio_submissao')
    def test_fluxo_centro_usa_link_unico_e_encaminha_a_propeg(self, gerar_pdf):
        self.client.force_login(self.coordenador)
        resposta = self.client.post(
            reverse('projeto_etapa', kwargs={'pk': self.projeto.pk, 'step': 5}),
            {'acao': 'submeter'},
        )

        self.assertEqual(resposta.status_code, 200)
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status, 'aguardando_conselho')
        gerar_pdf.assert_called_once_with(self.projeto, ANY)

        solicitacao = SolicitacaoAprovacaoCentro.objects.get(projeto=self.projeto)
        self.assertTrue(solicitacao.esta_ativa)
        self.assertEqual(len(mail.outbox), 1)
        correspondencia = re.search(r'/centro/aprovacao/([^/]+)/', mail.outbox[0].body)
        self.assertIsNotNone(correspondencia)
        token = correspondencia.group(1)
        self.assertNotEqual(solicitacao.token_hash, token)

        self.client.force_login(self.gestor)
        painel = self.client.get(reverse('gestor_dashboard'))
        self.assertNotIn(self.projeto, painel.context['projetos_pendentes'])
        self.assertNotIn(self.projeto, painel.context['projetos_aguardando_centro'])
        self.client.get(reverse('aprovar_projeto', kwargs={'pk': self.projeto.pk}))
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status, 'aguardando_conselho')

        self.client.logout()
        pagina = self.client.get(reverse('aprovacao_centro', kwargs={'token': token}))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Esta página permite somente')

        campo_arquivo = Anexo._meta.get_field('arquivo')
        with patch.object(campo_arquivo, 'storage', InMemoryStorage()):
            envio = self.client.post(
                reverse('aprovacao_centro', kwargs={'token': token}),
                data={
                    'responsavel_nome': 'Maria Diretora',
                    'responsavel_cargo': 'Diretora do Centro',
                    'ata_assembleia': SimpleUploadedFile(
                        'ata-aprovacao.pdf',
                        b'%PDF-1.4 ata aprovada',
                        content_type='application/pdf',
                    ),
                    'confirma_aprovacao': 'on',
                },
            )

        self.assertEqual(envio.status_code, 200)
        self.assertContains(envio, 'Ata registrada com sucesso')
        self.projeto.refresh_from_db()
        solicitacao.refresh_from_db()
        self.assertEqual(self.projeto.status, 'submetido')
        self.assertIsNotNone(solicitacao.utilizada_em)
        self.assertEqual(solicitacao.responsavel_nome, 'Maria Diretora')
        self.assertTrue(self.projeto.anexos.filter(tipo_anexo='ata_conselho').exists())

        segundo_envio = self.client.post(
            reverse('aprovacao_centro', kwargs={'token': token}),
            data={},
        )
        self.assertEqual(segundo_envio.status_code, 410)
        self.assertContains(segundo_envio, 'já foi utilizado', status_code=410)

        self.client.force_login(self.gestor)
        painel = self.client.get(reverse('gestor_dashboard'))
        self.assertIn(self.projeto, painel.context['projetos_pendentes'])

    def test_link_expirado_nao_expoe_o_projeto(self):
        solicitacao, token = SolicitacaoAprovacaoCentro.emitir(
            self.projeto,
            self.centro.email,
            validade_horas=1,
        )
        solicitacao.expira_em = timezone.now() - timedelta(minutes=1)
        solicitacao.save(update_fields=['expira_em'])
        self.projeto.status = 'aguardando_conselho'
        self.projeto.save(update_fields=['status'])

        resposta = self.client.get(reverse('aprovacao_centro', kwargs={'token': token}))

        self.assertEqual(resposta.status_code, 410)
        self.assertContains(resposta, 'expirou', status_code=410)

    def test_historico_filtra_por_multiplos_ods(self):
        ods_educacao = ODS.objects.create(titulo='ODS 4 - Educação de Qualidade')
        ods_clima = ODS.objects.create(titulo='ODS 13 - Ação Climática')
        self.projeto.status = 'submetido'
        self.projeto.save(update_fields=['status'])
        self.projeto.ods.add(ods_educacao)
        outro = Projeto.objects.create(
            coordenador=self.coordenador,
            centro_lotacao=self.centro,
            tipo_projeto=Projeto.TIPO_PROJETO_AGENCIA_FOMENTO,
            titulo='Projeto climático',
            status='submetido',
        )
        outro.ods.add(ods_clima)
        self.client.force_login(self.gestor)

        resposta = self.client.get(reverse('historico_projetos'), {'ods': [ods_educacao.pk]})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context['pagina_de_projetos']), [self.projeto])


class EtapasDoisETresTests(TestCase):
    def setUp(self):
        self.centro = CentroLotacao.objects.create(nome='Centro de Tecnologia')
        self.curso = CursoGraduacao.objects.create(
            nome='Sistemas de Informação',
            centro_lotacao=self.centro,
        )
        self.coordenador = Usuario.objects.create_user(
            cpf='52998224725',
            username='coordenador-etapas',
            email='coordenador-etapas@example.com',
            password='senha-segura-123',
            first_name='Ana',
            last_name='Coordenadora',
            perfil='coordenador',
            status='ativo',
            is_active=True,
        )
        self.aluno = Usuario.objects.create_user(
            cpf='11144477735',
            username='aluno-etapas',
            email='aluno-etapas@example.com',
            password='senha-segura-123',
            first_name='Bruno',
            last_name='Acadêmico',
            perfil='aluno',
            status='ativo',
            is_active=True,
            curso=self.curso,
        )
        self.projeto = Projeto.objects.create(
            coordenador=self.coordenador,
            centro_lotacao=self.centro,
            tipo_projeto=Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            titulo='Projeto das Etapas 2 e 3',
            status='rascunho',
        )

    def test_todos_os_campos_da_etapa_2_tem_limite_de_4000(self):
        form = ProjetoEtapa2AgenciaFomentoForm(instance=self.projeto)

        for nome in form.Meta.fields:
            with self.subTest(campo=nome):
                self.assertEqual(form.fields[nome].max_length, 4000)
                self.assertEqual(form.fields[nome].widget.attrs['maxlength'], 4000)
                self.assertEqual(form.fields[nome].widget.__class__.__name__, 'Textarea')

    def test_etapa_2_rejeita_conteudo_acima_de_4000_caracteres(self):
        form = ProjetoEtapa2AgenciaFomentoForm(
            data={
                'resumo': 'R' * 4001,
                'palavras_chave': 'pesquisa, inovação',
            },
            instance=self.projeto,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('resumo', form.errors)

    def test_membro_manual_e_validado_e_salvo(self):
        self.client.force_login(self.coordenador)
        resposta = self.client.post(
            reverse('projeto_etapa', kwargs={'pk': self.projeto.pk, 'step': 3}),
            data={
                'acao': 'proximo',
                'equipe-TOTAL_FORMS': '1',
                'equipe-INITIAL_FORMS': '0',
                'equipe-MIN_NUM_FORMS': '0',
                'equipe-MAX_NUM_FORMS': '1000',
                'equipe-0-origem_membro': EquipeProjeto.ORIGEM_MANUAL,
                'equipe-0-membro': '',
                'equipe-0-nome_membro_manual': 'Carla Pesquisadora',
                'equipe-0-cpf_manual': '935.411.347-80',
                'equipe-0-funcao': 'estudante_pos_mestrado',
                'equipe-0-carga_horaria_semanal': '20',
                'equipe-0-carga_horaria_total': '240',
            },
        )

        self.assertRedirects(
            resposta,
            reverse('projeto_etapa', kwargs={'pk': self.projeto.pk, 'step': 4}),
            fetch_redirect_response=False,
        )
        membro = self.projeto.equipe.get()
        self.assertIsNone(membro.membro)
        self.assertEqual(membro.nome_exibicao, 'Carla Pesquisadora')
        self.assertEqual(membro.cpf_exibicao, '935.411.347-80')
        self.assertEqual(membro.get_funcao_display(), 'Estudante Pós (Mestrado)')

    def test_cpf_de_usuario_existente_orienta_uso_da_busca(self):
        form = EquipeProjetoForm(
            data={
                'origem_membro': EquipeProjeto.ORIGEM_MANUAL,
                'nome_membro_manual': 'Bruno Acadêmico',
                'cpf_manual': self.aluno.cpf,
                'funcao': 'estudante_graduacao',
                'carga_horaria_semanal': 10,
                'carga_horaria_total': 120,
            },
            coordenador=self.coordenador,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('cpf_manual', form.errors)
        self.assertIn('usuário do sistema', str(form.errors['cpf_manual']))

    def test_busca_membro_por_nome_curso_e_cpf(self):
        self.client.force_login(self.coordenador)
        url = reverse('ajax_buscar_membros')

        for termo in ('Bruno', 'Sistemas', '111444', '111.444.777-35'):
            with self.subTest(termo=termo):
                resposta = self.client.get(url, {'q': termo})
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.json()['resultados'][0]['id'], self.aluno.pk)

    def test_etapas_2_e_3_renderizam_os_novos_controles(self):
        self.client.force_login(self.coordenador)

        etapa_2 = self.client.get(
            reverse('projeto_etapa', kwargs={'pk': self.projeto.pk, 'step': 2}),
        )
        self.assertEqual(etapa_2.status_code, 200)
        self.assertContains(etapa_2, 'Limite de 4.000 caracteres')
        self.assertContains(etapa_2, 'Remover arquivo selecionado')

        etapa_3 = self.client.get(
            reverse('projeto_etapa', kwargs={'pk': self.projeto.pk, 'step': 3}),
        )
        self.assertEqual(etapa_3.status_code, 200)
        self.assertContains(etapa_3, 'Adicionar usuário do sistema')
        self.assertContains(etapa_3, 'Adicionar manualmente')
        self.assertContains(etapa_3, 'Nome do Membro')
        self.assertContains(etapa_3, 'Carga Horária Total')

    def test_documento_digital_salvo_pode_ser_excluido_na_etapa_2(self):
        self.client.force_login(self.coordenador)
        campo_arquivo = Anexo._meta.get_field('arquivo')
        with patch.object(campo_arquivo, 'storage', InMemoryStorage()):
            anexo = Anexo.objects.create(
                projeto=self.projeto,
                tipo_anexo='projeto_completo',
                arquivo=SimpleUploadedFile('projeto.pdf', b'%PDF-1.4 teste'),
                descricao='Documento digital do projeto.',
            )
            etapa_2 = self.client.get(
                reverse('projeto_etapa', kwargs={'pk': self.projeto.pk, 'step': 2}),
            )
            self.assertContains(etapa_2, reverse('deletar_anexo', kwargs={'anexo_id': anexo.pk}))

            resposta = self.client.post(
                reverse('deletar_anexo', kwargs={'anexo_id': anexo.pk}),
                HTTP_REFERER=reverse('projeto_etapa', kwargs={'pk': self.projeto.pk, 'step': 2}),
            )

        self.assertRedirects(
            resposta,
            reverse('projeto_etapa', kwargs={'pk': self.projeto.pk, 'step': 2}),
            fetch_redirect_response=False,
        )
        self.assertFalse(Anexo.objects.filter(pk=anexo.pk).exists())


class EticaStatusEGestaoTests(TestCase):
    def setUp(self):
        self.coordenador = Usuario.objects.create_user(
            cpf='52998224725', username='coord-etica', email='coord.etica@example.com',
            password='senha-segura-123', first_name='Coordena', last_name='Dora',
            perfil='coordenador', status='ativo', is_active=True,
        )
        self.gestor = Usuario.objects.create_user(
            cpf='93541134780', username='gestor-etica', email='gestor.etica@example.com',
            password='senha-segura-123', first_name='Gestor', last_name='Teste',
            perfil='gestor', status='ativo', is_active=True,
        )
        self.centro = CentroLotacao.objects.create(nome='Centro Ética', email='centro.etica@example.com')
        self.projeto = Projeto.objects.create(
            coordenador=self.coordenador,
            centro_lotacao=self.centro,
            tipo_projeto=Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO,
            titulo='Projeto com aspectos éticos',
            resumo='Resumo',
            objetivo_geral='Objetivo',
            metodologia='Metodologia',
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=180),
            status='submetido',
            etica_obrigatoria=True,
            situacao_etica='submetido',
            etica_submetida_em=date.today(),
            prazo_aprovacao_etica=date.today() + timedelta(days=60),
        )

    def test_gestor_busca_usuario_pelo_nome_completo(self):
        self.coordenador.first_name = 'Ana'
        self.coordenador.last_name = 'Souza'
        self.coordenador.save(update_fields=['first_name', 'last_name'])
        self.client.force_login(self.gestor)

        resposta = self.client.get(reverse('gerenciar_usuarios'), {'q': 'Ana Souza'})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            list(resposta.context['pagina_de_usuarios'].object_list),
            [self.coordenador],
        )

    def _anexar_submissao_etica(self):
        campo_arquivo = Anexo._meta.get_field('arquivo')
        with patch.object(campo_arquivo, 'storage', InMemoryStorage()):
            return Anexo.objects.create(
                projeto=self.projeto,
                tipo_anexo='submissao_comite_etica',
                arquivo=SimpleUploadedFile('submissao.pdf', b'%PDF-1.4 submissao', content_type='application/pdf'),
            )

    def test_alerta_etica_cria_notificacao_email_e_nao_duplica(self):
        self._anexar_submissao_etica()

        self.assertEqual(processar_alertas_etica(date.today()), 1)
        self.assertEqual(processar_alertas_etica(date.today()), 0)
        self.assertEqual(NotificacaoPrazoEtica.objects.filter(projeto=self.projeto).count(), 1)
        self.assertEqual(Notificacao.objects.filter(destinatario=self.coordenador).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('60 dia', mail.outbox[0].subject)

    def test_gestor_nao_aprova_enquanto_etica_estiver_pendente(self):
        self._anexar_submissao_etica()
        self.client.force_login(self.gestor)

        resposta = self.client.get(reverse('aprovar_projeto', kwargs={'pk': self.projeto.pk}))

        self.assertRedirects(resposta, reverse('projeto_detalhe', kwargs={'pk': self.projeto.pk}))
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status, 'submetido')

    def test_upload_definitivo_libera_aprovacao(self):
        self._anexar_submissao_etica()
        self.client.force_login(self.coordenador)
        campo_arquivo = Anexo._meta.get_field('arquivo')
        with patch.object(campo_arquivo, 'storage', InMemoryStorage()):
            resposta = self.client.post(
                reverse('anexar_aprovacao_etica', kwargs={'pk': self.projeto.pk}),
                {'comprovante': SimpleUploadedFile(
                    'aprovacao.pdf', b'%PDF-1.4 aprovado', content_type='application/pdf'
                )},
            )

        self.assertRedirects(resposta, reverse('projeto_detalhe', kwargs={'pk': self.projeto.pk}))
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.situacao_etica, 'aprovado')
        self.assertFalse(self.projeto.etica_pendente)

    def test_finalizado_e_encerrado_sem_conclusao_sao_status_distintos(self):
        projeto_final = Projeto.objects.create(
            coordenador=self.coordenador, centro_lotacao=self.centro,
            titulo='Projeto concluído', status='aguardando_encerramento',
        )
        self.client.force_login(self.gestor)
        self.client.get(reverse('encerrar_projeto', kwargs={'pk': projeto_final.pk}))
        projeto_final.refresh_from_db()
        self.assertEqual(projeto_final.status, 'finalizado')
        self.assertIsNotNone(projeto_final.finalizado_em)

        resposta = self.client.post(
            reverse('encerrar_projeto_sem_conclusao', kwargs={'pk': self.projeto.pk}),
            {'motivo': 'Interrupção por inviabilidade técnica.'},
        )
        self.assertRedirects(resposta, reverse('projeto_detalhe', kwargs={'pk': self.projeto.pk}))
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status, 'encerrado')
        self.assertIn('inviabilidade', self.projeto.motivo_encerramento)
        self.assertEqual(self.projeto.encerrado_por, self.gestor)

    def test_edital_contabiliza_apenas_submissoes_ufac_financiadas(self):
        edital = Edital.objects.create(
            tipo='PROPEG', numero=44, ano=date.today().year, titulo='Edital de concorrência',
            descricao='Teste', data_inicio_submissoes=date.today() - timedelta(days=1),
            data_fim_submissoes=date.today() + timedelta(days=1), status='aberto', criado_por=self.gestor,
        )
        Projeto.objects.create(
            coordenador=self.coordenador, centro_lotacao=self.centro, edital=edital,
            tipo_projeto=Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
            titulo='Concorrente submetido', status='submetido',
        )
        Projeto.objects.create(
            coordenador=self.coordenador, centro_lotacao=self.centro, edital=edital,
            tipo_projeto=Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
            titulo='Rascunho não concorrente', status='rascunho',
        )
        self.client.force_login(self.gestor)

        resposta = self.client.get(reverse('gestor_detalhe_edital', kwargs={'pk': edital.pk}))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['total_submissoes'], 1)
        self.assertContains(resposta, 'Concorrente submetido')
        self.assertNotContains(resposta, 'Rascunho não concorrente')

    def test_gestor_inicia_cadastro_historico_e_edita_projeto(self):
        self.client.force_login(self.gestor)
        resposta = self.client.post(
            reverse('gestor_projeto_criar'),
            {'coordenador': self.coordenador.pk},
        )
        projeto = Projeto.objects.exclude(pk=self.projeto.pk).latest('pk')
        self.assertRedirects(
            resposta,
            reverse('projeto_etapa', kwargs={'pk': projeto.pk, 'step': 1}),
            fetch_redirect_response=False,
        )
        self.assertTrue(projeto.importado_legado)
        self.assertEqual(projeto.coordenador, self.coordenador)
        self.assertEqual(projeto.ultima_alteracao_gestor_por, self.gestor)

        pagina_edicao = self.client.get(reverse('projeto_editar', kwargs={'pk': self.projeto.pk}))
        self.assertRedirects(
            pagina_edicao,
            reverse('projeto_etapa', kwargs={'pk': self.projeto.pk, 'step': 1}),
            fetch_redirect_response=False,
        )
