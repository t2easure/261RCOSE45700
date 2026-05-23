import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function GET() {
  const res = await fetch(`${API}/search/accounts`, { cache: 'no-store' })
  const data = await res.json()
  return NextResponse.json(data)
}
