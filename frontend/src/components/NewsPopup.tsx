import { useState, useEffect, useCallback, useRef } from 'react'
import { useApp } from '../context/AppContext'

interface NewsItem {
  title: string
  source: string
  category: 'traffic' | 'weather' | 'event' | 'general'
  url?: string
  snippet?: string
}

export default function NewsPopup() {
  const { userLocation } = useApp()
  const [news, setNews] = useState<NewsItem[]>([])
  const [dismissed, setDismissed] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchNews = useCallback(async () => {
    try {
      const [eventsRes, trafficRes] = await Promise.allSettled([
        fetch(`/api/search/current-events?location=${encodeURIComponent('Bengaluru')}`).then(r => r.json()),
        fetch(`/api/search/current-events?location=${encodeURIComponent('Bangalore traffic road jam')}`).then(r => r.json()),
      ])

      const items: NewsItem[] = []

      if (eventsRes.status === 'fulfilled' && eventsRes.value?.events) {
        const text = eventsRes.value.events
        if (typeof text === 'string') {
          text.split('\n').filter(Boolean).forEach(line => {
            const clean = line.replace(/^[•\s*\-]+/, '').trim()
            if (clean) items.push({ title: clean, source: 'Reddit', category: 'event' })
          })
        }
      }

      if (trafficRes.status === 'fulfilled' && trafficRes.value?.events) {
        const text = trafficRes.value.events
        if (typeof text === 'string') {
          text.split('\n').filter(Boolean).forEach(line => {
            const clean = line.replace(/^[•\s*\-]+/, '').trim()
            if (clean) items.push({ title: clean, source: 'Traffic', category: 'traffic' })
          })
        }
      }

      if (items.length > 0) setNews(prev => {
        const titles = new Set(prev.map(n => n.title))
        const merged = [...prev]
        for (const item of items) {
          if (!titles.has(item.title)) merged.push(item)
        }
        return merged.slice(0, 15)
      })
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    fetchNews()
    intervalRef.current = setInterval(fetchNews, 120000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [fetchNews])

  if (dismissed || news.length === 0) return null

  return (
    <div className="news-popup fade-in">
      <div className="news-popup-header">
        <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--primary)' }}>newspaper</span>
        <span>Live Updates</span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>
          <span className="pulse-dot" style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#22c55e', marginRight: 4 }} />
          LIVE
        </span>
        <button className="news-dismiss" onClick={() => setDismissed(true)} title="Dismiss">✕</button>
      </div>
      <div className="news-popup-scroll">
        {news.map((item, i) => (
          <div key={i} className={`news-item ${item.category}`}>
            <div className="news-title">{item.title}</div>
            <div className="news-source">
              <span className="material-symbols-outlined" style={{ fontSize: 12 }}>
                {item.category === 'traffic' ? 'traffic' : item.category === 'weather' ? 'partly_cloudy_day' : item.category === 'event' ? 'event' : 'article'}
              </span>
              {item.source}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
