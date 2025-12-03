import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Send, CheckCircle2, Building2, User, Mail, Phone, MessageSquare } from 'lucide-react'

export default function QuotePage() {
  const [formData, setFormData] = useState({
    companyName: '',
    fullName: '',
    email: '',
    phone: '',
    projectType: '',
    boardComplexity: '',
    timeline: '',
    message: ''
  })
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    
    try {
      // Send quote request to backend
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/quotes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      })
      
      if (!response.ok) {
        throw new Error('Failed to submit quote request')
      }
      
      const result = await response.json()
      console.log('Quote request successful:', result)
      setSubmitted(true)
    } catch (error) {
      console.error('Error submitting quote:', error)
      alert('Failed to submit quote request. Please try again or contact us directly at pranavchahal@boardmint.io')
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-4">
        <div className="max-w-2xl w-full">
          <div className="card p-12 text-center">
            <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircle2 className="h-10 w-10 text-green-400" />
            </div>
            <h1 className="text-4xl font-bold text-gray-100 mb-4">Thank You!</h1>
            <p className="text-xl text-gray-300 mb-6">
              We've received your quote request.
            </p>
            <p className="text-gray-400 mb-8 leading-relaxed">
              Our team will review your requirements and get back to you within 24 hours 
              with a customized solution and pricing.
            </p>
            <div className="flex gap-4 justify-center flex-wrap">
              <Link to="/" className="btn-primary">
                <ArrowLeft className="inline-block h-5 w-5 mr-2" />
                Back to Home
              </Link>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-black">
      <div className="max-w-6xl mx-auto px-4 py-12">
        {/* Header */}
        <div className="mb-12">
          <Link to="/" className="inline-flex items-center text-gray-400 hover:text-pcbGreen transition-colors mb-8">
            <ArrowLeft className="h-5 w-5 mr-2" />
            Back to Home
          </Link>
          
          <div className="text-center">
            <h1 className="text-5xl font-bold mb-4" style={{
              color: '#16a34a',
              textShadow: '0 0 30px rgba(22, 163, 74, 0.5)'
            }}>Get a Custom Quote</h1>
            <p className="text-xl text-gray-400 max-w-2xl mx-auto">
              Tell us about your project and we'll provide a tailored solution for your team
            </p>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-12">
          {/* Form */}
          <div className="card p-8">
            <h2 className="text-2xl font-bold text-gray-100 mb-6">Project Details</h2>
            
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Company Name */}
              <div>
                <label htmlFor="companyName" className="block text-sm font-medium text-gray-300 mb-2">
                  Company Name *
                </label>
                <div className="relative">
                  <Building2 className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-500" />
                  <input
                    id="companyName"
                    name="companyName"
                    type="text"
                    required
                    value={formData.companyName}
                    onChange={handleChange}
                    className="w-full pl-10 pr-4 py-3 bg-gray-800 border border-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-pcbGreen focus:border-transparent transition-all placeholder-gray-500"
                    placeholder="Your Company"
                  />
                </div>
              </div>

              {/* Full Name */}
              <div>
                <label htmlFor="fullName" className="block text-sm font-medium text-gray-300 mb-2">
                  Full Name *
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-500" />
                  <input
                    id="fullName"
                    name="fullName"
                    type="text"
                    required
                    value={formData.fullName}
                    onChange={handleChange}
                    className="w-full pl-10 pr-4 py-3 bg-gray-800 border border-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-pcbGreen focus:border-transparent transition-all placeholder-gray-500"
                    placeholder="John Doe"
                  />
                </div>
              </div>

              {/* Email & Phone */}
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
                    Email *
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-500" />
                    <input
                      id="email"
                      name="email"
                      type="email"
                      required
                      value={formData.email}
                      onChange={handleChange}
                      className="w-full pl-10 pr-4 py-3 bg-gray-800 border border-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-pcbGreen focus:border-transparent transition-all placeholder-gray-500"
                      placeholder="you@company.com"
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="phone" className="block text-sm font-medium text-gray-300 mb-2">
                    Phone
                  </label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-500" />
                    <input
                      id="phone"
                      name="phone"
                      type="tel"
                      value={formData.phone}
                      onChange={handleChange}
                      className="w-full pl-10 pr-4 py-3 bg-gray-800 border border-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-pcbGreen focus:border-transparent transition-all placeholder-gray-500"
                      placeholder="+1 (555) 000-0000"
                    />
                  </div>
                </div>
              </div>

              {/* Project Type */}
              <div>
                <label htmlFor="projectType" className="block text-sm font-medium text-gray-300 mb-2">
                  Project Type *
                </label>
                <select
                  id="projectType"
                  name="projectType"
                  required
                  value={formData.projectType}
                  onChange={handleChange}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-pcbGreen focus:border-transparent transition-all"
                >
                  <option value="">Select project type</option>
                  <option value="building-automation">Building Automation</option>
                  <option value="iot">IoT / Connected Devices</option>
                  <option value="industrial">Industrial Controls</option>
                  <option value="power-electronics">Power Electronics</option>
                  <option value="medical">Medical Devices</option>
                  <option value="automotive">Automotive</option>
                  <option value="other">Other</option>
                </select>
              </div>

              {/* Board Complexity */}
              <div>
                <label htmlFor="boardComplexity" className="block text-sm font-medium text-gray-300 mb-2">
                  Board Complexity *
                </label>
                <select
                  id="boardComplexity"
                  name="boardComplexity"
                  required
                  value={formData.boardComplexity}
                  onChange={handleChange}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-pcbGreen focus:border-transparent transition-all"
                >
                  <option value="">Select complexity</option>
                  <option value="simple">Simple (2-4 layers, standard components)</option>
                  <option value="moderate">Moderate (4-6 layers, some BGAs)</option>
                  <option value="complex">Complex (6+ layers, HDI, dense BGAs)</option>
                  <option value="very-complex">Very Complex (High-speed, RF, multi-board)</option>
                </select>
              </div>

              {/* Timeline */}
              <div>
                <label htmlFor="timeline" className="block text-sm font-medium text-gray-300 mb-2">
                  Expected Timeline *
                </label>
                <select
                  id="timeline"
                  name="timeline"
                  required
                  value={formData.timeline}
                  onChange={handleChange}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-pcbGreen focus:border-transparent transition-all"
                >
                  <option value="">Select timeline</option>
                  <option value="urgent">Urgent (1-2 weeks)</option>
                  <option value="standard">Standard (2-4 weeks)</option>
                  <option value="flexible">Flexible (1-3 months)</option>
                  <option value="ongoing">Ongoing partnership</option>
                </select>
              </div>

              {/* Message */}
              <div>
                <label htmlFor="message" className="block text-sm font-medium text-gray-300 mb-2">
                  Additional Details
                </label>
                <div className="relative">
                  <MessageSquare className="absolute left-3 top-3 w-5 h-5 text-gray-500" />
                  <textarea
                    id="message"
                    name="message"
                    rows={4}
                    value={formData.message}
                    onChange={handleChange}
                    className="w-full pl-10 pr-4 py-3 bg-gray-800 border border-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-pcbGreen focus:border-transparent transition-all placeholder-gray-500 resize-none"
                    placeholder="Tell us about your specific requirements, design challenges, or questions..."
                  />
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 px-6 font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed text-lg"
                style={{
                  background: loading ? '#1a1a1a' : '#16a34a',
                  color: '#ffffff',
                  boxShadow: loading ? 'none' : '0 0 20px rgba(22, 163, 74, 0.3)'
                }}
              >
                {loading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Send className="h-5 w-5" />
                    Request Quote
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Info Sidebar */}
          <div className="space-y-6">
            {/* What to Expect */}
            <div className="card p-8">
              <h3 className="text-2xl font-bold text-gray-100 mb-6">What to Expect</h3>
              <div className="space-y-6">
                <div className="flex gap-4">
                  <div className="w-8 h-8 bg-green-500/20 rounded-full flex items-center justify-center flex-shrink-0">
                    <span className="text-green-400 font-bold">1</span>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-200 mb-1">Quick Response</h4>
                    <p className="text-sm text-gray-400">We'll review your request and respond within 24 hours</p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="w-8 h-8 bg-green-500/20 rounded-full flex items-center justify-center flex-shrink-0">
                    <span className="text-green-400 font-bold">2</span>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-200 mb-1">Custom Proposal</h4>
                    <p className="text-sm text-gray-400">Tailored solution based on your project needs</p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="w-8 h-8 bg-green-500/20 rounded-full flex items-center justify-center flex-shrink-0">
                    <span className="text-green-400 font-bold">3</span>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-200 mb-1">Transparent Pricing</h4>
                    <p className="text-sm text-gray-400">Clear breakdown of features and costs</p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="w-8 h-8 bg-green-500/20 rounded-full flex items-center justify-center flex-shrink-0">
                    <span className="text-green-400 font-bold">4</span>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-200 mb-1">Free Trial Option</h4>
                    <p className="text-sm text-gray-400">Test drive BoardMint on your actual designs</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Enterprise Features */}
            <div className="card p-8">
              <h3 className="text-xl font-bold text-gray-100 mb-4">Enterprise Features</h3>
              <ul className="space-y-3">
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-gray-300">Dedicated support & SLA</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-gray-300">Custom rule sets for your domain</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-gray-300">On-premise deployment option</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-gray-300">API integration with your workflow</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-gray-300">Team training & onboarding</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-gray-300">Volume pricing for multiple projects</span>
                </li>
              </ul>
            </div>

            {/* Contact */}
            <div className="card p-8 bg-gradient-to-br from-green-900/10 to-green-800/10 border-green-600/30">
              <h3 className="text-xl font-bold text-gray-100 mb-4">Have Questions?</h3>
              <p className="text-gray-300 mb-4">
                Prefer to talk? Our team is here to help.
              </p>
              <div className="space-y-2 text-sm">
                <p className="text-gray-400">
                  <Mail className="inline h-4 w-4 mr-2" />
                  pranavchahal@boardmint.io
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
