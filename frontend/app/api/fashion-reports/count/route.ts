import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const days = searchParams.get('days') ?? '30'
  const res = await fetch(`${API}/fashion-reports/count?days=${days}`, { cache: 'no-store' })
  const data = await res.json()
  return NextResponse.json(data)
}
