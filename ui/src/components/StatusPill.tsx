import React from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { BrownMascotState, StructuredInfo } from '../types.ts'
import { Mic, Brain, Volume2, WifiOff, AlertCircle, Sparkles, Play, CheckCircle, Search } from 'lucide-react'

interface StatusPillProps {
  state: BrownMascotState
  transcript: string | null
  statusMessage: string | null
  structuredInfo?: StructuredInfo | null
  isConnected: boolean
}

export const StatusPill: React.FC<StatusPillProps> = ({
  state,
  transcript,
  statusMessage,
  structuredInfo,
  isConnected
}) => {
  const isVisible = Boolean(
    transcript ||
    statusMessage ||
    state === 'WAKE_DETECTED' ||
    state === 'LISTENING' ||
    state === 'THINKING' ||
    state === 'EXECUTING' ||
    state === 'VERIFYING' ||
    state === 'SPEAKING' ||
    state === 'HAPPY' ||
    state === 'ERROR' ||
    !isConnected
  )

  const getStateIcon = () => {
    if (!isConnected) return <WifiOff size={13} className="text-red-400" />
    switch (state) {
      case 'WAKE_DETECTED':
        return <Sparkles size={13} className="text-amber-300 status-icon-pulse" />
      case 'LISTENING':
        return <Mic size={13} className="status-icon-pulse text-amber-400" />
      case 'THINKING':
        return <Brain size={13} className="status-icon-spin text-purple-400" />
      case 'EXECUTING':
        return <Play size={13} className="text-amber-400 status-icon-pulse" />
      case 'VERIFYING':
        return <Search size={13} className="text-blue-400 status-icon-spin" />
      case 'SPEAKING':
        return <Volume2 size={13} className="status-icon-wave text-amber-300" />
      case 'HAPPY':
        return <CheckCircle size={13} className="text-emerald-400" />
      case 'ERROR':
        return <AlertCircle size={13} className="text-rose-400" />
      default:
        return null
    }
  }

  const displayText = transcript || statusMessage || (state !== 'IDLE' && state !== 'SLEEPING' ? state : '')

  return (
    <div className="status-container">
      <AnimatePresence>
        {isVisible && displayText && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.94 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.96 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="status-pill-container"
          >
            <div className="status-pill-badge">
              {getStateIcon()}
              <span className="status-pill-text">{displayText}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Optional minimal translucent information card */}
      <AnimatePresence>
        {structuredInfo && (
          <motion.div
            initial={{ opacity: 0, height: 0, scale: 0.96 }}
            animate={{ opacity: 1, height: 'auto', scale: 1 }}
            exit={{ opacity: 0, height: 0, scale: 0.96 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="structured-info-card"
          >
            {structuredInfo.title && (
              <div className="info-card-header">{structuredInfo.title}</div>
            )}
            {structuredInfo.items && (
              <ul className="info-card-list">
                {structuredInfo.items.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            )}
            {structuredInfo.details && (
              <div className="info-card-grid">
                {Object.entries(structuredInfo.details).slice(0, 6).map(([k, v]) => (
                  <div key={k} className="info-grid-row">
                    <span className="info-grid-key">{k}</span>
                    <span className="info-grid-val">{String(v)}</span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
