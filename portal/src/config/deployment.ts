export type ProductModule = "kenya" | "malaysia" | "sedania" | "sacco" | "billing" | "mobile";
export type DeploymentMode = "managed" | "onprem";

export type DeploymentProfile = {
  mode: DeploymentMode;
  products: ProductModule[];
  brandName: string;
};

const ALL_PRODUCTS: ProductModule[] = ["kenya", "malaysia", "sedania", "sacco", "billing", "mobile"];

const DEFAULT_PROFILE: DeploymentProfile = {
  mode: "managed",
  products: ALL_PRODUCTS,
  brandName: "Buruuj Fintech",
};

let profile: DeploymentProfile = { ...DEFAULT_PROFILE, products: [...ALL_PRODUCTS] };

function asMode(value: unknown): DeploymentMode {
  return value === "onprem" || value === "on-prem" || value === "on_prem" ? "onprem" : "managed";
}

function asProducts(value: unknown): ProductModule[] {
  if (!Array.isArray(value)) return [...ALL_PRODUCTS];
  const found = value.filter((item): item is ProductModule => ALL_PRODUCTS.includes(item as ProductModule));
  return found.length ? found : [...ALL_PRODUCTS];
}

export function setDeploymentProfile(payload: {
  deployment_mode?: string;
  enabled_products?: string[];
  brand_name?: string;
  mode?: DeploymentMode;
  products?: ProductModule[];
  brandName?: string;
}) {
  profile = {
    mode: asMode(payload.mode || payload.deployment_mode),
    products: asProducts(payload.products || payload.enabled_products),
    brandName: (payload.brandName || payload.brand_name || profile.brandName || DEFAULT_PROFILE.brandName).trim()
      || DEFAULT_PROFILE.brandName,
  };
}

export function getDeploymentProfile(): DeploymentProfile {
  return profile;
}

export function isOnprem(): boolean {
  return profile.mode === "onprem";
}

export function productEnabled(name: ProductModule): boolean {
  return profile.products.includes(name);
}

export function isDefaultBrand(): boolean {
  const name = profile.brandName.toLowerCase();
  return name === "buruuj fintech" || name === "buruuj";
}
