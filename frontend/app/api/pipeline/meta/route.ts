import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function POST(request: Request) {
  const { searchParams } = new URL(request.url)
  const batchSize = searchParams.get('batch_size') ?? '100'
  const res = await fetch(`${API}/pipeline/meta?batch_size=${batchSize}`, {
    method: 'POST',
    cache: 'no-store',
  })
  const data = await res.json()
  return NextResponse.json(data)
}
