'use client'

import { useState } from 'react'

interface ImageCardProps {
  imageUrl: string
  accountName: string
  source: string
  postedAt: string | null
  captionAi: string | null
  similarity?: number
  postUrl?: string | null
  price?: number | null
  materialInfo?: string | null
  likes?: number | null
  followers?: number | null
  onDelete?: () => void
}

const SOURCE_LABELS: Record<string, string> = {
  instagram: 'Instagram',
  lookbook: 'Lookbook',
  youtube: 'YouTube',
}

export default function ImageCard({
  imageUrl,
  accountName,
  source,
  postedAt,
  captionAi,
  postUrl,
  price,
  materialInfo,
  likes,
  followers,
  onDelete,
}: ImageCardProps) {
  const [imgError, setImgError] = useState(false)
  const dateStr = postedAt
    ? new Date(postedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : ''
  const engagementRate = likes != null && followers != null && followers > 0
    ? ((likes / followers) * 100).toFixed(1)
    : null

  const content = (
    <>
      <div className="relative aspect-[3/4] overflow-hidden bg-cream-200">
        {imgError ? (
          <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-brown-300">
            <span className="text-xs font-medium">Image unavailable</span>
          </div>
        ) : (
          <img
            src={imageUrl}
            alt={captionAi ?? accountName}
            className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
            onError={() => setImgError(true)}
          />
        )}
        <span className="absolute left-2 top-2 rounded-full bg-white/80 px-2.5 py-1 text-[10px] font-medium text-brown-600 backdrop-blur-sm">
          {SOURCE_LABELS[source] ?? source}
        </span>
        {onDelete && (
          <button
            type="button"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete() }}
            title="삭제"
            className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-black/50 text-xs text-white opacity-0 transition hover:bg-red-500 group-hover:opacity-100"
          >
            ✕
          </button>
        )}
      </div>

      <div className="space-y-1 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-xs font-semibold text-brown-700">@{accountName}</span>
          {dateStr && <span className="shrink-0 text-[10px] text-brown-300">{dateStr}</span>}
        </div>
        {price != null && (
          <p className="text-xs font-semibold text-brown-800">₩{price.toLocaleString()}</p>
        )}
        {materialInfo && (
          <p className="truncate text-[10px] text-brown-400" title={materialInfo}>{materialInfo}</p>
        )}
        {likes != null && engagementRate && (
          <p className="text-[10px] text-brown-400">♥ {likes.toLocaleString()} · {engagementRate}%</p>
        )}
        {captionAi && (
          <div className="relative">
            <p className="line-clamp-2 text-[11px] leading-5 text-brown-500">{captionAi}</p>
            <div className="absolute bottom-full left-0 z-10 hidden w-full rounded-xl border border-brown-100 bg-white p-3 text-[11px] leading-5 text-brown-600 shadow-lg group-hover:block">
              {captionAi}
            </div>
          </div>
        )}
      </div>
    </>
  )

  const className = 'group overflow-hidden rounded-2xl bg-white shadow-sm transition hover:shadow-md'

  if (!postUrl) {
    return <div className={className}>{content}</div>
  }

  return (
    <a href={postUrl} target="_blank" rel="noreferrer noopener" className={className}>
      {content}
    </a>
  )
}
