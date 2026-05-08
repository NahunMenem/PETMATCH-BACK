import logging

import requests

from .config import settings

logger = logging.getLogger(__name__)
BREVO_EMAIL_URL = "https://api.brevo.com/v3/smtp/email"


def send_verification_email(*, to_email: str, name: str, token: str) -> None:
    verification_url = (
        f"{settings.PUBLIC_WEB_URL.rstrip('/')}/verificar-cuenta.html?token={token}"
    )
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:24px;background:#F9F5F1;font-family:Arial,sans-serif;">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:24px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.08);">
    <div style="background:linear-gradient(135deg,#FF7A1A,#FF5B45);padding:36px 32px;text-align:center;">
      <img src="https://res.cloudinary.com/dqsacd9ez/image/upload/v1776962385/PawMatch_2_wzj2kr.png"
           alt="PawMatch" style="height:44px;width:auto;" />
      <p style="color:rgba(255,255,255,.8);font-size:13px;margin:10px 0 0;font-weight:700;letter-spacing:.5px;">
        La app para conectar mascotas
      </p>
    </div>
    <div style="padding:36px 32px;">
      <h1 style="font-size:24px;font-weight:900;color:#1A1208;margin:0 0 12px;">
        Bienvenido/a, {name}
      </h1>
      <p style="color:#6B7280;font-size:15px;line-height:1.65;margin:0 0 28px;">
        Gracias por unirte a PawMatch. Para activar tu cuenta y empezar a
        conectar mascotas, confirma tu correo electronico tocando el boton.
      </p>
      <div style="text-align:center;margin:32px 0;">
        <a href="{verification_url}"
           style="background:linear-gradient(135deg,#FF7A1A,#FF5B45);color:#fff;
                  padding:16px 44px;border-radius:14px;text-decoration:none;
                  font-weight:900;font-size:16px;display:inline-block;
                  box-shadow:0 8px 24px rgba(255,107,0,.30);">
          Verificar mi cuenta
        </a>
      </div>
      <p style="color:#9CA3AF;font-size:12px;text-align:center;margin:24px 0 0;line-height:1.6;">
        Si no creaste esta cuenta, podes ignorar este correo.<br/>
        El enlace expira en <strong>24 horas</strong>.
      </p>
    </div>
  </div>
</body>
</html>"""
    text_content = "\n".join(
        [
            f"Hola {name},",
            "",
            "Para activar tu cuenta de PawMatch, abri este enlace:",
            verification_url,
            "",
            "Si no creaste esta cuenta, podes ignorar este correo.",
        ]
    )

    if not settings.BREVO_API_KEY:
        raise RuntimeError("BREVO_API_KEY is not configured")

    response = requests.post(
        BREVO_EMAIL_URL,
        headers={
            "accept": "application/json",
            "api-key": settings.BREVO_API_KEY,
            "content-type": "application/json",
        },
        json={
            "sender": {
                "name": settings.SMTP_FROM_NAME,
                "email": settings.SMTP_FROM_EMAIL or "noreply@pawmatch.com.ar",
            },
            "to": [{"email": to_email, "name": name}],
            "subject": "Verifica tu cuenta en PawMatch",
            "htmlContent": html_content,
            "textContent": text_content,
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Brevo email failed: {response.status_code} {response.text}"
        )
