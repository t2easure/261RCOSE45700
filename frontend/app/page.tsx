'use client'

import { useCallback, useEffect, useState } from 'react'
import Navbar, { type Tab } from '@/components/Navbar'
import SearchBar from '@/components/SearchBar'
import ImageCard from '@/components/ImageCard'
import CrawlButton from '@/components/CrawlButton'

interface Post {
  id: number
  image_url: string
  account_name: string
  source: string
  posted_at: string | null
  caption_ai: string | null
}

interface SearchResult extends Post {
  similarity: number
}

interface StyleTrend {
  title: string
  content: string
  representative_ids: number[]
}

interface FashionReport {
  id: number
  created_at: string
  period_start: string
  period_end: string
  summary: string
  top_keywords: string | string[]
  style_trends: string | StyleTrend[]
  post_count: number
}

interface Stats {
  total: number
  bySource: Record<string, number>
  lastRun: string | null
  captioned: number
  meta_captioned: number
  embedded: number
}

export default function Home() {
  const [tab, setTab] = useState<Tab>('dashboard')

  // 검색
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedKeywords, setExpandedKeywords] = useState<string[]>([])

  // 검색 필터
  const [searchDays, setSearchDays] = useState(60)
  const [searchSources, setSearchSources] = useState<string[]>([])
  const [searchAccounts, setSearchAccounts] = useState<string[]>([])
  const [availableAccounts, setAvailableAccounts] = useState<string[]>([])
  const [showAccountDropdown, setShowAccountDropdown] = useState(false)

  // 리포트
  const [reports, setReports] = useState<FashionReport[]>([])
  const [reportsLoading, setReportsLoading] = useState(false)
  const [selectedReport, setSelectedReport] = useState<FashionReport | null>(null)
  const [reportGenerating, setReportGenerating] = useState(false)
  const [reportStatusMessage, setReportStatusMessage] = useState<string | null>(null)
  const [reportDays, setReportDays] = useState(30)
  const [reportPostCount, setReportPostCount] = useState<number | null>(null)
  const [showGenerateModal, setShowGenerateModal] = useState(false)

  // 통계
  const [stats, setStats] = useState<Stats | null>(null)

  // 대시보드 최신 이미지
  const [recentPosts, setRecentPosts] = useState<Post[]>([])

  // 데이터 탭
  const [allPosts, setAllPosts] = useState<Post[]>([])
  const [allPostsLoading, setAllPostsLoading] = useState(false)
  const [dataSource, setDataSource] = useState<'all' | 'instagram' | 'lookbook'>('all')
  const [dataOffset, setDataOffset] = useState(0)
  const DATA_LIMIT = 40

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch('/api/stats')
      if (res.ok) setStats(await res.json())
    } catch {}
  }, [])

  const fetchRecentPosts = useCallback(async () => {
    try {
      const res = await fetch('/api/posts?limit=12')
      if (res.ok) {
        const data = await res.json()
        setRecentPosts(data.items ?? data)
      }
    } catch {}
  }, [])

  const fetchReports = useCallback(async () => {
    setReportsLoading(true)
    try {
      const res = await fetch('/api/fashion-reports')
      if (res.ok) setReports(await res.json())
    } catch {} finally { setReportsLoading(false) }
  }, [])

  const fetchAllPosts = useCallback(async (source: string, offset: number, append = false) => {
    setAllPostsLoading(true)
    try {
      const params = new URLSearchParams({ limit: String(DATA_LIMIT), offset: String(offset) })
      if (source !== 'all') params.set('source', source)
      const res = await fetch(`/api/posts?${params}`)
      if (res.ok) {
        const data = await res.json()
        const items: Post[] = data.items ?? data
        setAllPosts(prev => append ? [...prev, ...items] : items)
      }
    } catch {} finally { setAllPostsLoading(false) }
  }, [])

  useEffect(() => { fetchStats(); fetchRecentPosts() }, [fetchStats, fetchRecentPosts])
  useEffect(() => { if (tab === 'reports') fetchReports() }, [tab, fetchReports])
  useEffect(() => {
    if (tab === 'search' && availableAccounts.length === 0) {
      fetch('/api/search/accounts').then(r => r.json()).then(setAvailableAccounts).catch(() => {})
    }
  }, [tab])
  useEffect(() => {
    if (tab === 'data') { setDataOffset(0); fetchAllPosts(dataSource, 0) }
  }, [tab, dataSource, fetchAllPosts])
  useEffect(() => {
    if (tab !== 'reports') return
    fetch(`/api/fashion-reports/count?days=${reportDays}`)
      .then(r => r.json())
      .then(d => setReportPostCount(d.count))
      .catch(() => {})
  }, [tab, reportDays])

  async function doSearch(query: string, days: number, sources: string[], accounts: string[]) {
    setSearchLoading(true)
    try {
      const params = new URLSearchParams({ q: query, days: String(days) })
      if (sources.length > 0) params.set('sources', sources.join(','))
      if (accounts.length > 0) params.set('accounts', accounts.join(','))
      const res = await fetch(`/api/search?${params}`)
      if (res.ok) {
        const data = await res.json()
        setSearchResults(data.results ?? [])
        setExpandedKeywords(data.expanded_keywords ?? [])
      }
    } catch {} finally { setSearchLoading(false) }
  }

  async function handleSearch(query: string, days: number) {
    setSearchQuery(query)
    setSearchDays(days)
    setTab('search')
    await doSearch(query, days, searchSources, searchAccounts)
  }

  useEffect(() => {
    if (searchQuery) doSearch(searchQuery, searchDays, searchSources, searchAccounts)
  }, [searchSources, searchAccounts, searchDays])


  async function handleGenerateReport(confirmedDays?: number) {
    const days = confirmedDays ?? reportDays
    if (reportPostCount !== null && reportPostCount < 50) {
      if (!window.confirm('데이터가 부족합니다. 이대로 진행할까요?')) return
    }
    setReportGenerating(true)
    setReportStatusMessage(null)
    try {
      await fetch('/api/fashion-reports/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days }),
      })
      const pollStatus = async (): Promise<void> => {
        try {
          const res = await fetch('/api/fashion-reports/generate/status')
          const data = await res.json()
          setReportStatusMessage(data.message ?? null)
          if (data.state === 'idle' || data.state === 'error') {
            fetchReports()
            setReportGenerating(false)
            setReportStatusMessage(data.state === 'error' ? `오류: ${data.message}` : '✅ 리포트 생성 완료!')
            setTimeout(() => setReportStatusMessage(null), 3000)
          } else {
            setTimeout(pollStatus, 2000)
          }
        } catch {
          setTimeout(pollStatus, 2000)
        }
      }
      setTimeout(pollStatus, 2000)
    } catch { setReportGenerating(false) }
  }

  function handleLoadMore() {
    const next = dataOffset + DATA_LIMIT
    setDataOffset(next)
    fetchAllPosts(dataSource, next, true)
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
                AI Fashion Intelligence · 20대 여성 트렌드
              </p>
              <h1 className="font-serif text-6xl font-bold leading-tight tracking-wide uppercase">
                Discover the<br />Art of Trends
              </h1>
              <p className="mt-5 max-w-xl text-base text-brown-200 leading-7">
                인플루언서 & SPA 브랜드 이미지를 AI로 분석하여<br />
                20대 여성 패션 트렌드를 한눈에 파악합니다
              </p>
              <div className="mt-10 max-w-2xl">
                <SearchBar onSearch={handleSearch} loading={searchLoading} large />
              </div>
            </div>
            <div className="absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brown-600 opacity-40" />
            <div className="absolute -bottom-20 right-40 h-64 w-64 rounded-full bg-brown-500 opacity-30" />
          </section>

          {/* 통계 + 크롤링 버튼 */}
          <section className="border-b border-brown-200 bg-cream-50">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-8 py-5">
              <div className="flex gap-10">
                <Stat label="수집된 이미지" value={stats?.total?.toLocaleString() ?? '—'} />
                <Stat label="Instagram" value={String(stats?.bySource?.instagram ?? '—')} />
                <Stat label="브랜드 룩북" value={String(stats?.bySource?.lookbook ?? '—')} />
                <Stat label="마지막 수집" value={stats?.lastRun ? formatDate(stats.lastRun) : '—'} />
                <Stat label="1차 캡셔닝" value={String(stats?.captioned ?? '—')} />
                <Stat label="2차 캡셔닝" value={String(stats?.meta_captioned ?? '—')} />
                <Stat label="임베딩" value={String(stats?.embedded ?? '—')} />
              </div>
              <CrawlButton onComplete={() => { fetchStats(); fetchRecentPosts() }} />
            </div>
          </section>

          {/* 최근 수집 이미지 */}
          <section className="mx-auto max-w-7xl px-8 py-14">
            <div className="mb-8 flex items-end justify-between">
              <h2 className="font-serif text-3xl font-bold uppercase tracking-wide text-brown-700">
                Recently Collected
              </h2>
              <button
                onClick={() => setTab('data')}
                className="text-sm text-brown-400 hover:text-brown-700 transition"
              >
                전체 보기 →
              </button>
            </div>

            {recentPosts.length === 0 ? (
              <div className="rounded-2xl border-2 border-dashed border-brown-200 p-16 text-center">
                <p className="font-serif text-xl text-brown-300">No images yet</p>
                <p className="mt-2 text-sm text-brown-300">크롤링을 실행하면 이미지가 표시됩니다</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
                {recentPosts.map((p) => (
                  <ImageCard
                    key={p.id}
                    imageUrl={p.image_url}
                    accountName={p.account_name}
                    source={p.source}
                    postedAt={p.posted_at}
                    captionAi={p.caption_ai}
                  />
                ))}
              </div>
            )}
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
            <SearchBar onSearch={handleSearch} loading={searchLoading} days={searchDays} />
          </div>

          {/* 필터 패널 */}
          <div className="flex flex-wrap items-center gap-4 rounded-2xl bg-white px-5 py-4 shadow-sm">
            {/* 소스 */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-brown-400 shrink-0">소스</span>
              <div className="flex gap-1">
                {(['instagram', 'lookbook'] as const).map((s) => {
                  const active = searchSources.includes(s)
                  return (
                    <button
                      key={s}
                      onClick={() => setSearchSources(prev =>
                        active ? prev.filter(x => x !== s) : [...prev, s]
                      )}
                      className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                        active
                          ? 'bg-brown-600 text-cream-50'
                          : 'bg-brown-100 text-brown-500 hover:bg-brown-200'
                      }`}
                    >
                      {s === 'instagram' ? 'Instagram' : 'Lookbook'}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="h-4 w-px bg-brown-200" />

            {/* 기간 */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-brown-400 shrink-0">기간</span>
              <select
                value={searchDays}
                onChange={e => setSearchDays(Number(e.target.value))}
                className="rounded-lg border border-brown-200 bg-white px-2 py-1 text-xs text-brown-600 outline-none focus:border-brown-400"
              >
                <option value={7}>최근 1주</option>
                <option value={14}>최근 2주</option>
                <option value={30}>최근 1달</option>
                <option value={60}>최근 2달</option>
                <option value={90}>최근 3달</option>
                <option value={0}>전체</option>
              </select>
            </div>

            <div className="h-4 w-px bg-brown-200" />

            {/* 계정 */}
            <div className="relative flex items-center gap-2">
              <span className="text-xs text-brown-400 shrink-0">계정</span>
              <button
                onClick={() => setShowAccountDropdown(p => !p)}
                className="rounded-lg border border-brown-200 bg-white px-3 py-1 text-xs text-brown-600 hover:border-brown-400 transition"
              >
                {searchAccounts.length === 0 ? '전체' : `${searchAccounts.length}개 선택`} ▾
              </button>
              {showAccountDropdown && availableAccounts.length > 0 && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowAccountDropdown(false)} />
                  <div className="absolute left-0 top-8 z-20 max-h-52 w-48 overflow-y-auto rounded-xl border border-brown-100 bg-white shadow-lg">
                  <button
                    onClick={() => setSearchAccounts([])}
                    className="w-full px-4 py-2 text-left text-xs text-brown-500 hover:bg-brown-50"
                  >
                    전체 선택 해제
                  </button>
                  {availableAccounts.map((acc) => (
                    <label key={acc} className="flex cursor-pointer items-center gap-2 px-4 py-2 text-xs text-brown-700 hover:bg-brown-50">
                      <input
                        type="checkbox"
                        checked={searchAccounts.includes(acc)}
                        onChange={() => setSearchAccounts(prev =>
                          prev.includes(acc) ? prev.filter(x => x !== acc) : [...prev, acc]
                        )}
                        className="accent-brown-600"
                      />
                      @{acc}
                    </label>
                  ))}
                </div>
                </>
              )}
            </div>

            {(searchSources.length > 0 || searchAccounts.length > 0 || searchDays !== 60) && (
              <button
                onClick={() => { setSearchSources([]); setSearchAccounts([]); setSearchDays(60) }}
                className="ml-auto text-xs text-brown-400 hover:text-brown-600 transition"
              >
                필터 초기화
              </button>
            )}
          </div>

          {searchQuery && (
            <div>
              <div className="mb-5 space-y-2">
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

      {/* ── 리포트 생성 모달 ── */}
      {showGenerateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-80 rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <h3 className="font-serif text-lg font-bold text-brown-700">리포트 생성</h3>
            <div className="space-y-2">
              <label className="text-sm text-brown-600">분석 기간</label>
              <select
                value={reportDays}
                onChange={e => setReportDays(Number(e.target.value))}
                className="w-full rounded-xl border border-brown-200 bg-white px-3 py-2.5 text-sm text-brown-600 outline-none focus:border-brown-400"
              >
                <option value={1}>최근 1일</option>
                <option value={2}>최근 2일</option>
                <option value={3}>최근 3일</option>
                <option value={7}>최근 1주</option>
                <option value={14}>최근 2주</option>
                <option value={30}>최근 1달</option>
                <option value={60}>최근 2달</option>
                <option value={0}>전체</option>
              </select>
              {reportPostCount !== null && (
                <p className={`text-xs ${reportPostCount < 50 ? 'text-red-400' : 'text-brown-400'}`}>
                  {reportPostCount < 50
                    ? `⚠ 데이터 부족 (${reportPostCount}개)`
                    : `${reportPostCount}개 포스트 기반`}
                </p>
              )}
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowGenerateModal(false)}
                className="rounded-xl border border-brown-200 px-4 py-2 text-sm text-brown-500 hover:bg-brown-50"
              >
                취소
              </button>
              <button
                onClick={() => {
                  setShowGenerateModal(false)
                  handleGenerateReport()
                }}
                className="rounded-xl bg-brown-600 px-4 py-2 text-sm font-medium text-cream-50 hover:bg-brown-700"
              >
                생성
              </button>
            </div>
          </div>
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
              <p className="mt-2 text-sm text-brown-400">AI가 분석한 20대 여성 패션 트렌드 리포트</p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <button
                onClick={() => setShowGenerateModal(true)}
                disabled={reportGenerating}
                className="rounded-xl bg-brown-600 px-6 py-3 text-sm font-medium text-cream-50 transition hover:bg-brown-700 disabled:opacity-50"
              >
                {reportGenerating ? 'Generating...' : '+ Generate Report'}
              </button>
              {reportStatusMessage && (
                <span className="text-xs text-brown-400">{reportStatusMessage}</span>
              )}
            </div>
          </div>

          {selectedReport ? (
            <div className="space-y-5">
              <button
                onClick={() => setSelectedReport(null)}
                className="flex items-center gap-2 text-sm text-brown-500 transition hover:text-brown-700"
              >
                ← Back to list
              </button>
              <div className="rounded-2xl bg-white p-8 shadow-sm space-y-6">
                <p className="text-xs tracking-widest text-brown-300 uppercase">
                  {selectedReport.period_start
                    ? `${selectedReport.period_start} — ${selectedReport.period_end}`
                    : `전체 기간 — ${selectedReport.period_end}`}
                </p>
                <h3 className="font-serif text-2xl font-bold text-brown-700">{selectedReport.summary}</h3>

                {/* 키워드 태그 */}
                {(() => {
                  const kws = typeof selectedReport.top_keywords === 'string'
                    ? JSON.parse(selectedReport.top_keywords)
                    : selectedReport.top_keywords
                  return Array.isArray(kws) && kws.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {kws.map((kw: string) => (
                        <span key={kw} className="rounded-full bg-brown-100 px-3 py-1 text-xs text-brown-600">{kw}</span>
                      ))}
                    </div>
                  ) : null
                })()}

                {/* 트렌드별 상세 */}
                <TrendList styleTrends={selectedReport.style_trends} />

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
        <div className="mx-auto max-w-7xl px-8 py-10 space-y-6">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="font-serif text-4xl font-bold uppercase tracking-wide text-brown-700">
                All Images
              </h2>
              <p className="mt-2 text-sm text-brown-400">수집된 전체 패션 이미지</p>
            </div>
            {/* 소스 필터 */}
            <div className="flex gap-1 rounded-xl bg-brown-100 p-1">
              {(['all', 'instagram', 'lookbook'] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setDataSource(s)}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                    dataSource === s
                      ? 'bg-white text-brown-700 shadow-sm'
                      : 'text-brown-400 hover:text-brown-600'
                  }`}
                >
                  {s === 'all' ? 'All' : s === 'instagram' ? 'Instagram' : 'Lookbook'}
                </button>
              ))}
            </div>
          </div>

          {allPostsLoading && allPosts.length === 0 ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {Array.from({ length: 20 }).map((_, i) => (
                <div key={i} className="aspect-[3/4] animate-pulse rounded-2xl bg-brown-100" />
              ))}
            </div>
          ) : allPosts.length === 0 ? (
            <div className="rounded-2xl border-2 border-dashed border-brown-200 p-16 text-center">
              <p className="font-serif text-xl text-brown-300">No images</p>
              <p className="mt-2 text-sm text-brown-300">크롤링을 먼저 실행해주세요</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                {allPosts.map((p) => (
                  <ImageCard
                    key={p.id}
                    imageUrl={p.image_url}
                    accountName={p.account_name}
                    source={p.source}
                    postedAt={p.posted_at}
                    captionAi={p.caption_ai}
                  />
                ))}
              </div>
              <div className="flex justify-center pt-4">
                <button
                  onClick={handleLoadMore}
                  disabled={allPostsLoading}
                  className="rounded-xl border border-brown-200 bg-white px-8 py-3 text-sm text-brown-600 transition hover:border-brown-400 disabled:opacity-40"
                >
                  {allPostsLoading ? '불러오는 중...' : '더 보기'}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <footer className="mt-20 border-t border-brown-200 bg-brown-700 py-10 text-center">
        <p className="font-serif text-2xl font-bold tracking-widest text-cream-50">CRAI</p>
        <p className="mt-1 text-xs text-brown-300">Curated Reference AI — 20대 여성 패션 인텔리전스</p>
      </footer>
    </div>
  )
}

function TrendList({ styleTrends }: { styleTrends: string | StyleTrend[] }) {
  const [images, setImages] = useState<Record<number, string>>({})
  const trends: StyleTrend[] = typeof styleTrends === 'string' ? JSON.parse(styleTrends) : styleTrends

  useEffect(() => {
    const allIds = trends.flatMap(t => t.representative_ids ?? [])
    if (allIds.length === 0) return
    fetch(`/api/posts/by-ids?ids=${allIds.join(',')}`)
      .then(r => r.json())
      .then((rows: { id: number; image_url: string }[]) => {
        const map: Record<number, string> = {}
        rows.forEach(r => { map[r.id] = r.image_url })
        setImages(map)
      })
      .catch(() => {})
  }, [])

  if (!Array.isArray(trends)) return null
  return (
    <div className="space-y-5">
      {trends.map((trend, i) => (
        <div key={i} className="rounded-xl bg-cream-100 p-5 space-y-3">
          <h4 className="font-serif text-base font-bold text-brown-700">{trend.title}</h4>
          <p className="text-sm leading-7 text-brown-600">{trend.content}</p>
          {trend.representative_ids?.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              {trend.representative_ids.map(id => images[id] ? (
                <img key={id} src={images[id]} className="h-36 w-28 object-cover rounded-lg" />
              ) : null)}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-brown-400">{label}</p>
      <p className="mt-0.5 text-lg font-semibold text-brown-700">{value}</p>
    </div>
  )
}
