from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projetos_institucionais', '0032_etapa2_limite_e_membros_manuais'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='equipeprojeto',
            constraint=models.UniqueConstraint(
                condition=~models.Q(cpf_manual=''),
                fields=('projeto', 'cpf_manual'),
                name='equipe_cpf_manual_unico_por_projeto',
            ),
        ),
    ]
