import './MediaFullscreen.css'

export default function MediaFullscreen({ open, url, mediaType, onClose }) {
  if (!open) return null
  return (
    <div className="media-fullscreen-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <button type="button" className="media-fullscreen-close" onClick={onClose} aria-label="Close">
        ✕
      </button>
      <div className="media-fullscreen-content" onClick={(e) => e.stopPropagation()}>
        {mediaType === 'video' ? (
          <video src={url} controls autoPlay className="media-fullscreen-media" />
        ) : (
          <img src={url} alt="Full size" className="media-fullscreen-media" />
        )}
      </div>
    </div>
  )
}
