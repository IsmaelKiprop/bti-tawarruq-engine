/** Operator brand mark / lockup. Default art is Buruuj; other brands render a text lockup. */

import { getDeploymentProfile, isDefaultBrand } from "../config/deployment";

export const BURUUJ_LOGO_SRC = "/brand/buruuj-logo.png?v=2";
export const BURUUJ_LOGO_DARK_SRC = "/brand/buruuj-logo-dark.png?v=2";

type BrandLogoProps = {
  /** `lockup` = full logo; `mark` = compact crop for tight chrome */
  variant?: "lockup" | "mark";
  className?: string;
  alt?: string;
  /** Certificates stay on paper white. Portal chrome follows `data-theme`. */
  tone?: "auto" | "light" | "dark";
};

export function BrandLogo({
  variant = "lockup",
  className = "",
  alt,
  tone = "auto",
}: BrandLogoProps) {
  const brand = getDeploymentProfile().brandName;
  const shownAlt = alt || brand;
  const extra = className ? ` ${className}` : "";
  if (!isDefaultBrand()) {
    return (
      <span className={`brand-logo brand-logo--text brand-logo--${variant}${extra}`}>{brand}</span>
    );
  }
  if (tone === "light") {
    return (
      <img
        src={BURUUJ_LOGO_SRC}
        alt={shownAlt}
        className={`brand-logo brand-logo--${variant}${extra}`}
        draggable={false}
      />
    );
  }
  if (tone === "dark") {
    return (
      <img
        src={BURUUJ_LOGO_DARK_SRC}
        alt={shownAlt}
        className={`brand-logo brand-logo--${variant} brand-logo--on-dark${extra}`}
        draggable={false}
      />
    );
  }
  return (
    <span className={`brand-logo-swap brand-logo-swap--${variant}${extra}`}>
      <img
        src={BURUUJ_LOGO_SRC}
        alt={shownAlt}
        className={`brand-logo brand-logo--${variant} brand-logo--light`}
        draggable={false}
      />
      <img
        src={BURUUJ_LOGO_DARK_SRC}
        alt=""
        className={`brand-logo brand-logo--${variant} brand-logo--on-dark`}
        draggable={false}
      />
    </span>
  );
}
