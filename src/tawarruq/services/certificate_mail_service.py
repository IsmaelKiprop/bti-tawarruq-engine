"""PDF certificate attachments for customer email."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

Attachment = tuple[str, bytes, str]

DESK_CERTS = {
    3: ("Commodity purchase certificate", "purchase"),
    4: ("Murabaha sale certificate", "murabaha"),
    5: ("Agency appointment certificate", "agency"),
    6: ("Resale proceeds certificate", "resale"),
    7: ("Clearing certificate", "clearing"),
    8: ("Facility completion certificate", "complete"),
}


def _safe_name(filename: str, suffix: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ".-_" else "-" for ch in filename).strip("-") or "certificate"
    if not safe.lower().endswith(suffix):
        safe = f"{safe}{suffix}"
    return safe


def _pdf_text(value: object) -> str:
    if value is None or value == "":
        return "-"
    return str(value).encode("latin-1", "replace").decode("latin-1")


def render_certificate_pdf(
    *,
    title: str,
    subtitle: str,
    doc_ref: str,
    sections: list[tuple[str, list[tuple[str, object]]]],
    note: str | None = None,
) -> bytes:
    def _fallback_pdf() -> bytes:
        body = f"{title}\n{subtitle}\nRef: {doc_ref}\n{note or ''}".encode("latin-1", errors="replace")
        safe = body.replace(b"(", b"[").replace(b")", b"]")[:180]
        stream = b"BT /F1 12 Tf 72 720 Td (" + safe + b") Tj ET\n"
        return (
            b"%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
            b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>endobj\n"
            b"4 0 obj<< /Length "
            + str(len(stream)).encode()
            + b" >>stream\n"
            + stream
            + b"endstream\nendobj\nxref\n0 5\n0000000000 65535 f \ntrailer<< /Size 5 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"
        )

    try:
        from fpdf import FPDF

        pdf = FPDF(unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.set_margins(16, 16, 16)
        pdf.add_page()
        width = 178
        pdf.set_fill_color(11, 31, 58)
        pdf.rect(0, 0, 210, 32, "F")
        pdf.set_xy(16, 8)
        pdf.set_text_color(201, 162, 39)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(width, 6, "BURUUJ FINTECH")
        pdf.set_xy(16, 16)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(width, 6, "Tawarruq certificate")
        pdf.set_xy(16, 40)
        pdf.set_text_color(11, 31, 58)
        pdf.set_font("Helvetica", "B", 18)
        pdf.multi_cell(width, 8, _pdf_text(title))
        pdf.set_text_color(92, 107, 124)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(width, 5, _pdf_text(subtitle))
        pdf.ln(2)
        pdf.set_fill_color(244, 246, 249)
        pdf.set_text_color(11, 31, 58)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(width, 8, f"  Ref  {_pdf_text(doc_ref)}", fill=True)
        pdf.ln(12)
        for heading, rows in sections:
            pdf.set_x(16)
            pdf.set_text_color(11, 31, 58)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(width, 8, _pdf_text(heading))
            pdf.ln(8)
            for label, value in rows:
                pdf.set_x(16)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(92, 107, 124)
                pdf.cell(55, 6, _pdf_text(label))
                pdf.set_text_color(18, 32, 51)
                pdf.multi_cell(width - 55, 6, _pdf_text(value))
            pdf.ln(2)
        if note:
            pdf.ln(4)
            pdf.set_x(16)
            pdf.set_text_color(92, 107, 124)
            pdf.set_font("Helvetica", "I", 8)
            pdf.multi_cell(width, 5, _pdf_text(note))
        pdf.set_y(-16)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(92, 107, 124)
        pdf.cell(0, 6, "Confidential - for customer and institution use", align="C")
        return bytes(pdf.output())
    except Exception:
        return _fallback_pdf()


def pdf_bytes_attachment(filename: str, content: bytes) -> Attachment:
    return (_safe_name(filename, ".pdf"), content, "application/pdf")


def pdf_file_attachment(path: str | None, filename: str | None = None) -> Attachment | None:
    if not path:
        return None
    file = Path(path)
    if not file.is_file():
        return None
    name = filename or file.name
    return pdf_bytes_attachment(name, file.read_bytes())


def bsas_certificate_attachments(certificate) -> list[Attachment]:
    items: list[Attachment] = []
    uploaded = pdf_file_attachment(getattr(certificate, "pdf_path", None), getattr(certificate, "pdf_filename", None))
    if uploaded:
        items.append(uploaded)
        return items
    number = getattr(certificate, "certificate_number", None) or "bsas-receipt"
    content = render_certificate_pdf(
        title="Islamic Services Receipt",
        subtitle="Bursa Suq Al-Sila e-certificate recorded on this facility.",
        doc_ref=str(number),
        sections=[
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
                    ("Value", getattr(certificate, "value_amount", None)),
                    ("Selling date", getattr(certificate, "selling_date", None)),
                ],
            ),
        ],
        note="Issued from the Buruuj Tawarruq engine after the desk recorded the Bursa receipt.",
    )
    items.append(pdf_bytes_attachment(f"{number}-receipt.pdf", content))
    return items


def tawarruq_certificate_attachments(*, certificate_number: str, customer_name: str, institution_name: str, amount: str, currency: str) -> list[Attachment]:
    content = render_certificate_pdf(
        title="Tawarruq financing certificate",
        subtitle="Evidence that this facility completed commodity tawarruq and disbursement.",
        doc_ref=certificate_number,
        sections=[
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
        ],
        note="Keep this certificate with the customer journey record.",
    )
    return [pdf_bytes_attachment(f"{certificate_number}.pdf", content)]


def _desk_payload(case) -> dict:
    try:
        import json

        return json.loads(case.payload_json or "{}")
    except Exception:
        return {}


# Workflow / UI kinds → desk step that owns the PDF.
DESK_CERT_KIND_STEPS = {
    "purchase": 3,
    "murabahah": 4,
    "murabaha": 4,
    "agency": 5,
    "liquidation": 6,
    "resale": 6,
    "clearing": 7,
    "complete": 8,
}


def desk_certificate_attachment(case, kind: str) -> Attachment | None:
    step = DESK_CERT_KIND_STEPS.get(str(kind or "").strip().lower())
    if not step:
        return None
    items = desk_step_attachments(case, step)
    return items[0] if items else None


def desk_step_attachments(case, step: int) -> list[Attachment]:
    items: list[Attachment] = []
    payload = _desk_payload(case)
    orig = payload.get("origination") or {}
    initiate = payload.get("initiate") or {}
    murabaha = payload.get("murabaha") or {}
    proceeds = payload.get("proceeds") or {}
    clearing = payload.get("clearing") or {}
    ref = (payload.get("journey") or {}).get("customer_ref") or getattr(case, "id", "case")[:8]
    institution = case.institution.name if getattr(case, "institution", None) else "Institution"
    # Three trade certificates for a completed facility; single-step otherwise.
    if step == 8:
        steps = [3, 4, 6]
    else:
        steps = [step]
    for item in steps:
        spec = DESK_CERTS.get(item)
        if not spec:
            continue
        title, slug = spec
        content = render_certificate_pdf(
            title=title,
            subtitle="Tawarruq desk certificate for this customer facility.",
            doc_ref=f"{slug.upper()}-{ref}",
            sections=[
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
            ],
            note="This PDF is issued with the customer email. The same record is on the customer journey.",
        )
        items.append(pdf_bytes_attachment(f"{str(ref)[:8]}-{slug}-certificate.pdf", content))
    return items


def sedania_pack_attachments(db: Session, execution) -> list[Attachment]:
    from tawarruq.services.sedania_document_service import TRADE_DOC_LABELS
    from tawarruq.services.sedania_financing_service import render_execution_document

    items: list[Attachment] = []
    for kind, label in TRADE_DOC_LABELS.items():
        try:
            _html, filename = render_execution_document(db, execution, kind)
        except Exception:
            continue
        content = render_certificate_pdf(
            title=str(label),
            subtitle="AS SIDQ trade document for this Sedania facility.",
            doc_ref=Path(filename).stem,
            sections=[
                (
                    "Facility",
                    [
                        ("Customer", getattr(getattr(execution, "customer", None), "full_name", None)),
                        ("Institution", getattr(getattr(execution, "institution", None), "name", None)),
                        ("Amount", f"{execution.currency} {execution.amount}"),
                        ("Deferred", f"{execution.currency} {execution.deferred_price}"),
                    ],
                )
            ],
            note="Open the customer journey for the full branded document if needed.",
        )
        items.append(pdf_bytes_attachment(f"{Path(filename).stem}.pdf", content))
    return items
