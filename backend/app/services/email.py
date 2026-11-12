import os
import smtplib
from email.message import EmailMessage


class EmailConfigurationError(RuntimeError):
    pass


class EmailDeliveryError(RuntimeError):
    pass


def send_email(recipient: str, subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM")
    if not host or not sender:
        raise EmailConfigurationError(
            "SMTP_HOST and SMTP_FROM must be configured to send email."
        )

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError as error:
        raise EmailConfigurationError("SMTP_PORT must be a valid port number.") from error
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    use_starttls = os.getenv("SMTP_STARTTLS", "true").lower() == "true"

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    try:
        with smtp_class(host, port, timeout=15) as smtp:
            if use_starttls and not use_ssl:
                smtp.starttls()
            if username:
                smtp.login(username, password or "")
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryError("The configured SMTP server could not deliver email.") from error
