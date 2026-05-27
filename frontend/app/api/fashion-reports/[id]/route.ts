import { NextRequest, NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const res = await fetch(`${API}/fashion-reports/${params.id}`, { method: 'DELETE' })
  const data = await res.json().catch(() => ({}))
  return NextResponse.json(data, { status: res.status })
}

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const res = await fetch(`${API}/fashion-reports/${params.id}`)
  const data = await res.json().catch(() => ({}))
  return NextResponse.json(data, { status: res.status })
}
