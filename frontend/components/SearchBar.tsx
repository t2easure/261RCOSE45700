'use client'

import { useState, useEffect } from 'react'

interface SearchBarProps {
  onSearch: (query: string, days: number) => void
  loading?: boolean
  large?: boolean
  days?: number
}

export default function SearchBar({ onSearch, loading, large, days = 60 }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [suggested, setSuggested] = useState<string[]>([])

  useEffect(() => {
    fetch('/api/keywords')
      .then(r => r.json())
      .then(setSuggested)
      .catch(() => {})
  }, [])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const q = selected.length > 0 ? selected.join(' ') : query.trim()
    if (q) onSearch(q, days)
  }

  function toggleKeyword(kw: string) {
    setSelected(prev =>
      prev.includes(kw) ? prev.filter(k => k !== kw) : [...prev, kw]
    )
    setQuery('')
  }

  const effectiveQuery = selected.length > 0 ? selected.join(' ') : query

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={selected.length > 0 ? selected.join(' ') : query}
          onChange={(e) => { setQuery(e.target.value); setSelected([]) }}
          placeholder="패션 트렌드를 자유롭게 검색해보세요 (예: 편하면서 세련된 출근룩)"
          className={`flex-1 border border-brown-200 bg-white px-5 text-brown-800 placeholder-brown-300 outline-none transition focus:border-brown-500 focus:ring-2 focus:ring-brown-100 ${
            large ? 'rounded-2xl py-4 text-base' : 'rounded-xl py-3 text-sm'
          }`}
        />
        <button
          type="submit"
          disabled={loading || !effectiveQuery.trim()}
          className={`rounded-xl bg-brown-600 font-medium text-cream-50 transition hover:bg-brown-700 disabled:opacity-40 ${
            large ? 'px-8 py-4 text-base' : 'px-6 py-3 text-sm'
          }`}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      <div className="flex flex-wrap gap-2">
        {suggested.map((kw) => (
          <button
            key={kw}
            onClick={() => toggleKeyword(kw)}
            className={`rounded-full border px-3 py-1.5 text-xs transition ${
              selected.includes(kw)
                ? 'border-brown-600 bg-brown-600 text-cream-50'
                : 'border-brown-200 bg-white text-brown-500 hover:border-brown-400 hover:text-brown-700'
            }`}
          >
            {kw}
          </button>
        ))}
      </div>
    </div>
  )
}
