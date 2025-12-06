import { Link } from 'react-router-dom'
import { Upload, Shield, Radio, FileText, Zap, UserPlus, CheckCircle2, TrendingUp, Clock, DollarSign, MessageSquare, Cpu, BookOpen, Layers, ThermometerSun } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import Navbar from '../components/Navbar'
import LightRays from '../components/LightRays'
import { BorderBeam } from '../components/BorderBeam'

export default function HomePage() {
  const { user } = useAuth()
  const [displayedText, setDisplayedText] = useState('')
  const [showCursor, setShowCursor] = useState(true)
  const fullText = 'BoardMint'
  const typingSpeed = 90 // milliseconds per character

  useEffect(() => {
    let currentIndex = 0
    const intervalId = setInterval(() => {
      if (currentIndex <= fullText.length) {
        setDisplayedText(fullText.slice(0, currentIndex))
        currentIndex++
      } else {
        clearInterval(intervalId)
        // Hide cursor after typing completes
        setTimeout(() => setShowCursor(false), 500)
      }
    }, typingSpeed)

    return () => clearInterval(intervalId)
  }, [])

  return (
    <div className="relative">
      {/* Floating 3D Navbar */}
      <div className="fixed top-6 left-1/2 transform -translate-x-1/2 z-50 w-11/12 max-w-6xl">
        <div className="backdrop-blur-md bg-gray-900/80 border border-gray-700/50 shadow-2xl" style={{
          borderRadius: '50px',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.5), 0 0 20px rgba(22, 163, 74, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
          transform: 'perspective(1000px) rotateX(2deg)',
        }}>
          <Navbar />
        </div>
      </div>

      <div className="max-w-7xl mx-auto pt-24">
        {/* Hero Section */}
        <div className="text-center py-20 px-4 relative">
          {/* Light Rays Effect - from top of page */}
          <div className="absolute inset-0 overflow-hidden pointer-events-none" style={{ 
            height: '600px',
            top: '-100px'
          }}>
            <LightRays
              raysOrigin="top-center"
              raysColor="#a9ababff"
              raysSpeed={1.2}
              lightSpread={0.1}
              rayLength={0.5}
              followMouse={true}
              mouseInfluence={0.08}
              noiseAmount={0.05}
              distortion={0.03}
            />
          </div>

          <h1 className="text-7xl font-bold mb-6 tracking-tight relative z-10" style={{
            color: '#16a34a',
            textShadow: '0 0 30px rgba(22, 163, 74, 0.8), 0 0 60px rgba(22, 163, 74, 0.5), 0 0 90px rgba(22, 163, 74, 0.3)'
          }}>
            {displayedText}
            {showCursor && (
              <span className="animate-pulse" style={{
                borderRight: '3px solid #16a34a',
                marginLeft: '2px',
                display: 'inline-block'
              }}></span>
            )}
          </h1>
        <p className="text-3xl text-gray-300 mb-8 font-semibold">
          AI-Powered PCB Analysis for Hardware Teams
        </p>
        <p className="text-xl text-gray-400 max-w-3xl mx-auto mb-12 leading-relaxed">
          Catch critical design issues before manufacturing. RAG-powered AI analysis with industry-standard 
          rule engines (IPC-2221A, IEC 62368-1). From mains safety to high-speed signal integrity.
        </p>
        
        <div className="flex justify-center gap-6 flex-wrap">
          <Link to="/quote" className="btn-primary text-lg px-10 py-4 shadow-lg">
            <MessageSquare className="inline-block h-5 w-5 mr-2" />
            Get a Quote Today
          </Link>
        </div>

        {/* Dashboard Preview with BorderBeam */}
        <div className="mt-20 flex justify-center px-4">
          <div className="relative max-w-5xl w-full">
            <div className="relative rounded-2xl shadow-2xl">
              <div className="relative rounded-2xl overflow-hidden bg-gray-900 z-10">
                <video 
                  src="/images/ws vi.mp4"
                  className="w-full h-auto block"
                  loop
                  muted
                  playsInline
                  onMouseEnter={(e) => e.currentTarget.play()}
                  onMouseLeave={(e) => {
                    e.currentTarget.pause();
                    e.currentTarget.currentTime = 0;
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  Your browser does not support the video tag.
                </video>
              </div>
              <BorderBeam 
                duration={5}
                delay={0}
                borderWidth={4}
                colorFrom="#16a34a"
                colorTo="#00d4ff"
              />
            </div>
            <p className="text-center text-sm text-gray-500 mt-4">
              Real-time analysis results with detailed categorization and risk assessment
              <span className="block text-xs text-gray-600 mt-1">Hover to play demo</span>
            </p>
          </div>
        </div>
      </div>

      {/* Stats/Problem Section */}
      <div className="py-16 px-4">
        <div className="max-w-5xl mx-auto">
          <div className="card bg-gradient-to-br from-green-900/20 to-emerald-900/20 border-green-600/30 p-10">
            <div className="text-center mb-8">
              <h2 className="text-4xl font-bold text-gray-100 mb-4">The PCB Complexity Crisis</h2>
              <div className="text-6xl font-bold mb-6" style={{ color: '#16a34a', textShadow: '0 0 20px rgba(22, 163, 74, 0.5)' }}>53%</div>
              <p className="text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed">
                of electronics companies say increasing PCB complexity is their <span className="text-green-400 font-semibold">#1 time-to-market challenge</span>
              </p>
            </div>
            
            <div className="grid md:grid-cols-3 gap-6 mt-12">
              <div className="text-center">
                <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4 border border-green-500/30">
                  <TrendingUp className="h-8 w-8 text-green-400" />
                </div>
                <h3 className="text-lg font-semibold text-gray-200 mb-2">Dense, High-Speed Boards</h3>
                <p className="text-sm text-gray-400">Multi-layer, HDI, BGAs pushing design limits</p>
              </div>
              
              <div className="text-center">
                <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-4 border border-emerald-500/30">
                  <Clock className="h-8 w-8 text-emerald-400" />
                </div>
                <h3 className="text-lg font-semibold text-gray-200 mb-2">Manual Check Bottleneck</h3>
                <p className="text-sm text-gray-400">Waiting for fab feedback leads to costly respins</p>
              </div>
              
              <div className="text-center">
                <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4 border border-green-500/30">
                  <DollarSign className="h-8 w-8 text-green-400" />
                </div>
                <h3 className="text-lg font-semibold text-gray-200 mb-2">Delays & Scrap</h3>
                <p className="text-sm text-gray-400">Late-stage design issues cost time and money</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Solution Section */}
      <div className="py-16 px-4">
        <div className="max-w-5xl mx-auto text-center mb-12">
          <h2 className="text-4xl font-bold text-gray-100 mb-4">Industry-Standard Rule Engines + AI</h2>
          <p className="text-xl text-gray-400 max-w-3xl mx-auto">
            Comprehensive analysis powered by IPC-2221A, IEC 62368-1, IPC-2152 standards combined with 
            RAG-enhanced GPT-4 for domain-specific insights.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto">
          <div className="card p-8">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-red-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
                <Shield className="h-6 w-6 text-red-400" />
              </div>
              <div>
                <h3 className="text-xl font-semibold text-gray-100 mb-3">High-Voltage Safety (IEC 62368-1)</h3>
                <p className="text-gray-400 leading-relaxed">
                  Automatic clearance and creepage checks per IEC 62368-1 tables. Pollution degree and 
                  material group aware. Mains isolation verification with optocoupler/transformer detection.
                </p>
              </div>
            </div>
          </div>

          <div className="card p-8">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-purple-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
                <BookOpen className="h-6 w-6 text-purple-400" />
              </div>
              <div>
                <h3 className="text-xl font-semibold text-gray-100 mb-3">RAG-Powered AI Analysis</h3>
                <p className="text-gray-400 leading-relaxed">
                  GPT-4 enhanced with retrieval from IPC standards, TI/NXP app notes, and design guides.
                  Evidence-based findings with standard references, not generic advice.
                </p>
              </div>
            </div>
          </div>

          <div className="card p-8">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-blue-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
                <Layers className="h-6 w-6 text-blue-400" />
              </div>
              <div>
                <h3 className="text-xl font-semibold text-gray-100 mb-3">High-Speed Interfaces</h3>
                <p className="text-gray-400 leading-relaxed">
                  USB/PCIe/HDMI differential impedance checks, length matching validation, 5W spacing rule.
                  Reference plane continuity and via discontinuity analysis.
                </p>
              </div>
            </div>
          </div>

          <div className="card p-8">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-orange-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
                <ThermometerSun className="h-6 w-6 text-orange-400" />
              </div>
              <div>
                <h3 className="text-xl font-semibold text-gray-100 mb-3">Thermal & Current Analysis</h3>
                <p className="text-gray-400 leading-relaxed">
                  IPC-2152 trace current capacity, via thermal analysis, component power dissipation.
                  Thermal via recommendations and exposed pad heat spreading checks.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Technical Features */}
      <div className="py-16 px-4 border-t border-slate-700">
        <h2 className="text-3xl font-bold text-center text-gray-100 mb-12">
          Complete Rule Engine Coverage
        </h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto">
        <div className="card text-center">
          <div className="flex justify-center mb-4">
            <div className="p-3 bg-red-900/30 rounded-lg border border-red-600/30">
              <Shield className="h-8 w-8 text-red-500" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-gray-100 mb-2">
            Mains Safety
          </h3>
          <p className="text-sm text-gray-400">
            IEC 62368-1 clearance/creepage tables, pollution degrees, isolation barriers
          </p>
        </div>

        <div className="card text-center">
          <div className="flex justify-center mb-4">
            <div className="p-3 bg-blue-900/30 rounded-lg border border-blue-600/30">
              <Radio className="h-8 w-8 text-blue-500" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-gray-100 mb-2">
            Bus Interfaces
          </h3>
          <p className="text-sm text-gray-400">
            I2C/SPI/RS-485/CAN per TI app notes, pull-up calculations, termination
          </p>
        </div>

        <div className="card text-center">
          <div className="flex justify-center mb-4">
            <div className="p-3 bg-green-900/30 rounded-lg border border-green-600/30">
              <Zap className="h-8 w-8 text-green-500" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-gray-100 mb-2">
            Power & SMPS
          </h3>
          <p className="text-sm text-gray-400">
            Hot loop analysis, input/output capacitor placement, feedback routing
          </p>
        </div>

        <div className="card text-center">
          <div className="flex justify-center mb-4">
            <div className="p-3 bg-orange-900/30 rounded-lg border border-orange-600/30">
              <FileText className="h-8 w-8 text-orange-500" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-gray-100 mb-2">
            BOM Validation
          </h3>
          <p className="text-sm text-gray-400">
            E-series values, MLCC derating, voltage margins, standard packages
          </p>
        </div>
        </div>
      </div>

      {/* Supported Formats */}
      <div className="py-16 px-4 border-t border-slate-700">
        <h2 className="text-3xl font-bold text-center text-gray-100 mb-4">
          Universal Format Support
        </h2>
        <p className="text-center text-gray-400 mb-8 max-w-2xl mx-auto">
          Upload ZIP archives or single files - our universal parser auto-detects the format
        </p>
        <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-100 mb-3 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              PCB Native Formats
            </h3>
            <ul className="text-sm text-gray-300 space-y-1.5">
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                KiCad (.kicad_pcb, .kicad_sch)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                Eagle (.brd, .sch)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                Altium (.PcbDoc, .SchDoc)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                Cadence (.BRD, .DSN)
              </li>
            </ul>
          </div>

          <div className="card">
            <h3 className="text-lg font-semibold text-gray-100 mb-3 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span>
              Manufacturing Formats
            </h3>
            <ul className="text-sm text-gray-300 space-y-1.5">
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                Gerber RS-274X / X2
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                Excellon Drill (.drl)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                ODB++ (directory)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                IPC-2581 (.xml)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                IPC-D-356 Netlist
              </li>
            </ul>
          </div>

          <div className="card">
            <h3 className="text-lg font-semibold text-gray-100 mb-3 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-orange-500"></span>
              Assembly Data
            </h3>
            <ul className="text-sm text-gray-300 space-y-1.5">
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                BOM (CSV, Excel)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                Pick-and-Place (.pos, .csv)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                Centroid files (.xy)
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                STEP 3D models
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                IDF exchange
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* CTA */}
      <div className="text-center py-16">
        <h2 className="text-3xl font-bold text-gray-100 mb-4">
          Ready to analyze your PCB?
        </h2>
        <p className="text-lg text-gray-300 mb-8">
          Get instant feedback on design issues before manufacturing
        </p>
        {user ? (
          <Link to="/upload" className="btn-primary text-lg px-8 py-3">
            <Upload className="inline-block h-5 w-5 mr-2" />
            Upload Project
          </Link>
        ) : (
          <Link to="/signup" className="btn-primary text-lg px-8 py-3">
            <UserPlus className="inline-block h-5 w-5 mr-2" />
            Get Started Free
          </Link>
        )}
      </div>
      </div>
    </div>
  )
}
