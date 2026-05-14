'use client'

import { useCallback, useEffect, useState } from 'react'
import Navbar, { type Tab } from '@/components/Navbar'
import SearchBar from '@/components/SearchBar'
import ImageCard from '@/components/ImageCard'
import CrawlButton from '@/components/CrawlButton'

interface SearchResult {
  id: number
  image_url: string
  account_name: string
  source: string
  posted_at: string | null
  caption_ai: string | null
  similarity: number
}

interface FashionReport {
  id: number
  created_at: string
  period_start: string
  period_end: string
  summary: string
  full_report: string
  post_count: number
}

interface Stats {
  total: number
  bySource: Record<string, number>
  lastRun: string
}

export default function Home() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [reports, setReports] = useState<FashionReport[]>([])
  const [reportsLoading, setReportsLoading] = useState(false)
  const [selectedReport, setSelectedReport] = useState<FashionReport | null>(null)
  const [reportGenerating, setReportGenerating] = useState(false)
  const [stats, setStats] = useState<Stats | null>(null)

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch('/api/stats')
      if (res.ok) setStats(await res.json())
    } catch {}
  }, [])

  const fetchReports = useCallback(async () => {
    setReportsLoading(true)
    try {
      const res = await fetch('/api/fashion-reports')
      if (res.ok) setReports(await res.json())
    } catch {} finally { setReportsLoading(false) }
  }, [])

  useEffect(() => { fetchStats() }, [fetchStats])
  useEffect(() => { if (tab === 'reports') fetchReports() }, [tab, fetchReports])

  async function handleSearch(query: string, days: number) {
    setSearchLoading(true)
    setSearchQuery(query)
    setTab('search')
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&days=${days}`)
      if (res.ok) {
        const data = await res.json()
        setSearchResults(data.results ?? [])
      }
    } catch {} finally { setSearchLoading(false) }
  }

  async function handleGenerateReport() {
    setReportGenerating(true)
    try {
      await fetch('/api/fashion-reports/generate', { method: 'POST' })
      setTimeout(() => { fetchReports(); setReportGenerating(false) }, 3000)
    } catch { setReportGenerating(false) }
  }

  function formatDate(iso: string) {
    try { return new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' }) }
    catch { return iso }
  }

  return (
    <div className="min-h-screen bg-cream-200 font-sans">
      <Navbar tab={tab} onTabChange={setTab} />

      {/* ── 대시보드 ── */}
      {tab === 'dashboard' && (
        <>
          {/* Hero */}
          <section className="relative overflow-hidden bg-brown-700 text-cream-50">
            <div className="mx-auto max-w-7xl px-8 py-20">
              <p className="mb-3 text-xs font-medium tracking-[0.3em] text-brown-200 uppercase">
                Fashion Intelligence Platform
              </p>
              <h1 className="font-serif text-6xl font-bold leading-tight tracking-wide uppercase">
                Discover the<br />Art of Trends
              </h1>
              <p className="mt-5 max-w-xl text-base text-brown-200 leading-7">
                인플루언서 & 브랜드 이미지를 AI로 분석하여<br />
                패션 트렌드를 한눈에 파악합니다
              </p>
              <div className="mt-10 max-w-2xl">
                <SearchBar onSearch={handleSearch} loading={searchLoading} large />
              </div>
            </div>
            {/* 장식 원 */}
            <div className="absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brown-600 opacity-40" />
            <div className="absolute -bottom-20 right-40 h-64 w-64 rounded-full bg-brown-500 opacity-30" />
          </section>

          {/* 통계 바 */}
          <section className="border-b border-brown-200 bg-cream-50">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-8 py-5">
              <div className="flex gap-10">
                <Stat label="수집된 이미지" value={stats?.total?.toLocaleString() ?? '—'} />
                <Stat label="브랜드" value="5" />
                <Stat label="인플루언서" value={String(stats?.bySource?.instagram ?? '—')} />
                <Stat label="마지막 수집" value={stats?.lastRun ? formatDate(stats.lastRun) : '—'} />
              </div>
              <CrawlButton onComplete={fetchStats} />
            </div>
          </section>

          {/* 카테고리 그리드 */}
          <section className="mx-auto max-w-7xl px-8 py-14">
            <h2 className="mb-8 font-serif text-3xl font-bold uppercase tracking-wide text-brown-700">
              Browse by Style
            </h2>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {STYLE_CATEGORIES.map((cat) => (
                <button
                  key={cat.label}
                  onClick={() => handleSearch(cat.query, 60)}
                  className="group relative overflow-hidden rounded-2xl bg-brown-300 aspect-[4/5]"
                >
                  <div className="absolute inset-0 bg-gradient-to-t from-brown-800/80 via-transparent to-transparent" />
                  <div className="absolute bottom-0 left-0 p-5">
                    <p className="font-serif text-xl font-bold uppercase tracking-wider text-white">
                      {cat.label}
                    </p>
                  </div>
                  <div className="absolute inset-0 bg-brown-600/0 transition group-hover:bg-brown-600/20" />
                </button>
              ))}
            </div>
          </section>
        </>
      )}

      {/* ── 검색 ── */}
      {tab === 'search' && (
        <div className="mx-auto max-w-7xl px-8 py-10 space-y-8">
          <div>
            <h2 className="font-serif text-4xl font-bold uppercase tracking-wide text-brown-700">
              Image Search
            </h2>
            <p className="mt-2 text-sm text-brown-400">
              패션 키워드로 인플루언서 & 브랜드 이미지를 찾아보세요
            </p>
          </div>

          <div className="rounded-2xl bg-white p-6 shadow-sm">
            <SearchBar onSearch={handleSearch} loading={searchLoading} />
          </div>

          {searchQuery && (
            <div>
              <div className="mb-5 flex items-center justify-between">
                <p className="text-sm text-brown-500">
                  <span className="font-semibold text-brown-800">"{searchQuery}"</span> — {searchResults.length}개 결과
                </p>
              </div>

              {searchLoading ? (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                  {Array.from({ length: 10 }).map((_, i) => (
                    <div key={i} className="aspect-[3/4] animate-pulse rounded-2xl bg-brown-100" />
                  ))}
                </div>
              ) : searchResults.length === 0 ? (
                <div className="rounded-2xl border-2 border-dashed border-brown-200 p-16 text-center">
                  <p className="font-serif text-xl text-brown-300">No results found</p>
                  <p className="mt-2 text-sm text-brown-300">다른 키워드를 입력해보세요</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                  {searchResults.map((r) => (
                    <ImageCard
                      key={r.id}
                      imageUrl={r.image_url}
                      accountName={r.account_name}
                      source={r.source}
                      postedAt={r.posted_at}
                      captionAi={r.caption_ai}
                      similarity={r.similarity}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── 리포트 ── */}
      {tab === 'reports' && (
        <div className="mx-auto max-w-7xl px-8 py-10 space-y-8">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="font-serif text-4xl font-bold uppercase tracking-wide text-brown-700">
                Trend Reports
              </h2>
              <p className="mt-2 text-sm text-brown-400">AI가 분석한 패션 트렌드 리포트</p>
            </div>
            <button
              onClick={handleGenerateReport}
              disabled={reportGenerating}
              className="rounded-xl bg-brown-600 px-6 py-3 text-sm font-medium text-cream-50 transition hover:bg-brown-700 disabled:opacity-50"
            >
              {reportGenerating ? 'Generating...' : '+ Generate Report'}
            </button>
          </div>

          {selectedReport ? (
            <div className="space-y-5">
              <button
                onClick={() => setSelectedReport(null)}
                className="flex items-center gap-2 text-sm text-brown-500 transition hover:text-brown-700"
              >
                ← Back to list
              </button>
              <div className="rounded-2xl bg-white p-8 shadow-sm space-y-5">
                <p className="text-xs tracking-widest text-brown-300 uppercase">
                  {selectedReport.period_start} — {selectedReport.period_end}
                </p>
                <h3 className="font-serif text-2xl font-bold text-brown-700">{selectedReport.summary}</h3>
                <div className="rounded-xl bg-cream-100 p-6">
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-brown-600">
                    {selectedReport.full_report}
                  </pre>
                </div>
                <p className="text-xs text-brown-300">{selectedReport.post_count}개 이미지 기반 분석</p>
              </div>
            </div>
          ) : reportsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-2xl bg-brown-100" />
              ))}
            </div>
          ) : reports.length === 0 ? (
            <div className="rounded-2xl border-2 border-dashed border-brown-200 p-16 text-center">
              <p className="font-serif text-xl text-brown-300">No reports yet</p>
              <p className="mt-2 text-sm text-brown-300">데이터 수집 후 Generate Report를 눌러주세요</p>
            </div>
          ) : (
            <div className="space-y-3">
              {reports.map((r) => (
                <button
                  key={r.id}
                  onClick={() => setSelectedReport(r)}
                  className="flex w-full items-center gap-5 rounded-2xl bg-white px-6 py-5 text-left shadow-sm transition hover:shadow-md"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-xs tracking-widest text-brown-300 uppercase">{formatDate(r.created_at)}</p>
                    <p className="mt-1 truncate text-sm font-medium text-brown-700">{r.summary}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="rounded-full bg-cream-200 px-3 py-1 text-xs text-brown-500">
                      {r.post_count} images
                    </span>
                    <span className="text-brown-300">→</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── 데이터 ── */}
      {tab === 'data' && (
        <div className="mx-auto max-w-7xl px-8 py-10">
          <h2 className="font-serif text-4xl font-bold uppercase tracking-wide text-brown-700">Data</h2>
          <p className="mt-10 text-center text-brown-300">수집된 원본 데이터 뷰 — 준비 중</p>
        </div>
      )}

      {/* Footer */}
      <footer className="mt-20 border-t border-brown-200 bg-brown-700 py-10 text-center">
        <p className="font-serif text-2xl font-bold tracking-widest text-cream-50">CRAI</p>
        <p className="mt-1 text-xs text-brown-300">Curated Reference AI — Fashion Intelligence</p>
      </footer>
    </div>
  )
}

const STYLE_CATEGORIES = [
  { label: 'Comfort Classic', query: 'comfort classic' },
  { label: 'Oversized',       query: 'oversized' },
  { label: 'Minimal',         query: '미니멀' },
  { label: 'Street Style',    query: '스트리트' },
]

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-brown-400">{label}</p>
      <p className="mt-0.5 text-lg font-semibold text-brown-700">{value}</p>
    </div>
  )
}
