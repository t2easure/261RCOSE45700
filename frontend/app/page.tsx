'use client'

import { useCallback, useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, RadarChart, Radar, PolarGrid, PolarAngleAxis } from 'recharts'
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

interface TopInfluencer {
  account_name: string
  followers: number
  engagement_rate: number
  image_url: string
}

interface MaterialDist {
  material: string
  pct: number
}

interface TrendCluster {
  trend_name: string
  description?: string
  post_count: number
  is_leading: boolean
  avg_engagement_rate: number
  representative_ids: number[]
  representative_images: string[]
  brand_ratio?: number
  signal_strength?: number
  signal_label?: 'opportunity' | 'growing' | 'saturated' | 'weak'
  top_influencers?: TopInfluencer[]
  material_dist?: MaterialDist[]
}

interface EngagementPost {
  id: number
  account_name: string
  image_url: string
  caption_ai: string
  posted_at: string | null
  likes: number
  comments: number
  followers: number
  engagement_rate: number
}

interface LeadSignal {
  trend_name: string
  status: string
  days_ahead: number | null
  first_influencer_at: string
  first_influencer: string
  first_brand_at?: string
  first_brand?: string
  representative_image: string
}

interface FashionReport {
  id: number
  created_at: string
  period_start: string
  period_end: string
  summary: string
  top_keywords: string | string[]
  style_trends: string | StyleTrend[]
  trend_clusters: string | TrendCluster[] | null
  engagement_top: string | EngagementPost[] | null
  lead_signals: string | LeadSignal[] | null
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

  // 이미지 검색
  const [imageCaption, setImageCaption] = useState<string | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [imageSearchLoading, setImageSearchLoading] = useState(false)

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
  const [reportDateFrom, setReportDateFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 30); return d.toISOString().slice(0, 10)
  })
  const [reportDateTo, setReportDateTo] = useState(() => new Date().toISOString().slice(0, 10))
  const [reportPostCount, setReportPostCount] = useState<number | null>(null)
  const [reportSubTab, setReportSubTab] = useState<'weekly' | 'monthly' | 'custom'>('weekly')
  const [lightbox, setLightbox] = useState<{ url: string; caption?: string } | null>(null)

  // 통계
  const [stats, setStats] = useState<Stats | null>(null)

  // 대시보드 최신 이미지
  const [recentPosts, setRecentPosts] = useState<Post[]>([])

  // 데이터 탭
  const [allPosts, setAllPosts] = useState<Post[]>([])
  const [allPostsLoading, setAllPostsLoading] = useState(false)
  const [dataSource, setDataSource] = useState<'all' | 'instagram' | 'lookbook'>('all')
  const [dataOffset, setDataOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const DATA_LIMIT = 40

  // 관리 탭
  const [instagramConfig, setInstagramConfig] = useState<{ brands: string[]; influencers: string[] } | null>(null)
  const [brandConfig, setBrandConfig] = useState<Record<string, string> | null>(null)
  const [newAccount, setNewAccount] = useState('')
  const [newAccountType, setNewAccountType] = useState<'brands' | 'influencers'>('influencers')
  const [newBrandKey, setNewBrandKey] = useState('')
  const [newBrandUrl, setNewBrandUrl] = useState('')

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
        setHasMore(items.length === DATA_LIMIT)
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
    if (tab === 'data') { setDataOffset(0); setHasMore(true); fetchAllPosts(dataSource, 0) }
  }, [tab, dataSource, fetchAllPosts])

  useEffect(() => {
    if (tab !== 'manage') return
    fetch('/api/config/instagram').then(r => r.json()).then(setInstagramConfig).catch(() => {})
    fetch('/api/config/brands').then(r => r.json()).then(setBrandConfig).catch(() => {})
  }, [tab])
  useEffect(() => {
    if (tab !== 'reports') return
    fetch(`/api/fashion-reports/count?start_date=${reportDateFrom}&end_date=${reportDateTo}`)
      .then(r => r.json())
      .then(d => setReportPostCount(d.count))
      .catch(() => {})
  }, [tab, reportDateFrom, reportDateTo])

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


  async function handleImageSearch(file: File) {
    setImageSearchLoading(true)
    setImagePreview(URL.createObjectURL(file))
    setSearchQuery('')
    setTab('search')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch('/api/search/image', { method: 'POST', body: formData })
      if (res.ok) {
        const data = await res.json()
        setImageCaption(data.caption ?? null)
        setSearchResults(data.results ?? [])
      }
    } catch {} finally { setImageSearchLoading(false) }
  }

  async function handleGenerateReport() {
    const days = Math.ceil((new Date(reportDateTo).getTime() - new Date(reportDateFrom).getTime()) / 86400000)
    if (reportPostCount !== null && reportPostCount < 50) {
      if (!window.confirm('데이터가 부족합니다. 이대로 진행할까요?')) return
    }
    setReportGenerating(true)
    setReportStatusMessage(null)
    try {
      await fetch('/api/fashion-reports/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days, start_date: reportDateFrom, end_date: reportDateTo }),
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

          <div className="rounded-2xl bg-white p-6 shadow-sm space-y-4">
            <SearchBar onSearch={handleSearch} loading={searchLoading} days={searchDays} />
            <div className="flex items-center gap-3">
              <div className="h-px flex-1 bg-brown-100" />
              <span className="text-xs text-brown-300">또는 이미지로 검색</span>
              <div className="h-px flex-1 bg-brown-100" />
            </div>
            <label className={`flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-brown-200 py-4 text-sm text-brown-400 transition hover:border-brown-400 hover:text-brown-600 ${imageSearchLoading ? 'opacity-50 pointer-events-none' : ''}`}>
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={e => { if (e.target.files?.[0]) handleImageSearch(e.target.files[0]) }}
              />
              {imageSearchLoading ? '이미지 분석 중...' : '📷 이미지 업로드'}
            </label>
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

          {imagePreview && (
            <div className="space-y-5">
              <div className="flex items-start gap-4 rounded-2xl bg-white p-5 shadow-sm">
                <img src={imagePreview} className="h-28 w-20 rounded-xl object-cover shrink-0" />
                <div className="space-y-1">
                  <p className="text-xs font-medium text-brown-500">업로드한 이미지 분석 결과</p>
                  {imageCaption && <p className="text-sm text-brown-700 leading-6">{imageCaption}</p>}
                  <p className="text-xs text-brown-400">{searchResults.length}개 유사 이미지</p>
                  <button onClick={() => { setImagePreview(null); setImageCaption(null); setSearchResults([]) }} className="text-xs text-brown-300 hover:text-brown-500">초기화</button>
                </div>
              </div>
              {imageSearchLoading ? (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                  {Array.from({ length: 10 }).map((_, i) => (
                    <div key={i} className="aspect-[3/4] animate-pulse rounded-2xl bg-brown-100" />
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                  {searchResults.map((r) => (
                    <ImageCard key={r.id} imageUrl={r.image_url} accountName={r.account_name} source={r.source} postedAt={r.posted_at} captionAi={r.caption_ai} similarity={r.similarity} />
                  ))}
                </div>
              )}
            </div>
          )}

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
            {reportStatusMessage && (
              <span className="text-xs text-brown-400">{reportStatusMessage}</span>
            )}
          </div>

          {/* 서브탭 */}
          {!selectedReport && (
            <div className="flex gap-1 rounded-2xl bg-brown-100 p-1 w-fit">
              {([['weekly', 'Weekly'], ['monthly', 'Monthly'], ['custom', 'Custom']] as const).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setReportSubTab(key)}
                  className={`rounded-xl px-5 py-2 text-sm font-medium transition ${
                    reportSubTab === key
                      ? 'bg-white text-brown-700 shadow-sm'
                      : 'text-brown-400 hover:text-brown-600'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* 라이트박스 모달 */}
          {lightbox && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setLightbox(null)}>
              <div className="relative max-w-lg w-full" onClick={e => e.stopPropagation()}>
                <img src={lightbox.url} className="w-full max-h-[70vh] object-contain rounded-2xl shadow-2xl" />
                {lightbox.caption && (
                  <div className="mt-3 rounded-xl bg-white/90 px-4 py-3 text-xs text-brown-700 leading-5 max-h-36 overflow-y-auto">
                    {lightbox.caption}
                  </div>
                )}
                <button onClick={() => setLightbox(null)} className="absolute -top-3 -right-3 bg-white rounded-full w-8 h-8 flex items-center justify-center shadow text-brown-500 hover:text-brown-800 text-lg font-bold">×</button>
              </div>
            </div>
          )}

          {selectedReport ? (
            <div className="space-y-10">
              <div className="flex items-center justify-between">
                <button onClick={() => setSelectedReport(null)} className="flex items-center gap-2 text-sm text-brown-500 transition hover:text-brown-700">
                  ← 목록으로
                </button>
                <button
                  onClick={async () => {
                    if (!confirm('이 리포트를 삭제할까요?')) return
                    await fetch(`/api/fashion-reports/${selectedReport.id}`, { method: 'DELETE' })
                    setSelectedReport(null)
                    fetchReports()
                  }}
                  className="rounded-lg px-3 py-1.5 text-xs text-brown-300 hover:bg-red-50 hover:text-red-400 transition-colors"
                >
                  리포트 삭제
                </button>
              </div>

              {/* 헤더 */}
              <div className="rounded-2xl bg-white p-6 shadow-sm space-y-2">
                {(() => {
                  const clusters: TrendCluster[] = selectedReport.trend_clusters
                    ? (typeof selectedReport.trend_clusters === 'string' ? JSON.parse(selectedReport.trend_clusters) : selectedReport.trend_clusters)
                    : []
                  const topKeywords: string[] = selectedReport.top_keywords
                    ? (typeof selectedReport.top_keywords === 'string' ? JSON.parse(selectedReport.top_keywords) : selectedReport.top_keywords)
                    : []
                  const period = selectedReport.period_start
                    ? `${selectedReport.period_start?.slice(0,10)} ~ ${selectedReport.period_end?.slice(0,10)}`
                    : selectedReport.period_end?.slice(0,10)
                  const title = `패션 트렌드 리포트 · ${period}`
                  return (
                    <>
                      <p className="text-[10px] tracking-widest text-brown-300 uppercase font-medium">{selectedReport.post_count}개 이미지 분석</p>
                      <h2 className="font-serif text-2xl font-bold text-brown-800">{title}</h2>
                      {clusters.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {clusters.map((c, i) => (
                            <span key={i} className="rounded-full bg-brown-100 px-2.5 py-0.5 text-[11px] text-brown-600">{c.trend_name}</span>
                          ))}
                        </div>
                      )}
                      <p className="text-sm leading-7 text-brown-600 pt-2 border-t border-brown-50">{selectedReport.summary}</p>
                    </>
                  )
                })()}
              </div>

              {/* WoW 비교 섹션 — 추후 구현 예정 */}
              {false && (() => {
                const currentIdx = reports.findIndex(r => r.id === selectedReport.id)
                const prevReport = currentIdx >= 0 && currentIdx < reports.length - 1 ? reports[currentIdx + 1] : null
                if (!prevReport) return null

                const parseClusters = (r: FashionReport): TrendCluster[] =>
                  r.trend_clusters ? (typeof r.trend_clusters === 'string' ? JSON.parse(r.trend_clusters) : r.trend_clusters) : []

                const curr = parseClusters(selectedReport)
                const prev = parseClusters(prevReport)
                if (!curr.length || !prev.length) return null

                const currNames = curr.map(c => c.trend_name)
                const prevNames = prev.map(c => c.trend_name)

                const newTrends = curr.filter(c => !prevNames.includes(c.trend_name))
                const maintained = curr.filter(c => prevNames.includes(c.trend_name))
                const disappeared = prev.filter(c => !currNames.includes(c.trend_name))

                const currAvg = curr.reduce((s, c) => s + c.avg_engagement_rate, 0) / curr.length
                const prevAvg = prev.reduce((s, c) => s + c.avg_engagement_rate, 0) / prev.length
                const engDiff = ((currAvg - prevAvg) / prevAvg * 100)

                return (
                  <div className="space-y-2">
                    <h3 className="font-serif text-xl font-bold text-brown-700">주간 변화 비교</h3>
                    <p className="text-xs text-brown-400">직전 리포트({prevReport.period_start?.slice(0,10)} ~ {prevReport.period_end?.slice(0,10)})와 이번 리포트의 트렌드 변화를 비교합니다.</p>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 pt-1">
                      <div className="rounded-2xl bg-white p-4 shadow-sm text-center">
                        <p className="text-2xl font-bold text-green-600">{newTrends.length}</p>
                        <p className="text-xs text-brown-400 mt-1">신규 트렌드</p>
                      </div>
                      <div className="rounded-2xl bg-white p-4 shadow-sm text-center">
                        <p className="text-2xl font-bold text-blue-600">{maintained.length}</p>
                        <p className="text-xs text-brown-400 mt-1">유지 트렌드</p>
                      </div>
                      <div className="rounded-2xl bg-white p-4 shadow-sm text-center">
                        <p className="text-2xl font-bold text-brown-400">{disappeared.length}</p>
                        <p className="text-xs text-brown-400 mt-1">사라진 트렌드</p>
                      </div>
                      <div className="rounded-2xl bg-white p-4 shadow-sm text-center">
                        <p className={`text-2xl font-bold ${engDiff >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                          {engDiff >= 0 ? '+' : ''}{engDiff.toFixed(1)}%
                        </p>
                        <p className="text-xs text-brown-400 mt-1">평균 참여율 변화</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 pt-1">
                      {newTrends.length > 0 && (
                        <div className="rounded-2xl bg-green-50 p-4 space-y-1.5">
                          <p className="text-xs font-semibold text-green-700">신규 등장</p>
                          {newTrends.map((c, i) => <p key={i} className="text-sm text-green-800">+ {c.trend_name}</p>)}
                        </div>
                      )}
                      {maintained.length > 0 && (
                        <div className="rounded-2xl bg-blue-50 p-4 space-y-1.5">
                          <p className="text-xs font-semibold text-blue-700">지속 유지</p>
                          {maintained.map((c, i) => {
                            const prevC = prev.find(p => p.trend_name === c.trend_name)
                            const diff = prevC ? ((c.avg_engagement_rate - prevC.avg_engagement_rate) / (prevC.avg_engagement_rate || 1) * 100) : 0
                            return <p key={i} className="text-sm text-blue-800">= {c.trend_name} <span className={diff >= 0 ? 'text-green-600' : 'text-red-500'}>{diff >= 0 ? '↑' : '↓'}{Math.abs(diff).toFixed(0)}%</span></p>
                          })}
                        </div>
                      )}
                      {disappeared.length > 0 && (
                        <div className="rounded-2xl bg-brown-50 p-4 space-y-1.5">
                          <p className="text-xs font-semibold text-brown-500">소멸</p>
                          {disappeared.map((c, i) => <p key={i} className="text-sm text-brown-400">− {c.trend_name}</p>)}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })()}

              {/* 1섹션: 트렌드 레이더 */}
              {(() => {
                const clusters: TrendCluster[] = selectedReport.trend_clusters
                  ? (typeof selectedReport.trend_clusters === 'string' ? JSON.parse(selectedReport.trend_clusters) : selectedReport.trend_clusters)
                  : []
                if (!clusters.length) return null
                return (
                  <div className="space-y-2">
                    <h3 className="font-serif text-xl font-bold text-brown-700">Trend Radar</h3>
                    <p className="text-xs text-brown-400">AI가 수집된 이미지를 자동 분류한 이번 시즌 핵심 스타일 클러스터입니다. 이미지를 클릭하면 확대해서 볼 수 있어요.</p>
                    <div className="rounded-xl bg-brown-50 px-3 py-2.5 text-[11px] text-brown-400 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span className="font-medium text-brown-600">★ 트렌드 지수 (0~10점)</span>
                        <span>= 게시물 수(0~3) + 인플루언서 참여율(0~3) + 브랜드 미진입(0~2) + 선행일수(0~2)</span>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 pt-0.5 border-t border-brown-100">
                        <span><span className="font-medium text-orange-500">🔥 지금 올라타 ≥8</span> — 반응 뜨겁고 아직 브랜드가 안 들어온 초기 트렌드</span>
                        <span><span className="font-medium text-green-600">📈 뜨는 중 ≥5</span> — 볼륨과 참여율이 오르고 있는 성장 구간</span>
                        <span><span className="font-medium text-yellow-600">⚠️ 이미 많음</span> — 브랜드 게시물 비율 40%↑, 이미 상업화된 트렌드</span>
                        <span><span className="font-medium text-blue-400">👀 관망 3~5</span> — 볼륨은 있지만 참여율·브랜드 채택 데이터 불분명</span>
                        <span><span className="font-medium text-stone-400">💤 미미함 &lt;3</span> — 볼륨·참여율 모두 낮아 아직 신호 약한 트렌드</span>
                      </div>
                    </div>
                    {(() => {
                      const SIGNAL_META: Record<string, { label: string; icon: string; cls: string }> = {
                        opportunity: { label: '지금 올라타', icon: '🔥', cls: 'bg-orange-100 text-orange-600' },
                        growing:     { label: '뜨는 중', icon: '📈', cls: 'bg-green-100 text-green-600' },
                        saturated:   { label: '이미 많음', icon: '⚠️', cls: 'bg-yellow-100 text-yellow-600' },
                        moderate:    { label: '관망', icon: '👀', cls: 'bg-blue-50 text-blue-400' },
                        weak:        { label: '미미함', icon: '💤', cls: 'bg-stone-100 text-stone-500' },
                      }
                      return (
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 pt-1">
                          {clusters.map((c, i) => {
                            const brandRatio = c.brand_ratio ?? 0
                            const isSaturated = c.brand_ratio != null && brandRatio > 0.4
                            const sigLabel: string | null = isSaturated ? 'saturated'
                              : c.signal_strength == null ? null
                              : c.signal_strength >= 8 ? 'opportunity'
                              : c.signal_strength >= 5 ? 'growing'
                              : c.signal_strength >= 3 ? 'moderate'
                              : 'weak'
                            const sig = sigLabel ? SIGNAL_META[sigLabel] : null
                            const hasBrandRatio = c.brand_ratio != null
                            const radarData = [
                              { axis: '볼륨', value: Math.min((c.post_count / 50) * 100, 100) },
                              { axis: '참여율', value: Math.min((c.avg_engagement_rate / 0.02) * 100, 100) },
                              { axis: '미채택', value: Math.min((1 - brandRatio) * 100, 100) },
                              { axis: '선행성', value: c.signal_strength != null ? Math.max(0, Math.min(((c.signal_strength - Math.min(c.post_count/50*3,3) - Math.min(c.avg_engagement_rate/0.02*3,3) - (hasBrandRatio ? (1-brandRatio)*2 : 0)) / 2) * 100, 100)) : 0 },
                            ]
                            return (
                              <div key={i} className="rounded-2xl bg-white p-4 shadow-sm space-y-3">
                                {/* 헤더: 트렌드명 + 신호 배지 */}
                                <div className="flex items-start justify-between gap-2">
                                  <p className="font-semibold text-sm text-brown-800 leading-snug">{c.trend_name}</p>
                                  {sig && (
                                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${sig.cls}`}>
                                      {sig.icon} {sig.label}
                                    </span>
                                  )}
                                </div>

                                {/* 대표 이미지 */}
                                <div className="flex gap-1.5">
                                  {c.representative_images.slice(0, 3).map((url, j) => (
                                    <img
                                      key={j} src={url}
                                      className="h-28 w-0 flex-1 rounded-lg object-cover cursor-pointer hover:opacity-80 transition-opacity"
                                      title={c.description || c.trend_name}
                                      onClick={() => setLightbox({ url, caption: c.description })}
                                      onError={e => (e.currentTarget.style.display='none')}
                                    />
                                  ))}
                                </div>

                                {c.description && (
                                  <p className="text-[12px] leading-5 text-brown-500">{c.description}</p>
                                )}

                                {/* 트렌드 지수 레이더 */}
                                {c.signal_strength != null && (
                                  <div className="border-t border-brown-50 pt-2 space-y-1">
                                    <div className="flex items-center gap-2">
                                      <p className="text-xl font-bold text-brown-700">★ {c.signal_strength.toFixed(1)}</p>
                                      <div className="text-[11px] text-brown-400">
                                        <p>게시물 {c.post_count}개</p>
                                        {c.avg_engagement_rate > 0 && <p>참여율 {(c.avg_engagement_rate * 100).toFixed(1)}%</p>}
                                      </div>
                                    </div>
                                    <ResponsiveContainer width="100%" height={160}>
                                      <RadarChart data={radarData} outerRadius={50} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
                                        <PolarGrid stroke="#e5d9cf" />
                                        <PolarAngleAxis dataKey="axis" tick={{ fontSize: 10, fill: '#a08070' }} />
                                        <Radar dataKey="value" stroke="#c97b4b" fill="#c97b4b" fillOpacity={0.3} />
                                      </RadarChart>
                                    </ResponsiveContainer>
                                  </div>
                                )}

                                {/* 소재 분포 */}
                                {c.material_dist && c.material_dist.length > 0 && (
                                  <div className="border-t border-brown-50 pt-2">
                                    <p className="text-[10px] text-brown-300 uppercase tracking-wide mb-1">소재</p>
                                    <div className="flex flex-wrap gap-1">
                                      {c.material_dist.slice(0, 4).map((m, mi) => (
                                        <span key={mi} className="rounded-full bg-brown-50 px-2 py-0.5 text-[11px] text-brown-500">
                                          {m.material} {m.pct}%
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* TOP 3 인플루언서 */}
                                {c.top_influencers && c.top_influencers.length > 0 && (
                                  <div className="border-t border-brown-50 pt-2">
                                    <p className="text-[10px] text-brown-300 uppercase tracking-wide mb-1.5">Top Influencers</p>
                                    <div className="space-y-1.5">
                                      {c.top_influencers.slice(0, 3).map((inf, ii) => (
                                        <div key={ii} className="flex items-center gap-2">
                                          {inf.image_url && (
                                            <img src={inf.image_url} className="h-7 w-7 rounded-full object-cover shrink-0" onError={e => (e.currentTarget.style.display='none')} />
                                          )}
                                          <div className="min-w-0">
                                            <p className="text-[11px] text-brown-700 font-medium truncate">@{inf.account_name}</p>
                                            <p className="text-[10px] text-brown-400">{(inf.engagement_rate * 100).toFixed(1)}% eng</p>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* 트렌드 지수 없을 때 기본 통계 */}
                                {c.signal_strength == null && (
                                  <div className="flex gap-3 text-[11px] text-brown-400 border-t border-brown-50 pt-2">
                                    <span>게시물 {c.post_count}개</span>
                                    {c.avg_engagement_rate > 0 && (
                                      <span>평균 참여율 {(c.avg_engagement_rate * 100).toFixed(1)}%</span>
                                    )}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )
                    })()}
                  </div>
                )
              })()}

              {/* 2섹션: 인플루언서 선행 지수 — 월간(20일↑)에만 표시 */}
              {(() => {
                const periodDays = selectedReport.period_start && selectedReport.period_end
                  ? Math.round((new Date(selectedReport.period_end).getTime() - new Date(selectedReport.period_start).getTime()) / 86400000)
                  : 30
                if (periodDays < 20) return null
                const signals: LeadSignal[] = selectedReport.lead_signals
                  ? (typeof selectedReport.lead_signals === 'string' ? JSON.parse(selectedReport.lead_signals) : selectedReport.lead_signals)
                  : []
                if (!signals.length) return null
                return (
                  <div className="space-y-2">
                    <h3 className="font-serif text-xl font-bold text-brown-700">인플루언서 선행 지수</h3>
                    <p className="text-xs text-brown-400">브랜드보다 인플루언서가 먼저 입은 스타일을 추적합니다. 선행 일수가 클수록 아직 상업화되지 않은 조기 트렌드입니다.</p>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 pt-1">
                      {signals.map((s, i) => (
                        <div key={i} className="rounded-2xl bg-white shadow-sm overflow-hidden flex">
                          {s.representative_image && (
                            <img
                              src={s.representative_image}
                              className="h-36 w-28 object-cover shrink-0 cursor-pointer hover:opacity-80 transition-opacity"
                              title={s.trend_name}
                              onClick={() => setLightbox({ url: s.representative_image, caption: `${s.trend_name} — @${s.first_influencer}` })}
                              onError={e => (e.currentTarget.style.display='none')}
                            />
                          )}
                          <div className="flex flex-col justify-between p-4 flex-1 min-w-0">
                            <div>
                              <p className="text-sm font-semibold text-brown-800 leading-snug">{s.trend_name}</p>
                              <p className="text-xs text-brown-400 mt-1">최초 인플루언서: @{s.first_influencer}</p>
                              <p className="text-xs text-brown-400">{s.first_influencer_at?.slice(0,10)}</p>
                              {s.first_brand && (
                                <p className="text-xs text-brown-400 mt-1">브랜드 출현: @{s.first_brand}<br/>{s.first_brand_at?.slice(0,10)}</p>
                              )}
                            </div>
                            <span className={`mt-3 self-start rounded-full px-3 py-1 text-xs font-semibold ${s.status === '브랜드 미출현' ? 'bg-orange-100 text-orange-600' : 'bg-blue-100 text-blue-600'}`}>
                              {s.status}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}

              {/* 3섹션: Engagement 폭발 스타일 */}
              {(() => {
                const posts: EngagementPost[] = selectedReport.engagement_top
                  ? (typeof selectedReport.engagement_top === 'string' ? JSON.parse(selectedReport.engagement_top) : selectedReport.engagement_top)
                  : []
                if (!posts.length) return null
                return (
                  <div className="space-y-2">
                    <h3 className="font-serif text-xl font-bold text-brown-700">Engagement 폭발 스타일</h3>
                    <p className="text-xs text-brown-400">팔로워 대비 (좋아요 + 댓글) 비율이 가장 높은 게시물입니다. 실제 소비자 반응이 뜨거운 스타일을 한눈에 확인하세요.</p>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 pt-1">
                      {posts.map((p, i) => (
                        <div key={p.id} className="rounded-2xl bg-white shadow-sm overflow-hidden flex flex-col">
                          <div className="relative">
                            <img
                              src={p.image_url}
                              className="w-full aspect-[3/4] object-cover cursor-pointer hover:opacity-80 transition-opacity"
                              title={p.caption_ai ?? undefined}
                              onClick={() => setLightbox({ url: p.image_url, caption: p.caption_ai ?? undefined })}
                              onError={e => (e.currentTarget.style.display='none')}
                            />
                            <span className="absolute top-2 left-2 bg-black/50 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center">{i+1}</span>
                          </div>
                          <div className="p-2.5 flex flex-col gap-1 flex-1">
                            <p className="text-[11px] font-semibold text-brown-700">@{p.account_name}</p>
                            <p className="text-[10px] text-brown-500 leading-4 line-clamp-2 flex-1">{p.caption_ai}</p>
                            <div className="border-t border-brown-50 pt-1.5 mt-1">
                              <p className="text-sm font-bold text-brown-800">{(p.engagement_rate * 100).toFixed(1)}%</p>
                              <p className="text-[9px] text-brown-400">참여율 · ❤ {p.likes?.toLocaleString()}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}
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
          ) : (() => {
            const PALETTE = [
              { bg: '#f0e6d3', text: '#8b5e3c', border: '#d4a574' },
              { bg: '#dce8dc', text: '#3a6b3a', border: '#7fb57f' },
              { bg: '#dde4f0', text: '#3a4f7a', border: '#7a9acc' },
              { bg: '#f0dde8', text: '#7a3a5a', border: '#cc7a9a' },
              { bg: '#f0f0dd', text: '#5a5a1a', border: '#aaaa5a' },
              { bg: '#e8dddd', text: '#6b3a3a', border: '#bb7a7a' },
            ]

            const getPeriodDays = (r: FashionReport) =>
              r.period_start && r.period_end
                ? Math.round((new Date(r.period_end).getTime() - new Date(r.period_start).getTime()) / 86400000)
                : null

            // 서브탭에 따라 필터링 (custom은 전체)
            const filteredReports = reportSubTab === 'weekly'
              ? reports.filter(r => { const d = getPeriodDays(r); return d === null || d < 20 })
              : reportSubTab === 'monthly'
              ? reports.filter(r => { const d = getPeriodDays(r); return d !== null && d >= 20 })
              : reports

            const sorted = [...filteredReports].reverse()

            const kwCount: Record<string, number> = {}
            sorted.forEach(r => {
              const kws: string[] = r.top_keywords
                ? (typeof r.top_keywords === 'string' ? JSON.parse(r.top_keywords) : r.top_keywords)
                : []
              kws.forEach(k => { kwCount[k] = (kwCount[k] ?? 0) + 1 })
            })
            const recurring = Object.entries(kwCount)
              .filter(([, cnt]) => cnt >= 2)
              .map(([k]) => k)
            const kwColor: Record<string, typeof PALETTE[0]> = {}
            recurring.forEach((k, i) => { kwColor[k] = PALETTE[i % PALETTE.length] })

            const chartData = sorted.map(r => {
              const clusters: TrendCluster[] = r.trend_clusters
                ? (typeof r.trend_clusters === 'string' ? JSON.parse(r.trend_clusters) : r.trend_clusters)
                : []
              const avgSignal = clusters.length > 0 && clusters[0].signal_strength != null
                ? parseFloat((clusters.reduce((s, c) => s + (c.signal_strength ?? 0), 0) / clusters.length).toFixed(2))
                : null
              return {
                label: r.period_end?.slice(0, 10) ?? r.created_at.slice(0, 10),
                포스트수: r.post_count,
                평균신호강도: avgSignal,
              }
            })

            return (
              <div className="space-y-6">
                {/* 키워드 타임라인 + 시계열: weekly/monthly만 표시 */}
                {reportSubTab !== 'custom' && <>
                <div className="rounded-2xl bg-white p-6 shadow-sm">
                  <p className="text-sm font-semibold text-brown-700 mb-1">트렌드 키워드 타임라인</p>
                  <p className="text-xs text-brown-400 mb-5">같은 색 태그는 여러 리포트에 반복 등장한 키워드입니다</p>
                  <div className="space-y-0">
                    {sorted.map((r, ri) => {
                      const kws: string[] = r.top_keywords
                        ? (typeof r.top_keywords === 'string' ? JSON.parse(r.top_keywords) : r.top_keywords)
                        : []
                      const label = r.period_start
                        ? `${r.period_start.slice(5, 10)} ~ ${r.period_end?.slice(5, 10)}`
                        : r.period_end?.slice(0, 10) ?? r.created_at.slice(0, 10)
                      return (
                        <div key={r.id} className="flex items-start gap-4 group">
                          {/* 타임라인 축 */}
                          <div className="flex flex-col items-center w-28 shrink-0 pt-1">
                            <span className="text-[11px] text-brown-500 font-medium whitespace-nowrap">{label}</span>
                            {ri < sorted.length - 1 && (
                              <div className="w-px flex-1 bg-brown-200 mt-1 min-h-[28px]" />
                            )}
                          </div>
                          {/* 키워드 태그들 */}
                          <div className="flex flex-wrap gap-2 pb-5 pt-0.5">
                            {kws.map(kw => {
                              const color = kwColor[kw]
                              return color ? (
                                <span key={kw} style={{ background: color.bg, color: color.text, borderColor: color.border }}
                                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border">
                                  {kw}
                                </span>
                              ) : (
                                <span key={kw}
                                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-stone-100 text-stone-400 border border-stone-200">
                                  {kw}
                                </span>
                              )
                            })}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* 시계열 차트 */}
                <div className="rounded-2xl bg-white p-6 shadow-sm space-y-4">
                  <p className="text-sm font-semibold text-brown-700">리포트 시계열 추이</p>
                  <div>
                    <p className="text-xs text-brown-400 mb-2">분석 포스트 수</p>
                    <ResponsiveContainer width="100%" height={100}>
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0ebe4" />
                        <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#a89880' }} />
                        <YAxis tick={{ fontSize: 10, fill: '#a89880' }} width={35} />
                        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                        <Line type="monotone" dataKey="포스트수" stroke="#8b6f4e" strokeWidth={2} dot={{ r: 4 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div>
                    <p className="text-xs text-brown-400 mb-2">평균 트렌드 지수 (★ 0~10)</p>
                    <ResponsiveContainer width="100%" height={100}>
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0ebe4" />
                        <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#a89880' }} />
                        <YAxis domain={[0, 10]} tick={{ fontSize: 10, fill: '#a89880' }} width={35} />
                        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} formatter={(v: number) => [`★ ${v}`]} />
                        <Line type="monotone" dataKey="평균신호강도" stroke="#c07850" strokeWidth={2} dot={{ r: 4 }} connectNulls={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                </>}
                {/* 서브탭별 콘텐츠 */}
                {(() => {
                  const getPeriodDays = (r: FashionReport) =>
                    r.period_start && r.period_end
                      ? Math.round((new Date(r.period_end).getTime() - new Date(r.period_start).getTime()) / 86400000)
                      : null

                  const weekly  = reports.filter(r => { const d = getPeriodDays(r); return d === null || d < 20 })
                  const monthly = reports.filter(r => { const d = getPeriodDays(r); return d !== null && d >= 20 })
                  const custom  = reports.filter(r => { const d = getPeriodDays(r); return d !== null && d >= 7 && d < 20 === false && d !== 7 })

                  const ReportCard = ({ r, prevR }: { r: FashionReport; prevR?: FashionReport }) => {
                    const keywords: string[] = r.top_keywords
                      ? (typeof r.top_keywords === 'string' ? JSON.parse(r.top_keywords) : r.top_keywords)
                      : []
                    const prevKeywords: string[] = prevR?.top_keywords
                      ? (typeof prevR.top_keywords === 'string' ? JSON.parse(prevR.top_keywords) : prevR.top_keywords)
                      : []
                    const periodStr = r.period_start
                      ? `${r.period_start.slice(5,10)} ~ ${r.period_end?.slice(5,10)}`
                      : r.period_end?.slice(0,10) ?? ''
                    const periodDays = r.period_start && r.period_end
                      ? Math.round((new Date(r.period_end).getTime() - new Date(r.period_start).getTime()) / 86400000)
                      : null
                    const periodTag = periodDays === null ? null : periodDays >= 20 ? '월간' : '주간'

                    // 리포트 평균 신호강도
                    const clusters: TrendCluster[] = r.trend_clusters
                      ? (typeof r.trend_clusters === 'string' ? JSON.parse(r.trend_clusters) : r.trend_clusters)
                      : []
                    const avgSignal = clusters.length > 0 && clusters[0].signal_strength !== undefined
                      ? clusters.reduce((s, c) => s + (c.signal_strength ?? 0), 0) / clusters.length
                      : null
                    const maxSignal = clusters.length > 0 && clusters[0].signal_strength !== undefined
                      ? Math.max(...clusters.map(c => c.signal_strength ?? 0))
                      : null

                    // 키워드 순위 변화 계산
                    const getRankChange = (kw: string) => {
                      const prevIdx = prevKeywords.indexOf(kw)
                      const currIdx = keywords.indexOf(kw)
                      if (prevIdx === -1) return 'new'
                      const diff = prevIdx - currIdx
                      if (diff > 0) return `↑${diff}`
                      if (diff < 0) return `↓${Math.abs(diff)}`
                      return '→'
                    }

                    return (
                      <div className="flex w-full items-center gap-2 rounded-2xl bg-white px-4 py-4 shadow-sm transition hover:shadow-md">
                        <button className="flex flex-1 items-start text-left min-w-0" onClick={() => setSelectedReport(r)}>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-0.5">
                              <p className="text-[11px] text-brown-300">{periodStr}</p>
                              {periodTag && (
                                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${periodTag === '월간' ? 'bg-blue-100 text-blue-500' : 'bg-green-100 text-green-600'}`}>
                                  {periodTag}
                                </span>
                              )}
                              {maxSignal !== null && (
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                                  maxSignal >= 8 ? 'bg-orange-100 text-orange-600' :
                                  maxSignal >= 5 ? 'bg-green-100 text-green-600' :
                                  maxSignal >= 3 ? 'bg-yellow-100 text-yellow-600' :
                                  'bg-stone-100 text-stone-400'
                                }`}>★ {maxSignal.toFixed(1)}</span>
                              )}
                            </div>
                            <p className="text-sm font-semibold text-brown-800 leading-snug">{keywords[0] ?? '트렌드 리포트'}</p>
                            {keywords.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1.5">
                                {keywords.slice(0, 4).map((k, i) => {
                                  const change = getRankChange(k)
                                  return (
                                    <span key={i} className="inline-flex items-center gap-0.5 rounded-full bg-cream-200 px-2 py-0.5 text-[10px] text-brown-500">
                                      {k}
                                      {prevKeywords.length > 0 && (
                                        <span className={`font-bold text-[9px] ${
                                          change === 'new' ? 'text-blue-500' :
                                          change.startsWith('↑') ? 'text-green-500' :
                                          change.startsWith('↓') ? 'text-red-400' : 'text-brown-300'
                                        }`}>{change === 'new' ? 'NEW' : change}</span>
                                      )}
                                    </span>
                                  )
                                })}
                              </div>
                            )}
                            <p className="mt-1.5 text-[11px] text-brown-300">{r.post_count}개 분석</p>
                          </div>
                        </button>
                        <button
                          onClick={async () => {
                            if (!confirm('이 리포트를 삭제할까요?')) return
                            await fetch(`/api/fashion-reports/${r.id}`, { method: 'DELETE' })
                            fetchReports()
                          }}
                          className="shrink-0 rounded-lg p-1.5 text-xs text-brown-200 hover:bg-red-50 hover:text-red-400 transition-colors"
                        >✕</button>
                      </div>
                    )
                  }

                  if (reportSubTab === 'weekly') return (
                    <div className="space-y-2">
                      {weekly.length === 0
                        ? <p className="text-xs text-brown-300 text-center py-12">주간 리포트 없음</p>
                        : weekly.map(r => <ReportCard key={r.id} r={r} />)
                      }
                    </div>
                  )

                  if (reportSubTab === 'monthly') return (
                    <div className="space-y-2">
                      {monthly.length === 0
                        ? <p className="text-xs text-brown-300 text-center py-12">월간 리포트 없음</p>
                        : monthly.map(r => <ReportCard key={r.id} r={r} />)
                      }
                    </div>
                  )

                  // Custom 탭
                  return (
                    <div className="space-y-6">
                      {/* 생성 패널 */}
                      <div className="rounded-2xl bg-white p-6 shadow-sm space-y-4">
                        <p className="text-sm font-semibold text-brown-700">날짜 범위 선택</p>
                        <div className="flex items-center gap-3">
                          <div className="flex-1 space-y-1">
                            <p className="text-[11px] text-brown-400">시작일</p>
                            <input type="date" value={reportDateFrom} max={reportDateTo}
                              onChange={e => setReportDateFrom(e.target.value)}
                              className="w-full rounded-xl border border-brown-200 px-3 py-2 text-sm text-brown-700 outline-none focus:border-brown-400" />
                          </div>
                          <span className="text-brown-300 mt-5">—</span>
                          <div className="flex-1 space-y-1">
                            <p className="text-[11px] text-brown-400">종료일</p>
                            <input type="date" value={reportDateTo} min={reportDateFrom}
                              max={new Date().toISOString().slice(0,10)}
                              onChange={e => setReportDateTo(e.target.value)}
                              className="w-full rounded-xl border border-brown-200 px-3 py-2 text-sm text-brown-700 outline-none focus:border-brown-400" />
                          </div>
                        </div>
                        <div className="flex gap-1.5 flex-wrap">
                          {[{ label: '1주', days: 7 }, { label: '2주', days: 14 }, { label: '1달', days: 30 }, { label: '2달', days: 60 }].map(({ label, days }) => (
                            <button key={label}
                              onClick={() => {
                                const to = new Date().toISOString().slice(0,10)
                                const from = new Date(Date.now() - days * 86400000).toISOString().slice(0,10)
                                setReportDateFrom(from); setReportDateTo(to)
                              }}
                              className="rounded-full border border-brown-200 px-3 py-1 text-xs text-brown-500 hover:bg-brown-50"
                            >최근 {label}</button>
                          ))}
                        </div>
                        <div className="flex items-center justify-between">
                          {reportPostCount !== null && (
                            <p className={`text-xs ${reportPostCount < 50 ? 'text-red-400' : 'text-brown-400'}`}>
                              {reportPostCount < 50 ? `⚠ 데이터 부족 (${reportPostCount}개)` : `${reportPostCount}개 포스트 기반`}
                            </p>
                          )}
                          <button
                            onClick={handleGenerateReport}
                            disabled={reportGenerating}
                            className="ml-auto rounded-xl bg-brown-600 px-6 py-2.5 text-sm font-medium text-cream-50 hover:bg-brown-700 disabled:opacity-50 transition"
                          >
                            {reportGenerating ? 'Generating...' : '+ Generate Report'}
                          </button>
                        </div>
                      </div>
                      {/* 커스텀 리포트 목록 (전체, 최신순) */}
                      <div className="space-y-2">
                        {reports.length === 0
                          ? <p className="text-xs text-brown-300 text-center py-8">아직 생성된 리포트 없음</p>
                          : reports.map(r => <ReportCard key={r.id} r={r} />)
                        }
                      </div>
                    </div>
                  )
                })()}
              </div>
          )
          })()}
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
              {hasMore && (
                <div className="flex justify-center pt-4">
                  <button
                    onClick={handleLoadMore}
                    disabled={allPostsLoading}
                    className="rounded-xl border border-brown-200 bg-white px-8 py-3 text-sm text-brown-600 transition hover:border-brown-400 disabled:opacity-40"
                  >
                    {allPostsLoading ? '불러오는 중...' : '더 보기'}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── 관리 ── */}
      {tab === 'manage' && (
        <div className="mx-auto max-w-5xl px-8 py-10 space-y-10">
          <div>
            <h2 className="font-serif text-4xl font-bold uppercase tracking-wide text-brown-700">Manage</h2>
            <p className="mt-2 text-sm text-brown-400">수집 대상 계정 및 브랜드 URL 관리</p>
          </div>

          {/* Instagram 계정 */}
          <div className="rounded-2xl bg-white p-6 shadow-sm space-y-6">
            <h3 className="font-serif text-xl font-bold text-brown-700">Instagram 계정</h3>

            {(['influencers', 'brands'] as const).map((type) => (
              <div key={type} className="space-y-3">
                <p className="text-sm font-medium text-brown-600">{type === 'influencers' ? '인플루언서' : '브랜드'}</p>
                <div className="flex flex-wrap gap-2">
                  {instagramConfig?.[type].map((acc) => (
                    <span key={acc} className="flex items-center gap-1 rounded-full bg-brown-100 px-3 py-1 text-xs text-brown-700">
                      @{acc}
                      <button
                        onClick={async () => {
                          await fetch(`/api/config/instagram/${type}/${acc}`, { method: 'DELETE' })
                          fetch('/api/config/instagram').then(r => r.json()).then(setInstagramConfig)
                        }}
                        className="ml-1 text-brown-400 hover:text-red-500"
                      >×</button>
                    </span>
                  ))}
                </div>
              </div>
            ))}

            <div className="flex gap-2 items-center pt-2 border-t border-brown-100">
              <select
                value={newAccountType}
                onChange={e => setNewAccountType(e.target.value as 'brands' | 'influencers')}
                className="rounded-lg border border-brown-200 px-3 py-2 text-xs text-brown-600 outline-none"
              >
                <option value="influencers">인플루언서</option>
                <option value="brands">브랜드</option>
              </select>
              <input
                value={newAccount}
                onChange={e => setNewAccount(e.target.value)}
                placeholder="계정명 (@ 제외)"
                className="flex-1 rounded-lg border border-brown-200 px-3 py-2 text-xs text-brown-700 outline-none focus:border-brown-400"
              />
              <button
                onClick={async () => {
                  if (!newAccount.trim()) return
                  await fetch('/api/config/instagram', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: newAccount.trim(), type: newAccountType }),
                  })
                  setNewAccount('')
                  fetch('/api/config/instagram').then(r => r.json()).then(setInstagramConfig)
                }}
                className="rounded-lg bg-brown-600 px-4 py-2 text-xs font-medium text-cream-50 hover:bg-brown-700"
              >
                추가
              </button>
            </div>
          </div>

          {/* 브랜드 URL */}
          <div className="rounded-2xl bg-white p-6 shadow-sm space-y-4">
            <h3 className="font-serif text-xl font-bold text-brown-700">브랜드 URL</h3>

            <div className="space-y-2">
              {brandConfig && Object.entries(brandConfig).map(([key, url]) => (
                <div key={key} className="flex items-center gap-3 rounded-xl bg-brown-50 px-4 py-3">
                  <span className="w-32 shrink-0 text-xs font-medium text-brown-700">{key}</span>
                  <span className="flex-1 truncate text-xs text-brown-400">{url}</span>
                  <button
                    onClick={async () => {
                      await fetch(`/api/config/brands/${key}`, { method: 'DELETE' })
                      fetch('/api/config/brands').then(r => r.json()).then(setBrandConfig)
                    }}
                    className="text-brown-300 hover:text-red-500 transition"
                  >×</button>
                </div>
              ))}
            </div>

            <div className="flex gap-2 items-center pt-2 border-t border-brown-100">
              <input
                value={newBrandKey}
                onChange={e => setNewBrandKey(e.target.value)}
                placeholder="키 (예: musinsa_women)"
                className="w-40 rounded-lg border border-brown-200 px-3 py-2 text-xs text-brown-700 outline-none focus:border-brown-400"
              />
              <input
                value={newBrandUrl}
                onChange={e => setNewBrandUrl(e.target.value)}
                placeholder="URL"
                className="flex-1 rounded-lg border border-brown-200 px-3 py-2 text-xs text-brown-700 outline-none focus:border-brown-400"
              />
              <button
                onClick={async () => {
                  if (!newBrandKey.trim() || !newBrandUrl.trim()) return
                  await fetch('/api/config/brands', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: newBrandKey.trim(), url: newBrandUrl.trim() }),
                  })
                  setNewBrandKey('')
                  setNewBrandUrl('')
                  fetch('/api/config/brands').then(r => r.json()).then(setBrandConfig)
                }}
                className="rounded-lg bg-brown-600 px-4 py-2 text-xs font-medium text-cream-50 hover:bg-brown-700"
              >
                추가
              </button>
            </div>
          </div>
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
