import { useState, useEffect, useCallback } from 'react'
import { useApp } from '../context/AppContext'
import { getWeather } from '../services/api'

export default function HeaderBar() {
  const { userLocation, weather, setWeather, darkMode, toggleDarkMode } = useApp()
  const [time, setTime] = useState(new Date())
  const [locName, setLocName] = useState<string | null>(null)

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (userLocation && !weather) {
      getWeather(userLocation[0], userLocation[1]).then(r => {
        if (r?.condition || r?.temp) setWeather(r)
      }).catch(() => {})
    }
  }, [userLocation, weather, setWeather])

  const fetchLocName = useCallback(async (lat: number, lng: number) => {
    try {
      const r = await fetch(
        `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&zoom=16`,
        { headers: { 'User-Agent': 'Voyager/1.0' } }
      )
      const d = await r.json()
      const addr = d?.address
      if (addr) {
        const parts = [addr.suburb || addr.neighbourhood, addr.city_district || addr.town, addr.city].filter(Boolean)
        setLocName(parts.slice(0, 2).join(', '))
      }
    } catch {}
  }, [])

  useEffect(() => {
    if (userLocation && !locName) {
      fetchLocName(userLocation[0], userLocation[1])
    }
  }, [userLocation, locName, fetchLocName])

  const fmt = (n: number) => String(n).padStart(2, '0')
  const h = time.getHours()
  const m = time.getMinutes()
  const ampm = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 || 12

  return (
    <div className="header-bar">
      <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--primary)' }}>explore</span>
      <span className="header-clock">{fmt(h12)}:{fmt(m)} {ampm}</span>

      {weather && (
        <div className="header-weather">
          <span className="header-weather-icon material-symbols-outlined">
            {weather.condition?.toLowerCase().includes('rain') ? 'rainy' :
             weather.condition?.toLowerCase().includes('cloud') ? 'cloud' :
             weather.condition?.toLowerCase().includes('fog') ? 'foggy' :
             weather.condition?.toLowerCase().includes('clear') || weather.condition?.toLowerCase().includes('sun') ? 'sunny' : 'partly_cloudy_day'}
          </span>
          <span>{weather.temp != null ? `${Math.round(weather.temp)}°C` : ''}</span>
        </div>
      )}

      <div className="header-spacer" />

      {locName && (
        <div className="header-location">
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>location_on</span>
          {locName}
        </div>
      )}

      <button className="theme-toggle" onClick={toggleDarkMode} title={darkMode ? 'Light mode' : 'Dark mode'}>
        <span className="material-symbols-outlined">{darkMode ? 'light_mode' : 'dark_mode'}</span>
      </button>
    </div>
  )
}
