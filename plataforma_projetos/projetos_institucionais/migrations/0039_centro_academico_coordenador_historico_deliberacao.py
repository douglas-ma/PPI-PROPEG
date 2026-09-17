from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


CENTROS_ACADEMICOS = {
    'CCBN': 'CCBN - Centro Acadêmico de Ciências Biológicas e da Natureza',
    'CCET': 'CCET - Centro Acadêmico de Ciências Exatas e Tecnológicas',
    'CCJSA': 'CCJSA - Centro Acadêmico de Ciências Jurídicas e Sociais Aplicadas',
    'CCSD': 'CCSD - Centro Acadêmico de Ciências da Saúde e do Desporto',
    'CELA': 'CELA - Centro Acadêmico de Educação, Letras e Artes',
    'CFCH': 'CFCH - Centro Acadêmico de Filosofia e Ciências Humanas',
    'CEL': 'CEL - Centro Acadêmico de Educação e Letras (Campus Floresta)',
    'CMULTI': 'CMULTI - Centro Acadêmico Multidisciplinar (Campus Floresta)',
}

CENTROS_ANTERIORES = {
    'CCBN': 'CCBN - Centro de Ciências Biológicas e da Natureza',
    'CCET': 'CCET - Centro de Ciências Exatas e Tecnológicas',
    'CCJSA': 'CCJSA - Centro de Ciências Jurídicas e Sociais Aplicadas',
    'CCSD': 'CCSD - Centro de Ciências da Saúde e do Desporto',
    'CELA': 'CELA - Centro de Educação, Letras e Artes',
    'CFCH': 'CFCH - Centro de Filosofia e Ciências Humanas',
    'CEL': 'CEL - Centro de Educação e Letras (Campus Floresta)',
    'CMULTI': 'CMULTI - Centro Multidisciplinar (Campus Floresta)',
}


def atualizar_nomes_centros_academicos(apps, schema_editor):
    CentroLotacao = apps.get_model('projetos_institucionais', 'CentroLotacao')
    for sigla, nome in CENTROS_ACADEMICOS.items():
        centro = CentroLotacao.objects.filter(nome=sigla).first()
        if centro is None:
            centro = CentroLotacao.objects.filter(nome__startswith=f'{sigla} - ').first()
        if centro is not None and centro.nome != nome:
            centro.nome = nome
            centro.save(update_fields=['nome'])


def restaurar_nomes_centros_ciencias(apps, schema_editor):
    CentroLotacao = apps.get_model('projetos_institucionais', 'CentroLotacao')
    for sigla, nome in CENTROS_ACADEMICOS.items():
        centro = CentroLotacao.objects.filter(nome=nome).first()
        if centro is not None:
            centro.nome = CENTROS_ANTERIORES[sigla]
            centro.save(update_fields=['nome'])


class Migration(migrations.Migration):

    dependencies = [
        ('projetos_institucionais', '0038_alter_usuario_regime_trabalho'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='centrolotacao',
            options={
                'verbose_name': 'Centro Acadêmico',
                'verbose_name_plural': 'Centros Acadêmicos',
            },
        ),
        migrations.AlterModelOptions(
            name='solicitacaoaprovacaocentro',
            options={
                'ordering': ['-criada_em'],
                'verbose_name': 'Solicitação de Deliberação do Centro Acadêmico',
                'verbose_name_plural': 'Solicitações de Deliberação do Centro Acadêmico',
            },
        ),
        migrations.RunPython(
            atualizar_nomes_centros_academicos,
            restaurar_nomes_centros_ciencias,
        ),
        migrations.AlterField(
            model_name='usuario',
            name='centro_lotacao',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='projetos_institucionais.centrolotacao',
                verbose_name='Centro Acadêmico',
            ),
        ),
        migrations.AlterField(
            model_name='cursograduacao',
            name='centro_lotacao',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to='projetos_institucionais.centrolotacao',
                verbose_name='Centro Acadêmico',
            ),
        ),
        migrations.AlterField(
            model_name='programapos',
            name='centro_lotacao',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to='projetos_institucionais.centrolotacao',
                verbose_name='Centro Acadêmico',
            ),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='centro_lotacao',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='projetos_institucionais.centrolotacao',
                verbose_name='Centro Acadêmico',
            ),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='coordenador',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='projetos_coordenados',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='projeto',
            name='coordenador_externo_nome',
            field=models.CharField(
                blank=True,
                max_length=255,
                verbose_name='Nome do coordenador não cadastrado',
            ),
        ),
        migrations.AddField(
            model_name='projeto',
            name='coordenador_externo_cpf',
            field=models.CharField(
                blank=True,
                max_length=14,
                verbose_name='CPF do coordenador não cadastrado',
            ),
        ),
        migrations.AddField(
            model_name='projeto',
            name='coordenador_externo_email',
            field=models.EmailField(
                blank=True,
                max_length=254,
                verbose_name='E-mail do coordenador não cadastrado',
            ),
        ),
        migrations.AddField(
            model_name='solicitacaoaprovacaocentro',
            name='resultado_deliberacao',
            field=models.CharField(
                blank=True,
                choices=[
                    ('aprovado', 'Aprovado pelo Centro Acadêmico'),
                    ('reprovado', 'Reprovado pelo Centro Acadêmico'),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='status',
            field=models.CharField(
                choices=[
                    ('rascunho', 'Rascunho'),
                    ('submetido', 'Submetido'),
                    ('aguardando_conselho', 'Aguardando deliberação do Centro Acadêmico'),
                    ('aprovado', 'Aprovado'),
                    ('reprovado', 'Reprovado'),
                    ('em_andamento', 'Em andamento'),
                    ('aguardando_encerramento', 'Aguardando Finalização'),
                    ('finalizado', 'Finalizado'),
                    ('encerrado', 'Encerrado sem conclusão'),
                ],
                default='rascunho',
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name='anexo',
            name='tipo_anexo',
            field=models.CharField(
                choices=[
                    ('comite_etica', 'Aprovação do Comitê de Ética'),
                    ('submissao_comite_etica', 'Comprovante de Submissão ao Comitê de Ética'),
                    ('cronograma', 'Cronograma'),
                    ('imagens', 'Figuras, Imagens, etc.'),
                    ('projeto_completo', 'Projeto Completo'),
                    ('comprovante_fomento', 'Comprovante de Aprovação da Agência de Fomento'),
                    ('comprovante_aprovacao', 'Comprovante de Aprovação (Gestor)'),
                    ('ata_conselho', 'Ata de Deliberação do Centro Acadêmico'),
                    ('relatorio_submissao', 'Relatório de Submissão (Automático)'),
                    ('outro', 'Outro'),
                ],
                max_length=50,
                verbose_name='Tipo de Anexo',
            ),
        ),
    ]
