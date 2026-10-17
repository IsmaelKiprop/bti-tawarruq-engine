import json
from pathlib import Path

from tawarruq.bsas.base import BSASBackend, LegContext, LegExecutionResponse, LegExecutionResult
from tawarruq.bsas.desk_packet import build_desk_packet
from tawarruq.config import get_settings
from tawarruq.enums import LegNumber


def _send_manual_bridge_email(subject: str, body: str, attachment_path: Path) -> None:
    settings = get_settings()
    if not settings.manual_bridge_email_enabled or not settings.manual_bridge_email_to:
        return
    if not settings.smtp_host:
        return
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = settings.manual_bridge_email_to
    msg.attach(MIMEText(body, "plain"))
    with attachment_path.open("rb") as handle:
        part = MIMEApplication(handle.read(), Name=attachment_path.name)
        part["Content-Disposition"] = f'attachment; filename="{attachment_path.name}"'
        msg.attach(part)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_user:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


class ManualBridgeBackend(BSASBackend):
    """
    Generates Bursa-shaped desk request packets for ops to submit manually,
    then watches for certificate replies in the inbox directory.
    """

    def __init__(self, inbox_dir: Path | None = None) -> None:
        settings = get_settings()
        self.inbox_dir = inbox_dir or settings.manual_bridge_path
        self.requests_dir = self.inbox_dir / "requests"
        self.replies_dir = self.inbox_dir / "replies"
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.replies_dir.mkdir(parents=True, exist_ok=True)

    def _leg_label(self, leg_number: LegNumber) -> str:
        labels = {
            LegNumber.PURCHASE: "Leg 1: Agent Purchase (BSAS)",
            LegNumber.TRANSFER: "Leg 2: Ownership Transfer (OTC)",
            LegNumber.SALE: "Leg 3: Sale to BMIS (STB)",
        }
        return labels[leg_number]

    def execute_leg(self, context: LegContext) -> LegExecutionResponse:
        external_ref = f"MB-{context.transaction_id[:8]}-L{context.leg_number}"
        request_payload = build_desk_packet(context, external_ref=external_ref)
        request_payload["leg_label"] = self._leg_label(LegNumber(context.leg_number))
        request_payload["instructions"] = "\n".join(request_payload["processing_instructions"])

        request_path = self.requests_dir / f"{external_ref}.json"
        request_path.write_text(json.dumps(request_payload, indent=2), encoding="utf-8")

        email_path = self.requests_dir / f"{external_ref}.email.txt"
        email_path.write_text(request_payload["email_body"], encoding="utf-8")

        institution = context.institution_name or context.institution_code or "Institution"
        _send_manual_bridge_email(
            subject=f"REQUEST FOR LIVE ACCESS — {institution} [{external_ref}]",
            body=request_payload["email_body"],
            attachment_path=request_path,
        )

        existing = self.get_certificate(external_ref)
        if existing and existing.result == LegExecutionResult.CONFIRMED:
            return existing

        return LegExecutionResponse(
            result=LegExecutionResult.AWAITING_CONFIRMATION,
            external_ref=external_ref,
            manual_request_path=str(request_path),
        )

    def get_certificate(self, external_ref: str) -> LegExecutionResponse | None:
        reply_path = self.replies_dir / f"{external_ref}.json"
        if not reply_path.exists():
            return None
        payload = json.loads(reply_path.read_text(encoding="utf-8"))
        return LegExecutionResponse(
            result=LegExecutionResult.CONFIRMED,
            external_ref=external_ref,
            certificate_number=payload["certificate_number"],
            issuer=payload.get("issuer", "Bursa Malaysia Islamic Services Sdn.Bhd."),
        )
