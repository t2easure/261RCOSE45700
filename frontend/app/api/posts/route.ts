import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const source = searchParams.get('source') ?? ''
  const limit = searchParams.get('limit') ?? '50'
  const offset = searchParams.get('offset') ?? '0'
  const account_name = searchParams.get('account_name') ?? ''
  const sort = searchParams.get('sort') ?? ''
  const date_from = searchParams.get('date_from') ?? ''
  const date_to = searchParams.get('date_to') ?? ''

  const params = new URLSearchParams({ limit, offset })
  if (source) params.set('source', source)
  if (account_name) params.set('account_name', account_name)
  if (sort) params.set('sort', sort)
  if (date_from) params.set('date_from', date_from)
  if (date_to) params.set('date_to', date_to)

  const res = await fetch(`${API}/posts?${params}`, { cache: 'no-store' })
  const data = await res.json()
  return NextResponse.json(data)
}
