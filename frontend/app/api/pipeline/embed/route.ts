import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function POST() {
  const res = await fetch(`${API}/pipeline/embed`, {
    method: 'POST',
    cache: 'no-store',
  })
  const data = await res.json()
  return NextResponse.json(data)
}
