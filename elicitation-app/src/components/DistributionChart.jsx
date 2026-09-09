import React, { useRef, useState } from 'react';

/**
 * Interactive belief-distribution chart.
 *
 * Renders the (approximate) distribution implied by the expert's three inputs,
 * fit as a split-normal: the point estimate is the mode, and the lower/upper
 * bounds are treated as the 5th/95th percentiles of each half (90% CI).
 * All three values can be dragged directly on the chart.
 */

const X_MIN = -100;
const X_MAX = 100;
const Z90 = 1.645; // z-score for a 5%/95% tail
const MIN_SIGMA = 1.2; // keeps the curve drawable when a bound touches the mode

const W = 640;
const H = 210;
const PLOT = { x: 18, y: 16, w: W - 36 };
const BASE_Y = 158; // baseline (x-axis) y position
const CURVE_H = 128; // max curve height above baseline

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const xToPx = (x) => PLOT.x + ((x - X_MIN) / (X_MAX - X_MIN)) * PLOT.w;

function density(x, pe, sigL, sigR) {
  const sig = x < pe ? sigL : sigR;
  const d = (x - pe) / sig;
  return Math.exp(-0.5 * d * d);
}

function buildPaths(pe, lb, ub, sigL, sigR) {
  const curve = [];
  const shade = [];
  const step = 0.5;
  for (let x = X_MIN; x <= X_MAX + 1e-9; x += step) {
    const px = xToPx(x);
    const py = BASE_Y - density(x, pe, sigL, sigR) * CURVE_H;
    curve.push(`${curve.length === 0 ? 'M' : 'L'}${px.toFixed(1)},${py.toFixed(1)}`);
    if (x >= lb - 1e-9 && x <= ub + 1e-9) {
      shade.push(`${shade.length === 0 ? 'M' : 'L'}${px.toFixed(1)},${py.toFixed(1)}`);
    }
  }
  const shadePath =
    shade.join(' ') +
    ` L${xToPx(ub).toFixed(1)},${BASE_Y} L${xToPx(lb).toFixed(1)},${BASE_Y} Z`;
  return { curvePath: curve.join(' '), shadePath };
}

export default function DistributionChart({ lowerBound, pointEstimate, upperBound, onCommit }) {
  const svgRef = useRef(null);
  const [drag, setDrag] = useState(null);

  // Effective values: fall back to sensible defaults so the chart is always visible.
  const peRaw = parseFloat(pointEstimate);
  const pe = Number.isFinite(peRaw) ? clamp(peRaw, X_MIN, X_MAX) : 0;
  const lbRaw = parseFloat(lowerBound);
  const lb = Number.isFinite(lbRaw) ? clamp(Math.min(lbRaw, pe), X_MIN, X_MAX) : clamp(pe - 20, X_MIN, X_MAX);
  const ubRaw = parseFloat(upperBound);
  const ub = Number.isFinite(ubRaw) ? clamp(Math.max(ubRaw, pe), X_MIN, X_MAX) : clamp(pe + 20, X_MIN, X_MAX);

  const boundsSet = Number.isFinite(lbRaw) && Number.isFinite(ubRaw);

  const sigL = Math.max((pe - lb) / Z90, MIN_SIGMA);
  const sigR = Math.max((ub - pe) / Z90, MIN_SIGMA);
  const { curvePath, shadePath } = buildPaths(pe, lb, ub, sigL, sigR);

  const pxToValue = (clientX) => {
    const rect = svgRef.current.getBoundingClientRect();
    const svgX = ((clientX - rect.left) / rect.width) * W;
    return X_MIN + ((svgX - PLOT.x) / PLOT.w) * (X_MAX - X_MIN);
  };

  const moveTo = (which, clientX) => {
    let v = Math.round(pxToValue(clientX) * 2) / 2; // snap to 0.5
    v = clamp(v, X_MIN, X_MAX);
    const next = { lb, pe, ub };
    if (which === 'lb') next.lb = Math.min(v, pe);
    else if (which === 'ub') next.ub = Math.max(v, pe);
    else {
      // Dragging the central estimate pushes the bounds along if it passes them.
      next.pe = v;
      next.lb = Math.min(lb, v);
      next.ub = Math.max(ub, v);
    }
    onCommit(next);
  };

  const startDrag = (which) => (e) => {
    e.preventDefault();
    try { e.target.setPointerCapture(e.pointerId); } catch { /* noop */ }
    setDrag(which);
    moveTo(which, e.clientX);
  };
  const handleMove = (e) => { if (drag) moveTo(drag, e.clientX); };
  const endDrag = () => setDrag(null);

  const ticks = [-100, -50, 0, 50, 100];
  const peX = xToPx(pe);
  const lbX = xToPx(lb);
  const ubX = xToPx(ub);
  const peakY = BASE_Y - CURVE_H;

  const handleProps = (which) => ({
    onPointerDown: startDrag(which),
    style: { cursor: drag === which ? 'grabbing' : 'grab', touchAction: 'none' },
  });

  return (
    <div className={`dist-chart ${drag ? 'dragging' : ''}`}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="dist-chart-svg"
        onPointerMove={handleMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        role="img"
        aria-label={`Belief distribution: lower bound ${lb}%, central estimate ${pe}%, upper bound ${ub}%`}
      >
        {/* gridlines + ticks */}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={xToPx(t)} y1={PLOT.y} x2={xToPx(t)} y2={BASE_Y} className="dist-grid" />
            <text x={xToPx(t)} y={BASE_Y + 16} className="dist-tick" textAnchor="middle">
              {t > 0 ? `+${t}%` : `${t}%`}
            </text>
          </g>
        ))}

        {/* zero line slightly stronger */}
        <line x1={xToPx(0)} y1={PLOT.y} x2={xToPx(0)} y2={BASE_Y} className="dist-zero" />

        {/* shaded 90% CI area */}
        <path d={shadePath} className="dist-area" />

        {/* density curve */}
        <path d={curvePath} className="dist-curve" fill="none" />

        {/* baseline */}
        <line x1={PLOT.x} y1={BASE_Y} x2={PLOT.x + PLOT.w} y2={BASE_Y} className="dist-axis" />

        {/* guide lines */}
        <line x1={lbX} y1={BASE_Y} x2={lbX} y2={BASE_Y - density(lb, pe, sigL, sigR) * CURVE_H} className="dist-guide" />
        <line x1={ubX} y1={BASE_Y} x2={ubX} y2={BASE_Y - density(ub, pe, sigL, sigR) * CURVE_H} className="dist-guide" />
        <line x1={peX} y1={BASE_Y} x2={peX} y2={peakY} className="dist-guide central" />

        {/* value labels (bound labels hide when they would collide with the central one) */}
        {peX - lbX > 34 && (
          <text x={lbX} y={BASE_Y - density(lb, pe, sigL, sigR) * CURVE_H - 8} className="dist-value bound" textAnchor="middle">{lb}%</text>
        )}
        {ubX - peX > 34 && (
          <text x={ubX} y={BASE_Y - density(ub, pe, sigL, sigR) * CURVE_H - 8} className="dist-value bound" textAnchor="middle">{ub}%</text>
        )}
        <text x={peX} y={peakY - 8} className="dist-value central" textAnchor="middle">{pe}%</text>

        {/* drag handles on the baseline; bounds render on top so a collapsed
            interval can always be widened again */}
        <g {...handleProps('pe')}>
          <circle cx={peX} cy={BASE_Y} r={16} fill="transparent" />
          <circle cx={peX} cy={BASE_Y} r={9} className="dist-handle central" />
        </g>
        <g {...handleProps('lb')}>
          <circle cx={lbX} cy={BASE_Y} r={13} fill="transparent" />
          <circle cx={lbX} cy={BASE_Y} r={7.5} className="dist-handle bound" />
        </g>
        <g {...handleProps('ub')}>
          <circle cx={ubX} cy={BASE_Y} r={13} fill="transparent" />
          <circle cx={ubX} cy={BASE_Y} r={7.5} className="dist-handle bound" />
        </g>

        {/* handle role labels (hidden when too close to the central label) */}
        {peX - lbX > 56 && <text x={lbX} y={BASE_Y + 30} className="dist-role" textAnchor="middle">lower</text>}
        {ubX - peX > 56 && <text x={ubX} y={BASE_Y + 30} className="dist-role" textAnchor="middle">upper</text>}
        <text x={peX} y={BASE_Y + 30} className="dist-role central" textAnchor="middle">central</text>
      </svg>
      <p className="dist-caption">
        {boundsSet
          ? <>Your implied belief distribution — the shaded region is your ~90% credible interval. <strong>Drag the handles</strong> to adjust your estimates.</>
          : <><strong>Drag the handles</strong> to set your bounds and central estimate — the curve shows the belief distribution they imply.</>}
      </p>
    </div>
  );
}
