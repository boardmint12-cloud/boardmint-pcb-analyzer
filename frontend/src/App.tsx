import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import QuotePage from './pages/QuotePage'
import UploadPage from './pages/UploadPage'
import DashboardPage from './pages/DashboardPage'
import ProjectsPage from './pages/ProjectsPage'
import Navbar from './components/Navbar'

function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="min-h-screen" style={{ background: '#000000' }}>
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/quote" element={<QuotePage />} />

            {/* Protected routes */}
            <Route
              path="/upload"
              element={
                <ProtectedRoute>
                  <>
                    <Navbar />
                    <main className="container mx-auto px-4 py-8">
                      <UploadPage />
                    </main>
                  </>
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard"
              element={<Navigate to="/projects" replace />}
            />
            <Route
              path="/dashboard/:jobId"
              element={
                <ProtectedRoute>
                  <>
                    <Navbar />
                    <main className="container mx-auto px-4 py-8">
                      <DashboardPage />
                    </main>
                  </>
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects"
              element={
                <ProtectedRoute>
                  <>
                    <Navbar />
                    <main className="container mx-auto px-4 py-8">
                      <ProjectsPage />
                    </main>
                  </>
                </ProtectedRoute>
              }
            />

            {/* Catch all - redirect to home */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </AuthProvider>
    </Router>
  )
}

export default App
