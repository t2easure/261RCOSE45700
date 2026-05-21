import { NextRequest, NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function GET(req: NextRequest) {
  const ids = req.nextUrl.searchParams.get('ids') ?? ''
  const res = await fetch(`${API}/posts/by-ids?ids=${ids}`, { cache: 'no-store' })
  const data = await res.json()
  return NextResponse.json(data)
}
