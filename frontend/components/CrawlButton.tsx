'use client'

import { useState } from 'react'

interface CrawlButtonProps {
  onComplete: () => void
}

export default function CrawlButton({ onComplete }: CrawlButtonProps) {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function pollPipelineStatus(): Promise<void> {
    return new Promise((resolve) => {
      const check = async () => {
        try {
          const res = await fetch('/api/pipeline/status')
          const data = await res.json()
          if (data.state === 'idle' || data.state === 'error') {
            resolve()
          } else {
            setTimeout(check, 2000)
          }
        } catch {
          setTimeout(check, 2000)
        }
      }
      check()
    })
  }

  async function handleCrawl() {
    setLoading(true)
    setMessage(null)
    try {
      // 크롤링 시작 전 현재 수집 건수 및 마지막 로그 시각 저장
      const [beforeStatsRes, beforeLogsRes] = await Promise.all([
        fetch('/api/stats'),
        fetch('/api/logs'),
      ])
      const beforeStats = await beforeStatsRes.json()
      const beforeTotal = beforeStats.total ?? 0
      const beforeLogs = await beforeLogsRes.json().catch(() => [])
      const beforePipelineLog = Array.isArray(beforeLogs) ? beforeLogs.find((l: {source: string; run_at: string}) => l.source === 'pipeline') : null
      const lastLogBefore: string | null = beforePipelineLog ? beforePipelineLog.run_at : null

      const crawlStartedAt = new Date().toISOString()
      const res = await fetch('/api/crawl', { method: 'POST' })
      const data = await res.json()
      if (!data.success) {
        setMessage(`오류: ${data.message || '알 수 없는 오류가 발생했습니다.'}`)
        setLoading(false)
        return
      }

      setMessage('크롤링 진행 중...')

      // 완료될 때까지 10초마다 stats 폴링
      const MAX_WAIT = 60 * 15 * 1000 // 최대 15분
      const INTERVAL = 10000
      const startTime = Date.now()

      const poll = async (): Promise<void> => {
        if (Date.now() - startTime > MAX_WAIT) {
          setMessage('크롤링이 진행 중입니다. 잠시 후 새로고침하세요.')
          setLoading(false)
          onComplete()
          return
        }
        const statsRes = await fetch('/api/stats')
        const stats = await statsRes.json()
        const logs = await fetch('/api/logs').then(r => r.json()).catch(() => [])
        const elapsed = Math.round((Date.now() - startTime) / 1000)

        // pipeline 소스 로그가 새로 생겼으면 전체 완료로 판단
        const pipelineLog = Array.isArray(logs) ? logs.find((l: {source: string; run_at: string}) => l.source === 'pipeline') : null
        const isNewLog = pipelineLog && pipelineLog.run_at !== lastLogBefore
        if (isNewLog) {
          const newCount = (stats.total ?? 0) - beforeTotal

          // 1차 캡셔닝
          setMessage('크롤링 완료 → 1차 캡셔닝 중...')
          await fetch('/api/pipeline/caption', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ since: crawlStartedAt }) })
          await pollPipelineStatus()

          // 2차 메타 캡셔닝
          setMessage('크롤링 완료 → 2차 캡셔닝 중...')
          await fetch('/api/pipeline/meta', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ since: crawlStartedAt }) })
          await pollPipelineStatus()

          // 임베딩
          setMessage('크롤링 완료 → 임베딩 중...')
          await fetch('/api/pipeline/embed', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ since: crawlStartedAt }) })
          await pollPipelineStatus()

          setMessage(`완료! ${newCount > 0 ? `${newCount}건 새로 수집` : '새 데이터 없음'}`)
          setLoading(false)
          onComplete()
          return
        }

        setMessage(`크롤링 진행 중... (${elapsed}초)`)
        setTimeout(poll, INTERVAL)
      }

      setTimeout(poll, INTERVAL)
    } catch {
      setMessage('크롤링 요청 중 오류가 발생했습니다.')
      setLoading(false)
    }
  }

  async function handleStop() {
    await fetch('/api/crawl/stop', { method: 'POST' })
    setMessage('중단 신호 전송됨')
    setLoading(false)
  }

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={handleCrawl}
        disabled={loading}
        className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
      >
        {loading ? (
          <>
            <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            크롤링 중...
          </>
        ) : (
          '지금 크롤링 실행'
        )}
      </button>
      {loading && (
        <button
          onClick={handleStop}
          className="px-4 py-2 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 transition-colors"
        >
          중단
        </button>
      )}
      {message && (
        <span
          className={`text-sm ${
            message.startsWith('오류') ? 'text-red-600' : 'text-green-600'
          }`}
        >
          {message}
        </span>
      )}
    </div>
  )
}
