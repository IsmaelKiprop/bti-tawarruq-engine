import type { SessionUser } from "../api/client";

export type OpsRole =
  | "platform_admin"
  | "institution_admin"
  | "institution_ops"
  | "read_only"
  | "agent_dealer"
  | "shariah_officer";

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
    label: "Platform admin",
    scope: "platform",
    workspaceFallback: "All institutions",
    navDescription: "Full engine view across banks and SACCOs",
    showApiDocs: true,
    showWriteActions: true,
    showShariah: true,
    homePath: "/",
  },
  institution_admin: {
    label: "Institution admin",
    scope: "institution",
    workspaceFallback: "Your institution",
    navDescription: "Institution book, users, and ops desks",
    showApiDocs: false,
    showWriteActions: true,
    showShariah: true,
    homePath: "/",
  },
  institution_ops: {
    label: "Institution ops",
    scope: "institution",
    workspaceFallback: "Your institution",
    navDescription: "Run Kenya and Malaysia desks for your book",
    showApiDocs: false,
    showWriteActions: true,
    showShariah: false,
    homePath: "/",
  },
  read_only: {
    label: "Read only",
    scope: "institution",
    workspaceFallback: "Your institution",
    navDescription: "View journeys and audit without changing deals",
    showApiDocs: false,
    showWriteActions: false,
    showShariah: true,
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
  shariah_officer: {
    label: "Shariah officer",
    scope: "platform",
    workspaceFallback: "Shariah desk",
    navDescription: "Verify possession seals and the audit chain",
    showApiDocs: false,
    showWriteActions: false,
    showShariah: true,
    homePath: "/shariah",
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
  if (user.role === "platform_admin") return true;
  if (isDealerRole(user.role)) {
    return item.to === "/agent-dealers" || item.to === "/dealers";
  }
  if (item.excludeRoles?.includes(user.role as OpsRole)) return false;
  if (item.roles?.length && !item.roles.includes(user.role as OpsRole)) return false;
  if (item.permission && !user.permissions.includes(item.permission)) return false;
  return true;
}
