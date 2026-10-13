import { useId } from "react";

/**
 * Original, abstract illustrations for the authentication pages. Pure SVG + CSS animation (transform/opacity only),
 * decorative (aria-hidden) and free of any numbers or prices — they depict mood, not market data.
 * Motion is gentle and is switched off entirely by the global prefers-reduced-motion rule.
 */

const FILL_BOX = { transformBox: "fill-box" as const, transformOrigin: "center" };

function Particles({ points }: { points: [number, number, number][] }) {
  return (
    <>
      {points.map(([x, y, delay], index) => (
        <circle key={index} cx={x} cy={y} r={index % 3 === 0 ? 2.6 : 1.8} fill="#9ec1ff" className="animate-glow" style={{ animationDelay: `${delay}s` }} />
      ))}
    </>
  );
}

/** LOGIN: a luminous floating token inside orbital rings, with a rising chart and light trails. */
export function LoginArt({ className = "" }: { className?: string }) {
  const id = useId();
  return (
    <svg viewBox="0 0 640 640" className={className} aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id={`${id}-halo`} cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#5b8cff" stopOpacity="0.55" />
          <stop offset="0.6" stopColor="#7c4dff" stopOpacity="0.18" />
          <stop offset="1" stopColor="#7c4dff" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-coin`} x1="0.15" y1="0.1" x2="0.85" y2="0.95">
          <stop offset="0" stopColor="#8fb2ff" />
          <stop offset="0.5" stopColor="#4f6dff" />
          <stop offset="1" stopColor="#7c3aed" />
        </linearGradient>
        <linearGradient id={`${id}-ring`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#22d3ee" stopOpacity="0" />
          <stop offset="0.5" stopColor="#5b8cff" stopOpacity="0.9" />
          <stop offset="1" stopColor="#a855f7" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={`${id}-line`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#22d3ee" />
          <stop offset="1" stopColor="#10b981" />
        </linearGradient>
        <linearGradient id={`${id}-area`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#10b981" stopOpacity="0.35" />
          <stop offset="1" stopColor="#10b981" stopOpacity="0" />
        </linearGradient>
      </defs>

      <circle cx="320" cy="300" r="270" fill={`url(#${id}-halo)`} className="animate-glow" />

      {/* orbital rings */}
      <g style={FILL_BOX} className="animate-orbit-spin">
        <ellipse cx="320" cy="300" rx="250" ry="92" fill="none" stroke={`url(#${id}-ring)`} strokeWidth="1.6" transform="rotate(-18 320 300)" />
        <circle cx="552" cy="352" r="6" fill="#22d3ee" />
      </g>
      <g style={FILL_BOX} className="animate-orbit-spin-rev">
        <ellipse cx="320" cy="300" rx="210" ry="210" fill="none" stroke="#5b8cff" strokeOpacity="0.22" strokeDasharray="2 10" strokeWidth="2" />
        <ellipse cx="320" cy="300" rx="285" ry="120" fill="none" stroke={`url(#${id}-ring)`} strokeWidth="1" transform="rotate(26 320 300)" />
        <circle cx="96" cy="262" r="5" fill="#a855f7" />
      </g>

      {/* the token */}
      <g className="animate-float" style={FILL_BOX}>
        <circle cx="320" cy="300" r="118" fill={`url(#${id}-coin)`} />
        <circle cx="320" cy="300" r="118" fill="none" stroke="#fff" strokeOpacity="0.35" strokeWidth="2" />
        <circle cx="320" cy="300" r="96" fill="none" stroke="#fff" strokeOpacity="0.22" strokeWidth="1.5" />
        <path d="M320 300 m-118 0 a118 118 0 0 1 236 0" fill="#fff" fillOpacity="0.1" />
        {/* stylised "B" with the two vertical ticks */}
        <g fill="none" stroke="#fff" strokeWidth="14" strokeLinecap="round" strokeLinejoin="round">
          <path d="M292 248h46c24 0 36 14 36 30s-12 28-34 28h-48z" />
          <path d="M292 306h56c26 0 40 15 40 32s-14 32-40 32h-56z" />
          <path d="M292 248v122" />
          <path d="M312 226v22M340 226v22M312 370v22M340 370v22" strokeWidth="9" />
        </g>
      </g>

      {/* light trails */}
      <g fill="none" strokeLinecap="round">
        <path d="M30 470c120-40 190 20 290-18s190-130 290-170" stroke="#5b8cff" strokeOpacity="0.5" strokeWidth="2" className="animate-glow" />
        <path d="M30 500c130-30 200 40 300 0s180-110 280-140" stroke="#a855f7" strokeOpacity="0.4" strokeWidth="1.5" className="animate-glow" style={{ animationDelay: "1.2s" }} />
      </g>

      {/* chart */}
      <path d="M40 560 120 520 190 538 260 480 330 500 410 440 480 458 560 392 610 372V620H40Z" fill={`url(#${id}-area)`} />
      <path d="M40 560 120 520 190 538 260 480 330 500 410 440 480 458 560 392 610 372" fill="none" stroke={`url(#${id}-line)`} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1} className="animate-draw-line" />
      <circle cx="610" cy="372" r="5.5" fill="#10b981" />
      <circle cx="610" cy="372" r="12" fill="#10b981" fillOpacity="0.25" className="animate-glow" />

      {/* network */}
      <g stroke="#9ec1ff" strokeOpacity="0.28" strokeWidth="1">
        <path d="M84 120 170 78 260 130M170 78 250 40M520 90 584 150 530 214M584 150 620 100" fill="none" />
      </g>
      <Particles points={[[84, 120, 0], [170, 78, 0.6], [260, 130, 1.1], [250, 40, 1.7], [520, 90, 0.3], [584, 150, 0.9], [530, 214, 1.5], [620, 100, 2], [60, 330, 0.4], [600, 300, 1.3], [140, 430, 1], [500, 520, 0.2]]} />
    </svg>
  );
}

/** SIGNUP: layered glass panels (a chart, an allocation ring, an AI spark) around a growing network. */
export function SignupArt({ className = "" }: { className?: string }) {
  const id = useId();
  return (
    <svg viewBox="0 0 640 640" className={className} aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id={`${id}-halo`} cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#7c4dff" stopOpacity="0.5" />
          <stop offset="0.65" stopColor="#3b6dff" stopOpacity="0.14" />
          <stop offset="1" stopColor="#3b6dff" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-panel`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.14" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0.04" />
        </linearGradient>
        <linearGradient id={`${id}-up`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#34d399" />
          <stop offset="1" stopColor="#059669" />
        </linearGradient>
        <linearGradient id={`${id}-down`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fb7185" />
          <stop offset="1" stopColor="#e11d48" />
        </linearGradient>
        <linearGradient id={`${id}-ai`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#22d3ee" />
          <stop offset="1" stopColor="#a855f7" />
        </linearGradient>
      </defs>

      <circle cx="330" cy="320" r="280" fill={`url(#${id}-halo)`} className="animate-glow" />
      <g style={FILL_BOX} className="animate-orbit-spin">
        <circle cx="320" cy="320" r="250" fill="none" stroke="#5b8cff" strokeOpacity="0.25" strokeDasharray="3 12" strokeWidth="2" />
        <circle cx="570" cy="320" r="6" fill="#22d3ee" />
      </g>
      <g style={FILL_BOX} className="animate-orbit-spin-rev">
        <circle cx="320" cy="320" r="190" fill="none" stroke="#a855f7" strokeOpacity="0.22" strokeWidth="1.5" />
        <circle cx="130" cy="320" r="5" fill="#a855f7" />
      </g>

      {/* back panel: candlesticks */}
      <g className="animate-float-slow" style={FILL_BOX}>
        <rect x="70" y="120" width="300" height="190" rx="22" fill={`url(#${id}-panel)`} stroke="#fff" strokeOpacity="0.16" />
        <g strokeLinecap="round">
          {[
            [112, 262, 214, true], [146, 250, 190, true], [180, 232, 204, false], [214, 222, 176, true],
            [248, 200, 168, true], [282, 214, 184, false], [316, 190, 150, true],
          ].map(([x, y1, y2, up], index) => (
            <g key={index}>
              <line x1={x as number} x2={x as number} y1={(y2 as number) - 14} y2={(y1 as number) + 12} stroke={up ? "#34d399" : "#fb7185"} strokeWidth="2" />
              <rect x={(x as number) - 8} y={y2 as number} width="16" height={(y1 as number) - (y2 as number)} rx="3" fill={`url(#${id}-${up ? "up" : "down"})`} />
            </g>
          ))}
        </g>
        <rect x="96" y="144" width="86" height="8" rx="4" fill="#fff" fillOpacity="0.28" />
        <rect x="96" y="160" width="52" height="6" rx="3" fill="#fff" fillOpacity="0.14" />
      </g>

      {/* front panel: allocation ring */}
      <g className="animate-float" style={{ ...FILL_BOX, animationDelay: "-2s" }}>
        <rect x="300" y="250" width="270" height="200" rx="22" fill={`url(#${id}-panel)`} stroke="#fff" strokeOpacity="0.2" />
        <g transform="translate(398 350)" fill="none" strokeWidth="16" strokeLinecap="round">
          <circle r="48" stroke="#fff" strokeOpacity="0.08" />
          <circle r="48" stroke="#5b8cff" strokeDasharray="120 302" transform="rotate(-90)" />
          <circle r="48" stroke="#a855f7" strokeDasharray="70 302" strokeDashoffset="-128" transform="rotate(-90)" />
          <circle r="48" stroke="#22d3ee" strokeDasharray="42 302" strokeDashoffset="-206" transform="rotate(-90)" />
        </g>
        <rect x="468" y="318" width="78" height="8" rx="4" fill="#fff" fillOpacity="0.28" />
        <rect x="468" y="336" width="56" height="6" rx="3" fill="#fff" fillOpacity="0.14" />
        <rect x="468" y="352" width="66" height="6" rx="3" fill="#fff" fillOpacity="0.14" />
        <rect x="468" y="368" width="44" height="6" rx="3" fill="#fff" fillOpacity="0.14" />
      </g>

      {/* AI spark */}
      <g className="animate-float-slow" style={{ ...FILL_BOX, animationDelay: "-4s" }}>
        <rect x="120" y="400" width="190" height="96" rx="20" fill={`url(#${id}-panel)`} stroke="#a855f7" strokeOpacity="0.5" />
        <path d="M168 428l7 18 18 7-18 7-7 18-7-18-18-7 18-7z" fill={`url(#${id}-ai)`} />
        <rect x="206" y="430" width="78" height="8" rx="4" fill="#fff" fillOpacity="0.3" />
        <rect x="206" y="448" width="58" height="6" rx="3" fill="#fff" fillOpacity="0.15" />
        <rect x="206" y="464" width="70" height="6" rx="3" fill="#fff" fillOpacity="0.15" />
      </g>

      <g stroke="#9ec1ff" strokeOpacity="0.25">
        <path d="M60 80 140 50 220 84M520 70 588 118 560 190M40 560 110 596 200 566M470 560 544 592 596 540" fill="none" />
      </g>
      <Particles points={[[60, 80, 0], [140, 50, 0.7], [220, 84, 1.2], [520, 70, 0.4], [588, 118, 1], [560, 190, 1.6], [40, 560, 0.3], [110, 596, 0.9], [200, 566, 1.5], [470, 560, 0.5], [544, 592, 1.1], [596, 540, 1.8]]} />
    </svg>
  );
}
