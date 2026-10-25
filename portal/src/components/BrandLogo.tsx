/** Operator brand mark / lockup. Default art is Buruuj; other brands render a text lockup. */

import { getDeploymentProfile, isDefaultBrand } from "../config/deployment";

export const BURUUJ_LOGO_SRC = "/brand/buruuj-logo.png";

type BrandLogoProps = {
  /** `lockup` = full logo; `mark` = compact crop for tight chrome */
  variant?: "lockup" | "mark";
  className?: string;
  alt?: string;
};

export function BrandLogo({
  variant = "lockup",
  className = "",
  alt,
}: BrandLogoProps) {
  const brand = getDeploymentProfile().brandName;
  const shownAlt = alt || brand;
  if (!isDefaultBrand()) {
    return (
      <span
        className={`brand-logo brand-logo--text brand-logo--${variant}${className ? ` ${className}` : ""}`}
      >
        {brand}
      </span>
    );
  }
  return (
    <img
      src={BURUUJ_LOGO_SRC}
      alt={shownAlt}
      className={`brand-logo brand-logo--${variant}${className ? ` ${className}` : ""}`}
      draggable={false}
    />
  );
}
