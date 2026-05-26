import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const params = new URLSearchParams()
  const startDate = searchParams.get('start_date')
  const endDate = searchParams.get('end_date')
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const res = await fetch(`${API}/fashion-reports/count?${params}`, { cache: 'no-store' })
  const data = await res.json()
  return NextResponse.json(data)
}
