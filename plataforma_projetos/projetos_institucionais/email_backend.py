import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from email.utils import parseaddr


def _cliente_brevo():
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = settings.BREVO_API_KEY
    return sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )


def _remetente_brevo(endereco=None):
    nome, email = parseaddr(endereco or settings.DEFAULT_FROM_EMAIL)
    return {
        'email': email or settings.DEFAULT_FROM_EMAIL,
        'name': nome or 'PROPEG/UFAC',
    }


def enviar_email_brevo(destinatario_email, destinatario_nome, assunto, mensagem_texto):
    """Envia e-mail via API HTTP do Brevo — funciona no Render free."""
    api_instance = _cliente_brevo()

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": destinatario_email, "name": destinatario_nome}],
        sender=_remetente_brevo(),
        subject=assunto,
        text_content=mensagem_texto,
    )

    try:
        api_instance.send_transac_email(send_smtp_email)
        return True
    except ApiException as e:
        print(f"Erro ao enviar e-mail Brevo: {e}")
        return False


class BrevoEmailBackend(BaseEmailBackend):
    """Backend Django para envio transacional pela API HTTPS do Brevo."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_instance = _cliente_brevo()
        enviados = 0
        for email_message in email_messages:
            destinatarios = email_message.recipients()
            if not destinatarios:
                continue

            payload = {
                'to': [{'email': email} for email in destinatarios],
                'sender': _remetente_brevo(email_message.from_email),
                'subject': email_message.subject,
                'text_content': email_message.body,
            }
            for alternativa, mimetype in getattr(email_message, 'alternatives', []):
                if mimetype == 'text/html':
                    payload['html_content'] = alternativa
                    break

            try:
                api_instance.send_transac_email(
                    sib_api_v3_sdk.SendSmtpEmail(**payload)
                )
                enviados += 1
            except ApiException:
                if not self.fail_silently:
                    raise

        return enviados
