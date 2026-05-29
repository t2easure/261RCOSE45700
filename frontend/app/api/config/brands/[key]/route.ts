import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function DELETE(
  _request: Request,
  { params }: { params: { key: string } }
) {
  const res = await fetch(`${API}/config/brands/${params.key}`, {
    method: 'DELETE',
  })
  return NextResponse.json(await res.json(), { status: res.status })
}
