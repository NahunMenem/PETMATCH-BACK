import requests
from .config import settings

_BREVO_URL = "https://api.brevo.com/v3/smtp/email"
_SENDER = {"name": "PawMatch", "email": "noreply@pawmatch.com.ar"}


def _post_brevo(payload: dict) -> None:
    if not settings.BREVO_API_KEY:
        return
    try:
        r = requests.post(
            _BREVO_URL,
            json=payload,
            headers={
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        r.raise_for_status()
    except Exception:
        pass  # never block the main flow if email fails


def send_verification_email(email: str, name: str, token: str) -> None:
    verify_url = f"{settings.LANDING_URL}/verificar-cuenta?token={token}"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:24px;background:#F9F5F1;font-family:'Nunito Sans',Arial,sans-serif;">
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
        ¡Bienvenido/a, {name}!
      </h1>
      <p style="color:#6B7280;font-size:15px;line-height:1.65;margin:0 0 28px;">
        Gracias por unirte a PawMatch. Para activar tu cuenta y empezar a
        conectar mascotas, confirmá tu correo electrónico tocando el botón.
      </p>
      <div style="text-align:center;margin:32px 0;">
        <a href="{verify_url}"
           style="background:linear-gradient(135deg,#FF7A1A,#FF5B45);color:#fff;
                  padding:16px 44px;border-radius:14px;text-decoration:none;
                  font-weight:900;font-size:16px;display:inline-block;
                  box-shadow:0 8px 24px rgba(255,107,0,.30);">
          Verificar mi cuenta
        </a>
      </div>
      <p style="color:#9CA3AF;font-size:12px;text-align:center;margin:24px 0 0;line-height:1.6;">
        Si no creaste esta cuenta, podés ignorar este correo.<br/>
        El enlace expira en <strong>24 horas</strong>.
      </p>
    </div>
    <div style="background:#F9F5F1;padding:18px 32px;text-align:center;">
      <p style="color:#9CA3AF;font-size:11px;margin:0;">
        © 2026 PawMatch ·
        <a href="https://pawmatch.com.ar/privacidad.html"
           style="color:#9CA3AF;text-decoration:none;">Privacidad</a>
      </p>
    </div>
  </div>
</body>
</html>"""

    _post_brevo({
        "sender": _SENDER,
        "to": [{"email": email, "name": name}],
        "subject": "Verificá tu cuenta en PawMatch 🐾",
        "htmlContent": html,
    })
