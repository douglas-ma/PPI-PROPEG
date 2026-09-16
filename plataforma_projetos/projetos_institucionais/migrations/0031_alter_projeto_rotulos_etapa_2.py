from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projetos_institucionais', '0030_projeto_tipo_projeto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projeto',
            name='introducao',
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name='Introdução e Justificativa',
            ),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='resultados',
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name='Resultados Esperados',
            ),
        ),
    ]
