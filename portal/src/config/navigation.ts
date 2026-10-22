import type { ComponentType } from "react";
import { getRoleProfile, type OpsRole } from "./roles";
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
  roles?: OpsRole[];
  excludeRoles?: OpsRole[];
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
      { to: "/", label: "Dashboard", Icon: IconDashboard, end: true, hint: "Whole process at a glance" },
      {
        to: "/ops",
        label: "Ops Monitor",
        Icon: IconMonitor,
        hint: "Engine telemetry for your role",
        permission: "view_metrics",
      },
      { to: "/customer", label: "Customer Journey", Icon: IconApplications, hint: "Eight-step tracker and certificates" },
      {
        to: "/billing",
        label: "Billing",
        Icon: IconMonitor,
        hint: "Fees and invoices (BTI Finance)",
        permission: "manage_billing",
      },
      {
        to: "/reconciliation",
        label: "Reconciliation",
        Icon: IconTransactions,
        hint: "Settlement matching",
        permission: "reconcile",
      },
    ],
  },
  {
    id: "setup",
    label: "Setup & access",
    items: [
      { to: "/institutions", label: "Institutions", Icon: IconInstitutions, hint: "Onboard a bank or SACCO", permission: "manage_institutions" },
      { to: "/users", label: "Users", Icon: IconUsers, hint: "Roles and portal logins", permission: "manage_credentials" },
      { to: "/integrations", label: "Integrations", Icon: IconIntegrations, hint: "Partner credentials", permission: "manage_integrations" },
      { to: "/webhooks", label: "Webhooks & Keys", Icon: IconWebhooks, hint: "System-to-system", permission: "manage_credentials" },
    ],
  },
  {
    id: "kenya",
    label: "Kenya track: float / airtime",
    items: [
      { to: "/kenya", label: "Kenya Ops", Icon: IconKenya, hint: "Run the eight steps in order", permission: "write_ops" },
      { to: "/agent-dealers", label: "Agent Dealers", Icon: IconKenya, hint: "Step 2 float pool. Dealer adds float." },
      { to: "/customers", label: "Customers", Icon: IconUsers, hint: "Step 1 records and journey links", permission: "write_ops" },
      {
        to: "/mobile-lend",
        label: "Mobile Lend",
        Icon: IconUsers,
        hint: "Invite (ops) and approve (approver)",
        roles: ["bti_ops", "institution_admin", "institution_ops", "fi_approver"],
      },
      { to: "/repayments", label: "Repayments", Icon: IconRepayments, hint: "After disbursement", permission: "write_ops" },
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
      },
    ],
  },
  {
    id: "records",
    label: "Records & evidence",
    items: [
      { to: "/applications/new", label: "New Application", Icon: IconNewApplication, hint: "Start a journey", permission: "write_ops" },
      { to: "/applications", label: "Applications", Icon: IconApplications, hint: "Customer side" },
      { to: "/transactions", label: "Transactions", Icon: IconTransactions, hint: "Commodity side" },
      { to: "/shariah", label: "Shariah Audit", Icon: IconShariah, hint: "Verify the chain", permission: "view_shariah" },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((section) => section.items);

export const ROUTE_META: Record<string, { title: string; description: string }> = {
  "/": {
    title: "Dashboard",
    description: "System health, integrations, and quick actions",
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
  "/institutions": {
    title: "Institutions",
    description: "Onboard banks and SACCOs onto the Tawarruq engine",
  },
  "/users": {
    title: "Users",
    description: "Create ops logins and share temporary passwords",
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
  if (pathname === "/" && role) {
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
