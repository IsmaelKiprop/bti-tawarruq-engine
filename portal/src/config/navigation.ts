import type { ComponentType } from "react";
import type { ProductModule } from "./deployment";
import type { SessionUser } from "../api/client";
import { AUDIT_ROLES, canSeeNavItem, getHomePath, getRoleProfile, TESTER_SHELL, type OpsRole } from "./roles";
import {
  IconApplications,
  IconDashboard,
  IconInstitutions,
  IconIntegrations,
  IconKenya,
  IconMalaysia,
  IconMonitor,
  IconNewApplication,
  IconRepayments,
  IconSettings,
  IconShariah,
  IconTransactions,
  IconUsers,
  IconWebhooks,
} from "../components/icons";

type NavIcon = ComponentType<{ size?: number; className?: string }>;

export interface NavItem {
  to: string;
  label: string;
  Icon: NavIcon;
  end?: boolean;
  /** Shown under the label so people know what the page is for before clicking. */
  hint?: string;
  permission?: string;
  anyPermissions?: string[];
  roles?: OpsRole[];
  excludeRoles?: OpsRole[];
  /** Temporarily omit from the sidebar without removing the route. */
  hidden?: boolean;
  /** Hide unless this product module is enabled on the install. */
  product?: ProductModule;
  /** Hide on customer-server editions (Institutions directory). */
  hideOnOnprem?: boolean;
}

export interface NavSection {
  id: string;
  label: string;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
  {
    id: "overview",
    label: "Overview",
    items: [
      {
        to: "/origination",
        label: "Origination",
        Icon: IconNewApplication,
        hint: "FI Ops eight-step facility desk",
        anyPermissions: ["write_ops", "approve_txn"],
      },
      {
        to: "/",
        label: "Dashboard",
        Icon: IconDashboard,
        end: true,
        hint: "Customer FI charts and onboarding",
        excludeRoles: ["institution_ops", "fi_approver"],
      },
      {
        to: "/institutions/onboard",
        label: "Onboard FI",
        Icon: IconNewApplication,
        hint: "KYC wizard for a customer institution",
        anyPermissions: ["manage_institutions", "write_bti_ops"],
        hideOnOnprem: true,
      },
      {
        to: "/institutions",
        label: "Institutions",
        Icon: IconInstitutions,
        hint: "Customer institution directory",
        anyPermissions: ["manage_institutions", "write_bti_ops"],
        hideOnOnprem: true,
      },
      {
        to: "/institution",
        label: "FI profile",
        Icon: IconInstitutions,
        hint: "Your institution KYC and API client request",
        roles: ["institution_admin"],
      },
      { to: "/users", label: "Users", Icon: IconUsers, hint: "Roles and portal logins", permission: "manage_credentials" },
      { to: "/settings", label: "Settings", Icon: IconSettings, hint: "Your profile and security" },
      {
        to: "/customer",
        label: "Customer Journey",
        Icon: IconApplications,
        hint: "Eight-step tracker and certificates",
        hidden: true,
      },
      {
        to: "/billing",
        label: "Billing",
        Icon: IconMonitor,
        hint: "Fees and invoices (BTI Finance)",
        permission: "manage_billing",
        product: "billing",
        hidden: true,
      },
      {
        to: "/reconciliation",
        label: "Reconciliation",
        Icon: IconTransactions,
        hint: "Settlement matching",
        permission: "reconcile",
        hidden: true,
      },
    ],
  },
  {
    id: "setup",
    label: "Setup & access",
    items: [
      {
        to: "/integrations",
        label: "Integrations",
        Icon: IconIntegrations,
        hint: "Partner credentials",
        permission: "manage_integrations",
        hidden: true,
      },
      {
        to: "/webhooks",
        label: "Webhooks & Keys",
        Icon: IconWebhooks,
        hint: "System-to-system",
        permission: "manage_credentials",
        hidden: true,
      },
    ],
  },
  {
    id: "kenya",
    label: "Kenya track: float / airtime",
    items: [
      { to: "/kenya", label: "Kenya Ops", Icon: IconKenya, hint: "Run the eight steps in order", permission: "write_ops", product: "kenya" },
      {
        to: "/agent-dealers",
        label: "Agent Dealers",
        Icon: IconKenya,
        hint: "Step 2 float pool. Dealer adds float.",
        roles: ["bti_ops", "institution_admin", "institution_ops", "agent_dealer"],
        product: "kenya",
      },
      { to: "/customers", label: "Customers", Icon: IconUsers, hint: "Step 1 records and journey links", permission: "write_ops", product: "kenya" },
      {
        to: "/mobile-lend",
        label: "Mobile Lend",
        Icon: IconUsers,
        hint: "Invite (ops) and approve (approver)",
        roles: ["bti_ops", "institution_admin", "institution_ops", "fi_approver"],
        product: "mobile",
      },
      { to: "/repayments", label: "Repayments", Icon: IconRepayments, hint: "After disbursement", permission: "write_ops", product: "kenya" },
      {
        to: "/approvals",
        label: "Approvals",
        Icon: IconUsers,
        hint: "Maker-checker queue",
        permission: "approve_txn",
      },
    ],
  },
  {
    id: "sedania",
    label: "Sedania track: AS SIDQ",
    items: [
      {
        to: "/sedania",
        label: "Sedania Financing",
        Icon: IconMalaysia,
        hint: "Wakeel or Rasul, muqassah, CASA",
        permission: "write_ops",
        product: "sedania",
      },
    ],
  },
  {
    id: "malaysia",
    label: "Malaysia track: Bursa BSAS",
    items: [
      {
        to: "/malaysia",
        label: "Malaysia Manual Bridge",
        Icon: IconMalaysia,
        hint: "Desk packet in, e-cert out",
        permission: "write_ops",
        product: "malaysia",
      },
    ],
  },
  {
    id: "records",
    label: "Records & evidence",
    items: [
      {
        to: "/applications/new",
        label: "New Application",
        Icon: IconNewApplication,
        hint: "Start a journey",
        permission: "write_ops",
        hidden: true,
      },
      { to: "/applications", label: "Applications", Icon: IconApplications, hint: "Customer side", hidden: true },
      { to: "/transactions", label: "Transactions", Icon: IconTransactions, hint: "Commodity side", hidden: true },
      {
        to: "/shariah",
        label: "Shariah Audit",
        Icon: IconShariah,
        hint: "Tenant or all-institution chain",
        permission: "view_shariah",
        excludeRoles: ["institution_ops", "fi_approver"],
      },
      {
        to: "/documentation",
        label: "Documentation",
        Icon: IconApplications,
        hint: "Process guides and desk explainers",
        excludeRoles: ["agent_dealer"],
        hidden: true,
      },
    ],
  },
  {
    id: "oversight",
    label: "Oversight",
    items: [
      {
        to: "/ops",
        label: "Ops Monitor",
        Icon: IconMonitor,
        hint: "Engine telemetry for your role",
        permission: "view_metrics",
        excludeRoles: ["institution_ops", "fi_approver"],
      },
      {
        to: "/audit",
        label: "Audit trail",
        Icon: IconShariah,
        hint: "Grouped ops events from login onward",
        roles: AUDIT_ROLES,
      },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((section) => section.items).filter((item) => !item.hidden);

const AUTH_PATHS = new Set(["/login", "/change-password", "/mfa-enroll"]);

/** After login, honor `from` only if this role can open that page. */
export function safePostLoginPath(user: SessionUser | null | undefined, from?: string | null, authEnabled = true): string {
  const home = getHomePath(user?.role);
  const raw = (from || "").split("?")[0] || "";
  if (!raw || AUTH_PATHS.has(raw)) return home;
  const item = NAV_SECTIONS.flatMap((section) => section.items)
    .filter((entry) => !entry.hidden)
    .find((entry) => raw === entry.to || (entry.to !== "/" && raw.startsWith(`${entry.to}/`)));
  if (!item || !canSeeNavItem(item, user, authEnabled)) return home;
  return from || home;
}

export const ROUTE_META: Record<string, { title: string; description: string }> = {
  "/": {
    title: "Dashboard",
    description: "Customer FI charts, lifecycle counts, and engine uptime",
  },
  "/documentation": {
    title: "Documentation",
    description: "Process guides, desk explainers, and approval-limit notes",
  },
  "/audit": {
    title: "Audit trail",
    description: "Grouped portal and API operations scoped to your institutions",
  },
  "/ops": {
    title: "Ops Monitor",
    description: "RBAC context, metrics, and HTTP telemetry",
  },
  "/customer": {
    title: "Customer Journey Tracker",
    description: "Same eight financing steps the customer and Swagger use, plus certificates",
  },
  "/journey": {
    title: "Customer Journey Tracker",
    description: "Same eight financing steps the customer and Swagger use, plus certificates",
  },
  "/agent-dealers": {
    title: "Agent Dealers",
    description: "Kenya step 2 float pools. Only the dealer login can add float.",
  },
  "/dealers": {
    title: "Agent Dealers",
    description: "Kenya step 2 float pools. Only the dealer login can add float.",
  },
  "/settings": {
    title: "Settings",
    description: "Profile, HR record, password, MFA, and role shortcuts",
  },
  "/institutions": {
    title: "Institutions",
    description: "Customer financial institution directory and lifecycle",
  },
  "/institutions/onboard": {
    title: "Onboard financial institution",
    description: "KYC wizard for a customer bank, SACCO, or other financial institution",
  },
  "/institution": {
    title: "Institution profile",
    description: "FI Admin view of own KYC profile and API client request",
  },
  "/institutions/:institutionId": {
    title: "Institution management",
    description: "Engine settings: BSAS mode, maker-checker, billing fee",
  },
  "/institutions/:institutionId/onboard": {
    title: "Onboard financial institution",
    description: "Resume customer institution KYC",
  },
  "/users": {
    title: "Users",
    description: "Invite portal logins; manage profile, HR, and audit per user",
  },
  "/users/:userId": {
    title: "User management",
    description: "Admin profile, HR fields, access actions, and audit trail",
  },
  "/applications": {
    title: "Applications",
    description: "Customer-side book: cost, Murabaha, and which desk to open next",
  },
  "/applications/new": {
    title: "New Application",
    description: "Pick a customer, set cost and profit, then lock the Murabaha offer",
  },
  "/sedania": {
    title: "Sedania Financing",
    description: "AS SIDQ commodity Murabahah: SASC wakeel or Rasul, muqassah, CASA, or physical delivery",
  },
  "/malaysia": {
    title: "Malaysia Manual Bridge",
    description: "Submit BSAS trades off-platform, then paste e-certificates",
  },
  "/integrations": {
    title: "Integrations",
    description: "Configure M-Pesa, MNO, and institution profiles",
  },
  "/webhooks": {
    title: "Webhooks & Keys",
    description: "Manage callback URLs and API credentials",
  },
  "/origination": {
    title: "Origination",
    description: "FI Ops eight-step facility desk",
  },
  "/kenya": {
    title: "Kenya Ops Workbench",
    description: "Eight-step workbench: apply, buy float, possession, Murabaha, Wakala, sale, clear, pay",
  },
  "/repayments": {
    title: "Repayments",
    description: "Collect Murabaha installments and track overdue accounts",
  },
  "/shariah": {
    title: "Shariah Compliance",
    description: "Verify hash chain, possession seals, and export the audit ledger",
  },
  "/approvals": {
    title: "Approvals",
    description: "Maker-checker queue: Murabaha, liquidation, disbursement, and Mobile Lend",
  },
  "/mfa-enroll": {
    title: "Authenticator setup",
    description: "Privileged roles must enroll TOTP before using the portal",
  },
  "/billing": {
    title: "Billing & fees",
    description: "Platform usage charges and invoices for BTI Finance",
  },
  "/reconciliation": {
    title: "Reconciliation",
    description: "Settlement matching and exception management",
  },
  "/customers": {
    title: "Customers",
    description: "Kenya step 1: add customers, open applications, and share journey links",
  },
  "/transactions": {
    title: "Transactions",
    description: "Commodity legs, certificates, and settlement status",
  },
};

export function getRouteMeta(pathname: string, role?: string | null) {
  if (pathname === "/" && role && !TESTER_SHELL) {
    return { title: "Dashboard", description: getRoleProfile(role).navDescription };
  }
  if ((pathname.startsWith("/agent-dealers") || pathname.startsWith("/dealers")) && role === "agent_dealer") {
    return {
      title: "My float",
      description: "Add float to your pool. Kenya step 2 draws from it. You do not see the customer journey.",
    };
  }
  if (ROUTE_META[pathname]) return ROUTE_META[pathname];
  if (pathname.startsWith("/customer/") || pathname.startsWith("/journey/")) {
    return {
      title: "Customer Journey",
      description: "Live financing steps and downloadable certificates",
    };
  }
  if (pathname.startsWith("/customers/")) {
    return {
      title: "Customer Profile",
      description: "Customer record, applications, and journey links",
    };
  }
  if (pathname.startsWith("/users/") && pathname !== "/users") {
    return (
      ROUTE_META["/users/:userId"] || {
        title: "User management",
        description: "Admin profile, HR fields, access actions, and audit trail",
      }
    );
  }
  if (pathname === "/institutions/onboard" || pathname.endsWith("/onboard")) {
    return ROUTE_META["/institutions/onboard"];
  }
  if (pathname.startsWith("/institutions/") && pathname !== "/institutions") {
    return (
      ROUTE_META["/institutions/:institutionId"] || {
        title: "Institution management",
        description: "Engine settings: BSAS mode, maker-checker, billing fee",
      }
    );
  }
  if (pathname.startsWith("/applications/")) {
    return {
      title: "Application Detail",
      description: "Offer, contract, legs, and audit trail",
    };
  }
  if (pathname.startsWith("/transactions/")) {
    return {
      title: "Transaction Detail",
      description: "Leg execution and certificate confirmation",
    };
  }
  return {
    title: "Operations",
    description: "Monitor Tawarruq transactions and worker activity",
  };
}
