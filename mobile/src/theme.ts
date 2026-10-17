/** Buruuj Lend design tokens. Solid colors only. Default radius 5px. */
export const colors = {
  navy: "#0B1F3A",
  navySoft: "#152A45",
  navyDeep: "#071526",
  gold: "#C9A227",
  goldBright: "#D4AF37",
  goldMuted: "#F7F1DE",
  goldLine: "#E8D9A8",
  background: "#EEF1F5",
  surface: "#FFFFFF",
  surfaceMuted: "#F6F8FA",
  surfaceInk: "#0B1F3A",
  foreground: "#0B1F3A",
  muted: "#5A6878",
  mutedSoft: "#8B97A5",
  border: "#D5DCE5",
  borderStrong: "#B8C2CF",
  primary: "#0B1F3A",
  primaryForeground: "#FFFFFF",
  accent: "#C9A227",
  accentForeground: "#0B1F3A",
  success: "#1F6B4A",
  successSoft: "#E7F3ED",
  danger: "#B42318",
  dangerSoft: "#FCECEC",
  warning: "#B45309",
  warningSoft: "#FFF4E5",
  overlay: "rgba(11, 31, 58, 0.45)",
} as const;

export const space = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
  huge: 40,
} as const;

/** Default product radius is 5px. Pill only for status tags. */
export const radius = {
  default: 5,
  sm: 5,
  md: 5,
  lg: 5,
  pill: 999,
} as const;

export const type = {
  display: { fontSize: 28, fontWeight: "800" as const, letterSpacing: -0.6, lineHeight: 34 },
  title: { fontSize: 22, fontWeight: "800" as const, letterSpacing: -0.35, lineHeight: 28 },
  headline: { fontSize: 16, fontWeight: "700" as const, letterSpacing: -0.15, lineHeight: 22 },
  body: { fontSize: 15, fontWeight: "500" as const, lineHeight: 22 },
  label: { fontSize: 13, fontWeight: "600" as const, letterSpacing: 0.1 },
  caption: { fontSize: 12, fontWeight: "600" as const, letterSpacing: 0.2, lineHeight: 16 },
  overline: {
    fontSize: 11,
    fontWeight: "700" as const,
    letterSpacing: 0.8,
    textTransform: "uppercase" as const,
  },
  amount: { fontSize: 36, fontWeight: "800" as const, letterSpacing: -0.8, lineHeight: 42 },
};

export const shadow = {
  soft: {
    shadowColor: "#0B1F3A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  card: {
    shadowColor: "#0B1F3A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 3,
  },
  float: {
    shadowColor: "#0B1F3A",
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 10,
  },
} as const;
