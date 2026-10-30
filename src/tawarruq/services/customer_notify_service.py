from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote

from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.enums import AuditActor
from tawarruq.models.application import FinancingApplication
from tawarruq.models.customer import Customer
from tawarruq.services.audit_service import log_audit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OfferNotifyResult:
    status: str
    email: str | None
    journey_url: str
    smtp_sent: bool
    mail_path: str | None
    reason: str | None


def normalize_email(value: str | None) -> str | None:
    raw = (value or "").strip().lower()
    return raw or None


def customer_journey_url(customer_ref: str) -> str:
    settings = get_settings()
    base = (settings.portal_public_url or "http://127.0.0.1:5173").rstrip("/")
    return f"{base}/customer/{quote(customer_ref, safe='')}"


def notify_offer_ready(db: Session, application: FinancingApplication) -> OfferNotifyResult:
    """Email the customer the accept link after the Murabaha offer is locked.

    Never raises. SMTP is optional. A local copy is always written when an email exists.
    """
    journey_url = customer_journey_url(application.customer_ref)
    customer = getattr(application, "customer", None)
    if customer is None and application.customer_id:
        customer = db.get(Customer, application.customer_id)
    if customer is None:
        return OfferNotifyResult(
            status="skipped_no_customer",
            email=None,
            journey_url=journey_url,
            smtp_sent=False,
            mail_path=None,
            reason="This application has no customer record.",
        )
    email = normalize_email(customer.email)
    if not email:
        return OfferNotifyResult(
            status="skipped_no_email",
            email=None,
            journey_url=journey_url,
            smtp_sent=False,
            mail_path=None,
            reason="This customer has no email. Share the journey link yourself.",
        )
    if not application.offer:
        return OfferNotifyResult(
            status="skipped_no_offer",
            email=email,
            journey_url=journey_url,
            smtp_sent=False,
            mail_path=None,
            reason="Lock the Murabaha offer first.",
        )

    institution = getattr(application, "institution", None)
    institution_name = institution.name if institution is not None else "Your institution"
    currency = (application.currency or "KES").upper()
    offer = application.offer
    subject = f"Accept your Murabaha offer {application.customer_ref}"
    body = (
        f"Hello {customer.full_name},\n\n"
        f"{institution_name} has locked your Murabaha offer.\n\n"
        f"Cost: {currency} {offer.cost_price}\n"
        f"Profit: {currency} {offer.profit_amount}\n"
        f"You repay: {currency} {offer.total_payable}\n\n"
        "Open this link to accept. Only you can accept. The bank cannot do it for you.\n\n"
        f"{journey_url}\n\n"
        "Buruuj Tawarruq Engine\n"
    )

    mail_path: str | None = None
    try:
        settings = get_settings()
        path = settings.customer_mail_path / f"{application.customer_ref}.txt"
        path.write_text(f"To: {email}\nSubject: {subject}\n\n{body}", encoding="utf-8")
        mail_path = str(path)
    except Exception:
        logger.exception("Could not write customer offer mail file")

    smtp_sent = _send_smtp(email, subject, body)
    status = "sent" if smtp_sent else "filed"
    try:
        log_audit(
            db,
            entity_type="financing_offer",
            entity_id=application.offer.id,
            actor=AuditActor.SYSTEM,
            action="offer.email_notified",
            details=f"status={status} to={email}",
        )
    except Exception:
        logger.exception("Could not audit offer email")

    return OfferNotifyResult(
        status=status,
        email=email,
        journey_url=journey_url,
        smtp_sent=smtp_sent,
        mail_path=mail_path,
        reason=None if smtp_sent else "SMTP is not configured or the send failed. A local copy was written.",
    )


def notify_trade_documents_ready(
    db: Session,
    application: FinancingApplication,
    transaction,
    batch,
) -> OfferNotifyResult:
    """Email the customer the e-PO, invoice, and DO after Kenya possession."""
    from tawarruq.services.trade_evidence_service import (
        TRADE_DOC_KINDS,
        build_trade_document,
        render_trade_document_html,
        trade_documents_payload,
    )

    journey_url = customer_journey_url(application.customer_ref)
    customer = getattr(application, "customer", None)
    if customer is None and application.customer_id:
        customer = db.get(Customer, application.customer_id)
    if customer is None:
        return OfferNotifyResult(
            status="skipped_no_customer",
            email=None,
            journey_url=journey_url,
            smtp_sent=False,
            mail_path=None,
            reason="This application has no customer record.",
        )
    email = normalize_email(customer.email)
    docs = trade_documents_payload(batch)
    if not docs:
        return OfferNotifyResult(
            status="skipped_no_docs",
            email=email,
            journey_url=journey_url,
            smtp_sent=False,
            mail_path=None,
            reason="Trade documents are not issued yet.",
        )
    if not email:
        return OfferNotifyResult(
            status="skipped_no_email",
            email=None,
            journey_url=journey_url,
            smtp_sent=False,
            mail_path=None,
            reason="This customer has no email. Share the journey link yourself.",
        )

    label = docs.get("commodity_label") or "Kenya float"
    subject = f"Your {label} trade documents {application.customer_ref}"
    body = (
        f"Hello {customer.full_name},\n\n"
        f"Your Kenya trade documents are ready. This lot is {label}.\n\n"
        f"e-PO: {docs.get('purchase_order')}\n"
        f"Invoice: {docs.get('supplier_invoice')}\n"
        f"DO: {docs.get('delivery_order')}\n\n"
        "The delivery order states whether this is float or airtime, and whether it is Safaricom or Airtel.\n"
        "Open your journey to download them. The files are also attached if this mail went out over SMTP.\n\n"
        f"{journey_url}\n\n"
        "Buruuj Tawarruq Engine\n"
    )
    attachments: list[tuple[str, bytes, str]] = []
    for kind in TRADE_DOC_KINDS:
        try:
            doc = build_trade_document(application, transaction, batch, kind)
            html = render_trade_document_html(doc)
            attachments.append((doc["filename"], html.encode("utf-8"), "text/html"))
        except ValueError:
            continue

    mail_path: str | None = None
    try:
        settings = get_settings()
        path = settings.customer_mail_path / f"{application.customer_ref}-trade-docs.txt"
        path.write_text(f"To: {email}\nSubject: {subject}\n\n{body}", encoding="utf-8")
        mail_path = str(path)
        for filename, content, _ctype in attachments:
            (settings.customer_mail_path / filename).write_bytes(content)
    except Exception:
        logger.exception("Could not write customer trade-document mail file")

    smtp_sent = _send_smtp(email, subject, body, attachments)
    status = "sent" if smtp_sent else "filed"
    try:
        log_audit(
            db,
            entity_type="asset_batch",
            entity_id=batch.id,
            actor=AuditActor.SYSTEM,
            action="trade_docs.email_notified",
            details=f"status={status} to={email} commodity={label}",
        )
    except Exception:
        logger.exception("Could not audit trade document email")

    return OfferNotifyResult(
        status=status,
        email=email,
        journey_url=journey_url,
        smtp_sent=smtp_sent,
        mail_path=mail_path,
        reason=None if smtp_sent else "SMTP is not configured or the send failed. A local copy was written.",
    )


def notify_step_ready(
    db: Session,
    *,
    email: str | None,
    customer_name: str | None,
    customer_ref: str,
    title: str,
    body_line: str,
    institution_name: str | None = None,
) -> OfferNotifyResult:
    """Email the customer a later-step update with their journey link. Never raises."""
    journey_url = customer_journey_url(customer_ref)
    to_email = normalize_email(email)
    if not to_email:
        return OfferNotifyResult(
            status="skipped_no_email",
            email=None,
            journey_url=journey_url,
            smtp_sent=False,
            mail_path=None,
            reason="This customer has no email. Share the journey link yourself.",
        )
    name = (customer_name or "Customer").strip() or "Customer"
    house = (institution_name or "Your institution").strip() or "Your institution"
    subject = f"{title} {customer_ref}"
    body = (
        f"Hello {name},\n\n"
        f"{house}: {body_line}\n\n"
        "Open your customer journey to review and continue:\n"
        f"{journey_url}\n\n"
        "Buruuj Tawarruq Engine\n"
    )
    mail_path: str | None = None
    try:
        settings = get_settings()
        path = settings.customer_mail_path / f"{customer_ref}-{title.lower().replace(' ', '-')}.txt"
        path.write_text(f"To: {to_email}\nSubject: {subject}\n\n{body}", encoding="utf-8")
        mail_path = str(path)
    except Exception:
        logger.exception("Could not write customer step mail file")
    smtp_sent = _send_smtp(to_email, subject, body)
    status = "sent" if smtp_sent else "filed"
    try:
        log_audit(
            db,
            entity_type="customer_journey",
            entity_id=customer_ref,
            actor=AuditActor.SYSTEM,
            action="journey.step_notified",
            details=f"status={status} to={to_email} title={title}",
        )
    except Exception:
        logger.exception("Could not audit step email")
    return OfferNotifyResult(
        status=status,
        email=to_email,
        journey_url=journey_url,
        smtp_sent=smtp_sent,
        mail_path=mail_path,
        reason=None if smtp_sent else "SMTP is not configured or the send failed. A local copy was written.",
    )


def _send_smtp(
    to_email: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        return False
    try:
        import smtplib
        from email.mime.application import MIMEApplication
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        if attachments:
            msg = MIMEMultipart()
            msg.attach(MIMEText(body, "plain"))
            for filename, content, _ctype in attachments:
                part = MIMEApplication(content, Name=filename)
                part["Content-Disposition"] = f'attachment; filename="{filename}"'
                msg.attach(part)
        else:
            msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to_email
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_user:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("Could not send customer email via SMTP")
        return False
