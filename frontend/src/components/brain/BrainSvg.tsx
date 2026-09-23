import { useId, useMemo, useState } from 'react';
import type { BrainRegionMetrics } from '../../constants/brainMetrics';

interface Props {
  regions: BrainRegionMetrics[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

interface NodeDef {
  id: string;
  x: number;
  y: number;
  r: number;
}

interface RegionGeometry {
  id: string;
  path: string;
  labelX: number;
  labelY: number;
  nodes: NodeDef[];
}

const REGION_GEOMETRY: RegionGeometry[] = [
  {
    id: 'technique',
    path: 'M138 36C108 34 72 48 54 78C40 104 38 132 48 156C62 148 88 140 108 128C122 118 132 98 136 76C138 62 138 48 138 36Z',
    labelX: 88,
    labelY: 92,
    nodes: [
      { id: 't1', x: 78, y: 72, r: 3.2 },
      { id: 't2', x: 102, y: 58, r: 2.6 },
      { id: 't3', x: 64, y: 104, r: 2.8 },
      { id: 't4', x: 96, y: 98, r: 2.4 },
      { id: 't5', x: 118, y: 82, r: 2.2 },
    ],
  },
  {
    id: 'identity',
    path: 'M142 36C172 34 208 48 226 78C240 104 242 132 232 156C218 148 192 140 172 128C158 118 148 98 144 76C142 62 142 48 142 36Z',
    labelX: 192,
    labelY: 92,
    nodes: [
      { id: 'i1', x: 202, y: 72, r: 3.2 },
      { id: 'i2', x: 178, y: 58, r: 2.6 },
      { id: 'i3', x: 216, y: 104, r: 2.8 },
      { id: 'i4', x: 184, y: 98, r: 2.4 },
      { id: 'i5', x: 162, y: 82, r: 2.2 },
    ],
  },
  {
    id: 'needs_discovery',
    path: 'M48 158C36 176 32 204 40 228C48 248 66 260 86 266C96 248 104 224 108 200C110 182 104 164 92 154C78 146 62 150 48 158Z',
    labelX: 72,
    labelY: 208,
    nodes: [
      { id: 'd1', x: 62, y: 188, r: 3 },
      { id: 'd2', x: 84, y: 172, r: 2.5 },
      { id: 'd3', x: 70, y: 218, r: 2.7 },
      { id: 'd4', x: 94, y: 204, r: 2.3 },
    ],
  },
  {
    id: 'signal',
    path: 'M232 158C244 176 248 204 240 228C232 248 214 260 194 266C184 248 176 224 172 200C170 182 176 164 188 154C202 146 218 150 232 158Z',
    labelX: 208,
    labelY: 208,
    nodes: [
      { id: 's1', x: 218, y: 188, r: 3 },
      { id: 's2', x: 196, y: 172, r: 2.5 },
      { id: 's3', x: 210, y: 218, r: 2.7 },
      { id: 's4', x: 186, y: 204, r: 2.3 },
    ],
  },
  {
    id: 'objection_handling',
    path: 'M86 268C98 278 118 286 138 288C138 274 132 258 122 246C110 230 96 222 82 228C76 240 78 254 86 268Z',
    labelX: 108,
    labelY: 262,
    nodes: [
      { id: 'o1', x: 104, y: 248, r: 2.8 },
      { id: 'o2', x: 122, y: 266, r: 2.4 },
      { id: 'o3', x: 96, y: 268, r: 2.2 },
    ],
  },
  {
    id: 'closing',
    path: 'M194 268C182 278 162 286 142 288C142 274 148 258 158 246C170 230 184 222 198 228C204 240 202 254 194 268Z',
    labelX: 172,
    labelY: 262,
    nodes: [
      { id: 'c1', x: 176, y: 248, r: 2.8 },
      { id: 'c2', x: 158, y: 266, r: 2.4 },
      { id: 'c3', x: 184, y: 268, r: 2.2 },
    ],
  },
];

const CROSS_LINKS: Array<[string, string, string, string]> = [
  // [regionA, nodeA, regionB, nodeB]
  ['technique', 't4', 'needs_discovery', 'd2'],
  ['identity', 'i4', 'signal', 's2'],
  ['needs_discovery', 'd4', 'objection_handling', 'o1'],
  ['signal', 's4', 'closing', 'c1'],
  ['technique', 't5', 'identity', 'i5'],
  ['objection_handling', 'o2', 'closing', 'c2'],
];

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function regionFill(fill: number, active: boolean): string {
  if (fill <= 0) return active ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.03)';
  const alpha = lerp(0.08, 0.22, fill) + (active ? 0.08 : 0);
  return `rgba(255,255,255,${alpha.toFixed(3)})`;
}

function nodeOpacity(fill: number, active: boolean): number {
  if (fill <= 0) return active ? 0.35 : 0.15;
  return lerp(0.45, 1, fill) * (active ? 1 : 0.85);
}

export function BrainSvg({ regions, selectedId, onSelect }: Props) {
  const reactId = useId();
  const gradientId = `neural-glow-${reactId.replace(/:/g, '')}`;
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const regionMap = useMemo(
    () => new Map(regions.map((r) => [r.id, r])),
    [regions],
  );

  const activeId = hoveredId || selectedId;
  const activeRegion = activeId ? regionMap.get(activeId) : null;

  const nodeLookup = useMemo(() => {
    const map = new Map<string, { x: number; y: number; regionId: string }>();
    for (const geo of REGION_GEOMETRY) {
      for (const n of geo.nodes) {
        map.set(`${geo.id}:${n.id}`, { x: n.x, y: n.y, regionId: geo.id });
      }
    }
    return map;
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent, id: string) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(id);
    }
  };

  return (
    <div className="relative w-full flex flex-col items-center">
      <svg
        viewBox="0 0 280 320"
        className="w-full max-w-[240px] h-auto select-none"
        role="img"
        aria-label="Interactive knowledge map of agent learning regions"
      >
        <defs>
          <radialGradient id={gradientId} cx="50%" cy="42%" r="55%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.1)" />
            <stop offset="55%" stopColor="rgba(255,255,255,0.03)" />
            <stop offset="100%" stopColor="rgba(13,13,13,0)" />
          </radialGradient>
          <filter id={`${gradientId}-soft`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Ambient glow */}
        <ellipse cx="140" cy="150" rx="118" ry="130" fill={`url(#${gradientId})`} />

        {/* Outer silhouette */}
        <path
          d="M140 34C96 34 58 54 44 96C32 132 36 168 52 198C66 226 92 248 118 262C128 268 136 274 140 286C144 274 152 268 162 262C188 248 214 226 228 198C244 168 248 132 236 96C222 54 184 34 140 34Z"
          fill="rgba(255,255,255,0.02)"
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="1"
        />

        {/* Faint midline */}
        <line
          x1="140"
          y1="42"
          x2="140"
          y2="278"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="1"
          strokeDasharray="2 4"
        />

        {/* Cross-region connections */}
        {CROSS_LINKS.map(([ra, na, rb, nb]) => {
          const a = nodeLookup.get(`${ra}:${na}`);
          const b = nodeLookup.get(`${rb}:${nb}`);
          if (!a || !b) return null;
          const linked =
            activeId === ra || activeId === rb || (!activeId && (regionMap.get(ra)?.fill || 0) > 0);
          const fillA = regionMap.get(ra)?.fill || 0;
          const fillB = regionMap.get(rb)?.fill || 0;
          const strength = Math.max(fillA, fillB);
          if (strength <= 0 && !linked) return null;
          return (
            <line
              key={`${ra}-${na}-${rb}-${nb}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={linked ? 'rgba(255,255,255,0.45)' : 'rgba(255,255,255,0.12)'}
              strokeWidth={linked ? 1.2 : 0.7}
              className="neural-link"
            />
          );
        })}

        {/* Regions */}
        {REGION_GEOMETRY.map((geo) => {
          const metrics = regionMap.get(geo.id);
          const fill = metrics?.fill || 0;
          const isActive = activeId === geo.id;
          const isSelected = selectedId === geo.id;

          // Intra-region links
          const links: Array<[NodeDef, NodeDef]> = [];
          for (let i = 0; i < geo.nodes.length - 1; i++) {
            links.push([geo.nodes[i], geo.nodes[i + 1]]);
            if (i + 2 < geo.nodes.length) links.push([geo.nodes[i], geo.nodes[i + 2]]);
          }

          return (
            <g key={geo.id}>
              {links.map(([a, b], idx) => (
                <line
                  key={`${geo.id}-l-${idx}`}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={
                    isActive
                      ? 'rgba(255,255,255,0.5)'
                      : fill > 0
                        ? 'rgba(255,255,255,0.18)'
                        : 'rgba(255,255,255,0.06)'
                  }
                  strokeWidth={isActive ? 1.1 : 0.7}
                  className="neural-link"
                />
              ))}

              <path
                d={geo.path}
                fill={regionFill(fill, isActive)}
                stroke={
                  isSelected
                    ? 'rgba(255,255,255,0.9)'
                    : isActive
                      ? 'rgba(255,255,255,0.65)'
                      : 'rgba(255,255,255,0.14)'
                }
                strokeWidth={isSelected || isActive ? 1.6 : 1}
                className="cursor-pointer transition-[fill,stroke] duration-300 outline-none"
                role="button"
                tabIndex={0}
                aria-label={`${metrics?.label || geo.id}: ${metrics?.patterns || 0} patterns, ${metrics?.maturityLabel || 'Empty'}`}
                aria-pressed={isSelected}
                onMouseEnter={() => setHoveredId(geo.id)}
                onMouseLeave={() => setHoveredId(null)}
                onFocus={() => setHoveredId(geo.id)}
                onBlur={() => setHoveredId(null)}
                onClick={() => onSelect(geo.id)}
                onKeyDown={(e) => handleKeyDown(e, geo.id)}
              />

              {geo.nodes.map((node, idx) => {
                const visible = fill > 0 || isActive;
                const count = Math.max(1, Math.round((metrics?.patterns || 0) + (metrics?.documents || 0)));
                const show = idx < Math.min(geo.nodes.length, Math.max(2, Math.ceil(count / 2)));
                if (!visible && !show) return null;
                return (
                  <circle
                    key={node.id}
                    cx={node.x}
                    cy={node.y}
                    r={node.r * (isActive ? 1.25 : 1)}
                    fill={isActive ? '#ffffff' : fill > 0 ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.25)'}
                    opacity={nodeOpacity(fill, isActive)}
                    className={fill > 0 ? 'neural-node' : undefined}
                    style={{ pointerEvents: 'none' }}
                    filter={isActive ? `url(#${gradientId}-soft)` : undefined}
                  />
                );
              })}

              <text
                x={geo.labelX}
                y={geo.labelY}
                textAnchor="middle"
                className="pointer-events-none"
                fill={isActive ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.38)'}
                fontSize="8.5"
                fontWeight="500"
                letterSpacing="0.08em"
              >
                {metrics?.shortLabel || geo.id.slice(0, 4).toUpperCase()}
              </text>
            </g>
          );
        })}

        {/* Stem */}
        <path
          d="M132 286C130 298 126 308 120 316M148 286C150 298 154 308 160 316"
          stroke="rgba(255,255,255,0.14)"
          strokeWidth="1.4"
          fill="none"
          strokeLinecap="round"
        />
      </svg>

      {/* Tooltip */}
      <div
        className={`mt-3 w-full max-w-[220px] rounded-xl border px-3 py-2.5 transition-all duration-200 ${
          activeRegion
            ? 'border-white/20 bg-white/8 opacity-100'
            : 'border-transparent bg-transparent opacity-0'
        }`}
        aria-live="polite"
      >
        {activeRegion && (
          <>
            <p className="text-[13px] font-medium text-white/95">{activeRegion.label}</p>
            <p className="text-[11px] text-white/55 mt-0.5 leading-snug">
              {activeRegion.patterns} of {activeRegion.target} patterns · {activeRegion.maturityLabel}
            </p>
          </>
        )}
      </div>

      {/* Legend */}
      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 mt-3 w-full max-w-[240px]">
        {regions.map((r) => {
          const active = selectedId === r.id || hoveredId === r.id;
          return (
            <button
              key={r.id}
              type="button"
              onClick={() => onSelect(r.id)}
              onMouseEnter={() => setHoveredId(r.id)}
              onMouseLeave={() => setHoveredId(null)}
              className={`flex items-center gap-1.5 text-left rounded-lg px-1.5 py-1 transition-colors ${
                active ? 'bg-white/10' : 'hover:bg-white/5'
              }`}
            >
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{
                  backgroundColor:
                    r.fill <= 0
                      ? 'rgba(255,255,255,0.2)'
                      : `rgba(255,255,255,${0.35 + r.fill * 0.55})`,
                }}
              />
              <span className={`text-[11px] truncate ${active ? 'text-white/90' : 'text-white/45'}`}>
                {r.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
