import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function DELETE(_request: Request, { params }: { params: { id: string } }) {
  const res = await fetch(`${API}/posts/${params.id}`, { method: 'DELETE' })
  const data = await res.json()
  return NextResponse.json(data)
}
