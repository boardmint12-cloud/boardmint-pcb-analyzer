import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { User, LogOut, Building2 } from 'lucide-react'
import { useState } from 'react'

export default function Navbar() {
  const { user, organization, signOut } = useAuth()
  const navigate = useNavigate()
  const [showDropdown, setShowDropdown] = useState(false)

  const handleLogout = async () => {
    try {
      await signOut()
      navigate('/login')
    } catch (error) {
      console.error('Error signing out:', error)
    }
  }

  return (
    <nav className="bg-black border-b border-gray-800 shadow-2xl">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center group">
            <div>
              <span className="text-3xl font-bold tracking-tight" style={{
                color: '#16a34a',
                textShadow: '0 0 20px rgba(22, 163, 74, 0.5), 0 0 40px rgba(22, 163, 74, 0.3)'
              }}>
                BoardMint
              </span>
              <span className="ml-3 text-xs text-gray-500">PCB Analysis Platform</span>
            </div>
          </Link>
          
          <div className="flex items-center space-x-6">
            {user ? (
              <>
                <Link
                  to="/dashboard"
                  className="text-gray-300 hover:text-pcbGreen font-medium transition-colors"
                >
                  Dashboard
                </Link>
                <Link
                  to="/upload"
                  className="text-gray-300 hover:text-pcbGreen font-medium transition-colors"
                >
                  New Analysis
                </Link>
                <Link
                  to="/projects"
                  className="text-gray-300 hover:text-pcbGreen font-medium transition-colors"
                >
                  Projects
                </Link>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="text-gray-300 hover:text-pcbGreen font-medium transition-colors"
                >
                  Login
                </Link>
                <Link
                  to="/quote"
                  className="px-6 py-2 rounded-lg font-medium transition-all"
                  style={{
                    backgroundColor: '#16a34a',
                    color: 'white',
                    boxShadow: '0 0 20px rgba(22, 163, 74, 0.4)'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.boxShadow = '0 0 30px rgba(22, 163, 74, 0.6)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.boxShadow = '0 0 20px rgba(22, 163, 74, 0.4)';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  Get a Quote Today
                </Link>
              </>
            )}

            {/* User Menu */}
            {user && (
              <div className="relative">
                <button
                  onClick={() => setShowDropdown(!showDropdown)}
                  className="flex items-center gap-2 px-3 py-2 bg-gray-900 hover:bg-gray-800 rounded-lg transition-colors"
                >
                  <User className="w-4 h-4 text-gray-400" />
                  <span className="text-sm text-gray-300">{user.full_name}</span>
                </button>

                {showDropdown && (
                  <>
                    {/* Backdrop to close dropdown */}
                    <div 
                      className="fixed inset-0 z-10" 
                      onClick={() => setShowDropdown(false)}
                    />
                    
                    {/* Dropdown */}
                    <div className="absolute right-0 mt-2 w-64 bg-gray-900 border border-gray-800 rounded-lg shadow-xl z-20">
                      <div className="p-3 border-b border-gray-800">
                        <p className="text-sm font-medium text-gray-200">{user.full_name}</p>
                        <p className="text-xs text-gray-500">{user.email}</p>
                      </div>
                      
                      <div className="p-3 border-b border-gray-800">
                        <div className="flex items-center gap-2 text-xs text-gray-400">
                          <Building2 className="w-3 h-3" />
                          <span>{organization?.name}</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          Role: <span className="text-pcbGreen font-medium">{user.role}</span>
                        </p>
                      </div>

                      <button
                        onClick={handleLogout}
                        className="w-full px-3 py-2 flex items-center gap-2 text-sm text-gray-300 hover:bg-gray-800 transition-colors"
                      >
                        <LogOut className="w-4 h-4" />
                        Sign out
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}
