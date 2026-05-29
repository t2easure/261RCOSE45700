import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}))

  const res = await fetch(`${API}/fashion-reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ days: body.days ?? 30, start_date: body.start_date ?? null, end_date: body.end_date ?? null }),
    cache: 'no-store',
  })
  const data = await res.json()
  return NextResponse.json(data)
}
