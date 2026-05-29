import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function POST(request: Request) {
  const formData = await request.formData()
  const res = await fetch(`${API}/search/image`, {
    method: 'POST',
    body: formData,
  })
  return NextResponse.json(await res.json(), { status: res.status })
}
