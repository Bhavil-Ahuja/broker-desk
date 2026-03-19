import { Routes, Route, Navigate } from 'react-router-dom'
import LeadLogin from './pages/LeadLogin'
import LeadChat from './pages/LeadChat'
import BrokerDashboard from './pages/BrokerDashboard'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LeadLogin />} />
      <Route path="/chat" element={<LeadChat />} />
      <Route path="/broker" element={<BrokerDashboard />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
