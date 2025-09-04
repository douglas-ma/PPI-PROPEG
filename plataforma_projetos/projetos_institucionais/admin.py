from django.contrib import admin
from .models import (
    Usuario, Endereco, Titulacao, CentroLotacao, CursoGraduacao, 
    ProgramaPos, TipoEtico, ODS, GrupoPesquisa, AgenciaFinanciadora,
    Projeto, Documento, Ata, Relatorio
)

admin.site.register(Usuario)
admin.site.register(Endereco)
admin.site.register(Titulacao)
admin.site.register(CentroLotacao)
admin.site.register(CursoGraduacao)
admin.site.register(ProgramaPos)
admin.site.register(TipoEtico)
admin.site.register(ODS)
admin.site.register(GrupoPesquisa)
admin.site.register(AgenciaFinanciadora)
admin.site.register(Projeto)
admin.site.register(Documento)
admin.site.register(Ata)
admin.site.register(Relatorio)