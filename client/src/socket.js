import { io } from 'socket.io-client'

let socket = null

export function getSocket() {
  if (!socket) {
    socket = io(window.location.origin, { path: '/socket.io', transports: ['websocket', 'polling'] })
  }
  return socket
}

export function joinLead(leadId) {
  const s = getSocket()
  s.emit('join_lead', { lead_id: leadId })
}

export function joinBroker() {
  const s = getSocket()
  s.emit('join_broker')
}

export function onMessageForLead(cb) {
  getSocket().on('message_for_lead', cb)
}

export function onNewLeadMessage(cb) {
  getSocket().on('new_lead_message', cb)
}

export function onNewPendingApproval(cb) {
  getSocket().on('new_pending_approval', cb)
}

export function onMessageSent(cb) {
  getSocket().on('message_sent', cb)
}

export function onNewLead(cb) {
  getSocket().on('new_lead', cb)
}

export function onConnect(cb) {
  getSocket().on('connect', cb)
}

export function onDisconnect(cb) {
  getSocket().on('disconnect', cb)
}

export function off(event) {
  if (socket) socket.off(event)
}
