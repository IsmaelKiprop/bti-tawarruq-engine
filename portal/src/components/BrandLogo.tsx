/** Buruuj Fintech brand mark / lockup. */

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
  alt = "Buruuj Fintech",
}: BrandLogoProps) {
  return (
    <img
      src={BURUUJ_LOGO_SRC}
      alt={alt}
      className={`brand-logo brand-logo--${variant}${className ? ` ${className}` : ""}`}
      draggable={false}
    />
  );
}
