'use client'

interface TrendCluster {
  trend_name: string
  short_name?: string
  signal_strength?: number
}

interface FashionReport {
  id: number
  period_start: string
  period_end?: string
  trend_clusters: string | TrendCluster[] | null
}

interface Props {
  reports: FashionReport[]
  onDrill?: (cluster: TrendCluster, period: string) => void
  maxKeywords?: number
}

function linearSlope(vals: (number | null)[]): number {
  const filled = vals.map((v, i) => ({ x: i, y: v ?? 0 }))
  const n = filled.length
  if (n < 2) return 0
  const sumX = filled.reduce((s, p) => s + p.x, 0)
  const sumY = filled.reduce((s, p) => s + p.y, 0)
  const sumXY = filled.reduce((s, p) => s + p.x * p.y, 0)
  const sumX2 = filled.reduce((s, p) => s + p.x * p.x, 0)
  const denom = n * sumX2 - sumX * sumX
  return denom === 0 ? 0 : (n * sumXY - sumX * sumY) / denom
}

export default function KeywordHeatmap({ reports, onDrill, maxKeywords = 15 }: Props) {
  const sorted = [...reports].sort(
    (a, b) => new Date(a.period_start).getTime() - new Date(b.period_start).getTime()
  )

  const parseClusters = (r: FashionReport): TrendCluster[] => {
    if (!r.trend_clusters) return []
    return typeof r.trend_clusters === 'string' ? JSON.parse(r.trend_clusters) : r.trend_clusters
  }

  // Build keyword × period matrix
  const nameCount: Record<string, number> = {}
  sorted.forEach(r => parseClusters(r).forEach(c => {
    const n = c.short_name ?? c.trend_name
    nameCount[n] = (nameCount[n] ?? 0) + 1
  }))
  const keywords = Object.keys(nameCount)
    .sort((a, b) => nameCount[b] - nameCount[a])
    .slice(0, maxKeywords)

  const matrix: Record<string, (number | null)[]> = {}
  keywords.forEach(kw => {
    matrix[kw] = sorted.map(r => {
      const c = parseClusters(r).find(c => (c.short_name ?? c.trend_name) === kw)
      return c?.signal_strength ?? null
    })
  })

  if (!keywords.length) return null

  const periods = sorted.map(r =>
    r.period_start ? r.period_start.slice(5, 10) : ''
  )

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead>
          <tr>
            <th className="text-left font-normal text-brown-300 pr-3 pb-2 w-28 shrink-0">키워드</th>
            {periods.map((p, i) => (
              <th key={i} className="text-center font-normal text-brown-300 pb-2 px-1 min-w-[48px]">{p}</th>
            ))}
            <th className="text-center font-normal text-brown-300 pb-2 px-1 min-w-[40px]">추세</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-brown-50">
          {keywords.map(kw => {
            const vals = matrix[kw]
            const slope = linearSlope(vals)
            const total = vals.length
            const appeared = vals.filter(v => v !== null).length
            const appearRate = total > 0 ? appeared / total : 0
            const isSparse = appearRate < 0.3
            const isRising = !isSparse && slope > 0.5
            const isFalling = !isSparse && slope < -0.5

            return (
              <tr key={kw}>
                <td className="pr-3 py-1.5 font-medium text-brown-700 truncate max-w-[7rem]">{kw}</td>
                {vals.map((v, i) => {
                  const sig = v ?? 0
                  const bg = v === null
                    ? 'bg-stone-50'
                    : sig >= 8 ? 'bg-orange-400'
                    : sig >= 5 ? 'bg-green-400'
                    : sig >= 3 ? 'bg-yellow-300'
                    : 'bg-stone-200'
                  const report = sorted[i]
                  const cluster = v !== null
                    ? parseClusters(report).find(c => (c.short_name ?? c.trend_name) === kw)
                    : undefined
                  return (
                    <td key={i} className="px-1 py-1.5 text-center">
                      <div
                        className={`rounded-md h-6 w-full min-w-[36px] ${bg} ${cluster && onDrill ? 'cursor-pointer hover:opacity-70 transition-opacity' : ''}`}
                        title={v !== null ? `${sig.toFixed(1)}` : '—'}
                        onClick={() => cluster && onDrill && onDrill(cluster, report.period_start?.slice(0,10) ?? '')}
                      />
                    </td>
                  )
                })}
                <td className="px-1 py-1.5 text-center">
                  {isSparse
                    ? <span className="text-[10px] text-stone-300">— 단발</span>
                    : isRising
                    ? <span className="text-[10px] text-orange-500 font-medium">↑ 상승</span>
                    : isFalling
                    ? <span className="text-[10px] text-blue-400 font-medium">↓ 하락</span>
                    : <span className="text-[10px] text-green-500 font-medium">→ 유지</span>
                  }
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
