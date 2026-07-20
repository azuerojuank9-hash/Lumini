import logging
from app.infra.config import SENDGRID_API_KEY, EMAIL_ORIGEN

logger = logging.getLogger(__name__)


def enviar_correo(destino, asunto, cuerpo_html, adjunto_bytes=None, adjunto_nombre=None, adjunto_tipo=None):
    if not SENDGRID_API_KEY:
        logger.error(f'Intento de envío a {destino} sin SENDGRID_API_KEY configurado.')
        return False
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        import base64
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        mensaje = Mail(from_email=EMAIL_ORIGEN, to_emails=destino,
                       subject=asunto, html_content=cuerpo_html)
        if adjunto_bytes and adjunto_nombre and adjunto_tipo:
            adjunto = Attachment(
                FileContent(base64.b64encode(adjunto_bytes).decode()),
                FileName(adjunto_nombre),
                FileType(adjunto_tipo),
                Disposition('attachment'))
            mensaje.attachment = adjunto
        sg.client.mail.send.post(request_body=mensaje.get())
        return True
    except Exception as e:
        logger.error(f'Error al enviar correo a {destino}: {e}')
        return False
