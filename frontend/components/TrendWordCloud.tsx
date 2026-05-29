'use client'

import ReactWordcloud from 'react-wordcloud'

interface Props {
  words: { text: string; value: number }[]
}

const options = {
  rotations: 0,
  fontFamily: 'sans-serif',
  fontWeight: 'bold',
  fontSizes: [18, 96] as [number, number],
  padding: 2,
  colors: ['#5c3d2e', '#8b6350', '#b08060', '#c8a888', '#a07858'],
  enableTooltip: true,
  deterministic: true,
  spiral: 'rectangular' as const,
}

export default function TrendWordCloud({ words }: Props) {
  return (
    <div style={{ width: '100%', height: 560 }}>
      <ReactWordcloud words={words} options={options} />
    </div>
  )
}
