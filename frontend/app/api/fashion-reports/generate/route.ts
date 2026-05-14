import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function POST(request: Request) {
  const { searchParams } = new URL(request.url)
  const days = searchParams.get('days') ?? '14'

  const res = await fetch(`${API}/fashion-reports/generate?days=${days}`, {
    method: 'POST',
    cache: 'no-store',
  })
  const data = await res.json()
  return NextResponse.json(data)
}
