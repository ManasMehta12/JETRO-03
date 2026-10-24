import type { ComponentId } from '../simulation';

export function PartArtwork({ id }: { id: ComponentId }) {
  switch (id) {
    case 'base':
      return (
        <svg viewBox="0 0 100 60" width="100%" height="100%" fill="none">
          <defs>
            <linearGradient id="basePlateGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#3d6b59" />
              <stop offset="50%" stopColor="#295544" />
              <stop offset="100%" stopColor="#1a3d30" />
            </linearGradient>
            <linearGradient id="basePlateTop" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#437562" />
              <stop offset="100%" stopColor="#2c5a48" />
            </linearGradient>
          </defs>
          {/* Isometric base plate */}
          <path d="M15 32 L50 14 L85 32 L50 50 Z" fill="url(#basePlateTop)" stroke="#224a3a" strokeWidth="1" />
          <path d="M15 32 L50 50 L50 56 L15 38 Z" fill="#204637" />
          <path d="M85 32 L50 50 L50 56 L85 38 Z" fill="#173529" />
          {/* Holes */}
          <ellipse cx="28" cy="30" rx="3.5" ry="2" fill="#152e24" />
          <ellipse cx="72" cy="30" rx="3.5" ry="2" fill="#152e24" />
          <ellipse cx="50" cy="21" rx="3.5" ry="2" fill="#152e24" />
          <ellipse cx="50" cy="41" rx="3.5" ry="2" fill="#152e24" />
        </svg>
      );
    case 'housing':
      return (
        <svg viewBox="0 0 100 65" width="100%" height="100%" fill="none">
          <defs>
            <linearGradient id="housingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#437764" />
              <stop offset="50%" stopColor="#2a5746" />
              <stop offset="100%" stopColor="#1c3e32" />
            </linearGradient>
          </defs>
          {/* Base flange */}
          <path d="M20 46 L80 46 L85 52 L15 52 Z" fill="#244b3c" stroke="#1d3f32" strokeWidth="1" />
          {/* Housing main arch */}
          <path d="M28 46 C28 26 72 26 72 46 Z" fill="url(#housingGrad)" stroke="#1d3f32" strokeWidth="1.2" />
          {/* Split seam line */}
          <path d="M27 34 L73 34" stroke="#173529" strokeWidth="1.5" strokeDasharray="3 2" />
          {/* Central bearing bore */}
          <circle cx="50" cy="38" r="13" fill="#18362a" stroke="#3b6957" strokeWidth="1.5" />
          <circle cx="50" cy="38" r="8" fill="#10251d" />
          {/* Top grease nipple / bolt */}
          <rect x="47" y="19" width="6" height="5" rx="1.5" fill="#c49a45" />
          {/* Mounting holes */}
          <ellipse cx="24" cy="49" rx="3" ry="1.5" fill="#12271e" />
          <ellipse cx="76" cy="49" rx="3" ry="1.5" fill="#12271e" />
        </svg>
      );
    case 'shaft':
      return (
        <svg viewBox="0 0 100 55" width="100%" height="100%" fill="none">
          <defs>
            <linearGradient id="shaftSteel" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#f0f3f2" />
              <stop offset="25%" stopColor="#d2dbd8" />
              <stop offset="50%" stopColor="#ffffff" />
              <stop offset="75%" stopColor="#9fb0ac" />
              <stop offset="100%" stopColor="#758884" />
            </linearGradient>
          </defs>
          {/* Shaft cylinder */}
          <g transform="rotate(-12 50 28)">
            <rect x="10" y="22" width="80" height="12" rx="6" fill="url(#shaftSteel)" stroke="#829591" strokeWidth="1" />
            {/* Chamfered right edge */}
            <ellipse cx="89" cy="28" rx="2" ry="5.5" fill="#cbd6d3" stroke="#829591" strokeWidth="0.8" />
            {/* Keyway slot */}
            <rect x="62" y="24" width="16" height="3" rx="1" fill="#586b67" />
          </g>
        </svg>
      );
    case 'bearing':
      return (
        <svg viewBox="0 0 100 65" width="100%" height="100%" fill="none">
          <defs>
            <linearGradient id="ringSteel" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f5f7f6" />
              <stop offset="50%" stopColor="#b4c0bd" />
              <stop offset="100%" stopColor="#788a86" />
            </linearGradient>
            <radialGradient id="ballShine" cx="35%" cy="35%" r="65%">
              <stop offset="0%" stopColor="#ffffff" />
              <stop offset="60%" stopColor="#cbd5d2" />
              <stop offset="100%" stopColor="#6e7e7b" />
            </radialGradient>
          </defs>
          {/* Isometric outer race */}
          <ellipse cx="50" cy="33" rx="28" ry="24" fill="url(#ringSteel)" stroke="#687875" strokeWidth="1.5" />
          <ellipse cx="50" cy="33" rx="23" ry="19" fill="#93a39f" />
          {/* Brass cage channel */}
          <ellipse cx="50" cy="33" rx="20" ry="16" fill="#c4a566" />
          {/* Balls */}
          <circle cx="50" cy="17" r="4.2" fill="url(#ballShine)" />
          <circle cx="67" cy="24" r="4.2" fill="url(#ballShine)" />
          <circle cx="70" cy="36" r="4.2" fill="url(#ballShine)" />
          <circle cx="61" cy="46" r="4.2" fill="url(#ballShine)" />
          <circle cx="39" cy="46" r="4.2" fill="url(#ballShine)" />
          <circle cx="30" cy="36" r="4.2" fill="url(#ballShine)" />
          <circle cx="33" cy="24" r="4.2" fill="url(#ballShine)" />
          {/* Inner race */}
          <ellipse cx="50" cy="33" rx="13" ry="10" fill="url(#ringSteel)" stroke="#5f706d" strokeWidth="1.2" />
          <ellipse cx="50" cy="33" rx="8" ry="6" fill="#2d3c38" />
        </svg>
      );
  }
}

export function ToolArtwork({ id }: { id: string }) {
  switch (id) {
    case 'alignment-jig':
      return (
        <svg viewBox="0 0 60 60" width="100%" height="100%" fill="none">
          <circle cx="30" cy="30" r="22" stroke="#8ca398" strokeWidth="2" strokeDasharray="3 3" />
          <circle cx="30" cy="30" r="14" stroke="#2e6853" strokeWidth="2.5" />
          <circle cx="30" cy="30" r="4" fill="#2e6853" />
          <line x1="30" y1="4" x2="30" y2="56" stroke="#2e6853" strokeWidth="1.8" />
          <line x1="4" y1="30" x2="56" y2="30" stroke="#2e6853" strokeWidth="1.8" />
        </svg>
      );
    case 'bearing-sleeve':
      return (
        <svg viewBox="0 0 60 60" width="100%" height="100%" fill="none">
          <defs>
            <linearGradient id="sleeveGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#7a8d88" />
              <stop offset="35%" stopColor="#e1e8e5" />
              <stop offset="70%" stopColor="#9fb0ac" />
              <stop offset="100%" stopColor="#697a76" />
            </linearGradient>
          </defs>
          <path d="M18 20 L42 20 L42 46 L18 46 Z" fill="url(#sleeveGrad)" stroke="#596a66" strokeWidth="1.5" />
          <ellipse cx="30" cy="20" rx="12" ry="5" fill="#cad5d2" stroke="#596a66" strokeWidth="1.2" />
          <ellipse cx="30" cy="20" rx="6" ry="2.5" fill="#3a4845" />
          <ellipse cx="30" cy="46" rx="12" ry="5" fill="#8b9d99" />
        </svg>
      );
    case 'hex-key':
      return (
        <svg viewBox="0 0 60 60" width="100%" height="100%" fill="none">
          <defs>
            <linearGradient id="hexSteel" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#bcc9c5" />
              <stop offset="50%" stopColor="#f0f4f3" />
              <stop offset="100%" stopColor="#6e7f7b" />
            </linearGradient>
          </defs>
          {/* L shape hex wrench */}
          <path
            d="M20 12 L20 40 Q20 48 28 48 L46 48 L46 42 L27 42 Q25 42 25 39 L25 12 Z"
            fill="url(#hexSteel)"
            stroke="#596a66"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
      );
    case 'handwheel':
      return (
        <svg viewBox="0 0 60 60" width="100%" height="100%" fill="none">
          <circle cx="30" cy="30" r="22" stroke="#2b5344" strokeWidth="5" />
          <circle cx="30" cy="30" r="8" fill="#2b5344" />
          <circle cx="30" cy="30" r="4" fill="#a4b5ad" />
          {/* Spokes */}
          <line x1="30" y1="11" x2="30" y2="49" stroke="#2b5344" strokeWidth="3" />
          <line x1="11" y1="30" x2="49" y2="30" stroke="#2b5344" strokeWidth="3" />
          {/* Turning knob */}
          <circle cx="43" cy="20" r="4" fill="#d49b42" stroke="#946a25" strokeWidth="1" />
        </svg>
      );
    default:
      return null;
  }
}
