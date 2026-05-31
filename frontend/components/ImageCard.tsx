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
}

const SOURCE_LABELS: Record<string, string> = {
  instagram: 'Instagram',
  lookbook:  'Lookbook',
  youtube:   'YouTube',
}

export default function ImageCard({ imageUrl, accountName, source, postedAt, captionAi, similarity, postUrl, price, materialInfo, likes, followers }: ImageCardProps) {
  const [imgError, setImgError] = useState(false)
  const dateStr = postedAt
    ? new Date(postedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : ''

  return (
    <div className={`group overflow-hidden rounded-2xl bg-white shadow-sm transition hover:shadow-md ${postUrl ? 'cursor-pointer' : ''}`} onClick={() => postUrl && window.open(postUrl, '_blank')}>
      <div className="relative aspect-[3/4] overflow-hidden bg-cream-200">
        {imgError ? (
          <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-brown-300">
            <span className="text-2xl">🖼</span>
            <span className="text-[10px]">이미지 만료</span>
          </div>
        ) : (
          <img
            src={imageUrl}
            alt={captionAi ?? accountName}
            className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
            onError={() => setImgError(true)}
          />
        )}
        {/* 소스 뱃지 */}
        <span className="absolute left-2 top-2 rounded-full bg-white/80 px-2.5 py-1 text-[10px] font-medium text-brown-600 backdrop-blur-sm">
          {SOURCE_LABELS[source] ?? source}
        </span>
        {/* 유사도 */}
        {similarity !== undefined && (
          <span className="absolute right-2 top-2 rounded-full bg-brown-700/70 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur-sm">
            {Math.round(similarity * 100)}%
          </span>
        )}
      </div>

      <div className="p-3 space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-brown-700">@{accountName}</span>
          {dateStr && <span className="text-[10px] text-brown-300">{dateStr}</span>}
        </div>
        {price != null && (
          <p className="text-xs font-semibold text-brown-800">₩{price.toLocaleString()}</p>
        )}
        {materialInfo && (
          <p className="text-[10px] text-brown-400 truncate" title={materialInfo}>{materialInfo}</p>
        )}
        {likes != null && followers != null && followers > 0 && (
          <p className="text-[10px] text-brown-400">❤ {likes.toLocaleString()} · {((likes / followers) * 100).toFixed(1)}%</p>
        )}
        {captionAi && (
          <div className="relative">
            <p className="line-clamp-2 text-[11px] leading-5 text-brown-500">{captionAi}</p>
            <div className="absolute bottom-full left-0 z-10 hidden group-hover:block w-full rounded-xl bg-white border border-brown-100 shadow-lg p-3 text-[11px] leading-5 text-brown-600">
              {captionAi}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
