const SVG_W = 600

function maxOf(data, keys) {
  return data.reduce((m, d) => Math.max(m, ...keys.map((k) => Number(d[k]) || 0)), 0)
}

export function LineChart({ data, xKey = 'date', series = [], height = 200, colors = {} }) {
  if (!data || data.length === 0) return <div className="empty">No data yet.</div>
  const pad = 30
  const w = SVG_W
  const h = height
  const yMax = Math.max(maxOf(data, series.map((s) => s.key)) * 1.1, 1)
  const step = (w - pad * 2) / Math.max(data.length - 1, 1)
  const x = (i) => pad + i * step
  const y = (v) => h - pad - (Number(v) / yMax) * (h - pad * 2)

  const stepCount = series.length
  if (stepCount === 0) return <div className="empty">No series.</div>

  const xTicks = []
  const tickCount = Math.min(8, data.length)
  const interval = Math.max(1, Math.floor(data.length / tickCount))
  for (let i = 0; i < data.length; i += interval) {
    xTicks.push({ i, label: String(data[i][xKey] ?? '').slice(0, 10) })
  }

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} style={{ overflow: 'visible' }}>
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <line key={f} x1={pad} x2={w - pad} y1={y(yMax * f)} y2={y(yMax * f)} stroke="#e5e7eb" strokeWidth="1" />
      ))}
      {series.map((s) => {
        const path = data.map((d, i) => (i === 0 ? `M ${x(i)} ${y(s.key in d ? d[s.key] : 0)}` : `L ${x(i)} ${y(s.key in d ? d[s.key] : 0)}`)).join(' ')
        const color = s.color || colors[s.key] || '#2563eb'
        return (
          <g key={s.key}>
            <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
            {data.map((d, i) => (
              <circle key={i} cx={x(i)} cy={y(s.key in d ? d[s.key] : 0)} r="3" fill="#fff" stroke={color} strokeWidth="2" />
            ))}
          </g>
        )
      })}
      {xTicks.map(({ i, label }) => (
        <text key={i} x={x(i)} y={h - 8} fontSize="10" fill="#6b7280" textAnchor="middle">{label}</text>
      ))}
      <text x={pad} y={12} fontSize="11" fill="#6b7280">max {yMax.toFixed(1)}</text>
    </svg>
  )
}

export function BarChart({ data, xKey = 'date', series = [], height = 220, colors = {} }) {
  if (!data || data.length === 0) return <div className="empty">No data yet.</div>
  const pad = 30
  const w = SVG_W
  const h = height
  const yMax = Math.max(maxOf(data, series.map((s) => s.key)) * 1.1, 1)
  const slot = (w - pad * 2) / data.length
  const barW = Math.min(28, slot * 0.6 / Math.max(series.length, 1))

  const y = (v) => h - pad - (Number(v) / yMax) * (h - pad * 2)

  const tickCount = Math.min(8, data.length)
  const interval = Math.max(1, Math.floor(data.length / tickCount))

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} style={{ overflow: 'visible' }}>
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <line key={f} x1={pad} x2={w - pad} y1={y(yMax * f)} y2={y(yMax * f)} stroke="#e5e7eb" strokeWidth="1" />
      ))}
      {data.map((d, i) => (
        <g key={i}>
          {series.map((s, si) => {
            const v = s.key in d ? d[s.key] : 0
            const color = s.color || colors[s.key] || '#16a34a'
            const bw = series.length === 1 ? slot * 0.6 : barW
            const bx = pad + i * slot + slot / 2 - (series.length * bw) / 2 + si * bw
            return <rect key={s.key} x={bx} y={y(v)} width={bw} height={Math.max(0, h - pad - y(v))} rx="3" fill={color} />
          })}
        </g>
      ))}
      {data.map((d, i) =>
        i % interval === 0 ? (
          <text key={i} x={pad + i * slot + slot / 2} y={h - 8} fontSize="10" fill="#6b7280" textAnchor="middle">
            {String(d[xKey] ?? '').slice(0, 10)}
          </text>
        ) : null,
      )}
      <text x={pad} y={12} fontSize="11" fill="#6b7280">max {yMax.toFixed(1)}</text>
    </svg>
  )
}

export function DonutChart({ segments = [], size = 180, thickness = 26, centerLabel = 'Total', centerValue }) {
  const total = segments.reduce((s, seg) => s + (seg.value || 0), 0)
  if (total === 0) return <div className="empty">No data yet.</div>
  const r = (size - thickness) / 2
  const c = size / 2
  const circ = 2 * Math.PI * r
  let offset = 0
  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <svg width={size} height={size}>
        <circle cx={c} cy={c} r={r} fill="none" stroke="#e5e7eb" strokeWidth={thickness} />
        {segments.map((seg, i) => {
          const frac = (seg.value || 0) / total
          const dash = frac * circ
          const el = (
            <circle
              key={i}
              cx={c} cy={c} r={r} fill="none"
              stroke={seg.color}
              strokeWidth={thickness}
              strokeDasharray={`${dash} ${circ - dash}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
            />
          )
          offset += dash
          return el
        })}
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ fontSize: 12, color: '#6b7280' }}>{centerLabel}</div>
        <div style={{ fontSize: 22, fontWeight: 700 }}>{centerValue !== undefined ? centerValue : total}</div>
      </div>
    </div>
  )
}

export function Sparkline({ values = [], color = '#2563eb', width = 120, height = 34 }) {
  if (!values || values.length < 2) return <div style={{ width, height }} />
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = Math.max(max - min, 0.0001)
  const step = width / (values.length - 1)
  const pts = values.map((v, i) => `${i * step},${height - ((v - min) / range) * height}`).join(' ')
  return (
    <svg width={width} height={height}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}