import { useEffect } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { getRouteMeta, NAV_SECTIONS } from "../config/navigation";
import { canSeeNavItem, getHomePath, isDealerRole, TESTER_SHELL } from "../config/roles";
import { useSidebar } from "../hooks/useSidebar";
import { useTheme } from "../hooks/useTheme";
import { useUiAudit } from "../hooks/useUiAudit";
import {
  IconChevronLeft,
  IconChevronRight,
  IconClose,
  IconLogout,
  IconMenu,
  IconMoon,
  IconSettings,
  IconSun,
} from "./icons";
import { BrandLogo } from "./BrandLogo";

function isNavActive(pathname: string, to: string, end?: boolean) {
  if (end) return pathname === to;
  if (to === "/applications") {
    return pathname === "/applications" || (pathname.startsWith("/applications/") && pathname !== "/applications/new");
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { authEnabled, user, logout, engineHealth, refreshHealth } = useAuth();
  const { collapsed, mobileOpen, isMobile, toggleCollapsed, closeMobile, toggleMobile } = useSidebar();
  useUiAudit();

  useEffect(() => {
    if (engineHealth.checkedAt != null) return;
    void refreshHealth();
  }, [engineHealth.checkedAt, refreshHealth]);

  useEffect(() => {
    if (!user) return;
    const id = window.setInterval(() => {
      void refreshHealth();
    }, 60_000);
    return () => window.clearInterval(id);
  }, [user, refreshHealth]);

  const meta = getRouteMeta(location.pathname, user?.role);

  function canSee(item: (typeof NAV_SECTIONS)[number]["items"][number]) {
    if (item.hidden) return false;
    return canSeeNavItem(item, user, authEnabled);
  }

  const navSections = NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter(canSee),
  })).filter((section) => section.items.length > 0);

  const shellClass = [
    "app-shell",
    collapsed && !isMobile ? "sidebar-collapsed" : "",
    mobileOpen ? "sidebar-mobile-open" : "",
  ]
    .filter(Boolean)
    .join(" ");

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className={shellClass}>
      {mobileOpen && (
        <button type="button" className="sidebar-backdrop" aria-label="Close navigation" onClick={closeMobile} />
      )}

      <aside className="sidebar" aria-label="Main navigation">
        <div className="sidebar-inner">
          <div className="sidebar-brand">
            <BrandLogo variant="lockup" className="sidebar-logo-full" />
            <BrandLogo variant="mark" className="sidebar-logo-mark" alt="" />
            {isMobile && (
              <button
                type="button"
                className="icon-btn sidebar-close"
                onClick={closeMobile}
                aria-label="Close navigation"
              >
                <IconClose size={16} />
              </button>
            )}
          </div>

          <nav className="sidebar-nav">
            {navSections.map((section) => (
              <div className="nav-section" key={section.id}>
                <span className="nav-section-label">{section.label}</span>
                {section.items.map((item) => {
                  const active = isNavActive(location.pathname, item.to, item.end);
                  const ItemIcon = item.Icon;
                  const label =
                    isDealerRole(user?.role) && item.to === "/agent-dealers" ? "My float" : item.label;
                  const hint =
                    isDealerRole(user?.role) && item.to === "/agent-dealers"
                      ? "Add float. Kenya step 2 draws from this pool."
                      : item.hint;
                  return (
                    <Link
                      key={item.to}
                      to={item.to}
                      className={active ? "nav-link active" : "nav-link"}
                      title={
                        collapsed && !isMobile
                          ? `${label}${hint ? `: ${hint}` : ""}`
                          : hint
                      }
                      onClick={closeMobile}
                    >
                      <span className="nav-icon">
                        <ItemIcon />
                      </span>
                      <span className="nav-label">
                        {label}
                        {hint ? <small>{hint}</small> : null}
                      </span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>

          <div className="sidebar-footer">
            <div className="sidebar-footer-row sidebar-docs-row">
              <span className="sidebar-footer-spacer" />
              <HealthBadge
                online={engineHealth.online}
                compact={collapsed && !isMobile}
                onRefresh={() => void refreshHealth()}
              />
            </div>
            <div className="sidebar-footer-row">
              {authEnabled && user ? (
                <button
                  type="button"
                  className="sidebar-doc-link sidebar-logout"
                  onClick={handleLogout}
                  title={collapsed && !isMobile ? "Log out" : undefined}
                >
                  <IconLogout size={16} />
                  <span>Log out</span>
                </button>
              ) : (
                <span className="sidebar-footer-spacer" />
              )}
              {!isMobile ? (
                <button
                  type="button"
                  className="icon-btn sidebar-collapse-btn"
                  onClick={toggleCollapsed}
                  aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                  title={collapsed ? "Expand" : "Collapse"}
                >
                  {collapsed ? <IconChevronRight size={16} /> : <IconChevronLeft size={16} />}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </aside>

      <div className="main-column">
        <header className="navbar">
          <div className="navbar-start">
            {isMobile && (
              <button type="button" className="icon-btn" onClick={toggleMobile} aria-label="Open navigation">
                <IconMenu />
              </button>
            )}
            <div className="navbar-titles">
              <h1>{meta.title}</h1>
              <p>{meta.description}</p>
            </div>
          </div>

          <div className="navbar-actions">
            <button
              type="button"
              className="icon-btn"
              onClick={toggleTheme}
              aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
            >
              {theme === "light" ? <IconMoon /> : <IconSun />}
            </button>
            {user ? (
              <Link to="/settings" className="icon-btn" aria-label="Settings" title="Settings">
                <IconSettings />
              </Link>
            ) : authEnabled ? (
              <Link to="/login" className="btn btn-secondary btn-sm">
                Log in
              </Link>
            ) : null}
          </div>
        </header>

        <main className="content">
          {isDealerRole(user?.role) &&
          !TESTER_SHELL &&
          !location.pathname.startsWith("/agent-dealers") &&
          !location.pathname.startsWith("/dealers") ? (
            <Navigate to={getHomePath(user?.role)} replace />
          ) : (
            <Outlet />
          )}
        </main>
      </div>
    </div>
  );
}

function HealthBadge({
  online,
  compact = false,
  onRefresh,
}: {
  online: boolean | null;
  compact?: boolean;
  onRefresh?: () => void;
}) {
  const label = online === null ? "Checking" : online ? "Engine live" : "Engine offline";

  return (
    <button
      type="button"
      className={`health-badge sidebar-health${online === false ? " is-offline" : ""}${compact ? " is-compact" : ""}`}
      title={`${label} — click to refresh`}
      aria-label={label}
      onClick={onRefresh}
    >
      <span className={`health-dot${online === false ? " offline" : online === null ? " checking" : ""}`} />
      <span className="health-label">{label}</span>
    </button>
  );
}
