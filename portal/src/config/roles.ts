import type { SessionUser } from "../api/client";

/** Stable role values — aligned with BTI_Tawarruq_Users_ver_001.docx */
export type OpsRole =
  | "platform_admin"
  | "bti_ops"
  | "bti_finance"
  | "institution_admin"
  | "institution_ops"
  | "fi_approver"
  | "shariah_officer"
  | "reconciler"
  | "read_only"
  | "agent_dealer";

/** Roles selectable when creating a portal login (not api_client). */
export const PORTAL_ROLE_OPTIONS: { value: OpsRole; label: string; btiOnly?: boolean }[] = [
  { value: "platform_admin", label: "BTI Platform Super Admin", btiOnly: true },
  { value: "bti_ops", label: "BTI Tawarruq Operations", btiOnly: true },
  { value: "bti_finance", label: "BTI Finance / Billing", btiOnly: true },
  { value: "institution_admin", label: "FI Administrator" },
  { value: "institution_ops", label: "FI Operations Officer" },
  { value: "fi_approver", label: "FI Approver (maker-checker)" },
  { value: "shariah_officer", label: "Shariah / Audit (read-only)" },
  { value: "reconciler", label: "Reconciliation Officer" },
  { value: "read_only", label: "Read only" },
  { value: "agent_dealer", label: "Agent dealer (Kenya float desk)" },
];

type NavVisibility = {
  to: string;
  permission?: string;
  roles?: OpsRole[];
  excludeRoles?: OpsRole[];
};

export type RoleProfile = {
  label: string;
  scope: "platform" | "institution" | "dealer";
  workspaceFallback: string;
  navDescription: string;
  showApiDocs: boolean;
  showWriteActions: boolean;
  showShariah: boolean;
  homePath: string;
};

const ROLE_PROFILES: Record<string, RoleProfile> = {
  platform_admin: {
    label: "BTI Super Admin",
    scope: "platform",
    workspaceFallback: "All institutions",
    navDescription: "Platform configuration and tenant lifecycle",
    showApiDocs: true,
    showWriteActions: false,
    showShariah: true,
    homePath: "/institutions",
  },
  bti_ops: {
    label: "BTI Operations",
    scope: "platform",
    workspaceFallback: "All institutions (ops)",
    navDescription: "Cross-tenant workflow monitoring and exceptions",
    showApiDocs: true,
    showWriteActions: true,
    showShariah: true,
    homePath: "/ops",
  },
  bti_finance: {
    label: "BTI Finance",
    scope: "platform",
    workspaceFallback: "Billing",
    navDescription: "Usage fees, invoicing, and receivables",
    showApiDocs: false,
    showWriteActions: false,
    showShariah: false,
    homePath: "/billing",
  },
  institution_admin: {
    label: "FI Administrator",
    scope: "institution",
    workspaceFallback: "Your institution",
    navDescription: "Institution users, config, and ops desks",
    showApiDocs: false,
    showWriteActions: true,
    showShariah: true,
    homePath: "/",
  },
  institution_ops: {
    label: "FI Operations",
    scope: "institution",
    workspaceFallback: "Your institution",
    navDescription: "Initiate and monitor Tawarruq journeys",
    showApiDocs: false,
    showWriteActions: true,
    showShariah: false,
    homePath: "/kenya",
  },
  fi_approver: {
    label: "FI Approver",
    scope: "institution",
    workspaceFallback: "Your institution",
    navDescription: "Approve or reject within delegated authority",
    showApiDocs: false,
    showWriteActions: false,
    showShariah: false,
    homePath: "/approvals",
  },
  shariah_officer: {
    label: "Shariah / Audit",
    scope: "institution",
    workspaceFallback: "Audit desk",
    navDescription: "Read-only evidence, certificates, and hash chain",
    showApiDocs: false,
    showWriteActions: false,
    showShariah: true,
    homePath: "/shariah",
  },
  reconciler: {
    label: "Reconciliation",
    scope: "institution",
    workspaceFallback: "Settlement",
    navDescription: "Match confirmations to settlement records",
    showApiDocs: false,
    showWriteActions: false,
    showShariah: false,
    homePath: "/reconciliation",
  },
  read_only: {
    label: "Read only",
    scope: "institution",
    workspaceFallback: "Your institution",
    navDescription: "View journeys without changing deals",
    showApiDocs: false,
    showWriteActions: false,
    showShariah: false,
    homePath: "/",
  },
  agent_dealer: {
    label: "Agent dealer",
    scope: "dealer",
    workspaceFallback: "Your float pool",
    navDescription: "Add float for Kenya step 2. No customer journey.",
    showApiDocs: false,
    showWriteActions: false,
    showShariah: false,
    homePath: "/agent-dealers",
  },
};

const DEFAULT_PROFILE: RoleProfile = {
  label: "Operator",
  scope: "institution",
  workspaceFallback: "Workspace",
  navDescription: "Tawarruq operations",
  showApiDocs: true,
  showWriteActions: true,
  showShariah: true,
  homePath: "/",
};

export function getRoleProfile(role?: string | null): RoleProfile {
  if (!role) return DEFAULT_PROFILE;
  return ROLE_PROFILES[role] || { ...DEFAULT_PROFILE, label: role };
}

export function getHomePath(role?: string | null): string {
  return getRoleProfile(role).homePath;
}

export function isDealerRole(role?: string | null): boolean {
  return role === "agent_dealer";
}

export function canSeeNavItem(
  item: NavVisibility,
  user: SessionUser | null | undefined,
  authEnabled: boolean,
): boolean {
  if (!authEnabled || !user) return true;
  if (isDealerRole(user.role)) {
    return item.to === "/agent-dealers" || item.to === "/dealers";
  }
  if (item.excludeRoles?.includes(user.role as OpsRole)) return false;
  if (item.roles?.length && !item.roles.includes(user.role as OpsRole)) return false;
  if (item.permission && !user.permissions.includes(item.permission)) return false;
  return true;
}
