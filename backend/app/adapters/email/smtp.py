import smtplib
from email.message import EmailMessage
from app.core.config import settings

class SMTPEmailProvider:
    identity="smtp";version="1.0"
    def send(self,to:str,subject:str,text:str)->None:
        if not settings.smtp_host:raise RuntimeError("SMTP is not configured")
        message=EmailMessage();message["From"]=settings.smtp_from_email;message["To"]=to;message["Subject"]=subject;message.set_content(text)
        with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
            if settings.smtp_use_tls:smtp.starttls()
            if settings.smtp_username:smtp.login(settings.smtp_username,settings.smtp_password or "")
            smtp.send_message(message)
    def health(self):return {"status":"healthy" if settings.smtp_host else "not_configured","host_configured":bool(settings.smtp_host)}
