'use client'

import { useState } from 'react'

interface SearchBarProps {
  onSearch: (query: string, days: number) => void
  loading?: boolean
  large?: boolean
}

const PERIOD_OPTIONS = [
  { value: 30, label: '1 Month' },
  { value: 60, label: '2 Months' },
]

const SUGGESTED = ['Comfort Classic', 'Oversized', 'Neutral Tone', 'Crop Jacket', 'Icy Blue', '미니멀', '스트리트']

export default function SearchBar({ onSearch, loading, large }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [days, setDays] = useState(60)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (query.trim()) onSearch(query.trim(), days)
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search fashion keywords (e.g. Comfort Classic)"
          className={`flex-1 border border-brown-200 bg-white px-5 text-brown-800 placeholder-brown-300 outline-none transition focus:border-brown-500 focus:ring-2 focus:ring-brown-100 ${
            large ? 'rounded-2xl py-4 text-base' : 'rounded-xl py-3 text-sm'
          }`}
        />
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-xl border border-brown-200 bg-white px-3 py-3 text-sm text-brown-600 outline-none focus:border-brown-400"
        >
          {PERIOD_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className={`rounded-xl bg-brown-600 font-medium text-cream-50 transition hover:bg-brown-700 disabled:opacity-40 ${
            large ? 'px-8 py-4 text-base' : 'px-6 py-3 text-sm'
          }`}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      <div className="flex flex-wrap gap-2">
        {SUGGESTED.map((kw) => (
          <button
            key={kw}
            onClick={() => { setQuery(kw); onSearch(kw, days) }}
            className="rounded-full border border-brown-200 bg-white px-3 py-1.5 text-xs text-brown-500 transition hover:border-brown-400 hover:text-brown-700"
          >
            {kw}
          </button>
        ))}
      </div>
    </div>
  )
}
