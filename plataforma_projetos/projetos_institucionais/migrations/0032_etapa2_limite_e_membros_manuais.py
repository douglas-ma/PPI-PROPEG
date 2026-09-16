from django.db import migrations, models
import django.db.models.deletion


def migrar_funcoes_antigas(apps, schema_editor):
    EquipeProjeto = apps.get_model('projetos_institucionais', 'EquipeProjeto')
    mapeamento = {
        'coordenador_auxiliar': 'coordenador',
        'pesquisador': 'coordenador',
        'aluno_bolsista': 'estudante_graduacao',
        'aluno_voluntario': 'estudante_graduacao',
        'aluno_pesquisador': 'estudante_graduacao',
        'tecnico': 'coordenador',
        'colaborador': 'coordenador',
        'outro': 'coordenador',
    }
    for funcao_antiga, funcao_nova in mapeamento.items():
        EquipeProjeto.objects.filter(funcao=funcao_antiga).update(funcao=funcao_nova)


class Migration(migrations.Migration):

    dependencies = [
        ('projetos_institucionais', '0031_alter_projeto_rotulos_etapa_2'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projeto',
            name='resumo',
            field=models.TextField(blank=True, max_length=4000, null=True),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='palavras_chave',
            field=models.TextField(blank=True, help_text='Separe por vírgulas. Ex.: Tecnologia, Educação, Web', max_length=4000, null=True),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='introducao',
            field=models.TextField(blank=True, max_length=4000, null=True, verbose_name='Introdução e Justificativa'),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='objetivo_geral',
            field=models.TextField(blank=True, max_length=4000, null=True, verbose_name='Objetivo Geral'),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='objetivos_especificos',
            field=models.TextField(blank=True, max_length=4000, null=True, verbose_name='Objetivos Específicos'),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='metodologia',
            field=models.TextField(blank=True, max_length=4000, null=True),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='resultados',
            field=models.TextField(blank=True, max_length=4000, null=True, verbose_name='Resultados Esperados'),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='parcerias',
            field=models.TextField(blank=True, max_length=4000, null=True),
        ),
        migrations.AlterField(
            model_name='projeto',
            name='referencias',
            field=models.TextField(blank=True, max_length=4000, null=True),
        ),
        migrations.AlterUniqueTogether(
            name='equipeprojeto',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='equipeprojeto',
            name='origem_membro',
            field=models.CharField(choices=[('sistema', 'Usuário do sistema'), ('manual', 'Preenchimento manual')], default='sistema', max_length=10, verbose_name='Forma de cadastro'),
        ),
        migrations.AddField(
            model_name='equipeprojeto',
            name='nome_membro_manual',
            field=models.CharField(blank=True, max_length=255, verbose_name='Nome do Membro'),
        ),
        migrations.AddField(
            model_name='equipeprojeto',
            name='cpf_manual',
            field=models.CharField(blank=True, max_length=14, verbose_name='CPF'),
        ),
        migrations.AlterField(
            model_name='equipeprojeto',
            name='membro',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='participa_em', to='projetos_institucionais.usuario'),
        ),
        migrations.AlterField(
            model_name='equipeprojeto',
            name='funcao',
            field=models.CharField(choices=[('coordenador', 'Coordenador'), ('estudante_graduacao', 'Estudante Graduação'), ('estudante_pos_mestrado', 'Estudante Pós (Mestrado)'), ('estudante_pos_doutorado', 'Estudante Pós (Doutorado)'), ('estudante_pos_especializacao', 'Estudante Pós (Especialização)'), ('estudante_ensino_medio', 'Estudante Ensino Médio'), ('estudante_ensino_fundamental', 'Estudante Ensino Fundamental')], default='coordenador', max_length=50, verbose_name='Função na Equipe'),
        ),
        migrations.AlterField(
            model_name='equipeprojeto',
            name='carga_horaria_semanal',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Carga Horária Semanal (h)'),
        ),
        migrations.AlterField(
            model_name='equipeprojeto',
            name='carga_horaria_total',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Carga Horária Total (h)'),
        ),
        migrations.RunPython(migrar_funcoes_antigas, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='equipeprojeto',
            constraint=models.UniqueConstraint(condition=models.Q(('membro__isnull', False)), fields=('projeto', 'membro'), name='equipe_usuario_unico_por_projeto'),
        ),
    ]
