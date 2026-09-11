import React, { useMemo } from 'react'
import { JellyBlobMascot, type JellyBlobMood } from 'feral-blob'
import 'feral-blob/blob.css'
import { BrownMascotState } from '../types.ts'

interface BrownMascotProps {
  state: BrownMascotState
  blinkCount: number
  celebrateCount: number
  onPoke: () => void
  onWake: () => void
}

export const BrownMascot: React.FC<BrownMascotProps> = ({
  state,
  blinkCount,
  celebrateCount,
  onPoke,
  onWake
}) => {
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

  // Native smooth talking loop provided directly by feral-blob
  const mouth = state === 'SPEAKING' ? 'open' : undefined

  // Nod during SPEAKING for lifelike cadence
  const nod = state === 'SPEAKING'

  // Sparkle in eyes during active states
  const sparkle = state === 'LISTENING' || state === 'HAPPY'

  // CSS class for simple state hooks
  const stateClass = `brown-mascot--${state.toLowerCase()}`

  return (
    <div className={`brown-mascot-wrapper ${stateClass}`}>
      <JellyBlobMascot
        mood={mood}
        mouth={mouth}
        nod={nod}
        sparkle={sparkle}
        blink={blinkCount}
        celebrate={celebrateCount}
        onPoke={onPoke}
        onWake={onWake}
        eyeStyle="v1"
        happyEyes="smile"
        className="brown-mascot-svg"
      />
    </div>
  )
}
