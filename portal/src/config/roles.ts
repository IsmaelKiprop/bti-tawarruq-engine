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

/** Display order for invite and catalogue. Values stay API codes; labels are what the UI shows. */
export const PORTAL_ROLE_OPTIONS: { value: OpsRole; label: string; btiOnly?: boolean }[] = [
  { value: "platform_admin", label: "Super Admin", btiOnly: true },
  { value: "bti_ops", label: "BTI Ops", btiOnly: true },
  { value: "bti_finance", label: "BTI Finance", btiOnly: true },
  { value: "institution_admin", label: "FI Admin" },
  { value: "institution_ops", label: "FI Operations" },
  { value: "fi_approver", label: "FI Approver" },
  { value: "shariah_officer", label: "Shariah / Audit" },
  { value: "reconciler", label: "Reconciliation" },
  { value: "read_only", label: "Read only" },
  { value: "agent_dealer", label: "Agent dealer" },
];

/** Who may invite whom. Read only and Agent dealer stay off the invite form. */
export const INVITE_TARGETS_BY_CREATOR: Record<string, OpsRole[]> = {
  platform_admin: [
    "platform_admin",
    "bti_ops",
    "bti_finance",
    "institution_admin",
    "institution_ops",
    "fi_approver",
    "shariah_officer",
    "reconciler",
  ],
  institution_admin: [
    "institution_admin",
    "institution_ops",
    "fi_approver",
    "shariah_officer",
    "reconciler",
  ],
};

const PLATFORM_SCOPED_INVITE_ROLES: OpsRole[] = ["platform_admin", "bti_ops", "bti_finance"];

export function roleLabel(role?: string | null): string {
  if (!role) return "Operator";
  const named = PORTAL_ROLE_OPTIONS.find((opt) => opt.value === role);
  if (named) return named.label;
  return getRoleProfile(role).label;
}

export function inviteRoleOptions(creatorRole?: string | null) {
  const allowed = INVITE_TARGETS_BY_CREATOR[creatorRole || ""];
  const values = new Set(
    allowed
      ? allowed
      : [
          ...INVITE_TARGETS_BY_CREATOR.platform_admin,
          ...INVITE_TARGETS_BY_CREATOR.institution_admin,
        ],
  );
  return PORTAL_ROLE_OPTIONS.filter((opt) => values.has(opt.value)).map((opt) => ({
    value: opt.value,
    label: opt.label,
  }));
}

export function defaultInviteRole(creatorRole?: string | null): OpsRole {
  if (creatorRole === "platform_admin") return "institution_admin";
  return "institution_ops";
}

export function inviteNeedsInstitution(role: string): boolean {
  return !PLATFORM_SCOPED_INVITE_ROLES.includes(role as OpsRole);
}

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
    label: "Super Admin",
    scope: "platform",
    workspaceFallback: "All institutions",
    navDescription: "Platform configuration and tenant lifecycle",
    showApiDocs: true,
    showWriteActions: false,
    showShariah: true,
    homePath: "/institutions",
  },
  bti_ops: {
    label: "BTI Ops",
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
    label: "FI Admin",
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
