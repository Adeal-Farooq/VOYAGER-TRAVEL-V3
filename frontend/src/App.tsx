import { AppProvider } from './context/AppContext'
import MainPage from './pages/MainPage'

export default function App() {
  return (
    <AppProvider>
      <MainPage />
    </AppProvider>
  )
}
