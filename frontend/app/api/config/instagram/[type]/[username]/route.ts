import { NextResponse } from 'next/server'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export async function DELETE(
  _request: Request,
  { params }: { params: { type: string; username: string } }
) {
  const res = await fetch(`${API}/config/instagram/${params.type}/${params.username}`, {
    method: 'DELETE',
  })
  return NextResponse.json(await res.json(), { status: res.status })
}
