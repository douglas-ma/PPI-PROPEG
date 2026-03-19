import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from django.conf import settings


def enviar_email_brevo(destinatario_email, destinatario_nome, assunto, mensagem_texto):
    """Envia e-mail via API HTTP do Brevo — funciona no Render free."""
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = settings.BREVO_API_KEY

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": destinatario_email, "name": destinatario_nome}],
        sender={"email": settings.DEFAULT_FROM_EMAIL, "name": "PROPEG/UFAC"},
        subject=assunto,
        text_content=mensagem_texto,
    )

    try:
        api_instance.send_transac_email(send_smtp_email)
        return True
    except ApiException as e:
        print(f"Erro ao enviar e-mail Brevo: {e}")
        return False