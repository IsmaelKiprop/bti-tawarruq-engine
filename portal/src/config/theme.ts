/**
 * BTI / Buruuj platform brand theme (single source of truth).
 * Keep `styles/tokens.css` in sync with the values below.
 *
 * Primary palette
 * - BTI Gold: #D4A017
 * - Deep Charcoal / Black: #1C1917
 * - Pure White: #FFFFFF
 *
 * Accent & executive tones
 * - Metallic Gold: #D4AF37
 * - Secondary Gold: #C5A059
 * - Primary Mustard: #C2A44D
 *
 * Typeface: Book Antiqua
 */
export const brandPalette = {
  btiGold: "#D4A017",
  charcoal: "#1C1917",
  white: "#FFFFFF",
  metallicGold: "#D4AF37",
  secondaryGold: "#C5A059",
  mustard: "#C2A44D",
} as const;

export const theme = {
  radius: "5px",
  fontFamily: '"Book Antiqua", "Palatino Linotype", Palatino, "Times New Roman", serif',
  brand: {
    gold: brandPalette.btiGold,
    charcoal: brandPalette.charcoal,
    white: brandPalette.white,
    metallicGold: brandPalette.metallicGold,
    secondaryGold: brandPalette.secondaryGold,
    mustard: brandPalette.mustard,
    /** @deprecated use charcoal — kept for older call sites */
    navy: brandPalette.charcoal,
    navyDeep: brandPalette.charcoal,
    goldBright: brandPalette.metallicGold,
    goldSoft: brandPalette.secondaryGold,
  },
  light: {
    background: brandPalette.white,
    surface: brandPalette.white,
    surfaceElevated: "#FAF8F4",
    foreground: brandPalette.charcoal,
    muted: "#6B6560",
    border: "#E5DFD3",
    primary: brandPalette.btiGold,
    primaryForeground: brandPalette.charcoal,
    accent: brandPalette.metallicGold,
    accentForeground: brandPalette.charcoal,
    secondary: "#F3EEE4",
    secondaryForeground: brandPalette.charcoal,
    destructive: "#B42318",
    success: "#1F6B4A",
    warning: brandPalette.mustard,
    info: brandPalette.secondaryGold,
    focus: brandPalette.metallicGold,
    sidebar: brandPalette.white,
    navbar: brandPalette.white,
    scrollbarTrack: "#F3EEE4",
    scrollbarThumb: brandPalette.secondaryGold,
  },
  dark: {
    background: brandPalette.charcoal,
    surface: "#26211E",
    surfaceElevated: "#2F2A26",
    foreground: brandPalette.white,
    muted: "#A39E97",
    border: "#3D3732",
    primary: brandPalette.btiGold,
    primaryForeground: brandPalette.charcoal,
    accent: brandPalette.metallicGold,
    accentForeground: brandPalette.charcoal,
    secondary: "#2F2A26",
    secondaryForeground: brandPalette.white,
    destructive: "#F97066",
    success: "#3DCF8E",
    warning: brandPalette.mustard,
    info: brandPalette.secondaryGold,
    focus: brandPalette.metallicGold,
    sidebar: "#26211E",
    navbar: "#26211E",
    scrollbarTrack: brandPalette.charcoal,
    scrollbarThumb: brandPalette.mustard,
  },
} as const;

export type ThemeMode = "light" | "dark";
