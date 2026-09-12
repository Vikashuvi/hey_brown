import React from 'react'

interface SpeechBubbleProps {
  text: string | null
  className?: string
}

export const SpeechBubble: React.FC<SpeechBubbleProps> = ({ text, className = '' }) => {
  if (!text) return null

  return (
    <div className={`strobi-speech-container ${className}`}>
      <div className="strobi-speech-bubble">
        <span className="strobi-speech-text">{text}</span>
        {/* Downward comic pointer towards Strobi crown */}
        <div className="strobi-speech-caret" aria-hidden="true" />
      </div>
    </div>
  )
}
