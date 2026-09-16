from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    Usuario, Endereco, Titulacao, CentroLotacao, CursoGraduacao, 
    ProgramaPos, TipoEtico, ODS, GrupoPesquisa, AgenciaFinanciadora,
    Projeto, Documento, Ata, Relatorio, Anexo, SolicitacaoAprovacaoCentro
)

@admin.action(description="Aprovar usuários selecionados e notificar por e-mail")
def approve_users(modeladmin, request, queryset):
    queryset.update(is_active=True, status='ativo')
    for user in queryset:
        if not user.is_active:
            user.is_active = True
            user.save()
            send_mail(
                subject="Sua conta na Plataforma PROPEG foi aprovada!",
                message=f'Olá, {user.first_name}!\n\nSua conta na Plataforma PROPEG foi ativada. Agora você pode fazer login e acessar o sistema.\n\nAtenciosamente,\nEquipe PROPEG',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            
class UsuarioAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'perfil', 'is_active')
    list_filter = ('perfil', 'is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('email', 'first_name', 'last_name', 'cpf')
    ordering = ('email',)
    actions = ['approve_users']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informações Pessoais', {
            'fields': ('first_name', 'last_name', 'cpf', 'perfil')
            }),
        ('Permissões', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
            }),
        ('Datas Importantes', {
            'fields': ('last_login', 'date_joined')
            }),
    )



admin.site.register(Usuario, UsuarioAdmin)

admin.site.register(Anexo)
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
admin.site.register(SolicitacaoAprovacaoCentro)
