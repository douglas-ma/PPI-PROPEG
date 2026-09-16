from django.db import migrations


def classificar_comprovantes(apps, schema_editor):
    Projeto = apps.get_model('projetos_institucionais', 'Projeto')
    Anexo = apps.get_model('projetos_institucionais', 'Anexo')
    projetos_aprovados = Anexo.objects.filter(
        tipo_anexo='comite_etica',
        projeto__etica_obrigatoria=True,
    ).values_list('projeto_id', flat=True)
    Projeto.objects.filter(pk__in=projetos_aprovados).update(situacao_etica='aprovado')


class Migration(migrations.Migration):

    dependencies = [
        ('projetos_institucionais', '0036_etica_auditoria_e_status_finalizado'),
    ]

    operations = [
        migrations.RunPython(classificar_comprovantes, migrations.RunPython.noop),
    ]
