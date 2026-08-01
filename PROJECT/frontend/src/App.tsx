import { useEffect } from "react";
import { AppProvider, useApp } from "./context/AppContext";
import { api } from "./services/api";
import MainPage from "./pages/MainPage";

function WeatherLoader() {
  const { userLoc, setWeather } = useApp();
  useEffect(() => {
    const lat = userLoc?.lat ?? 12.9716;
    const lng = userLoc?.lng ?? 77.5946;
    api.weather(lat, lng).then(setWeather).catch(() => setWeather(null));
  }, [userLoc, setWeather]);
  return null;
}

function App() {
  useEffect(() => {
    if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
      document.documentElement.classList.add("dark");
    }
  }, []);

  return (
    <AppProvider>
      <WeatherLoader />
      <MainPage />
    </AppProvider>
  );
}

export default App;
