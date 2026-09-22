import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext.jsx'
import LoginPage from './pages/LoginPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import InventoryPage from './pages/InventoryPage.jsx'
import CategoriesPage from './pages/CategoriesPage.jsx'
import TransactionsPage from './pages/TransactionsPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import AnalyticsPage from './pages/AnalyticsPage.jsx'
import RiskPage from './pages/RiskPage.jsx'
import RecommendationsPage from './pages/RecommendationsPage.jsx'
import AnomaliesPage from './pages/AnomaliesPage.jsx'
import SimulationPage from './pages/SimulationPage.jsx'
import NotificationsPage from './pages/NotificationsPage.jsx'
import ProductDetailPage from './pages/ProductDetailPage.jsx'
import Layout from './components/Layout.jsx'

function Protected({ children }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="inventory" element={<InventoryPage />} />
        <Route path="categories" element={<CategoriesPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="risk" element={<RiskPage />} />
        <Route path="recommendations" element={<RecommendationsPage />} />
        <Route path="anomalies" element={<AnomaliesPage />} />
        <Route path="simulation" element={<SimulationPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="products/:id" element={<ProductDetailPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}