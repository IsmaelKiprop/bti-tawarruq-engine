"""HTML/PDF certificate attachments for customer email."""

from __future__ import annotations

from pathlib import Path
from sqlalchemy.orm import Session

from tawarruq.services.document_brand import kv_sections, render_branded_document

Attachment = tuple[str, bytes, str]

DESK_CERTS = {
    3: ("Commodity purchase certificate", "purchase"),
    4: ("Murabaha sale certificate", "murabaha"),
    5: ("Agency appointment certificate", "agency"),
    6: ("Resale proceeds certificate", "resale"),
    7: ("Clearing certificate", "clearing"),
    8: ("Facility completion certificate", "complete"),
}


def html_attachment(filename: str, html: str) -> Attachment:
    safe = "".join(ch if ch.isalnum() or ch in ".-_" else "-" for ch in filename).strip("-") or "certificate"
    if not safe.lower().endswith(".html"):
        safe = f"{safe}.html"
    return (safe, html.encode("utf-8"), "text/html")


def pdf_attachment(path: str | None, filename: str | None = None) -> Attachment | None:
    if not path:
        return None
    file = Path(path)
    if not file.is_file():
        return None
    name = filename or file.name
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return (name, file.read_bytes(), "application/pdf")


def render_bsas_certificate_html(certificate) -> str:
    number = getattr(certificate, "certificate_number", None) or "BSAS"
    return render_branded_document(
        title="Islamic Services Receipt",
        subtitle="Bursa Suq Al-Sila' e-certificate recorded on this facility.",
        doc_ref=number,
        eyebrow="Bursa Malaysia Islamic Services",
        sections_html=kv_sections(
            [
                (
                    "Certificate",
                    [
                        ("Number", number),
                        ("Issuer", getattr(certificate, "issuer", None)),
                        ("Seller", getattr(certificate, "seller", None)),
                        ("Buyer", getattr(certificate, "buyer", None)),
                        ("Bid no", getattr(certificate, "bid_no", None)),
                    ],
                ),
                (
                    "Commodity",
                    [
                        ("Product", getattr(certificate, "product_code", None)),
                        ("Description", getattr(certificate, "product_description", None)),
                        ("Unit", getattr(certificate, "unit", None)),
                        ("Volume", getattr(certificate, "volume", None)),
                    ],
                ),
                (
                    "Value",
                    [
                        ("Currency", getattr(certificate, "currency", None)),
                        ("Price", getattr(certificate, "price", None)),
                        ("MYR equivalent", getattr(certificate, "price_myr_equivalent", None)),
                        ("Value", getattr(certificate, "value_amount", None)),
                        ("Selling date", getattr(certificate, "selling_date", None)),
                    ],
                ),
            ]
        ),
        note="This copy was issued from the Buruuj Tawarruq engine after the desk recorded the Bursa receipt.",
        filename_hint=str(number),
    )


def bsas_certificate_attachments(certificate) -> list[Attachment]:
    items: list[Attachment] = []
    pdf = pdf_attachment(getattr(certificate, "pdf_path", None), getattr(certificate, "pdf_filename", None))
    if pdf:
        items.append(pdf)
    number = getattr(certificate, "certificate_number", None) or "bsas-receipt"
    items.append(html_attachment(f"{number}-receipt.html", render_bsas_certificate_html(certificate)))
    return items


def render_tawarruq_certificate_html(*, certificate_number: str, customer_name: str, institution_name: str, amount: str, currency: str) -> str:
    return render_branded_document(
        title="Tawarruq financing certificate",
        subtitle="Evidence that this facility completed commodity tawarruq and disbursement.",
        doc_ref=certificate_number,
        sections_html=kv_sections(
            [
                (
                    "Certificate",
                    [
                        ("Number", certificate_number),
                        ("Issuer", "Buruuj Fintech"),
                        ("Institution", institution_name),
                        ("Customer", customer_name),
                    ],
                ),
                ("Facility", [("Amount", f"{currency} {amount}")]),
            ]
        ),
        note="Keep this certificate with the customer journey record.",
        filename_hint=certificate_number,
    )


def tawarruq_certificate_attachments(*, certificate_number: str, customer_name: str, institution_name: str, amount: str, currency: str) -> list[Attachment]:
    html = render_tawarruq_certificate_html(
        certificate_number=certificate_number,
        customer_name=customer_name,
        institution_name=institution_name,
        amount=amount,
        currency=currency,
    )
    return [html_attachment(f"{certificate_number}.html", html)]


def render_desk_certificate_html(case, step: int) -> str | None:
    spec = DESK_CERTS.get(step)
    if not spec:
        return None
    title, slug = spec
    payload = {}
    try:
        import json

        payload = json.loads(case.payload_json or "{}")
    except Exception:
        payload = {}
    orig = payload.get("origination") or {}
    initiate = payload.get("initiate") or {}
    murabaha = payload.get("murabaha") or {}
    resale = payload.get("resale") or {}
    proceeds = payload.get("proceeds") or {}
    clearing = payload.get("clearing") or {}
    ref = (payload.get("journey") or {}).get("customer_ref") or case.id[:8]
    institution = case.institution.name if getattr(case, "institution", None) else "Institution"
    return render_branded_document(
        title=title,
        subtitle="Tawarruq desk certificate for this customer facility.",
        doc_ref=f"{slug.upper()}-{ref}",
        sections_html=kv_sections(
            [
                (
                    "Customer",
                    [
                        ("Name", orig.get("customer_name")),
                        ("Email", orig.get("customer_email")),
                        ("Phone", orig.get("customer_phone")),
                        ("Institution", institution),
                        ("Reference", ref),
                    ],
                ),
                (
                    "Facility",
                    [
                        ("Amount", orig.get("approved_facility_amount")),
                        ("Profit", orig.get("profit") or murabaha.get("profit")),
                        ("Commodity", initiate.get("commodity") or orig.get("facility_product_type") or "Airtime"),
                        ("Purchase", initiate.get("purchase_complete")),
                        ("Murabaha total", murabaha.get("deferred_sale_price")),
                        ("Facility account", murabaha.get("facility_account")),
                        ("CASA", proceeds.get("customer_account_number")),
                        ("Clearing", clearing.get("settlement_ref")),
                    ],
                ),
            ]
        ),
        note="This certificate is issued with the customer email. The same record is on the customer journey.",
        filename_hint=f"{slug}-{ref}",
    )


def desk_step_attachments(case, step: int) -> list[Attachment]:
    items: list[Attachment] = []
    steps = list(range(3, step + 1)) if step == 8 else [step]
    for item in steps:
        html = render_desk_certificate_html(case, item)
        if not html:
            continue
        slug = DESK_CERTS[item][1]
        ref = getattr(case, "id", "case")[:8]
        items.append(html_attachment(f"{ref}-{slug}-certificate.html", html))
    return items


def sedania_pack_attachments(db: Session, execution) -> list[Attachment]:
    from tawarruq.services.sedania_document_service import TRADE_DOC_LABELS
    from tawarruq.services.sedania_financing_service import render_execution_document

    items: list[Attachment] = []
    for kind in TRADE_DOC_LABELS:
        try:
            html, filename = render_execution_document(db, execution, kind)
        except Exception:
            continue
        items.append(html_attachment(filename, html))
    return items
