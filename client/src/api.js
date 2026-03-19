const API = '/api'

function headers(token) {
  const h = { 'Content-Type': 'application/json' }
  if (token) h['Authorization'] = token
  return h
}

export async function register(body) {
  const res = await fetch(`${API}/register`, { method: 'POST', headers: headers(), body: JSON.stringify(body) })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Registration failed')
  return data
}

export async function login(body) {
  const res = await fetch(`${API}/login`, { method: 'POST', headers: headers(), body: JSON.stringify(body) })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Login failed')
  return data
}

export async function getHistory(token) {
  const res = await fetch(`${API}/history`, { headers: headers(token) })
  if (res.status === 401) throw new Error('Unauthorized')
  const data = await res.json()
  return data.history || []
}

export async function sendMessage(token, message) {
  const res = await fetch(`${API}/send`, {
    method: 'POST',
    headers: headers(token),
    body: JSON.stringify({ message }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Send failed')
  return data
}

export async function getRecommendedProperties(token) {
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const leadId = user.id
  if (!leadId) return []
  const res = await fetch(`${API}/lead/properties/recommended?lead_id=${leadId}`, { headers: headers(token) })
  if (!res.ok) return []
  return res.json()
}

export async function getLeads() {
  const res = await fetch(`${API}/broker/leads`)
  if (!res.ok) throw new Error('Failed to load leads')
  const data = await res.json()
  return data.leads || []
}

export async function getLeadDetails(leadId) {
  const res = await fetch(`${API}/broker/lead/${leadId}`)
  if (!res.ok) throw new Error('Failed to load lead')
  return res.json()
}

export async function brokerSendMessage(leadId, message) {
  const res = await fetch(`${API}/broker/send_message`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ lead_id: leadId, message }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Send failed')
  return data
}

export async function approveMessage(approvalId, body = {}) {
  const res = await fetch(`${API}/broker/approval/${approvalId}/approve`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Approve failed')
  return data
}

export async function rejectMessage(approvalId, body = {}) {
  const res = await fetch(`${API}/broker/approval/${approvalId}/reject`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Reject failed')
  return data
}

export async function getGlobalSettings() {
  const res = await fetch(`${API}/broker/global_settings`)
  if (!res.ok) throw new Error('Failed to load settings')
  return res.json()
}

export async function updateGlobalSettings(global_auto_send) {
  const res = await fetch(`${API}/broker/global_settings`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify({ global_auto_send }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Update failed')
  return data
}

export async function toggleLeadAutoSend(leadId, auto_send) {
  const res = await fetch(`${API}/broker/lead/${leadId}/auto_send`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify({ auto_send }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Update failed')
  return data
}

// Broker properties
const BROKER_ID = 1

export async function getBrokerProperties() {
  const res = await fetch(`${API}/broker/properties?broker_id=${BROKER_ID}`)
  if (!res.ok) throw new Error('Failed to load properties')
  const data = await res.json()
  return data.properties || []
}

export async function addProperty(body) {
  const res = await fetch(`${API}/broker/property`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ ...body, broker_id: BROKER_ID }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Failed to add property')
  return data
}

export async function uploadPropertyMedia(propertyId, file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API}/broker/property/${propertyId}/media`, {
    method: 'POST',
    body: form,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Upload failed')
  return data
}

export async function deleteProperty(propertyId) {
  const res = await fetch(`${API}/broker/property/${propertyId}`, { method: 'DELETE' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Delete failed')
  return data
}

export async function deletePropertyMedia(mediaId) {
  const res = await fetch(`${API}/broker/property/media/${mediaId}`, { method: 'DELETE' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Delete failed')
  return data
}

export async function markPropertyViewed(propertyId, leadId) {
  const res = await fetch(`${API}/lead/property/${propertyId}/view`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ lead_id: leadId }),
  })
  if (!res.ok) return
  return res.json()
}
