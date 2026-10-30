import type { SessionUser } from "../api/client";
import { getDeploymentProfile, isOnprem, productEnabled, type ProductModule } from "./deployment";

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
    "shariah_officer",
    "reconciler",
  ],
  bti_ops: ["institution_admin"],
  institution_admin: [
    "institution_admin",
    "institution_ops",
    "fi_approver",
    "shariah_officer",
    "reconciler",
  ],
};

const PLATFORM_SCOPED_INVITE_ROLES: OpsRole[] = ["platform_admin", "bti_ops", "bti_finance"];

/** Invited on the BTI book (no institution) or the FI book (one tenant). */
const DUAL_SCOPE_INVITE_ROLES: OpsRole[] = ["shariah_officer", "reconciler"];

export function isDualScopeInviteRole(role: string): boolean {
  return DUAL_SCOPE_INVITE_ROLES.includes(role as OpsRole);
}

const ONPREM_ROLE_LABELS: Partial<Record<OpsRole, string>> = {
  platform_admin: "Site Admin",
  bti_ops: "Site Ops",
  bti_finance: "Site Finance",
  institution_admin: "Admin",
  institution_ops: "Operations",
  fi_approver: "Approver",
};

export function roleLabel(role?: string | null): string {
  if (!role) return "Operator";
  if (isOnprem() && ONPREM_ROLE_LABELS[role as OpsRole]) {
    return ONPREM_ROLE_LABELS[role as OpsRole] as string;
  }
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
    label: roleLabel(opt.value),
  }));
}

export function defaultInviteRole(creatorRole?: string | null): OpsRole {
  if (creatorRole === "platform_admin" || creatorRole === "bti_ops") return "institution_admin";
  return "institution_ops";
}

export function inviteNeedsInstitution(role: string, book?: "bti" | "fi"): boolean {
  if (isDualScopeInviteRole(role)) return book !== "bti";
  return !PLATFORM_SCOPED_INVITE_ROLES.includes(role as OpsRole);
}

/** Super Admin and BTI Ops pick the Active FI when inviting FI Admin. */
export function canAssignInviteInstitution(creatorRole?: string | null): boolean {
  return creatorRole === "platform_admin" || creatorRole === "bti_ops";
}

/** BTI book: operator staff and any login with no institution. FI book: tenant-bound desks. */
export function isBtiManagedUser(role?: string | null, institutionId?: string | null): boolean {
  if (PLATFORM_SCOPED_INVITE_ROLES.includes(role as OpsRole)) return true;
  return !institutionId;
}

export function inviteRoleOptionsForBook(creatorRole: string | null | undefined, book: "bti" | "fi") {
  return inviteRoleOptions(creatorRole).filter((opt) => {
    if (isDualScopeInviteRole(opt.value)) return true;
    return book === "bti"
      ? PLATFORM_SCOPED_INVITE_ROLES.includes(opt.value)
      : !PLATFORM_SCOPED_INVITE_ROLES.includes(opt.value);
  });
}

type NavVisibility = {
  to: string;
  permission?: string;
  anyPermissions?: string[];
  roles?: OpsRole[];
  excludeRoles?: OpsRole[];
  product?: ProductModule;
  hideOnOnprem?: boolean;
  provider?: "sedania" | "bursa";
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
    homePath: "/",
  },
  bti_ops: {
    label: "BTI Ops",
    scope: "platform",
    workspaceFallback: "All institutions (ops)",
    navDescription: "Cross-tenant workflow monitoring and exceptions",
    showApiDocs: true,
    showWriteActions: true,
    showShariah: true,
    homePath: "/kenya",
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
    homePath: "/origination",
  },
  fi_approver: {
    label: "FI Approver",
    scope: "institution",
    workspaceFallback: "Your institution",
    navDescription: "Approve or reject within delegated authority",
    showApiDocs: false,
    showWriteActions: false,
    showShariah: false,
    homePath: "/origination",
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
  const base = !role ? DEFAULT_PROFILE : ROLE_PROFILES[role] || { ...DEFAULT_PROFILE, label: role };
  if (!isOnprem()) return base;
  const brand = getDeploymentProfile().brandName;
  const label = ONPREM_ROLE_LABELS[role as OpsRole] || base.label;
  return {
    ...base,
    label,
    workspaceFallback: role === "platform_admin" || role === "bti_ops" || role === "bti_finance" ? brand : base.workspaceFallback,
    homePath: role === "platform_admin" ? "/" : base.homePath,
  };
}

/** Who may open Audit. Keep in sync with the `/audit` nav item. */
export const AUDIT_ROLES: OpsRole[] = [
  "platform_admin",
  "bti_ops",
  "bti_finance",
  "institution_admin",
  "shariah_officer",
  "reconciler",
];

/** Temporary tester shell: hide product desks until BTI Admin signs off. */
export const TESTER_SHELL = true;

const TESTER_VISIBLE_PATHS = [
  "/",
  "/ops",
  "/institutions",
  "/institutions/onboard",
  "/institution",
  "/users",
  "/audit",
  "/settings",
  "/origination",
  "/shariah",
  "/malaysia",
  "/sedania",
] as const;

export function isTesterVisiblePath(to: string): boolean {
  const path = to.split("?")[0] || "/";
  return TESTER_VISIBLE_PATHS.some((allowed) => path === allowed || (allowed !== "/" && path.startsWith(`${allowed}/`)));
}

export function getHomePath(role?: string | null): string {
  const path = getRoleProfile(role).homePath;
  if (TESTER_SHELL && !isTesterVisiblePath(path)) return "/";
  return path;
}

export function isDealerRole(role?: string | null): boolean {
  return role === "agent_dealer";
}

export function canSeeNavItem(
  item: NavVisibility,
  user: SessionUser | null | undefined,
  authEnabled: boolean,
): boolean {
  if (TESTER_SHELL && !isTesterVisiblePath(item.to)) return false;
  if (item.hideOnOnprem && isOnprem()) return false;
  if (item.product && !productEnabled(item.product)) return false;
  if (!authEnabled || !user) return true;
  if (isDealerRole(user.role)) {
    if (TESTER_SHELL) return item.to === "/" || item.to === "/settings";
    return item.to === "/agent-dealers" || item.to === "/dealers";
  }
  if (item.provider && user.role !== "platform_admin" && (user.active_provider || "sedania") !== item.provider) {
    return false;
  }
  if (item.excludeRoles?.includes(user.role as OpsRole)) return false;
  if (item.roles?.length && !item.roles.includes(user.role as OpsRole)) return false;
  if (item.anyPermissions?.length) {
    if (!item.anyPermissions.some((permission) => user.permissions.includes(permission))) return false;
  } else if (item.permission && !user.permissions.includes(item.permission)) {
    return false;
  }
  return true;
}
