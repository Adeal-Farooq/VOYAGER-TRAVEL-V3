import { useEffect, useState } from "react";
import { useApp } from "../context/AppContext";
import "./HeaderBar.css";

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <span className="clock">
      {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true })}
    </span>
  );
}

const WEATHER_ICON: Record<string, string> = {
  clear: "sunny", cloudy: "cloud", fog: "foggy", rain: "rainy", snow: "weather_snowy",
  thunderstorm: "thunderstorm", drizzle: "grain", unknown: "help",
};

export default function HeaderBar() {
  const { dark, toggleDark, weather, userLoc, setUserLoc, setFlyTo } = useApp();
  const icon = WEATHER_ICON[weather?.condition ?? "unknown"] ?? "help";

  const goToCurrentLocation = () => {
    if (userLoc) {
      setFlyTo(userLoc);
      return;
    }
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const p = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setUserLoc(p);
        setFlyTo(p);
      },
      () => setUserLoc({ lat: 12.9716, lng: 77.5946, name: "Bengaluru" }),
      { timeout: 6000 },
    );
  };

  return (
    <header className="header-bar glass">
      <div className="brand row">
        <span className="logo">VOYAGER</span>
        <span className="logo-sub">v2</span>
      </div>
      <div className="header-right row">
        <div className="weather row" title={weather?.condition ?? "Weather unavailable"}>
          <span className="material-symbols-outlined">{icon}</span>
          {weather?.temp_c != null ? (
            <span className="temp">{Math.round(weather.temp_c)}°</span>
          ) : (
            <span className="muted">weather —</span>
          )}
          {weather?.rain_next_hour && <span className="badge live">rain soon</span>}
        </div>
        <button className="loc-btn" onClick={goToCurrentLocation} title="Go to current location">
          <span className="material-symbols-outlined">my_location</span>
        </button>
        <span className="muted truncate loc-name">{userLoc?.name ?? "Bengaluru"}</span>
        <button className="dark-toggle" onClick={toggleDark} title="Toggle theme">
          <span className="material-symbols-outlined">{dark ? "light_mode" : "dark_mode"}</span>
        </button>
      </div>
      <Clock />
    </header>
  );
}
