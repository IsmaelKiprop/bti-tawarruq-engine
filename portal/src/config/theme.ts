/**
 * Buruuj Fintech brand theme.
 * Navy + gold sampled from the official logo lockup.
 * Portal CSS variables in styles/tokens.css must stay in sync with this file.
 */
export const theme = {
  radius: "5px",
  fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
  brand: {
    navy: "#0B1F3A",
    navyDeep: "#071526",
    gold: "#C9A227",
    goldBright: "#D4AF37",
    goldSoft: "#E8C96A",
  },
  light: {
    background: "#F3F5F8",
    surface: "#FFFFFF",
    surfaceElevated: "#FFFFFF",
    foreground: "#0B1F3A",
    muted: "#5C6B7A",
    border: "#D8DEE6",
    primary: "#0B1F3A",
    primaryForeground: "#FFFFFF",
    accent: "#C9A227",
    accentForeground: "#0B1F3A",
    secondary: "#EEF2F6",
    secondaryForeground: "#1E3348",
    destructive: "#B42318",
    success: "#1F6B4A",
    warning: "#B45309",
    info: "#1D4E8C",
    focus: "#C9A227",
    sidebar: "#FFFFFF",
    navbar: "#FFFFFF",
    scrollbarTrack: "#F3F5F8",
    scrollbarThumb: "#C5CDD8",
  },
  dark: {
    background: "#070D16",
    surface: "#0F1824",
    surfaceElevated: "#162233",
    foreground: "#F2F4F7",
    muted: "#9AA8B8",
    border: "#243247",
    primary: "#D4AF37",
    primaryForeground: "#0B1F3A",
    accent: "#E8C96A",
    accentForeground: "#0B1F3A",
    secondary: "#162233",
    secondaryForeground: "#E5EAF0",
    destructive: "#F97066",
    success: "#3DCF8E",
    warning: "#F5B84C",
    info: "#6BA3E0",
    focus: "#E8C96A",
    sidebar: "#0F1824",
    navbar: "#0F1824",
    scrollbarTrack: "#070D16",
    scrollbarThumb: "#334155",
  },
} as const;

export type ThemeMode = "light" | "dark";
