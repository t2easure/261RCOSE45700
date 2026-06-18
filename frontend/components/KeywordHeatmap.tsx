'use client'

import { useMemo, useState } from 'react'

interface TrendCluster {
  trend_name: string
  short_name?: string
  signal_strength?: number
  post_count: number
  is_leading: boolean
  avg_engagement_rate: number
  representative_ids: number[]
  representative_images: string[]
  [key: string]: unknown
}

interface FashionReport {
  id: number
  period_start: string
  period_end: string
  created_at: string
  trend_clusters: string | TrendCluster[] | null
}

interface Props {
  reports: FashionReport[]
  mode: 'weekly' | 'monthly'
  onCellClick?: (cluster: TrendCluster, period: string) => void
}

function parseClusters(r: FashionReport): TrendCluster[] {
  if (!r.trend_clusters) return []
  return typeof r.trend_clusters === 'string' ? JSON.parse(r.trend_clusters) : r.trend_clusters
}

function periodLabel(r: FashionReport, mode: 'weekly' | 'monthly') {
  if (mode === 'monthly') return r.period_start?.slice(0, 7) ?? r.created_at.slice(0, 7)
  return r.period_start ? `${r.period_start.slice(5, 10)}` : r.created_at.slice(5, 10)
}

// signal_strength 이론상 최대 10점이지만, post_count>=50·engagement>=2% 같은 조건이
// 동시에 충족돼야 8점대가 나와 실제로는 거의 도달하지 않음. 실측 분포(대략 1~5.5)에 맞춰
// 고정 threshold를 재조정 (시계열 비교가 가능하도록 절대값 유지)
function cellColor(value: number | null): string {
  if (value === null) return 'bg-brown-50 text-transparent'
  if (value >= 5.5) return 'bg-orange-400 text-white'    // 강한 신호
  if (value >= 4.3) return 'bg-orange-200 text-orange-800' // 성장
  if (value >= 3.2) return 'bg-yellow-200 text-yellow-800' // 포화 진입
  if (value >= 1.5) return 'bg-green-100 text-green-700'
  return 'bg-stone-100 text-stone-400' // 약함
}

function linearSlope(values: number[]): number {
  const n = values.length
  if (n < 2) return 0
  const xs = values.map((_, i) => i)
  const meanX = (n - 1) / 2
  const meanY = values.reduce((s, v) => s + v, 0) / n
  const num = xs.reduce((s, x, i) => s + (x - meanX) * (values[i] - meanY), 0)
  const den = xs.reduce((s, x) => s + (x - meanX) ** 2, 0)
  return den === 0 ? 0 : num / den
}

export default function KeywordHeatmap({ reports, mode, onCellClick }: Props) {
  const [topN, setTopN] = useState(12)

  const sorted = useMemo(
    () => [...reports].sort((a, b) => new Date(a.period_start ?? a.created_at).getTime() - new Date(b.period_start ?? b.created_at).getTime()),
    [reports]
  )

  const { keywords, matrix, slopes } = useMemo(() => {
    const nameCount: Record<string, number> = {}
    sorted.forEach(r =>
      parseClusters(r).forEach(c => {
        const n = c.short_name ?? c.trend_name
        nameCount[n] = (nameCount[n] ?? 0) + 1
      })
    )
    const allNames = Object.keys(nameCount).sort((a, b) => nameCount[b] - nameCount[a]).slice(0, topN)

    const mat: Record<string, (number | null)[]> = {}
    allNames.forEach(n => { mat[n] = sorted.map(() => null) })

    sorted.forEach((r, ti) => {
      parseClusters(r).forEach(c => {
        const n = c.short_name ?? c.trend_name
        if (mat[n]) mat[n][ti] = c.signal_strength ?? 0
      })
    })

    const slopes: Record<string, number> = {}
    allNames.forEach(n => {
      const vals = mat[n].filter((v): v is number => v !== null)
      slopes[n] = linearSlope(vals)
    })

    return { keywords: allNames, matrix: mat, slopes }
  }, [sorted, topN])

  if (sorted.length === 0) return (
    <div className="rounded-2xl border-2 border-dashed border-brown-200 p-10 text-center text-xs text-brown-300">
      리포트 데이터가 없습니다
    </div>
  )

  const periods = sorted.map(r => periodLabel(r, mode))

  return (
    <div className="space-y-3">
      {/* Top N 컨트롤 */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-brown-400 shrink-0">상위 키워드 수</span>
        <input
          type="range"
          min={5}
          max={20}
          value={topN}
          onChange={e => setTopN(Number(e.target.value))}
          className="w-28 accent-brown-600"
        />
        <span className="text-xs font-semibold text-brown-600 w-6">{topN}</span>
        <span className="ml-auto flex gap-3 text-[11px] text-brown-400">
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-orange-400"/>≥5.5 강한 신호</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-orange-200"/>≥4.3</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-yellow-200"/>≥3.2</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-green-100"/>≥1.5</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-stone-100 border border-stone-200"/>미진입</span>
        </span>
      </div>

      {/* 히트맵 그리드 */}
      <div className="overflow-x-auto rounded-2xl border border-brown-100 bg-white">
        <table className="w-full text-[11px] border-collapse">
          <thead>
            <tr>
              <th className="sticky left-0 bg-white px-4 py-2.5 text-left text-[10px] font-medium text-brown-400 min-w-[140px] border-b border-brown-100">키워드</th>
              {periods.map((p, i) => (
                <th key={i} className="px-1 py-2.5 text-center text-[10px] font-medium text-brown-400 border-b border-brown-100 whitespace-nowrap min-w-[52px]">{p}</th>
              ))}
              <th className="px-3 py-2.5 text-center text-[10px] font-medium text-brown-400 border-b border-brown-100 min-w-[60px]">추세</th>
            </tr>
          </thead>
          <tbody>
            {keywords.map((kw, ki) => {
              const slope = slopes[kw]
              const appeared = matrix[kw].filter(v => v !== null).length
              // 등장 횟수 기준 판단: 기울기는 데이터 포인트 2개 이상이어야 의미 있음
              const isNew = appeared <= 1
              const isRising = !isNew && slope > 0.5
              const isFalling = !isNew && slope < -0.5
              return (
                <tr key={kw} className={ki % 2 === 0 ? 'bg-cream-50/40' : 'bg-white'}>
                  <td className="sticky left-0 px-4 py-1.5 font-medium text-brown-700 border-r border-brown-100 min-w-[140px] whitespace-nowrap" style={{ background: ki % 2 === 0 ? 'rgb(253,251,247,0.4)' : 'white' }}>
                    {kw}
                    {isRising && <span className="ml-1 text-orange-500 font-bold">↑</span>}
                    {isFalling && <span className="ml-1 text-stone-400">↓</span>}
                  </td>
                  {matrix[kw].map((val, ti) => {
                    const cluster = parseClusters(sorted[ti]).find(c => (c.short_name ?? c.trend_name) === kw)
                    return (
                      <td key={ti} className="p-0.5 text-center">
                        <button
                          className={`w-full rounded-md py-1.5 text-[10px] font-semibold transition hover:opacity-80 ${cellColor(val)}`}
                          title={val !== null ? `${kw} · ${periods[ti]} · 신호강도 ${val.toFixed(1)}` : `${kw} · ${periods[ti]} · 데이터 없음`}
                          onClick={() => {
                            if (cluster && onCellClick) onCellClick(cluster, sorted[ti].period_start?.slice(0, 10) ?? '')
                          }}
                          disabled={val === null || !onCellClick}
                        >
                          {val !== null ? val.toFixed(1) : ''}
                        </button>
                      </td>
                    )
                  })}
                  <td className="px-3 py-1.5 text-center">
                    {isRising ? (
                      <span className="inline-flex items-center gap-0.5 rounded-full bg-orange-50 px-2 py-0.5 text-[10px] font-semibold text-orange-600">
                        🔥 급상승
                      </span>
                    ) : isFalling ? (
                      <span className="text-[10px] text-stone-400">↘ 하강</span>
                    ) : isNew ? (
                      <span className="text-[10px] text-stone-300">🆕 신규</span>
                    ) : (
                      <span className="text-[10px] text-brown-300">→ 유지</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
