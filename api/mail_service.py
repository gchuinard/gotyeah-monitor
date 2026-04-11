import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

SMTP_HOST = os.getenv("SMTP_HOST", "mailpit")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@gotyeah.local")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def _base_template(title: str, preview: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">

  <!-- Preview text (hidden) -->
  <span style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preview}</span>

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#0ea5e9,#6366f1);border-radius:16px 16px 0 0;padding:32px 40px;text-align:center;">
              <p style="margin:0 0 6px;font-size:11px;font-weight:600;letter-spacing:0.2em;text-transform:uppercase;color:rgba(255,255,255,0.7);">GotYeah Monitor</p>
              <h1 style="margin:0;font-size:22px;font-weight:700;color:#ffffff;">{title}</h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background:#ffffff;padding:36px 40px;">
              {content}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;border-radius:0 0 16px 16px;border-top:1px solid #e2e8f0;padding:20px 40px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#94a3b8;">
                Cet email a été envoyé automatiquement, merci de ne pas y répondre.<br/>
                &copy; 2026 GotYeah Monitor
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


async def _send(to: str, subject: str, html: str) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = to
    message.attach(MIMEText(html, "html"))

    kwargs: dict = {"hostname": SMTP_HOST, "port": SMTP_PORT}
    if SMTP_USER and SMTP_PASSWORD:
        kwargs["username"] = SMTP_USER
        kwargs["password"] = SMTP_PASSWORD
        kwargs["start_tls"] = True

    await aiosmtplib.send(message, **kwargs)


async def send_verification_email(to: str, token: str) -> None:
    link = f"{FRONTEND_URL}/verify-email?token={token}"
    content = f"""
      <p style="margin:0 0 16px;font-size:15px;color:#475569;line-height:1.6;">
        Bienvenue sur <strong style="color:#0f172a;">GotYeah Monitor</strong> !<br/>
        Cliquez sur le bouton ci-dessous pour confirmer votre adresse email et activer votre compte.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0;">
        <tr>
          <td align="center">
            <a href="{link}"
               style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#0ea5e9,#6366f1);
                      color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;
                      border-radius:10px;letter-spacing:0.02em;">
              ✉ Vérifier mon email
            </a>
          </td>
        </tr>
      </table>

      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;margin-top:8px;">
        <p style="margin:0 0 6px;font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;">Lien de secours</p>
        <p style="margin:0;font-size:12px;color:#94a3b8;word-break:break-all;">{link}</p>
      </div>

      <p style="margin:24px 0 0;font-size:13px;color:#94a3b8;line-height:1.6;">
        ⏱ Ce lien expire dans <strong>24 heures</strong>.<br/>
        Si vous n'avez pas créé de compte, ignorez simplement cet email.
      </p>
    """
    html = _base_template(
        title="Vérifiez votre adresse email",
        preview="Activez votre compte GotYeah Monitor en un clic.",
        content=content,
    )
    await _send(to, "Vérifiez votre email – GotYeah Monitor", html)


async def send_email_change_confirm(to: str, token: str) -> None:
    """Mail envoyé à la NOUVELLE adresse pour confirmer le changement."""
    link = f"{FRONTEND_URL}/confirm-email-change?token={token}"
    content = f"""
      <p style="margin:0 0 16px;font-size:15px;color:#475569;line-height:1.6;">
        Vous avez demandé à changer votre adresse email sur <strong style="color:#0f172a;">GotYeah Monitor</strong>.<br/>
        Cliquez ci-dessous pour confirmer que cette adresse vous appartient.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0;">
        <tr>
          <td align="center">
            <a href="{link}"
               style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#0ea5e9,#6366f1);
                      color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;
                      border-radius:10px;letter-spacing:0.02em;">
              ✉ Confirmer ma nouvelle adresse
            </a>
          </td>
        </tr>
      </table>

      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;margin-top:8px;">
        <p style="margin:0 0 6px;font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;">Lien de secours</p>
        <p style="margin:0;font-size:12px;color:#94a3b8;word-break:break-all;">{link}</p>
      </div>

      <p style="margin:24px 0 0;font-size:13px;color:#94a3b8;line-height:1.6;">
        ⏱ Ce lien expire dans <strong>24 heures</strong>.<br/>
        Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.
      </p>
    """
    html = _base_template(
        title="Confirmez votre nouvelle adresse",
        preview="Validez le changement d'adresse email de votre compte GotYeah Monitor.",
        content=content,
    )
    await _send(to, "Confirmez votre nouvelle adresse – GotYeah Monitor", html)


async def send_email_change_cancel(to: str, token: str, new_email: str) -> None:
    """Mail envoyé à l'ANCIENNE adresse pour prévenir et permettre l'annulation."""
    link = f"{FRONTEND_URL}/cancel-email-change?token={token}"
    content = f"""
      <p style="margin:0 0 16px;font-size:15px;color:#475569;line-height:1.6;">
        Une demande de changement d'adresse email a été effectuée sur votre compte.<br/>
        La nouvelle adresse demandée est : <strong style="color:#0f172a;">{new_email}</strong>
      </p>

      <p style="margin:0 0 20px;font-size:14px;color:#475569;line-height:1.6;">
        Si c'est bien vous, vous n'avez rien à faire.<br/>
        Si vous n'êtes <strong>pas</strong> à l'origine de cette demande, annulez-la immédiatement :
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 28px;">
        <tr>
          <td align="center">
            <a href="{link}"
               style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#f43f5e,#e11d48);
                      color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;
                      border-radius:10px;letter-spacing:0.02em;">
              🚫 Annuler le changement
            </a>
          </td>
        </tr>
      </table>

      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;margin-top:8px;">
        <p style="margin:0 0 6px;font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;">Lien de secours</p>
        <p style="margin:0;font-size:12px;color:#94a3b8;word-break:break-all;">{link}</p>
      </div>

      <p style="margin:24px 0 0;font-size:13px;color:#94a3b8;line-height:1.6;">
        ⏱ Ce lien est valable <strong>24 heures</strong>, même si le changement a déjà été confirmé.
      </p>
    """
    html = _base_template(
        title="Changement d'adresse email",
        preview=f"Une demande de changement vers {new_email} a été effectuée sur votre compte.",
        content=content,
    )
    await _send(to, "Changement d'adresse email – GotYeah Monitor", html)


async def send_password_reset_email(to: str, token: str) -> None:
    link = f"{FRONTEND_URL}/reset-password?token={token}"
    content = f"""
      <p style="margin:0 0 16px;font-size:15px;color:#475569;line-height:1.6;">
        Vous avez demandé la réinitialisation de votre mot de passe.<br/>
        Cliquez sur le bouton ci-dessous pour en choisir un nouveau.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0;">
        <tr>
          <td align="center">
            <a href="{link}"
               style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#0ea5e9,#6366f1);
                      color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;
                      border-radius:10px;letter-spacing:0.02em;">
              🔑 Réinitialiser mon mot de passe
            </a>
          </td>
        </tr>
      </table>

      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;margin-top:8px;">
        <p style="margin:0 0 6px;font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;">Lien de secours</p>
        <p style="margin:0;font-size:12px;color:#94a3b8;word-break:break-all;">{link}</p>
      </div>

      <p style="margin:24px 0 0;font-size:13px;color:#94a3b8;line-height:1.6;">
        ⏱ Ce lien expire dans <strong>1 heure</strong>.<br/>
        Si vous n'êtes pas à l'origine de cette demande, ignorez cet email — votre mot de passe ne sera pas modifié.
      </p>
    """
    html = _base_template(
        title="Réinitialisation de mot de passe",
        preview="Choisissez un nouveau mot de passe pour votre compte GotYeah Monitor.",
        content=content,
    )
    await _send(to, "Réinitialisation de mot de passe – GotYeah Monitor", html)
