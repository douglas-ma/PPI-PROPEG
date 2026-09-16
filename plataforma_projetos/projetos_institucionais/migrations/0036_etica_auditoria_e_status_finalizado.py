from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projetos_institucionais', '0035_solicitacao_aprovacao_centro'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projeto',
            name='status',
            field=models.CharField(
                choices=[
                    ('rascunho', 'Rascunho'),
                    ('submetido', 'Submetido'),
                    ('aguardando_conselho', 'Aguardando aprovação do Centro'),
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
        migrations.AddField(
            model_name='projeto',
            name='situacao_etica',
            field=models.CharField(
                blank=True,
                choices=[
                    ('aprovado', 'Comprovante de aprovação'),
                    ('submetido', 'Comprovante de submissão'),
                ],
                default='',
                max_length=20,
                verbose_name='Situação do documento ético',
            ),
        ),
        migrations.AddField(
            model_name='projeto',
            name='etica_submetida_em',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='projeto',
            name='prazo_aprovacao_etica',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='projeto',
            name='importado_legado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='projeto',
            name='ultima_alteracao_gestor_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='projeto',
            name='ultima_alteracao_gestor_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='projetos_alterados_como_gestor',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='projeto',
            name='finalizado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='projeto',
            name='encerrado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='projeto',
            name='encerrado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='projetos_encerrados_sem_conclusao',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='projeto',
            name='motivo_encerramento',
            field=models.TextField(blank=True),
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
                    ('ata_conselho', 'Ata de Aprovação do Centro'),
                    ('relatorio_submissao', 'Relatório de Submissão (Automático)'),
                    ('outro', 'Outro'),
                ],
                max_length=50,
                verbose_name='Tipo de Anexo',
            ),
        ),
        migrations.CreateModel(
            name='NotificacaoPrazoEtica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dias_restantes', models.PositiveSmallIntegerField()),
                ('enviada_em', models.DateTimeField(auto_now_add=True)),
                ('projeto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alertas_prazo_etica', to='projetos_institucionais.projeto')),
            ],
            options={'ordering': ['-enviada_em']},
        ),
        migrations.AddConstraint(
            model_name='notificacaoprazoetica',
            constraint=models.UniqueConstraint(fields=('projeto', 'dias_restantes'), name='alerta_etica_unico_por_prazo'),
        ),
        migrations.RunSQL(
            "UPDATE projetos_institucionais_projeto SET status = 'finalizado', finalizado_em = CURRENT_TIMESTAMP WHERE status = 'encerrado'",
            "UPDATE projetos_institucionais_projeto SET status = 'encerrado', finalizado_em = NULL WHERE status = 'finalizado'",
        ),
    ]
