"""PDF certificate attachments for customer email (Bursa-style three-leg desk certs)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

Attachment = tuple[str, bytes, str]

AGENT_NAME = "Buruuj Fintech"
SEDANIA_PARTY = "Sedania"

# kind → human title used in PDF / filenames
DESK_CERT_KINDS = {
    "sedania_to_fi": "Commodity purchase certificate (Sedania to FI)",
    "fi_to_customer": "Murabaha sale certificate (FI to Customer)",
    "customer_to_sedania": "Commodity sale certificate (Customer to Sedania)",
}

# Workflow / UI kinds → which desk step owns the PDF.
DESK_CERT_KIND_STEPS = {
    "sedania_to_fi": 3,
    "fi_to_customer": 4,
    "customer_to_sedania": 5,
    # Legacy aliases (older cases / emails)
    "purchase": 3,
    "murabahah": 4,
    "murabaha": 4,
    "complete": 5,
}

# step → cert kind for that leg
DESK_CERTS = {
    3: ("Commodity purchase certificate (Sedania to FI)", "sedania_to_fi"),
    4: ("Murabaha sale certificate (FI to Customer)", "fi_to_customer"),
    5: ("Commodity sale certificate (Customer to Sedania)", "customer_to_sedania"),
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
        pdf.cell(width, 6, "Tawarruq e-certificate")
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
        pdf.cell(width, 8, f"  Certificate number  {_pdf_text(doc_ref)}", fill=True)
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
            pdf.multi_cell(width, 4, _pdf_text(note))
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


def tawarruq_certificate_attachments(
    *,
    certificate_number: str,
    customer_name: str,
    institution_name: str,
    amount: str,
    currency: str,
) -> list[Attachment]:
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


def _cert_number(slug: str, ref: str) -> str:
    return f"{slug.upper().replace('_', '-')}-{str(ref)[:12]}"


def desk_certificate_attachment(case, kind: str) -> Attachment | None:
    key = str(kind or "").strip().lower()
    step = DESK_CERT_KIND_STEPS.get(key)
    if not step:
        return None
    items = desk_step_attachments(case, step, pack_all=False)
    return items[0] if items else None


def desk_step_attachments(case, step: int, *, pack_all: bool | None = None) -> list[Attachment]:
    items: list[Attachment] = []
    payload = _desk_payload(case)
    orig = payload.get("origination") or {}
    initiate = payload.get("initiate") or {}
    murabaha = payload.get("murabaha") or {}
    customer_sale = payload.get("customer_sale") or {}
    stamps = payload.get("timestamps") if isinstance(payload.get("timestamps"), dict) else {}
    ref = (payload.get("journey") or {}).get("customer_ref") or getattr(case, "id", "case")[:8]
    institution = case.institution.name if getattr(case, "institution", None) else "Institution"
    commodity = (
        murabaha.get("commodity")
        or initiate.get("commodity")
        or customer_sale.get("commodity")
        or orig.get("facility_product_type")
        or "Airtime"
    )
    units = (
        murabaha.get("units")
        or initiate.get("units")
        or initiate.get("commodity_quantity")
        or customer_sale.get("units")
        or orig.get("approved_facility_amount")
        or "1"
    )
    unit_cost = initiate.get("unit_cost") or murabaha.get("cost_price") or orig.get("approved_facility_amount") or "-"
    total_cost = initiate.get("total_cost") or murabaha.get("cost_price") or orig.get("approved_facility_amount") or "-"
    total_price = murabaha.get("total_price") or murabaha.get("deferred_sale_price") or orig.get("contract_price") or "-"
    currency = "KES"

    # Pack of three when facility is complete (step 8) or final customer-sale notify
    want_all = pack_all if pack_all is not None else step in {5, 8}
    step_list = [3, 4, 5] if want_all else [step]

    for item in step_list:
        spec = DESK_CERTS.get(item)
        if not spec:
            continue
        title, slug = spec

        if item == 3:
            seller = initiate.get("seller_name") or initiate.get("commodity_seller") or SEDANIA_PARTY
            buyer = initiate.get("buyer_name") or initiate.get("commodity_buyer") or institution
            trade_rows = [
                ("Seller", seller),
                ("Buyer", buyer),
                ("Product / commodity", commodity),
                ("Unit", "lot"),
                ("Volume / units", units),
                ("Unit cost", f"{currency} {unit_cost}"),
                ("Total / Value", f"{currency} {total_cost}"),
                ("Currency", currency),
                ("Timestamp", stamps.get("purchase") or initiate.get("purchase_timestamp") or "-"),
                ("Agent", initiate.get("agent_name") or initiate.get("commodity_agent") or AGENT_NAME),
            ]
        elif item == 4:
            seller = murabaha.get("seller_name") or institution
            buyer = murabaha.get("buyer_name") or orig.get("customer_name") or "Customer"
            # Murabaha narrative: total price only (no profit/cost breakdown)
            trade_rows = [
                ("Seller", seller),
                ("Buyer", buyer),
                ("Owner", buyer),
                ("Product / commodity", commodity),
                ("Unit", "lot"),
                ("Volume / units", units),
                ("Total / Value", f"{currency} {total_price}"),
                ("Currency", currency),
                ("Timestamp", stamps.get("sale") or murabaha.get("sale_timestamp") or "-"),
                ("Agent", murabaha.get("agent_name") or AGENT_NAME),
            ]
        else:
            seller = customer_sale.get("seller_name") or orig.get("customer_name") or "Customer"
            buyer = customer_sale.get("buyer_name") or SEDANIA_PARTY
            sale_total = customer_sale.get("total_price") or customer_sale.get("total_cost") or total_cost
            trade_rows = [
                ("Seller", seller),
                ("Buyer", buyer),
                ("Product / commodity", commodity),
                ("Unit", "lot"),
                ("Volume / units", units),
                ("Unit cost", f"{currency} {customer_sale.get('unit_cost') or unit_cost}"),
                ("Total / Value", f"{currency} {sale_total}"),
                ("Currency", currency),
                ("Timestamp", stamps.get("customer_sale") or customer_sale.get("sale_timestamp") or "-"),
                ("Agent", customer_sale.get("agent_name") or AGENT_NAME),
            ]

        content = render_certificate_pdf(
            title=title,
            subtitle="Electronic trade certificate issued for this Tawarruq facility.",
            doc_ref=_cert_number(slug, ref),
            sections=[
                (
                    "Parties",
                    [
                        ("Institution", institution),
                        ("Customer", orig.get("customer_name")),
                        ("Email", orig.get("customer_email")),
                        ("Phone", orig.get("customer_phone")),
                        ("Reference", ref),
                    ],
                ),
                ("Trade", trade_rows),
            ],
            note=f"Agent: {AGENT_NAME}. Issued for the customer facility record.",
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
