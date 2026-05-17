import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const source = searchParams.get('source') ?? ''
  const limit = searchParams.get('limit') ?? '50'
  const offset = searchParams.get('offset') ?? '0'

  const params = new URLSearchParams({ limit, offset })
  if (source) params.set('source', source)

  const res = await fetch(`${API}/posts?${params}`, { cache: 'no-store' })
  const data = await res.json()
  return NextResponse.json(data)
}
