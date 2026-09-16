from django.db import migrations


def corrigir_funcao_de_alunos(apps, schema_editor):
    EquipeProjeto = apps.get_model('projetos_institucionais', 'EquipeProjeto')
    EquipeProjeto.objects.filter(
        membro__perfil='aluno',
        funcao='coordenador',
    ).update(funcao='estudante_graduacao')


class Migration(migrations.Migration):

    dependencies = [
        ('projetos_institucionais', '0033_equipe_cpf_manual_unico'),
    ]

    operations = [
        migrations.RunPython(corrigir_funcao_de_alunos, migrations.RunPython.noop),
    ]
