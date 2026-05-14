'use client'

export type Tab = 'dashboard' | 'search' | 'reports' | 'data'

const TABS: { value: Tab; label: string }[] = [
  { value: 'dashboard', label: 'Trends' },
  { value: 'search', label: 'Search' },
  { value: 'reports', label: 'Reports' },
  { value: 'data', label: 'Data' },
]

interface NavbarProps {
  tab: Tab
  onTabChange: (v: Tab) => void
}

export default function Navbar({ tab, onTabChange }: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-brown-200 bg-cream-50/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-8 py-4">
        {/* 로고 */}
        <button onClick={() => onTabChange('dashboard')} className="flex items-baseline gap-1">
          <span className="font-serif text-2xl font-bold tracking-widest text-brown-700">C</span>
          <span className="font-serif text-2xl font-bold tracking-widest text-brown-500">RAI</span>
        </button>

        {/* 탭 */}
        <nav className="flex items-center gap-1">
          {TABS.map((t) => (
            <button
              key={t.value}
              onClick={() => onTabChange(t.value)}
              className={`rounded-full px-5 py-2 text-sm font-medium tracking-wide transition ${
                tab === t.value
                  ? 'bg-brown-600 text-cream-50'
                  : 'text-brown-500 hover:bg-brown-100 hover:text-brown-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {/* 기간 뱃지 */}
        <div className="flex items-center gap-2 text-xs text-brown-400">
          <span className="h-2 w-2 rounded-full bg-brown-400 animate-pulse" />
          Live collecting
        </div>
      </div>
    </header>
  )
}
