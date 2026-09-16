from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Notificacao, NotificacaoPrazoEtica, Projeto


PRAZOS_ALERTA_ETICA = (60, 30, 15, 7, 3, 1)


def processar_alertas_etica(data_referencia=None):
    """Cria uma notificação e envia e-mail nos marcos do prazo de 90 dias."""
    hoje = data_referencia or timezone.localdate()
    projetos = Projeto.objects.filter(
        etica_obrigatoria=True,
        situacao_etica='submetido',
        prazo_aprovacao_etica__isnull=False,
    ).select_related('coordenador')

    enviados = 0
    for projeto in projetos:
        if projeto.anexos.filter(tipo_anexo='comite_etica').exists():
            continue
        dias = (projeto.prazo_aprovacao_etica - hoje).days
        if dias < 0:
            continue
        # Se a rotina não rodou exatamente no dia do marco, envia o alerta
        # pendente mais próximo no primeiro processamento posterior.
        marcos_pendentes = [marco for marco in PRAZOS_ALERTA_ETICA if dias <= marco]
        if not marcos_pendentes:
            continue
        marco = min(marcos_pendentes)

        with transaction.atomic():
            alerta, criado = NotificacaoPrazoEtica.objects.get_or_create(
                projeto=projeto,
                dias_restantes=marco,
            )
            if not criado:
                continue
            link = reverse('projeto_detalhe', args=[projeto.pk])
            mensagem = (
                f'Faltam {dias} dia(s) para anexar a aprovação ética do projeto '
                f'"{projeto.titulo}". O prazo termina em '
                f'{projeto.prazo_aprovacao_etica.strftime("%d/%m/%Y")}.'
            )
            Notificacao.objects.create(
                destinatario=projeto.coordenador,
                mensagem=mensagem,
                link=link,
            )

        if projeto.coordenador.email:
            send_mail(
                subject=f'Prazo para aprovação ética: {dias} dia(s)',
                message=(
                    f'Olá, {projeto.coordenador.get_full_name() or projeto.coordenador.username}.\n\n'
                    f'{mensagem}\n\nAcesse a plataforma para anexar o comprovante definitivo.\n\n'
                    'Equipe PROPEG/UFAC'
                ),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=[projeto.coordenador.email],
                fail_silently=True,
            )
        enviados += 1
    return enviados
