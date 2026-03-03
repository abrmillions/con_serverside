import base64
import json
import smtplib
import requests

def _xoauth2_sasl(email_address: str, access_token: str) -> str:
    return base64.b64encode(
        f"user={email_address}\x01auth=Bearer {access_token}\x01\x01".encode("utf-8")
    ).decode("utf-8")

def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("access_token", "")

def send_with_gmail_oauth(from_email: str, to_emails: list[str], message_str: str, client_id: str, client_secret: str, refresh_token: str) -> None:
    try:
        access_token = _get_access_token(client_id, client_secret, refresh_token)
    except requests.HTTPError as e:
        detail = ""
        try:
            detail = e.response.text
        except Exception:
            detail = str(e)
        raise RuntimeError(f"Failed to get access token: {detail}")
    if not access_token:
        raise RuntimeError("No access token")
    sasl = _xoauth2_sasl(from_email, access_token)
    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
    try:
        server.ehlo()
        server.starttls()
        server.ehlo()
        try:
            feats = getattr(server, "esmtp_features", {}) or {}
            auth_supported = "auth" in feats
        except Exception:
            auth_supported = False
        if not auth_supported:
            try:
                server.quit()
            except Exception:
                try:
                    server.close()
                except Exception:
                    pass
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
            server.ehlo()
            feats = getattr(server, "esmtp_features", {}) or {}
            if "auth" not in feats:
                raise RuntimeError("SMTP server does not advertise AUTH; verify access to smtp.gmail.com on 587 or 465 with TLS.")
        attempts = 0
        while True:
            attempts += 1
            code, resp = server.docmd("AUTH", "XOAUTH2 " + sasl)
            if code == 235:
                break
            detail = ""
            try:
                if resp:
                    # For 334 challenges, Gmail sends base64 JSON; for 535, it's plain text
                    if code == 334:
                        decoded = base64.b64decode(resp.strip()).decode("utf-8", errors="ignore")
                        try:
                            j = json.loads(decoded)
                            parts = []
                            if "error" in j:
                                parts.append(f"error={j.get('error')}")
                            if "error_description" in j:
                                parts.append(j.get("error_description"))
                            if "scope" in j:
                                parts.append(f"scope={j.get('scope')}")
                            if "status" in j:
                                parts.append(f"status={j.get('status')}")
                            if "login_hint" in j:
                                parts.append(f"user_hint={j.get('login_hint')}")
                            detail = "; ".join([p for p in parts if p]) or decoded
                        except Exception:
                            detail = decoded
                    else:
                        detail = resp.decode("utf-8", errors="ignore")
            except Exception:
                detail = ""
            if attempts < 2:
                try:
                    access_token = _get_access_token(client_id, client_secret, refresh_token)
                    if access_token:
                        sasl = _xoauth2_sasl(from_email, access_token)
                        continue
                except Exception:
                    pass
            hint = "Ensure refresh token has https://mail.google.com/ scope; From address matches token account or a verified send-as alias; token not revoked; Workspace allows SMTP/IMAP access."
            raise RuntimeError(f"XOAUTH2 auth failed: {code}{(' - ' + detail) if detail else ''}. {hint}")
        server.sendmail(from_email, to_emails, message_str)
    finally:
        try:
            server.quit()
        except Exception:
            server.close()
