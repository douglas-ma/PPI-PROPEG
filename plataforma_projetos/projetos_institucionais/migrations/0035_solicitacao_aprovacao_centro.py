from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projetos_institucionais', '0034_corrigir_funcao_legada_de_alunos'),
    ]

    operations = [
        migrations.CreateModel(
            name='SolicitacaoAprovacaoCentro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(editable=False, max_length=64, unique=True)),
                ('email_destinatario', models.EmailField(max_length=254)),
                ('criada_em', models.DateTimeField(auto_now_add=True)),
                ('expira_em', models.DateTimeField()),
                ('utilizada_em', models.DateTimeField(blank=True, null=True)),
                ('invalidada_em', models.DateTimeField(blank=True, null=True)),
                ('responsavel_nome', models.CharField(blank=True, max_length=255)),
                ('responsavel_cargo', models.CharField(blank=True, max_length=255)),
                ('ata', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solicitacao_centro', to='projetos_institucionais.anexo')),
                ('projeto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='solicitacoes_aprovacao_centro', to='projetos_institucionais.projeto')),
            ],
            options={
                'verbose_name': 'Solicitação de Aprovação do Centro',
                'verbose_name_plural': 'Solicitações de Aprovação do Centro',
                'ordering': ['-criada_em'],
            },
        ),
    ]
