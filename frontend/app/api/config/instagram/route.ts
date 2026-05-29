import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function GET() {
  const res = await fetch(`${API}/config/instagram`, { cache: 'no-store' })
  return NextResponse.json(await res.json())
}

export async function POST(request: Request) {
  const body = await request.json()
  const res = await fetch(`${API}/config/instagram`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return NextResponse.json(await res.json(), { status: res.status })
}
