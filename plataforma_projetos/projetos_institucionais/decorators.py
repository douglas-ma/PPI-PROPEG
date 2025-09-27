from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def gestor_required(view_func):
    """
    Decorador que verifica se o usuário logado tem o perfil de 'gestor'.
    """
    decorated_view = user_passes_test(
        lambda u: u.is_authenticated and u.perfil == 'gestor',
        login_url='login',
        redirect_field_name=None
    )(view_func)
    return decorated_view

def coordenador_required(view_func):
    """
    Decorador que verifica se o usuário logado tem o perfil de 'coordenador'.
    """
    decorated_view = user_passes_test(
        lambda u: u.is_authenticated and u.perfil == 'coordenador',
        login_url='home',
        redirect_field_name=None
    )(view_func)
    return decorated_view

def aluno_required(view_func):
    """
    Decorador que verifica se o usuário logado tem o perfil de 'aluno'.
    """
    decorated_view = user_passes_test(
        lambda u: u.is_authenticated and u.perfil == 'aluno',
        login_url='home',
        redirect_field_name=None
    )(view_func)
    return decorated_view