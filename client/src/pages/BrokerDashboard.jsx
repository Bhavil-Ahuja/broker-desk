import { useState, useEffect, useRef } from 'react'
import {
  getLeads,
  getLeadDetails,
  brokerSendMessage,
  approveMessage,
  rejectMessage,
  getGlobalSettings,
  updateGlobalSettings,
  toggleLeadAutoSend,
  getBrokerProperties,
  addProperty,
  uploadPropertyMedia,
  deleteProperty,
  deletePropertyMedia,
} from '../api'
import {
  getSocket,
  joinBroker,
  onNewLeadMessage,
  onNewPendingApproval,
  onMessageSent,
  onNewLead,
  onConnect,
  onDisconnect,
} from '../socket'
import MediaFullscreen from '../components/MediaFullscreen'
import './BrokerDashboard.css'

const PROPERTY_TYPES = ['apartment', 'villa', 'independent_house', 'studio', 'penthouse']
const FURNISHING_OPTIONS = ['furnished', 'semi-furnished', 'unfurnished']

export default function BrokerDashboard() {
  const [brokerPage, setBrokerPage] = useState('leads')
  const [leads, setLeads] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [leadDetail, setLeadDetail] = useState(null)
  const [reply, setReply] = useState('')
  const [sending, setSending] = useState(false)
  const [live, setLive] = useState(false)
  const [globalAutoSend, setGlobalAutoSend] = useState(true)
  const [editedApprovalMessages, setEditedApprovalMessages] = useState({})
  const [editedRecommendationIds, setEditedRecommendationIds] = useState({})
  const [addedRecommendationProperties, setAddedRecommendationProperties] = useState({})
  const [brokerPropertiesForPicker, setBrokerPropertiesForPicker] = useState([])
  const [addPropertyPickerFor, setAddPropertyPickerFor] = useState(null)
  const messagesEndRef = useRef(null)

  // Properties tab state
  const [properties, setProperties] = useState([])
  const [showAddProperty, setShowAddProperty] = useState(false)
  const [newPropertyId, setNewPropertyId] = useState(null)
  const [uploadModeFor, setUploadModeFor] = useState(null)
  const [confirmDeleteMedia, setConfirmDeleteMedia] = useState(null)
  const [confirmDeleteProp, setConfirmDeleteProp] = useState(null)
  const [fullscreenMedia, setFullscreenMedia] = useState({ open: false, url: null, mediaType: 'image' })
  const [addForm, setAddForm] = useState({
    title: '', locality: '', bhk: 2, budget: 5000000, property_type: 'apartment',
    furnishing_status: 'furnished', area_sqft: 1200, available_from: '', amenities: '', description: '',
  })

  useEffect(() => {
    loadLeads()
    getGlobalSettings().then((s) => setGlobalAutoSend(s.global_auto_send !== false)).catch(() => {})
  }, [])

  useEffect(() => {
    if (brokerPage === 'properties') loadProperties()
  }, [brokerPage])

  useEffect(() => {
    const hasRecommendations = leadDetail?.pending_approvals?.some((a) => (a.recommended_property_ids || []).length > 0)
    if (hasRecommendations && brokerPropertiesForPicker.length === 0) {
      getBrokerProperties().then(setBrokerPropertiesForPicker).catch(() => {})
    }
  }, [leadDetail?.pending_approvals, brokerPage])

  async function loadProperties() {
    try {
      const list = await getBrokerProperties()
      setProperties(list)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    getSocket().connect()
    joinBroker()
    onConnect(() => setLive(true))
    onDisconnect(() => setLive(false))
    const refresh = () => {
      loadLeads()
      if (selectedId) loadLeadDetail(selectedId)
    }
    onNewLeadMessage(refresh)
    onNewPendingApproval(refresh)
    onMessageSent(refresh)
    onNewLead(loadLeads)
    return () => {
      getSocket().off('new_lead_message')
      getSocket().off('new_pending_approval')
      getSocket().off('message_sent')
      getSocket().off('new_lead')
    }
  }, [selectedId])

  useEffect(() => {
    if (selectedId) loadLeadDetail(selectedId)
    else setLeadDetail(null)
  }, [selectedId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [leadDetail?.conversations])

  async function loadLeads() {
    try {
      const list = await getLeads()
      setLeads(list)
      if (!selectedId && list.length > 0) setSelectedId(list[0].lead?.id)
    } catch (e) {
      console.error(e)
    }
  }

  async function loadLeadDetail(id) {
    try {
      const data = await getLeadDetails(id)
      setLeadDetail(data)
    } catch (e) {
      setLeadDetail(null)
    }
  }

  async function handleSend(e) {
    e.preventDefault()
    const text = reply.trim()
    if (!text || !selectedId || sending) return
    setSending(true)
    setReply('')
    try {
      await brokerSendMessage(selectedId, text)
      await loadLeadDetail(selectedId)
      await loadLeads()
    } catch (err) {
      alert(err.message)
      setReply(text)
    } finally {
      setSending(false)
    }
  }

  async function handleApprove(approvalId) {
    const approval = leadDetail?.pending_approvals?.find((a) => a.id === approvalId)
    const message = (editedApprovalMessages[approvalId] != null ? editedApprovalMessages[approvalId] : approval?.ai_message) ?? ''
    const recommendationIds = editedRecommendationIds[approvalId] ?? approval?.recommended_property_ids ?? []
    const body = { custom_message: message.trim() || approval?.ai_message }
    if (approval && Array.isArray(approval.recommended_property_ids)) {
      body.recommended_property_ids = recommendationIds
    }
    try {
      await approveMessage(approvalId, body)
      setEditedApprovalMessages((prev) => { const next = { ...prev }; delete next[approvalId]; return next })
      setEditedRecommendationIds((prev) => { const next = { ...prev }; delete next[approvalId]; return next })
      setAddedRecommendationProperties((prev) => { const next = { ...prev }; delete next[approvalId]; return next })
      setAddPropertyPickerFor(null)
      await loadLeadDetail(selectedId)
      await loadLeads()
    } catch (e) {
      alert(e.message)
    }
  }

  async function handleReject(approvalId) {
    try {
      await rejectMessage(approvalId)
      setEditedRecommendationIds((prev) => { const next = { ...prev }; delete next[approvalId]; return next })
      setAddedRecommendationProperties((prev) => { const next = { ...prev }; delete next[approvalId]; return next })
      setAddPropertyPickerFor(null)
      await loadLeadDetail(selectedId)
      await loadLeads()
    } catch (e) {
      alert(e.message)
    }
  }

  function getCurrentRecommendationIds(approval) {
    return editedRecommendationIds[approval.id] ?? approval.recommended_property_ids ?? []
  }

  function getPropertyForRecommendation(approval, propertyId) {
    const fromList = (approval.recommended_properties || []).find((p) => p.id === propertyId)
    if (fromList) return fromList
    return addedRecommendationProperties[approval.id]?.[propertyId]
  }

  function handleRemoveRecommendation(approvalId, propertyId) {
    setEditedRecommendationIds((prev) => {
      const current = prev[approvalId] ?? leadDetail?.pending_approvals?.find((a) => a.id === approvalId)?.recommended_property_ids ?? []
      return { ...prev, [approvalId]: current.filter((id) => id !== propertyId) }
    })
  }

  function handleAddRecommendation(approvalId, property) {
    setEditedRecommendationIds((prev) => {
      const current = prev[approvalId] ?? leadDetail?.pending_approvals?.find((a) => a.id === approvalId)?.recommended_property_ids ?? []
      if (current.includes(property.id)) return prev
      return { ...prev, [approvalId]: [...current, property.id] }
    })
    setAddedRecommendationProperties((prev) => ({
      ...prev,
      [approvalId]: { ...(prev[approvalId] || {}), [property.id]: property },
    }))
    setAddPropertyPickerFor(null)
  }

  async function handleGlobalAutoSendChange(checked) {
    try {
      await updateGlobalSettings(checked)
      setGlobalAutoSend(checked)
    } catch (e) {
      alert(e.message)
    }
  }

  async function handleLeadAutoSendChange(leadId, checked) {
    try {
      await toggleLeadAutoSend(leadId, checked)
      await loadLeadDetail(selectedId)
      await loadLeads()
    } catch (e) {
      alert(e.message)
    }
  }

  async function handleAddProperty(e) {
    e.preventDefault()
    if (!addForm.title?.trim() || !addForm.locality?.trim()) {
      alert('Title and Locality are required')
      return
    }
    try {
      const data = await addProperty({
        title: addForm.title.trim(),
        locality: addForm.locality.trim(),
        bhk: Number(addForm.bhk) || 2,
        budget: Number(addForm.budget) || 5000000,
        property_type: addForm.property_type,
        furnishing_status: addForm.furnishing_status,
        area_sqft: addForm.area_sqft ? Number(addForm.area_sqft) : null,
        available_from: addForm.available_from || null,
        amenities: addForm.amenities || null,
        description: addForm.description || null,
      })
      setShowAddProperty(false)
      setNewPropertyId(data.property?.id ?? data.id)
      setAddForm({ title: '', locality: '', bhk: 2, budget: 5000000, property_type: 'apartment', furnishing_status: 'furnished', area_sqft: 1200, available_from: '', amenities: '', description: '' })
      await loadProperties()
    } catch (e) {
      alert(e.message)
    }
  }

  async function handleUploadMedia(propertyId, files) {
    if (!files?.length) return
    try {
      for (const file of files) {
        await uploadPropertyMedia(propertyId, file)
      }
      setNewPropertyId(null)
      setUploadModeFor(null)
      await loadProperties()
    } catch (e) {
      alert(e.message)
    }
  }

  async function handleDeleteProperty(propId) {
    try {
      await deleteProperty(propId)
      setConfirmDeleteProp(null)
      await loadProperties()
    } catch (e) {
      alert(e.message)
    }
  }

  async function handleDeleteMedia(mediaId) {
    try {
      await deletePropertyMedia(mediaId)
      setConfirmDeleteMedia(null)
      await loadProperties()
    } catch (e) {
      alert(e.message)
    }
  }

  const selectedLead = leads.find((l) => l.lead?.id === selectedId)
  const leadAutoSend = leadDetail?.lead?.auto_send != null ? Boolean(leadDetail.lead.auto_send) : true

  return (
    <div className={`broker-app ${brokerPage === 'properties' ? 'broker-app-properties' : ''}`}>
      <div className="broker-leads">
        <div className="broker-nav-tabs">
          <button type="button" className={brokerPage === 'leads' ? 'active' : ''} onClick={() => setBrokerPage('leads')}>Leads</button>
          <button type="button" className={brokerPage === 'properties' ? 'active' : ''} onClick={() => setBrokerPage('properties')}>Properties</button>
        </div>
        {brokerPage === 'leads' && (
          <>
            <div className="broker-leads-header">Leads</div>
            <div className="broker-leads-list scrollable">
          {leads.map((item) => {
            const lead = item.lead || {}
            const isSelected = lead.id === selectedId
            return (
              <button
                type="button"
                key={lead.id}
                className={`broker-lead-row ${isSelected ? 'selected' : ''}`}
                onClick={() => setSelectedId(lead.id)}
              >
                <div className="name">{lead.name || 'Unknown'}</div>
                <div className="preview">{item.latest_message || 'No messages'}</div>
                {item.pending_approvals > 0 && (
                  <span className="badge">{item.pending_approvals} approval{item.pending_approvals !== 1 ? 's' : ''}</span>
                )}
              </button>
            )
          })}
            </div>
            <p className="broker-leads-footer">
              <a href="/">Lead app →</a>
            </p>
          </>
        )}
      </div>
      {brokerPage === 'leads' && (
        <>
      <div className="broker-chat">
        {selectedId && leadDetail ? (
          <>
            <div className="broker-chat-header">
              <h3>{leadDetail.lead?.name || 'Lead'}</h3>
              <div className="broker-chat-header-right">
                <label className="broker-toggle">
                  <span className="broker-toggle-label">🤖 Auto-Send</span>
                  <input
                    type="checkbox"
                    checked={leadAutoSend}
                    onChange={(e) => handleLeadAutoSendChange(selectedId, e.target.checked)}
                  />
                  <span className="broker-toggle-slider" />
                </label>
                <span className="live-indicator">
                  {live && <span className="live-dot" />}
                  {live ? 'Live' : 'Offline'}
                </span>
              </div>
            </div>
            <div className="broker-messages scrollable">
              {(leadDetail.conversations || []).map((c, i) => (
                <div key={i} className={`msg ${c.role === 'user' ? 'assistant' : 'user'}`}>
                  <div className="msg-avatar">{c.role === 'user' ? '👤' : '🤖'}</div>
                  <div>
                    <div className="msg-bubble">{c.content}</div>
                    <div className="msg-time">
                      {c.created_at ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                      {c.sent_by === 'broker' && ' · You'}
                      {c.sent_by === 'ai' && ' · AI'}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <form className="broker-input-area" onSubmit={handleSend}>
              <div className="row">
                <textarea
                  placeholder="Reply to lead... (Enter to send, Shift+Enter for new line)"
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      if (reply.trim() && selectedId && !sending) handleSend(e)
                    }
                  }}
                  disabled={sending}
                  rows={3}
                />
                <button type="submit" disabled={sending}>{sending ? '...' : 'Send'}</button>
              </div>
            </form>
          </>
        ) : (
          <div className="broker-chat-empty">Select a lead</div>
        )}
      </div>
      <div className="broker-detail">
        <div className="broker-detail-title">Details & approvals</div>
        <div className="broker-detail-content scrollable">
          <div className="broker-detail-section">
            <h4>Settings</h4>
            <label className="broker-toggle">
              <span className="broker-toggle-label">🌐 Global Auto-Send</span>
              <input
                type="checkbox"
                checked={globalAutoSend}
                onChange={(e) => handleGlobalAutoSendChange(e.target.checked)}
              />
              <span className="broker-toggle-slider" />
            </label>
            <p className="broker-toggle-hint">When on, AI replies go to leads without approval. When off, you must approve each reply.</p>
          </div>
          {leadDetail?.requirements && (
            <div className="broker-detail-section">
              <h4>Requirements</h4>
              <p>
                {leadDetail.requirements.bhk && `${leadDetail.requirements.bhk} BHK · `}
                {leadDetail.requirements.preferred_locality || '—'} ·{' '}
                {leadDetail.requirements.furnishing || '—'} ·{' '}
                {leadDetail.requirements.budget_max != null ? `Up to ₹${Number(leadDetail.requirements.budget_max).toLocaleString()}` : '—'}
              </p>
            </div>
          )}
          <div className="broker-detail-section">
            <h4>Pending approvals</h4>
            {(!leadDetail?.pending_approvals || leadDetail.pending_approvals.length === 0) ? (
              <p className="muted">None</p>
            ) : (
              leadDetail.pending_approvals.map((a) => {
                const hasRecommendations = (a.recommended_property_ids || []).length > 0
                const currentIds = getCurrentRecommendationIds(a)
                const availableToAdd = brokerPropertiesForPicker.filter((p) => !currentIds.includes(p.id))
                return (
                <div key={a.id} className="pending-block">
                  <div className="pending-block-label">AI reply — edit if needed, then Approve</div>
                  <textarea
                    className="pending-block-edit"
                    value={editedApprovalMessages[a.id] != null ? editedApprovalMessages[a.id] : (a.ai_message || '')}
                    onChange={(e) => setEditedApprovalMessages((prev) => ({ ...prev, [a.id]: e.target.value }))}
                    placeholder="AI reply..."
                    rows={4}
                  />
                  {hasRecommendations && (
                    <div className="pending-recommendations">
                      <div className="pending-recommendations-header">
                        <span className="pending-recommendations-title">Properties to recommend ({currentIds.length})</span>
                        {availableToAdd.length > 0 && (
                          <div className="pending-recommendations-add">
                            <button type="button" className="btn-secondary small" onClick={() => setAddPropertyPickerFor(addPropertyPickerFor === a.id ? null : a.id)}>+ Add property</button>
                            {addPropertyPickerFor === a.id && (
                              <div className="pending-recommendations-picker">
                                {availableToAdd.map((p) => (
                                  <button type="button" key={p.id} className="pending-picker-item" onClick={() => handleAddRecommendation(a.id, p)}>
                                    {p.title} · {p.locality} · ₹{Number(p.budget).toLocaleString()}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="pending-recommendations-list">
                        {currentIds.map((pid) => {
                          const prop = getPropertyForRecommendation(a, pid)
                          if (!prop) return null
                          return (
                            <div key={pid} className="pending-rec-card">
                              <div className="pending-rec-card-body">
                                <strong>{prop.title}</strong>
                                <span>{prop.locality} · {prop.bhk} BHK · ₹{Number(prop.budget).toLocaleString()}</span>
                              </div>
                              <button type="button" className="btn-danger small" onClick={() => handleRemoveRecommendation(a.id, pid)} title="Remove from list">Remove</button>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                  <div className="actions">
                    <button type="button" className="btn-approve" onClick={() => handleApprove(a.id)}>Approve & send</button>
                    <button type="button" className="btn-reject" onClick={() => handleReject(a.id)}>Reject</button>
                  </div>
                </div>
                )
              })
            )}
          </div>
        </div>
      </div>
        </>
      )}
      {brokerPage === 'properties' && (
        <div className="broker-properties-panel scrollable">
          <div className="broker-properties-header">
            <h2>Property Management</h2>
            <div className="broker-properties-actions">
              <button type="button" className="btn-secondary" onClick={loadProperties}>Refresh</button>
              {!showAddProperty && !newPropertyId && (
                <button type="button" className="btn-primary" onClick={() => setShowAddProperty(true)}>Add New Property</button>
              )}
            </div>
          </div>

          {showAddProperty && !newPropertyId && (
            <div className="broker-add-property-form">
              <h3>Add New Property</h3>
              <form onSubmit={handleAddProperty}>
                <div className="form-row">
                  <label>Title *</label>
                  <input value={addForm.title} onChange={(e) => setAddForm((f) => ({ ...f, title: e.target.value }))} placeholder="e.g. 3BHK Luxury Apartment" required />
                </div>
                <div className="form-row">
                  <label>Locality *</label>
                  <input value={addForm.locality} onChange={(e) => setAddForm((f) => ({ ...f, locality: e.target.value }))} placeholder="e.g. Whitefield" required />
                </div>
                <div className="form-row two-cols">
                  <div><label>BHK</label><input type="number" min={1} max={10} value={addForm.bhk} onChange={(e) => setAddForm((f) => ({ ...f, bhk: e.target.value }))} /></div>
                  <div><label>Budget (₹)</label><input type="number" min={0} step="any" value={addForm.budget} onChange={(e) => setAddForm((f) => ({ ...f, budget: e.target.value }))} /></div>
                </div>
                <div className="form-row two-cols">
                  <div><label>Type</label><select value={addForm.property_type} onChange={(e) => setAddForm((f) => ({ ...f, property_type: e.target.value }))}>{PROPERTY_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}</select></div>
                  <div><label>Furnishing</label><select value={addForm.furnishing_status} onChange={(e) => setAddForm((f) => ({ ...f, furnishing_status: e.target.value }))}>{FURNISHING_OPTIONS.map((t) => <option key={t} value={t}>{t.replace(/-/g, ' ')}</option>)}</select></div>
                </div>
                <div className="form-row two-cols">
                  <div><label>Area (sq ft)</label><input type="number" min={0} value={addForm.area_sqft} onChange={(e) => setAddForm((f) => ({ ...f, area_sqft: e.target.value }))} /></div>
                  <div><label>Available from</label><input type="date" value={addForm.available_from} onChange={(e) => setAddForm((f) => ({ ...f, available_from: e.target.value }))} /></div>
                </div>
                <div className="form-row"><label>Amenities</label><input value={addForm.amenities} onChange={(e) => setAddForm((f) => ({ ...f, amenities: e.target.value }))} placeholder="Gym, Pool, Parking" /></div>
                <div className="form-row"><label>Description</label><textarea value={addForm.description} onChange={(e) => setAddForm((f) => ({ ...f, description: e.target.value }))} rows={3} placeholder="Describe the property..." /></div>
                <div className="form-actions">
                  <button type="submit" className="btn-primary">Save &amp; Continue to Upload Media</button>
                  <button type="button" className="btn-secondary" onClick={() => setShowAddProperty(false)}>Cancel</button>
                </div>
              </form>
            </div>
          )}

          {newPropertyId && (
            <div className="broker-upload-media-section">
              <h3>Upload property media</h3>
              <p className="muted">Property created. Add images or videos (jpg, png, mp4, webp).</p>
              <input type="file" accept="image/*,video/*" multiple onChange={(e) => { const files = e.target.files; if (files?.length) handleUploadMedia(newPropertyId, Array.from(files)); e.target.value = ''; }} />
              <div className="upload-media-buttons">
                <button type="button" className="btn-secondary" onClick={() => { setNewPropertyId(null); loadProperties(); }}>Done</button>
              </div>
            </div>
          )}

          {!showAddProperty && !newPropertyId && properties.length === 0 && (
            <p className="muted">No properties yet. Click Add New Property to get started.</p>
          )}

          {!showAddProperty && !newPropertyId && properties.length > 0 && (
            <div className="broker-properties-list">
              {properties.map((prop) => (
                <div key={prop.id} className="broker-property-card">
                  <h4>{prop.title}</h4>
                  <div className="broker-property-meta">
                    <span>{prop.locality}</span>
                    <span>{prop.bhk} BHK</span>
                    <span>₹{Number(prop.budget).toLocaleString()}</span>
                    <span>{(prop.property_type || '').replace(/_/g, ' ')}</span>
                    <span>{(prop.furnishing_status || '').replace(/_/g, ' ')}</span>
                  </div>
                  {prop.description && <p className="broker-property-desc">{prop.description}</p>}
                  {prop.amenities && <p className="broker-property-amenities">Amenities: {prop.amenities}</p>}
                  <div className="broker-property-actions">
                    <button type="button" className="btn-secondary" onClick={() => setUploadModeFor(uploadModeFor === prop.id ? null : prop.id)}>{uploadModeFor === prop.id ? 'Cancel' : 'Add Media'}</button>
                    {confirmDeleteProp === prop.id ? (
                      <>
                        <span className="confirm-text">Delete property?</span>
                        <button type="button" className="btn-danger" onClick={() => handleDeleteProperty(prop.id)}>Yes, delete</button>
                        <button type="button" className="btn-secondary" onClick={() => setConfirmDeleteProp(null)}>Cancel</button>
                      </>
                    ) : (
                      <button type="button" className="btn-danger" onClick={() => setConfirmDeleteProp(prop.id)}>Delete property</button>
                    )}
                  </div>
                  {uploadModeFor === prop.id && (
                    <div className="broker-upload-inline">
                      <input type="file" accept="image/*,video/*" multiple onChange={(e) => { const files = e.target.files; if (files?.length) handleUploadMedia(prop.id, Array.from(files)); setUploadModeFor(null); e.target.value = ''; }} />
                    </div>
                  )}
                  {prop.media?.length > 0 && (
                    <div className="broker-media-gallery">
                      <h5>Media ({prop.media.length})</h5>
                      <div className="broker-media-grid">
                        {prop.media.map((m) => (
                          <div key={m.id} className="broker-media-item">
                            {m.media_type === 'image' ? (
                              <img src={m.cloudinary_url} alt="" />
                            ) : (
                              <video src={m.cloudinary_url} controls />
                            )}
                            <div className="broker-media-item-actions">
                              <button type="button" className="btn-icon" onClick={() => setFullscreenMedia({ open: true, url: m.cloudinary_url, mediaType: m.media_type || 'image' })} title="Fullscreen">⛶</button>
                              {confirmDeleteMedia === m.id ? (
                                <>
                                  <button type="button" className="btn-danger small" onClick={() => handleDeleteMedia(m.id)}>Confirm</button>
                                  <button type="button" className="btn-secondary small" onClick={() => setConfirmDeleteMedia(null)}>Cancel</button>
                                </>
                              ) : (
                                <button type="button" className="btn-danger small" onClick={() => setConfirmDeleteMedia(m.id)}>Delete</button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <MediaFullscreen
        open={fullscreenMedia.open}
        url={fullscreenMedia.url}
        mediaType={fullscreenMedia.mediaType}
        onClose={() => setFullscreenMedia({ open: false, url: null, mediaType: 'image' })}
      />
    </div>
  )
}
