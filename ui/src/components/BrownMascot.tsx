import React, { useMemo, useRef } from 'react'
import {
  Avatar,
  type AvatarController,
  type AnimationKey,
  type ExpressionKey,
  type AvatarDefinition,
  strobiDefinition
} from '../avatar'
import { BrownMascotState } from '../types.ts'
import { useSettings } from '../context/SettingsContext'

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
  const avatarRef = useRef<AvatarController>(null)
  const { settings } = useSettings()

  // Map Brown assistant state to Strobi procedural animation or expression
  const { animation, expression } = useMemo<{
    animation?: AnimationKey
    expression?: ExpressionKey
  }>(() => {
    switch (state) {
      case 'SLEEPING':
        return { animation: 'sleeping' }
      case 'WAKE_DETECTED':
        return { animation: 'waking' }
      case 'LISTENING':
        return { animation: 'listening' }
      case 'THINKING':
        return { animation: 'thinking' }
      case 'EXECUTING':
      case 'VERIFYING':
        return { animation: 'working' }
      case 'SPEAKING':
        return { animation: 'speaking' }
      case 'HAPPY':
        return { animation: 'excited' }
      case 'CONFUSED':
        return { animation: 'suspicious' }
      case 'CONCERNED':
        return { expression: 'downward-gaze' }
      case 'ERROR':
        return { animation: 'angry' }
      case 'OFFLINE':
        return { animation: 'bored' }
      case 'IDLE':
      default:
        return { animation: 'idle' }
    }
  }, [state])

  const handleClick = () => {
    if (state === 'SLEEPING') {
      onWake()
    } else {
      onPoke()
      avatarRef.current?.play('excited')
    }
  }

  const size = settings.mascotSize || 110

  return (
    <div
      className="strobi-mascot-wrapper"
      onClick={handleClick}
      role="button"
      style={{
        width: size,
        height: size,
        filter: `drop-shadow(0 10px 22px ${settings.primaryColor}66) drop-shadow(0 4px 12px rgba(15, 9, 38, 0.5))`
      }}
      aria-label={`${settings.assistantName} assistant, state: ${state}`}
    >
      <Avatar
        ref={avatarRef}
        definition={strobiDefinition as unknown as AvatarDefinition}
        animation={animation}
        expression={expression}
        size={size}
        glossy={settings.glossyEffect}
        ariaLabel={`${settings.assistantName} procedural 3D avatar`}
      />
    </div>
  )
}
export default BrownMascot
