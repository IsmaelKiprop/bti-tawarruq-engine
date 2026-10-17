export type BsasModeId = "mock" | "manual_bridge" | "live";

export interface BsasModeProfile {
  id: BsasModeId;
  label: string;
  when: string;
}

export const BSAS_MODES: Record<BsasModeId, BsasModeProfile> = {
  mock: {
    id: "mock",
    label: "Mock",
    when: "Local testing only. The engine pretends the Malaysia commodity desk confirmed the trade.",
  },
  manual_bridge: {
    id: "manual_bridge",
    label: "Manual bridge",
    when: "Ops paste a Suq Al-Sila' e-certificate from the Bursa desk. Use this until live API keys exist.",
  },
  live: {
    id: "live",
    label: "Live API",
    when: "The engine calls Bursa Suq Al-Sila' or Eiger when credentials are set on Integrations.",
  },
};

export const BSAS_MODE_ORDER: BsasModeId[] = ["manual_bridge", "mock", "live"];

export function getBsasMode(mode?: string | null): BsasModeProfile {
  if (mode && mode in BSAS_MODES) return BSAS_MODES[mode as BsasModeId];
  return BSAS_MODES.manual_bridge;
}
