import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const q = searchParams.get('q') ?? ''
  const days = searchParams.get('days') ?? '60'
  const limit = searchParams.get('limit') ?? '20'

  const res = await fetch(
    `${API}/search?q=${encodeURIComponent(q)}&days=${days}&limit=${limit}`,
    { cache: 'no-store' }
  )
  const data = await res.json()
  return NextResponse.json(data)
}
