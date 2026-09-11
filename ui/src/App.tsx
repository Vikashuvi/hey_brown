import React, { useMemo } from 'react'
import { useBrownState } from './hooks/useBrownState.ts'
import { BrownMascot } from './components/BrownMascot.tsx'
import { BlobSpeech, type JellyBlobMood } from 'feral-blob'
import { StatusPill } from './components/StatusPill.tsx'

export const App: React.FC = () => {
  const {
    state,
    transcript,
    statusMessage,
    structuredInfo,
    blinkCount,
    celebrateCount,
    isConnected,
    handlePoke,
    handleWake
  } = useBrownState('ws://127.0.0.1:8766')

  // Map Brown state machine to feral-blob mood
  const mood: JellyBlobMood = useMemo(() => {
    switch (state) {
      case 'SLEEPING':
        return 'sleepy'
      case 'WAKE_DETECTED':
        return 'curious'
      case 'LISTENING':
        return 'neutral'
      case 'THINKING':
        return 'hmm'
      case 'EXECUTING':
        return 'neutral'
      case 'VERIFYING':
        return 'hmm'
      case 'SPEAKING':
        return 'neutral'
      case 'HAPPY':
        return 'happy'
      case 'CONFUSED':
        return 'sideEye'
      case 'CONCERNED':
        return 'sad'
      case 'ERROR':
        return 'angry'
      case 'OFFLINE':
        return 'sleepy'
      case 'IDLE':
      default:
        return 'neutral'
    }
  }, [state])

  // Speech bubble text - strictly formatted for the official BlobSpeech cloud
  const speechText = useMemo(() => {
    const formatClean = (text: string, maxLen: number = 32) => {
      const clean = text.replace(/^"|"$/g, '').trim()
      if (clean.length <= maxLen) return clean
      const sub = clean.slice(0, maxLen)
      const lastSpace = sub.lastIndexOf(' ')
      return (lastSpace > 14 ? sub.slice(0, lastSpace) : sub) + '…'
    }

    if (transcript) return formatClean(transcript)
    if (statusMessage) return formatClean(statusMessage)
    if (state === 'HAPPY') return "That's the good stuff."
    if (state === 'WAKE_DETECTED') return "Yeah, I'm here."
    if (state === 'LISTENING') return "I'm listening..."
    if (state === 'THINKING') return "Thinking..."
    if (state === 'EXECUTING') return "Executing..."
    if (state === 'SPEAKING') return "Speaking..."
    return null
  }, [transcript, statusMessage, state])

  return (
    <div className="brown-overlay-root">
      {/* Official feral-blob speech cloud directly above mascot */}
      <div className="speech-bubble-slot">
        {speechText && (
          <BlobSpeech
            mood={mood}
            messages={{ [mood]: speechText }}
          />
        )}
      </div>

      {/* Living blob character with exact library geometry and placement */}
      <div className="mascot-stage">
        <BrownMascot
          state={state}
          blinkCount={blinkCount}
          celebrateCount={celebrateCount}
          onPoke={handlePoke}
          onWake={handleWake}
        />
      </div>

      {/* Structured details drawer if present */}
      {structuredInfo && (
        <StatusPill
          state={state}
          transcript={null}
          statusMessage={null}
          structuredInfo={structuredInfo}
          isConnected={isConnected}
        />
      )}
    </div>
  )
}
export default App
