import { useEffect, useState } from "react";

const DESKTOP = 400;
const MOBILE = 280;

/** Chart height that fits small screens: shorter below the `sm` breakpoint (640px). Safe where matchMedia is missing. */
export function useChartHeight(): number {
  const [height, setHeight] = useState(DESKTOP);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const query = window.matchMedia("(max-width: 639px)");
    const apply = () => setHeight(query.matches ? MOBILE : DESKTOP);
    apply();
    query.addEventListener?.("change", apply);
    return () => query.removeEventListener?.("change", apply);
  }, []);

  return height;
}
