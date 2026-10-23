"""Generate docs/BTI_Tawarruq_Users_ver_001.docx from the live engine role model."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "BTI_Tawarruq_Users_ver_001.docx"


def set_run(run, *, size=11, bold=False, color=None):
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def add_heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        set_run(run, size=16 if level == 1 else 13 if level == 2 else 12, bold=True, color=(15, 40, 71))
    return p


def add_para(doc, text, *, bold=False, italic=False, size=11):
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run(run, size=size, bold=bold)
    run.italic = italic
    p.paragraph_format.space_after = Pt(8)
    return p


def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(item, style="List Bullet")
        p.paragraph_format.space_after = Pt(2)
        for run in p.runs:
            set_run(run, size=11)


def shade_header(row):
    for cell in row.cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = tcPr.makeelement(qn("w:shd"), {qn("w:fill"): "0F2847", qn("w:val"): "clear"})
        tcPr.append(shd)
        for p in cell.paragraphs:
            for run in p.runs:
                set_run(run, size=10, bold=True, color=(255, 255, 255))


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    hdr = table.rows[0]
    for i, h in enumerate(headers):
        hdr.cells[i].text = h
    shade_header(hdr)
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            cell = table.rows[r_i + 1].cells[c_i]
            cell.text = val
            for p in cell.paragraphs:
                for run in p.runs:
                    set_run(run, size=9)
    doc.add_paragraph()
    return table


def build() -> Path:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.9)
    section.right_margin = Inches(0.9)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = title.add_run("BTI TAWARRUQ ORCHESTRATION SYSTEM")
    set_run(r, size=20, bold=True, color=(15, 40, 71))

    sub = doc.add_paragraph()
    r = sub.add_run("User Categories and Access Roles")
    set_run(r, size=16, bold=True, color=(15, 40, 71))

    add_para(
        doc,
        "Purpose: Define the principal human and system actors that interact with BTI’s "
        "multi-tenant Tawarruq orchestration platform, together with their responsibilities, "
        "access boundaries, and the engine role codes that implement them.",
        italic=True,
    )

    add_heading(doc, "Document Control", 1)
    add_table(
        doc,
        ["Field", "Value"],
        [
            ["Document title", "BTI Tawarruq Orchestration System — User Categories and Access Roles"],
            ["Document type", "Project / Product Requirements Supporting Document"],
            ["Version", "1.2"],
            ["Status", "Complete catalogue for engine alignment; remains flexible to stakeholder edits"],
            ["Product owner", "BTI"],
            ["Technical owner", "Buruuj Fintech / BTI Tawarruq Engine"],
            ["Scope", "Human users, tenant roles, machine identities, and external system actors"],
            ["Companion", "docs/USERS_ACCESS_CONTROLS.md (engine APIs, maker-checker, billing, MFA)"],
        ],
    )

    add_heading(doc, "1. Purpose", 1)
    add_para(
        doc,
        "This document defines the user categories and system actors for BTI’s Tawarruq "
        "Orchestration System, which BTI intends to offer to banks, SACCOs, microfinance "
        "institutions, and other eligible financial institutions. It provides a foundation "
        "for role-based access control, tenant isolation, segregation of duties, and "
        "operational accountability.",
    )
    add_para(
        doc,
        "End customers are outside the system’s user model and do not receive direct BTI "
        "system access. Customer-facing acceptance, signing, or communication is handled "
        "through the financial institution’s own approved channels (including the FI’s "
        "mobile app where the FI issues it).",
    )
    add_para(
        doc,
        "The platform does not require a separate application for every category. One "
        "identity, tenant, role, and permission framework presents features according to "
        "assigned scope. Role names in this document are product language; engine codes "
        "are the stable API values.",
    )

    add_heading(doc, "2. Platform Context", 1)
    add_para(
        doc,
        "The platform orchestrates digital Tawarruq transactions and related commodity-trading "
        "steps, including integration with Sedania / BSAS (or equivalent desks) subject to "
        "applicable integration arrangements. Financial institutions may initiate transactions "
        "through the BTI ops portal (ops.buruujfintech.com) or approved system-to-system APIs "
        "(api.buruujfintech.com).",
    )
    add_para(
        doc,
        "The platform operates as a multi-tenant service. Each financial institution’s data, "
        "transactions, configuration, and billing records must be segregated from those of "
        "other institutions. Access is granted according to role, tenant scope, assigned "
        "permissions, and transaction authority.",
    )

    add_heading(doc, "3. User and System Actor Categories", 1)

    add_heading(doc, "3.1 BTI Platform Super Administrator", 2)
    add_para(doc, "Category / scope: BTI internal; platform-wide. Engine role: platform_admin.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Manage global platform configuration and shared settings.",
            "Create, configure, suspend, or deactivate financial institution tenants.",
            "Invite Super Admin, FI Admin, BTI Ops, Shariah, BTI Finance, and Recon. Does not invite FI Ops or FI Approver.",
            "Issue institution API keys for core-banking onboard.",
            "Configure platform-level controls and monitor service health and integrations.",
            "Maintain oversight of platform-wide limits and operational policies.",
        ],
    )
    add_para(
        doc,
        "Access and control: Powerful administrative actions must be authenticated strongly "
        "and logged. Super-admin must not be the only path for day-to-day trade execution. "
        "Only this role may assign other BTI-internal roles, create institutions, or issue API keys. "
        "FI Operations and FI Approver are invited by the FI Administrator."
    )

    add_heading(doc, "3.2 BTI Tawarruq Operations Officer", 2)
    add_para(doc, "Category / scope: BTI internal; operational oversight. Engine role: bti_ops.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Monitor transaction workflows across participating institutions.",
            "Investigate failed Sedania / partner requests, delayed responses, and callback exceptions.",
            "Perform controlled retries or exception handling where permitted.",
            "Track transaction completion and settlement status.",
            "Escalate incidents to technical, compliance, or financial teams.",
        ],
    )
    add_para(
        doc,
        "Access and control: Cross-tenant visibility is limited to operational need. This role "
        "does not manage tenant lifecycle (no manage_institutions). Customer-identifiable "
        "detail access should be justified, controlled, and audited.",
    )

    add_heading(doc, "3.3 BTI Finance and Billing Officer", 2)
    add_para(doc, "Category / scope: BTI internal; commercial operations. Engine role: bti_finance.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Maintain approved platform fee and billing configurations.",
            "Review transaction-based or volume-based usage charges.",
            "Generate invoices and monitor receivables.",
            "Reconcile billed usage with transaction and platform records.",
            "Produce billing and revenue reports.",
        ],
    )
    add_para(
        doc,
        "Access and control: Billing permissions must not grant trade execution, transaction "
        "approval, or audit-log modification. Portal home is the Billing workspace.",
    )

    add_heading(doc, "3.4 Financial Institution Administrator", 2)
    add_para(doc, "Category / scope: One tenant. Engine role: institution_admin.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Invite FI Admin, FI Ops, FI Approver, Shariah, and Recon for this institution. Cannot invite BTI Super Admin, BTI Ops, or BTI Finance.",
            "Maintain institution-specific configuration, products, and limits within delegated authority.",
            "Request BTI to onboard the institution API key; manage integration configuration.",
            "View institution-level transactions, reports, usage, and fees.",
            "Configure institution approval workflows where supported.",
        ],
    )
    add_para(
        doc,
        "Access and control: Must not access another institution’s data. Cannot create BTI-internal "
        "users or issue API keys. High-risk setting changes should be subject to approval where required.",
    )

    add_heading(doc, "3.5 Financial Institution Operations Officer", 2)
    add_para(doc, "Category / scope: One tenant; transaction operations. Engine role: institution_ops.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Submit Tawarruq financing requests through the portal or an authorized integrated channel.",
            "Initiate permitted commodity purchase and sale instructions (Kenya float and Malaysia BSAS desks).",
            "Monitor transaction states, confirmations, and settlement progress.",
            "Retrieve certificates and transaction documents.",
            "Invite mobile borrowers where the FI uses Buruuj Lend (invite is ops; approval is the Approver).",
            "Investigate pending, failed, or exceptional transactions and escalate issues.",
        ],
    )
    add_para(
        doc,
        "Access and control: Initiation and approval must be separated where maker-checker is required. "
        "This role has write_ops and does not have approve_txn.",
    )

    add_heading(doc, "3.6 Financial Institution Approver", 2)
    add_para(doc, "Category / scope: One tenant; authorization. Engine role: fi_approver.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Approve or reject financing or transaction instructions within assigned authority.",
            "Apply delegated limits by amount, product, branch, or other configured dimensions.",
            "Review exceptions and permitted manual corrections.",
            "Confirm that required approvals are complete before the workflow proceeds.",
        ],
    )
    add_para(
        doc,
        "Access and control: Recommended control role. Whether it is mandatory, and which steps "
        "require approval, is configured with each institution. MVP: Mobile Lend approve/reject "
        "requires approve_txn. Institution admin also holds approve_txn so a small FI can start "
        "without a dedicated approver person. Transaction-limit dimensions remain a design item.",
    )

    add_heading(doc, "3.7 Shariah Compliance Officer / Auditor", 2)
    add_para(doc, "Category / scope: BTI or FI; audit scope varies. Engine role: shariah_officer.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Review transaction sequence, commodity purchase and sale evidence, and required authorizations.",
            "Inspect timestamps, commodity certificate references, and supporting documentation.",
            "Review exceptions and potential sequencing violations.",
            "Generate audit evidence and reports for the relevant Shariah supervisory function.",
        ],
    )
    add_para(
        doc,
        "Access and control: FI auditors are tenant-scoped. Access is read-only (view_shariah). "
        "HTTP writes are blocked. BTI-wide Shariah access, if required, is assigned by Super Admin "
        "and must remain read-only.",
    )

    add_heading(doc, "3.8 Reconciliation and Settlement Officer", 2)
    add_para(doc, "Category / scope: BTI and/or FI. Engine role: reconciler.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Match commodity trade confirmations to settlement and account records.",
            "Investigate settlement discrepancies and failed or incomplete movements.",
            "Track outstanding reconciliation items and exceptions.",
            "Prepare reconciliation reports and support month-end or periodic close.",
        ],
    )
    add_para(
        doc,
        "Access and control: Permissions remain identifiable even if the function is combined with "
        "operations in a small team. BTI-wide reconciler has no institution bind; FI reconciler is "
        "tenant-scoped. Adjustments must be traceable and subject to approval. Portal home is the "
        "Reconciliation workspace: scan trades vs disbursements, classify outstanding/mismatch/matched, "
        "and resolve with an auditable note.",
    )

    add_heading(doc, "3.9 Read-only Viewer", 2)
    add_para(doc, "Category / scope: One tenant; observation. Engine role: read_only.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "View journeys, applications, and operational metrics without changing deals.",
            "Support training, observation, or limited management oversight.",
        ],
    )
    add_para(
        doc,
        "Access and control: GET and metrics only. Not a substitute for Shariah audit (no view_shariah).",
    )

    add_heading(doc, "3.10 Financial Institution Integration Administrator / API Client", 2)
    add_para(doc, "Category / scope: Institution-scoped machine identity. Engine role: api_client.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Authenticate the institution’s systems to BTI APIs (X-API-Key; optional HMAC).",
            "Submit authorized quote, buy, sell, and status requests.",
            "Receive status notifications and retrieve permitted results or certificates.",
            "Support integration monitoring and credential rotation.",
        ],
    )
    add_para(
        doc,
        "Access and control: Non-human identity — not a portal login. Institution-specific credentials, "
        "narrowly scoped permissions (api_submit + write_ops), rate limits, secret handling, and "
        "auditable requests. Production credentials must not be shared between tenants.",
    )

    add_heading(doc, "3.11 External Trading Platform / Settlement System", 2)
    add_para(doc, "Category / scope: External system identity. Not a portal role.")
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Exchange trade instructions and receive confirmations through supported interfaces.",
            "Return transaction references and commodity ownership evidence where available.",
            "Provide status notifications or callbacks (Daraja, MNO possession, Sedania/BSAS).",
            "Supply settlement information required for reconciliation.",
        ],
    )
    add_para(
        doc,
        "Access and control: Sedania / BSAS / M-Pesa / MNO integrations authenticate as system "
        "callbacks (callback token / partner credentials), not as users who sign in. Exact "
        "capabilities depend on the external platform’s approved API.",
    )

    add_heading(doc, "3.12 Agent Dealer (Kenya float desk)", 2)
    add_para(
        doc,
        "Category / scope: Kenya operating extra vs the original BTI MVP table. Engine role: agent_dealer.",
    )
    add_para(doc, "Primary responsibilities", bold=True)
    add_bullets(
        doc,
        [
            "Top up the authorised agent-dealer float pool used at Kenya step 2.",
            "Operate only the dealer desk — no customer journey, no FI ops book.",
        ],
    )
    add_para(
        doc,
        "Access and control: Bound to one dealer record (agent_dealer_id). Portal paths other than "
        "the dealer desk are blocked. Institution ops cannot add dealer float.",
    )

    add_heading(doc, "4. Recommended MVP Role Set and Engine Mapping", 1)
    add_para(
        doc,
        "Implement a common identity, tenant, role, and permission framework, then present features "
        "according to each actor’s assigned scope.",
    )
    add_table(
        doc,
        ["Doc category", "Engine role", "MVP priority", "Identity"],
        [
            ["BTI Platform Super Administrator", "platform_admin", "Essential", "Portal"],
            ["BTI Tawarruq Operations Officer", "bti_ops", "Essential", "Portal"],
            ["BTI Finance / Billing Officer", "bti_finance", "Essential if billing in MVP", "Portal"],
            ["Financial Institution Administrator", "institution_admin", "Essential", "Portal"],
            ["Financial Institution Operations Officer", "institution_ops", "Essential", "Portal"],
            ["Financial Institution Approver", "fi_approver", "Essential where policy requires", "Portal"],
            ["Shariah / Audit User", "shariah_officer", "Essential control", "Portal"],
            ["Reconciliation Officer", "reconciler", "Essential capability", "Portal"],
            ["Read-only Viewer", "read_only", "Recommended", "Portal"],
            ["Institution API Client", "api_client", "Essential for API onboarding", "Machine key"],
            ["External Trading Platform", "(callback / partner auth)", "Essential integration", "System"],
            ["Agent Dealer (Kenya)", "agent_dealer", "Kenya desk extra", "Portal"],
        ],
    )

    add_heading(doc, "5. Permission Catalogue", 1)
    add_para(
        doc,
        "Permissions are stable strings. Roles compose them. Super Admin holds platform permissions "
        "except write_ops, approve_txn, and dealer_desk — Super Admin is not a trade or approval desk.",
    )
    add_table(
        doc,
        ["Permission", "Meaning", "Typical holders"],
        [
            ["read", "View tenant-scoped records", "Most human roles"],
            ["write_ops", "Initiate and progress Tawarruq desks", "FI ops, BTI ops, FI admin, API client"],
            ["write_bti_ops", "Cross-tenant operational exceptions", "BTI ops, Super Admin"],
            ["approve_txn", "Maker-checker authorization", "FI approver, FI admin (not Super Admin)"],
            ["export_data", "CSV / Shariah pack downloads", "Super Admin, BTI ops, finance, Shariah, reconciler, FI admin"],
            ["manage_credentials", "Portal users and webhooks; API key create is Super Admin only", "FI admin, Super Admin"],
            ["manage_integrations", "Partner credential profiles", "FI admin, Super Admin"],
            ["manage_institutions", "Tenant lifecycle", "Super Admin only"],
            ["manage_billing", "Fees and invoices", "BTI finance, Super Admin"],
            ["reconcile", "Settlement matching", "Reconciler, Super Admin"],
            ["view_metrics", "Ops monitor telemetry", "Most roles"],
            ["view_shariah", "Audit ledger and certificates", "Shariah, BTI ops, admins"],
            ["api_submit", "Machine quote/buy/sell/status", "API client, Super Admin"],
            ["dealer_desk", "Kenya float top-up only", "Agent dealer"],
        ],
    )

    add_heading(doc, "6. Access Control Design Principles", 1)
    add_bullets(
        doc,
        [
            "Tenant isolation: Every FI’s users, transactions, documents, configuration, and billing records are isolated from other tenants.",
            "Role-based access control: Grant permissions through defined roles rather than one-off privileges.",
            "Least privilege: Each human or system identity receives only the access required for its responsibilities.",
            "Maker-checker separation: The person initiating a sensitive step must not be the sole approver of that step where the FI requires it.",
            "Transaction limits: Enforce delegated authority by amount and any other FI-defined dimensions (product, branch) once confirmed.",
            "System identity controls: Treat API clients and external integrations as non-human identities with scoped credentials, rotation, and monitoring.",
            "Auditability: Record who or what performed an action, tenant context, timestamp, transaction reference, outcome, and relevant changes.",
            "Controlled exception handling: Retries, reversals, corrections, and manual overrides follow explicit rules and produce an auditable record.",
            "Separation of duties: Platform administration, trade operations, billing, approval, and audit must not be bundled into unrestricted access.",
            "Secure authentication: Portal uses email/password sessions; APIs use X-API-Key; privileged users should use stronger verification as BTI requires.",
        ],
    )

    add_heading(doc, "7. High-Level Access Matrix", 1)
    add_table(
        doc,
        ["Action", "Primary actor", "Data scope", "Control note"],
        [
            ["Manage tenants and global configuration", "BTI Super Admin", "Platform", "Logged; not a trade desk"],
            ["Manage BTI staff", "BTI Super Admin", "Platform", "Invites Super Admin, BTI Ops, BTI Finance, Shariah, Recon, FI Admin"],
            ["Manage institution users", "FI Admin", "Own tenant", "Invites FI Admin, FI Ops, FI Approver, Shariah, Recon. Super Admin does not invite FI Ops or FI Approver"],
            ["Issue API keys", "BTI Super Admin", "Tenant", "FI Admin requests BTI to onboard"],
            ["Initiate transaction", "FI Ops / API Client", "Own tenant", "write_ops / api_submit"],
            ["Approve transaction / mobile activation", "FI Approver", "Own tenant", "approve_txn; not write_ops"],
            ["Monitor cross-tenant operations", "BTI Ops", "Operationally limited", "No tenant create/suspend"],
            ["View Shariah evidence", "Shariah / Audit", "Own tenant or approved scope", "Read-only"],
            ["Manage invoices and platform fees", "BTI Finance", "BTI commercial records", "No trade approval"],
            ["Perform settlement reconciliation", "Reconciler", "Assigned scope", "BTI-wide or tenant"],
            ["Top up Kenya dealer float", "Agent dealer", "Bound dealer pool", "Ops cannot top up"],
            ["Execute commodity trades / confirm settlement", "External platform", "Integration scope", "Callbacks, not portal login"],
        ],
    )

    add_heading(doc, "8. Important Workflow Control", 1)
    add_para(
        doc,
        "The platform must prevent a commodity resale from being initiated before the required "
        "commodity purchase is confirmed. The system validates transaction state and evidence from "
        "the trading platform before allowing subsequent steps. Any retry or exception process must "
        "not bypass the required sequencing controls (including Kenya possession-before-Murabaha "
        "and No-Inah independent sale).",
    )
    add_para(
        doc,
        "This document defines user categories and access boundaries. Detailed Shariah approval "
        "rules, full transaction-state models, regulatory obligations, external API capabilities, "
        "and institution-specific approval policies are confirmed during solution design and may "
        "change this catalogue without requiring a rewrite of the permission framework.",
    )

    add_heading(doc, "9. Engine Implementation Status (v1.2)", 1)
    add_para(
        doc,
        "Live on the Tawarruq engine (ops portal + API). One portal; features shown by role. "
        "AUTH_ENABLED=false still executes immediately so mock and lab flows can run without a checker.",
    )
    add_table(
        doc,
        ["Capability", "Status", "Notes"],
        [
            ["Role enum + permission map", "Live", "src/tawarruq/enums.py, services/rbac.py"],
            ["Portal Users picker", "Live", "Super Admin invites Super Admin, FI Admin, BTI Ops, Shariah, BTI Finance, Recon. FI Admin invites FI desk staff. Super Admin does not invite FI Ops or FI Approver"],
            ["API key onboard", "Live", "Super Admin only; FI Admin requests BTI"],
            ["Tenant isolation + suspend", "Live", "Writes blocked when Institution.active is false"],
            ["BTI Ops vs Super Admin split", "Live", "Super Admin has write_bti_ops, not write_ops/approve_txn"],
            ["Maker-checker Murabaha / liquidation / disbursement", "Live", "write_ops queues; approve_txn executes; no self-approve"],
            ["Approval amount limits", "Live", "min(institution.approval_limit_amount, user.approval_limit_amount)"],
            ["Shariah read-only", "Live", "Writes blocked at middleware"],
            ["API client keys", "Live", "Preferred machine role api_client; skips maker-checker"],
            ["Billing invoices", "Live", "Disbursed volume × institution billing_fee_bps"],
            ["Reconciliation workspace", "Live", "Scan trades vs disbursements; resolve with audit note"],
            ["Privileged MFA (TOTP)", "Live", "Super Admin / BTI Ops / BTI Finance enroll + login challenge"],
            ["Export by role", "Live", "export_data on Shariah pack, audit CSV, billing/recon exports"],
            ["BTI Ops retries", "Live", "write_bti_ops on Kenya/Malaysia failed-leg retry"],
            ["Product/branch limits", "Configurable later", "Amount limits live; product/branch per FI (section 11)"],
            ["End-customer BTI portal access", "Out of scope", "FI channels and customer journey APIs only"],
        ],
    )

    add_heading(doc, "10. Seeded Catalogue Identities (test / production seed)", 1)
    add_para(
        doc,
        "When OPS_SEED_USERS=true the engine idempotently creates missing catalogue users. Existing "
        "emails (including the already-created Super Admin) are never overwritten. Domain defaults "
        "to buruujfintech.com. Temporary seed password is rotated out of band; first login forces "
        "change-password.",
    )
    add_table(
        doc,
        ["Seeded identity", "Role"],
        [
            ["OPS_BOOTSTRAP_ADMIN_EMAIL (e.g. admin@…)", "platform_admin"],
            ["bti.ops@…", "bti_ops"],
            ["bti.finance@…", "bti_finance"],
            ["fi.admin@…", "institution_admin (default / MWALIMU tenant)"],
            ["fi.ops@…", "institution_ops"],
            ["fi.approver@…", "fi_approver"],
            ["shariah@…", "shariah_officer"],
            ["reconciler@…", "reconciler (BTI-wide)"],
            ["fi.reconciler@…", "reconciler (tenant)"],
            ["readonly@…", "read_only"],
            ["dealer@…", "agent_dealer (SEED-DEALER pool)"],
            ["seed-api-client key", "api_client"],
        ],
    )
    add_para(
        doc,
        "Re-run: python -m tawarruq.cli seed-ops-users. New secrets append to data/ops_seed_credentials.txt "
        "(not committed). Portal: https://ops.buruujfintech.com  API: https://api.buruujfintech.com/docs",
    )

    add_heading(doc, "11. Decisions to Confirm with BTI and Each Financial Institution", 1)
    add_bullets(
        doc,
        [
            "Confirm that all customer-facing acceptance, signing, and communications remain within the FI’s approved channels, with no direct end-customer access to BTI.",
            "Confirm each FI’s approval_steps (murabaha, liquidation, disbursement) and amount limits; product/branch limits can be added later.",
            "Which BTI staff roles may view customer-identifiable transaction data, and under what circumstances?",
            "Will reconciliation and operations be separate teams in the first release? (Engine already supports both combined and split.)",
            "Which user categories need export, download, or document-generation privileges?",
            "What are the external trading platform’s actual API, callback, certificate, and settlement capabilities?",
            "Which authentication methods, credential rotation periods, and privileged-access controls are required for Super Admin?",
            "What audit-log retention, tamper-resistance, and reporting requirements apply?",
        ],
    )

    add_heading(doc, "12. Reference Basis and Assumptions", 1)
    add_para(
        doc,
        "This document is based on the Buruuj Tawarruq-as-a-Service Product Requirements Document, "
        "which identifies financial institutions, FI loan officers/administrators, Buruuj system "
        "administrators, and customer-facing processes delivered through financial institutions, "
        "and describes multi-tenancy, API and portal access, billing, reconciliation, and audit "
        "controls. Additional roles (BTI ops, finance, approver, reconciler, Shariah, API client, "
        "read-only, agent dealer) are recommended design roles to support operational segregation "
        "and a bank-ready service.",
    )
    add_para(
        doc,
        "They are proposals for stakeholder validation, not confirmed organizational positions or "
        "regulatory determinations. Engine implementation uses a data-driven role/permission map "
        "so catalogue edits can be absorbed without a separate app per persona.",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}")
