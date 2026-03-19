from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from .forms import PerfilUsuarioForm, EnderecoForm, RegistroUsuarioForm
from projetos_institucionais.forms import CoordenadorProfileForm, AlunoProfileForm, GestorProfileForm
from projetos_institucionais.models import Usuario
import re

def login_view(request):
    if request.method == 'POST':
        cpf   = request.POST.get('cpf', '')
        senha = request.POST.get('senha', '')
        lembrar = request.POST.get('remember')

        if not cpf or not senha:
            messages.error(request, 'CPF e senha são obrigatórios.')
            return redirect('home')

        cpf_limpo = re.sub(r'[^0-9]', '', cpf)
        user = authenticate(request, cpf=cpf_limpo, password=senha)

        if user is not None:
            if user.is_active:
                login(request, user)
                # "Manter login": sem lembrar → sessão expira ao fechar o browser
                if lembrar:
                    request.session.set_expiry(60 * 60 * 24 * 30)  # 30 dias
                else:
                    request.session.set_expiry(0)  # expira ao fechar o browser
                return redirect('tela_principal')
            else:
                messages.warning(request, 'Sua conta ainda está em análise e aguarda aprovação.')
        else:
            messages.error(request, 'CPF ou senha inválidos.')

        return redirect('home')

    if request.user.is_authenticated:
        return redirect('tela_principal')
    return redirect('home')

def logout_view(request):
    logout(request)
    return redirect('home')

def esqueceu_senha(request):
    if request.method == 'POST':
        cpf_raw = request.POST.get('cpf', '')
        cpf = re.sub(r'[^0-9]', '', cpf_raw)
        try:
            user = Usuario.objects.get(cpf=cpf, is_active=True)
        except Usuario.DoesNotExist:
            # Não revelamos se o CPF existe ou não (segurança)
            messages.success(
                request,
                'Se este CPF estiver cadastrado, você receberá um e-mail com instruções.'
            )
            return redirect('home')

        if not user.email:
            messages.warning(
                request,
                'Não há e-mail cadastrado para este CPF. Entre em contato com a PROPEG.'
            )
            return redirect('home')

        # Gera token seguro
        uid   = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link  = request.build_absolute_uri(
            reverse('redefinir_senha', kwargs={'uidb64': uid, 'token': token})
        )

        # Envia e-mail
        subject_mail = 'Redefinição de Senha — PROPEG'
        body_mail = (
            f'Olá, {user.get_full_name() or user.username}!\n\n'
            f'Recebemos uma solicitação para redefinir a senha da sua conta na Plataforma PROPEG/UFAC.\n\n'
            f'Clique no link abaixo para criar uma nova senha (válido por 24 horas):\n\n'
            f'{link}\n\n'
            f'Se você não solicitou a redefinição, ignore este e-mail.\n\n'
            f'Atenciosamente,\nEquipe PROPEG/UFAC'
        )
        brevo_key = getattr(settings, 'BREVO_API_KEY', '')
        if brevo_key:
            try:
                import sib_api_v3_sdk
                configuration = sib_api_v3_sdk.Configuration()
                configuration.api_key['api-key'] = brevo_key
                api = sib_api_v3_sdk.TransactionalEmailsApi(
                    sib_api_v3_sdk.ApiClient(configuration)
                )
                api.send_transac_email(sib_api_v3_sdk.SendSmtpEmail(
                    to=[{"email": user.email, "name": user.get_full_name() or user.username}],
                    sender={"email": settings.DEFAULT_FROM_EMAIL, "name": "PROPEG/UFAC"},
                    subject=subject_mail,
                    text_content=body_mail,
                ))
            except Exception as e:
                print(f"Erro Brevo: {e}")
        else:
            send_mail(subject_mail, body_mail,
                      getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@propeg.ufac.br'),
                      [user.email], fail_silently=True)

        messages.success(
            request,
            f'Instruções de redefinição de senha foram enviadas para {user.email}.'
        )
        return redirect('home')

    # GET — renderiza pelo painel deslizante da home
    return render(request, 'home/home.html', {
        'mostrar_senha': True,
        'form_registro': __import__('login.forms', fromlist=['RegistroUsuarioForm']).RegistroUsuarioForm(),
    })


def redefinir_senha(request, uidb64, token):
    """Exibe formulário de nova senha após clicar no link do e-mail."""
    try:
        uid  = force_str(urlsafe_base64_decode(uidb64))
        user = Usuario.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(
            request,
            'Este link de redefinição é inválido ou já expirou. Solicite um novo.'
        )
        return redirect('home')

    if request.method == 'POST':
        nova = request.POST.get('nova_senha', '')
        conf = request.POST.get('confirmar_senha', '')
        if len(nova) < 8:
            messages.error(request, 'A senha deve ter pelo menos 8 caracteres.')
        elif nova != conf:
            messages.error(request, 'As senhas não coincidem.')
        else:
            user.set_password(nova)
            user.save()
            messages.success(request, 'Senha redefinida com sucesso! Faça login.')
            return redirect('home')

    return render(request, 'login/redefinir_senha.html', {
        'uidb64': uidb64,
        'token':  token,
    })

def registro_view(request):
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True   # ativa automaticamente, sem precisar de aprovação
            user.status    = 'ativo'
            user.save()
            messages.success(request, 'Cadastro realizado com sucesso! Faça login para acessar a plataforma.')
            return redirect('home')
        return render(request, 'home/home.html', {
            'form_registro':   form,
            'mostrar_registro': True,
        })
    else:
        form = RegistroUsuarioForm()
    return render(request, 'home/home.html', {'form_registro': form})

@login_required
def perfil_view(request):
    contexto = {
        'usuario': request.user
    }
    return render(request, 'login/perfilusuario.html', contexto)

@login_required
def perfil_editar_view(request):
    user = request.user
    user_form_class = None

    if user.perfil == 'coordenador':
        user_form_class = CoordenadorProfileForm
    elif user.perfil == 'aluno':
        user_form_class = AlunoProfileForm
    elif user.perfil == 'gestor':
        user_form_class = GestorProfileForm
    else:
        messages.info(request, 'Seu perfil é gerenciado pelo sistema.')
        return redirect('perfil')

    endereco_instance = user.endereco if hasattr(user, 'endereco') else None

    if request.method == 'POST':
        user_form    = user_form_class(request.POST, instance=user)
        endereco_form = EnderecoForm(request.POST, instance=endereco_instance)

        # Verifica se o usuário tentou preencher algum campo de endereço
        campos_endereco = ['rua', 'numero', 'bairro', 'cidade', 'estado', 'cep']
        endereco_preenchido = any(request.POST.get(c, '').strip() for c in campos_endereco)

        if user_form.is_valid():
            usuario = user_form.save(commit=False)

            # Só valida/salva endereço se o usuário preencheu algum campo
            if endereco_preenchido:
                if endereco_form.is_valid():
                    endereco = endereco_form.save()
                    usuario.endereco = endereco
                else:
                    messages.warning(request, 'Dados pessoais salvos, mas há erros no endereço — corrija-os.')
                    usuario.save()
                    return render(request, 'login/perfileditar.html', {
                        'user_form':     user_form,
                        'endereco_form': endereco_form,
                    })

            try:
                usuario.save()
                messages.success(request, 'Perfil atualizado com sucesso!')
                return redirect('perfil')
            except Exception as e:
                messages.error(request, f'Erro ao salvar o perfil: {e}')
        else:
            if endereco_preenchido:
                endereco_form.is_valid()
    else:
        user_form     = user_form_class(instance=user)
        endereco_form = EnderecoForm(instance=endereco_instance)

    return render(request, 'login/perfileditar.html', {
        'user_form':    user_form,
        'endereco_form': endereco_form,
    })

@login_required
def endereco_editar_view(request):
    try:
        endereco_instance = request.user.endereco
    except AttributeError:
        endereco_instance = None
    
    if request.method == 'POST':
        form = EnderecoForm(request.POST, instance=endereco_instance)
        if form.is_valid():
            endereco = form.save()
            request.user.endereco = endereco
            request.user.save()

            messages.success(request, 'Endereço atualizado com sucesso!')
            return redirect('perfil')
    else:
        form = EnderecoForm(instance=endereco_instance)
    
    contexto = {
        'form': form
    }
    return render(request, 'login/perfilendereco.html', contexto)