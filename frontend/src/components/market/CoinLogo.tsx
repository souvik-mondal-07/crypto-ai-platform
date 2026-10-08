import { useState } from "react";
import { Coins } from "lucide-react";

interface CoinLogoProps {
  src: string | null;
  alt: string;
  size?: number;
}

/** Coin logo image with a graceful icon fallback if the URL is missing or fails to load — never a broken-image icon. */
export function CoinLogo({ src, alt, size = 24 }: CoinLogoProps) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div
        className="flex flex-shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500"
        style={{ width: size, height: size }}
      >
        <Coins style={{ width: size * 0.6, height: size * 0.6 }} aria-hidden="true" />
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      className="flex-shrink-0 rounded-full"
      onError={() => setFailed(true)}
    />
  );
}
