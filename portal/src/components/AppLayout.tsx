import { useEffect, useState } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, fetchHealth } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { getRouteMeta, NAV_SECTIONS } from "../config/navigation";
import { canSeeNavItem, getHomePath, getRoleProfile, isDealerRole } from "../config/roles";
import { useSidebar } from "../hooks/useSidebar";
import { useTheme } from "../hooks/useTheme";
import {
  IconChevronLeft,
  IconChevronRight,
  IconClose,
  IconExternal,
  IconLogout,
  IconMenu,
  IconMoon,
  IconSun,
} from "./icons";
import { BrandLogo } from "./BrandLogo";
import { PageGuide } from "./ProcessGuide";
import "./layout.css";

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
  const { authEnabled, user, logout } = useAuth();
  const { collapsed, mobileOpen, isMobile, toggleCollapsed, closeMobile, toggleMobile } = useSidebar();
  const [institutionLabel, setInstitutionLabel] = useState(user?.institution_name || "");

  const profile = getRoleProfile(user?.role);
  const meta = getRouteMeta(location.pathname, user?.role);

  useEffect(() => {
    if (user?.institution_name) {
      setInstitutionLabel(user.institution_name);
      return;
    }
    if (!user?.institution_id) {
      setInstitutionLabel(getRoleProfile(user?.role).workspaceFallback);
      return;
    }
    let active = true;
    api
      .listInstitutions()
      .then((list) => {
        if (!active) return;
        const match = list.find((item) => item.id === user.institution_id);
        setInstitutionLabel(match?.name || "");
      })
      .catch(() => {
        if (active) setInstitutionLabel("");
      });
    return () => {
      active = false;
    };
  }, [user?.institution_id, user?.institution_name, user?.role]);

  function canSee(item: (typeof NAV_SECTIONS)[number]["items"][number]) {
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
            {!isMobile && (
              <button
                type="button"
                className="sidebar-toggle"
                onClick={toggleCollapsed}
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                {collapsed ? <IconChevronRight size={16} /> : <IconChevronLeft size={16} />}
                <span className="sidebar-toggle-label">{collapsed ? "Expand" : "Collapse"}</span>
              </button>
            )}
            {profile.showApiDocs ? (
              <a
                className="sidebar-doc-link"
                href="http://127.0.0.1:8000/docs"
                target="_blank"
                rel="noreferrer"
                title={collapsed && !isMobile ? "API docs" : undefined}
              >
                <IconExternal size={16} />
                <span>API docs</span>
              </a>
            ) : null}
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
            ) : null}
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
            <span className="auth-session" title="Portal session">
              <span className="health-badge auth-identity">
                {user ? (
                  <span className="auth-session-meta">
                    <strong>{user.full_name}</strong>
                    <span>
                      {institutionLabel || profile.workspaceFallback}
                      {" · "}
                      {profile.label}
                    </span>
                  </span>
                ) : authEnabled ? (
                  "Signed out"
                ) : (
                  "Auth off"
                )}
              </span>
              {user ? (
                <Link to="/change-password" className="btn btn-secondary btn-sm logout-btn change-password-btn">
                  Change password
                </Link>
              ) : authEnabled ? (
                <Link to="/login" className="btn btn-secondary btn-sm logout-btn">
                  Log in
                </Link>
              ) : null}
              {authEnabled && user ? (
                <button type="button" className="btn btn-primary btn-sm logout-btn" onClick={handleLogout}>
                  Log out
                </button>
              ) : null}
            </span>
            <button
              type="button"
              className="icon-btn"
              onClick={toggleTheme}
              aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
            >
              {theme === "light" ? <IconMoon /> : <IconSun />}
            </button>
            <HealthBadge />
          </div>
        </header>

        <main className="content">
          <PageGuide />
          {isDealerRole(user?.role) &&
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

function HealthBadge() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((data) => setOnline(data.status === "ok" || data.status === "degraded"))
      .catch(() => setOnline(false));
  }, []);

  const label = online === null ? "Checking" : online ? "Engine live" : "Engine offline";

  return (
    <span className={`health-badge${online === false ? " is-offline" : ""}`} title="Engine status">
      <span className={`health-dot${online === false ? " offline" : ""}`} />
      {label}
    </span>
  );
}
