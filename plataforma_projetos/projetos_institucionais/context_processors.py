from .models import Notificacao
from django.core.cache import cache
from django.utils import timezone

from .ethics_notifications import processar_alertas_etica

def unread_notifications_context(request):
    if request.user.is_authenticated:
        # Executa no máximo uma varredura por dia em cada instância web. O comando
        # `notificar_prazos_etica` continua disponível para o agendador diário.
        chave = f'alertas-etica-processados-{timezone.localdate().isoformat()}'
        if cache.add(chave, True, timeout=60 * 60 * 26):
            try:
                processar_alertas_etica()
            except Exception:
                cache.delete(chave)
        unread_count = Notificacao.objects.filter(destinatario=request.user, lida=False).count()
        return {'unread_notifications_count': unread_count}
    return {}
