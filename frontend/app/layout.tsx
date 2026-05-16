import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'CRAI — Curated Reference AI',
  description: '패션 인플루언서 트렌드 분석 대시보드',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  )
}
