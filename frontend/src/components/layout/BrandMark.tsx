import { useId } from "react";

/** The Crypto AI Platform mark: a faceted token on an electric-blue → violet gradient. Pure SVG, no image request. */
export function BrandMark({ className = "h-9 w-9" }: { className?: string }) {
  const id = useId();
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-a`} x1="6" y1="4" x2="42" y2="44" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5b8cff" />
          <stop offset="0.55" stopColor="#7c4dff" />
          <stop offset="1" stopColor="#22d3ee" />
        </linearGradient>
        <linearGradient id={`${id}-b`} x1="0" y1="0" x2="0" y2="1">
          <stop stopColor="#fff" stopOpacity="0.55" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d="M24 3 42 13.5v21L24 45 6 34.5v-21L24 3Z" fill={`url(#${id}-a)`} />
      <path d="M24 3 42 13.5 24 24 6 13.5 24 3Z" fill={`url(#${id}-b)`} opacity="0.7" />
      <path d="M24 24v21M24 24 6 13.5M24 24 42 13.5" stroke="#fff" strokeOpacity="0.35" strokeWidth="1.2" fill="none" />
      <circle cx="24" cy="24" r="4.2" fill="#fff" />
    </svg>
  );
}
