import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getHistory, sendMessage, getRecommendedProperties, markPropertyViewed } from '../api'
import { getSocket, joinLead, onMessageForLead, onConnect, onDisconnect } from '../socket'
import MediaFullscreen from '../components/MediaFullscreen'
import './LeadChat.css'

export default function LeadChat() {
  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [properties, setProperties] = useState([])
  const [tab, setTab] = useState('chat')
  const [live, setLive] = useState(false)
  const [sending, setSending] = useState(false)
  const [expandedPropertyId, setExpandedPropertyId] = useState(null)
  const [fullscreenMedia, setFullscreenMedia] = useState({ open: false, url: null, mediaType: 'image' })
  const messagesEndRef = useRef(null)

  useEffect(() => {
    if (!token) {
      navigate('/', { replace: true })
      return
    }
    loadHistory()
    loadProperties()
  }, [token, navigate])

  useEffect(() => {
    if (!user.id) return
    getSocket().connect()
    joinLead(user.id)
    onConnect(() => setLive(true))
    onDisconnect(() => setLive(false))
    const handler = () => {
      loadHistory()
      loadProperties()
    }
    onMessageForLead(handler)
    return () => {
      getSocket().off('message_for_lead')
    }
  }, [user.id])

  async function loadHistory() {
    try {
      const history = await getHistory(token)
      setMessages(history.map((h) => ({ role: h.role, content: h.content, created_at: h.created_at })))
    } catch (e) {
      if (e.message === 'Unauthorized') {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        navigate('/', { replace: true })
      }
    }
  }

  async function loadProperties() {
    try {
      const list = await getRecommendedProperties(token)
      setProperties(list)
    } catch (_) {}
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending) return
    setSending(true)
    setInput('')
    try {
      await sendMessage(token, text)
      await loadHistory()
      await loadProperties()
    } catch (e) {
      setInput(text)
      alert(e.message)
    } finally {
      setSending(false)
    }
  }

  function handleLogout() {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/', { replace: true })
  }

  if (!user.id) return null

  return (
    <div className="lead-app">
      <div className="lead-chat">
        <div className="lead-header">
          <h2>Broker Chat</h2>
          <span className="live-indicator">
            {live && <span className="live-dot" />}
            {live ? 'Live' : 'Offline'}
          </span>
        </div>
        <div className="lead-tabs">
          <button type="button" className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}>Chat</button>
          <button type="button" className={tab === 'properties' ? 'active' : ''} onClick={() => { setTab('properties'); loadProperties(); }}>Properties</button>
        </div>
        {tab === 'chat' && (
          <>
            <div className="lead-messages scrollable">
              {messages.map((m, i) => (
                <div key={i} className={`msg ${m.role === 'user' ? 'user' : 'assistant'}`}>
                  <div className="msg-avatar">{m.role === 'user' ? '👤' : '🏠'}</div>
                  <div>
                    <div className="msg-bubble">{m.content}</div>
                    <div className="msg-time">{m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <form className="lead-input-area" onSubmit={handleSend}>
              <div className="row">
                <textarea
                  placeholder="Type a message... (Enter to send, Shift+Enter for new line)"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      if (input.trim() && !sending) handleSend(e)
                    }
                  }}
                  disabled={sending}
                  rows={3}
                />
                <button type="submit" disabled={sending}>{sending ? '...' : 'Send'}</button>
              </div>
            </form>
          </>
        )}
        {tab === 'properties' && (
          <div className="lead-properties-full scrollable">
            <h3>Recommended properties</h3>
            {properties.length === 0 ? (
              <p className="muted">No properties recommended yet. Keep chatting so we can match you.</p>
            ) : (
              <div className="prop-list">
                {properties.map((rec) => {
                  const p = rec.property || {}
                  const recAt = rec.recommended_at ? new Date(rec.recommended_at).toLocaleDateString() : ''
                  const isExpanded = expandedPropertyId === (p.id || rec.id)
                  return (
                    <div key={rec.id || p.id} className={`prop-card lead-prop-card ${isExpanded ? 'expanded' : ''}`}>
                      <button
                        type="button"
                        className="prop-card-head"
                        onClick={() => {
                          setExpandedPropertyId(isExpanded ? null : (p.id || rec.id))
                          if (!isExpanded && p.id && user.id) markPropertyViewed(p.id, user.id).catch(() => {})
                        }}
                      >
                        <div className="prop-card-title">{p.title}</div>
                        <p className="prop-card-meta">₹{p.budget != null ? Number(p.budget).toLocaleString() : '—'} · {p.bhk || '—'} BHK · {(p.furnishing_status || '').replace(/_/g, ' ')}</p>
                        {recAt && <div className="meta">Recommended {recAt}</div>}
                        <span className="prop-card-toggle">{isExpanded ? '▼' : '▶'}</span>
                      </button>
                      {isExpanded && (
                        <div className="prop-card-detail">
                          <p><strong>Location:</strong> {p.locality || '—'}</p>
                          <p><strong>Type:</strong> {(p.property_type || '').replace(/_/g, ' ')}</p>
                          {p.area_sqft && <p><strong>Area:</strong> {p.area_sqft} sq ft</p>}
                          {p.description && <p className="prop-desc"><strong>Description:</strong> {p.description}</p>}
                          {p.amenities && <p className="prop-amenities"><strong>Amenities:</strong> {p.amenities}</p>}
                          {p.media?.length > 0 && (
                            <div className="lead-prop-media">
                              <strong>Media</strong>
                              <div className="lead-prop-media-grid">
                                {p.media.map((m) => (
                                  <div key={m.id} className="lead-prop-media-item">
                                    {m.media_type === 'image' ? (
                                      <img src={m.cloudinary_url} alt="" />
                                    ) : (
                                      <video src={m.cloudinary_url} controls />
                                    )}
                                    <button
                                      type="button"
                                      className="lead-prop-fullscreen-btn"
                                      onClick={() => setFullscreenMedia({ open: true, url: m.cloudinary_url, mediaType: m.media_type || 'image' })}
                                      title="View fullscreen"
                                    >
                                      ⛶ Fullscreen
                                    </button>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="lead-sidebar">
        <div className="lead-sidebar-title">Recommended properties</div>
        <div className="lead-sidebar-list scrollable">
          {properties.length === 0 ? (
            <p className="muted">None yet</p>
          ) : (
            properties.slice(0, 5).map((rec) => {
              const p = rec.property || {}
              return (
                <div key={rec.id || p.id} className="prop-card">
                  <strong>{p.title}</strong>
                  <p>₹{p.budget != null ? Number(p.budget).toLocaleString() : '—'} · {p.bhk || '—'} BHK</p>
                  {rec.recommended_at && <div className="meta">{new Date(rec.recommended_at).toLocaleDateString()}</div>}
                </div>
              )
            })
          )}
        </div>
        <div className="lead-user-bar">
          {user.name} · <button type="button" className="link" onClick={handleLogout}>Logout</button>
        </div>
      </div>
      <MediaFullscreen
        open={fullscreenMedia.open}
        url={fullscreenMedia.url}
        mediaType={fullscreenMedia.mediaType}
        onClose={() => setFullscreenMedia({ open: false, url: null, mediaType: 'image' })}
      />
    </div>
  )
}
