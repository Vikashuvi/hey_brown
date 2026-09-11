import { useState, useEffect, useRef, useCallback } from 'react'
import { BrownMascotState, StructuredInfo, UIEventMessage } from '../types.ts'

declare global {
  interface Window {
    webkit?: {
      messageHandlers?: {
        brownNative?: {
          postMessage: (msg: any) => void
        }
      }
    }
  }
}

interface UseBrownStateReturn {
  state: BrownMascotState
  transcript: string | null
  statusMessage: string | null
  structuredInfo: StructuredInfo | null
  audioLevel: number
  blinkCount: number
  celebrateCount: number
  isConnected: boolean
  handlePoke: () => void
  handleWake: () => void
}

export function useBrownState(wsUrl: string = 'ws://127.0.0.1:8766'): UseBrownStateReturn {
  const [state, setState] = useState<BrownMascotState>('IDLE')
  const [transcript, setTranscript] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [structuredInfo, setStructuredInfo] = useState<StructuredInfo | null>(null)
  const [audioLevel, setAudioLevel] = useState<number>(0)
  const [blinkCount, setBlinkCount] = useState<number>(0)
  const [celebrateCount, setCelebrateCount] = useState<number>(0)
  const [isConnected, setIsConnected] = useState<boolean>(false)

  const wsRef = useRef<WebSocket | null>(null)
  const dismissTimerRef = useRef<any>(null)
  const thinkingGazeIntervalRef = useRef<any>(null)
  const offlineTimerRef = useRef<any>(null)

  // Notify native macOS wrapper (Brown.app) when state changes
  const notifyNative = useCallback((currentState: BrownMascotState, meta?: Record<string, any>) => {
    try {
      window.webkit?.messageHandlers?.brownNative?.postMessage({
        state: currentState,
        ...meta
      })
    } catch {
      // Ignored if outside WKWebView
    }
  }, [])

  // Auto-dismiss: smoothly returns to IDLE and hides overlay
  const scheduleReturnToIdle = useCallback((delayMs: number = 2200) => {
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
    dismissTimerRef.current = setTimeout(() => {
      setState('IDLE')
      setTranscript(null)
      setStatusMessage(null)
      setStructuredInfo(null)
      notifyNative('IDLE')
    }, delayMs)
  }, [notifyNative])

  // Clear dismiss timer when actively interacting
  const keepActive = useCallback(() => {
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
  }, [])

  // ── Offline auto-hide: dismiss overlay after 12s if offline ──────────
  useEffect(() => {
    if (state === 'OFFLINE') {
      if (offlineTimerRef.current) clearTimeout(offlineTimerRef.current)
      offlineTimerRef.current = setTimeout(() => {
        setTranscript(null)
        setStatusMessage(null)
        notifyNative('IDLE', { reason: 'offline_timeout' })
      }, 12000)
    } else {
      if (offlineTimerRef.current) clearTimeout(offlineTimerRef.current)
    }

    return () => {
      if (offlineTimerRef.current) clearTimeout(offlineTimerRef.current)
    }
  }, [state, notifyNative])



  // Connect to Python UIEventBridge WebSocket
  useEffect(() => {
    let reconnectTimeout: any = null
    let active = true

    function connect() {
      if (!active) return
      try {
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
          setIsConnected(true)
          setState('IDLE')
          setStatusMessage(null)
          notifyNative('IDLE', { connected: true })
        }

        ws.onmessage = (event) => {
          try {
            const msg: UIEventMessage = JSON.parse(event.data)
            handleEvent(msg)
          } catch (e) {
            console.error('[BrownUI] JSON parse error:', e)
          }
        }

        ws.onclose = () => {
          setIsConnected(false)
          setState('OFFLINE')
          notifyNative('OFFLINE', { connected: false })
          reconnectTimeout = setTimeout(connect, 2000)
        }

        ws.onerror = () => {
          ws.close()
        }
      } catch {
        setIsConnected(false)
        setState('OFFLINE')
        reconnectTimeout = setTimeout(connect, 2000)
      }
    }

    connect()

    return () => {
      active = false
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
      if (wsRef.current) wsRef.current.close()
    }
  }, [wsUrl, notifyNative])

  // Process incoming engine events
  const handleEvent = useCallback((msg: UIEventMessage) => {
    keepActive()

    switch (msg.event) {
      case 'state_change': {
        const engineState = (msg.data.state || '').toUpperCase()
        if (engineState === 'SLEEPING') {
          scheduleReturnToIdle(600)
        } else if (engineState === 'WAKE_DETECTED') {
          setState('WAKE_DETECTED')
          setStatusMessage("Yeah, I'm here.")
          setBlinkCount((b) => b + 1)
          notifyNative('WAKE_DETECTED')
        } else if (engineState === 'LISTENING' || engineState === 'ACTIVE_CONVERSATION') {
          setState('LISTENING')
          setStatusMessage("I'm listening...")
          notifyNative('LISTENING')
        } else if (engineState === 'THINKING') {
          setState('THINKING')
          setStatusMessage('Thinking...')
          notifyNative('THINKING')
        } else if (engineState === 'EXECUTING') {
          setState('EXECUTING')
          setStatusMessage(msg.data.description || 'Executing...')
          notifyNative('EXECUTING', { description: msg.data.description })
        } else if (engineState === 'VERIFYING') {
          setState('VERIFYING')
          setStatusMessage(msg.data.description || 'Verifying...')
          notifyNative('VERIFYING')
        } else if (engineState === 'SPEAKING') {
          setState('SPEAKING')
          notifyNative('SPEAKING')
        } else if (engineState === 'HAPPY') {
          setState('HAPPY')
          setStatusMessage("That's the good stuff.")
          setCelebrateCount((c) => c + 1)
          notifyNative('HAPPY')
          scheduleReturnToIdle(2400)
        } else if (engineState === 'CONFUSED') {
          setState('CONFUSED')
          setStatusMessage('Hmm, not sure about that.')
          notifyNative('CONFUSED')
          scheduleReturnToIdle(2800)
        } else if (engineState === 'CONCERNED') {
          setState('CONCERNED')
          setStatusMessage('Something went wrong.')
          notifyNative('CONCERNED')
          scheduleReturnToIdle(3000)
        }
 else if (engineState === 'ERROR') {
          setState('ERROR')
          setStatusMessage(msg.data.message || 'Error occurred')
          notifyNative('ERROR')
          scheduleReturnToIdle(3500)
        }
        break
      }

      case 'audio_active': {
        const level = Number(msg.data.level) || 0
        setAudioLevel(Math.min(1.0, level * 2.5))
        break
      }


      case 'transcript': {
        if (msg.data.text) {
          setTranscript(`"${msg.data.text}"`)
          notifyNative(state, { transcript: msg.data.text })
        }
        break
      }

      case 'tts_speaking': {
        const isSpeaking = Boolean(msg.data.speaking)
        if (isSpeaking) {
          setState('SPEAKING')
          if (msg.data.text) {
            setStatusMessage(msg.data.text)
          }
          notifyNative('SPEAKING', { text: msg.data.text })
        } else {
          scheduleReturnToIdle(1800)
        }
        break
      }

      case 'tool_result': {
        if (msg.data.message) {
          setStatusMessage(msg.data.message)
        }
        if (msg.data.data && typeof msg.data.data === 'object') {
          setStructuredInfo({
            title: msg.data.tool,
            details: msg.data.data
          })
        }
        break
      }

      case 'reaction': {
        const mood = (msg.data.mood || '').toLowerCase()
        if (msg.data.message) {
          setStatusMessage(msg.data.message)
        }

        if (mood === 'happy') {
          setState('HAPPY')
          setCelebrateCount((c) => c + 1)
        } else if (mood === 'confused') {
          setState('CONFUSED')
        } else if (mood === 'concerned') {
          setState('CONCERNED')
        }

        scheduleReturnToIdle(2200)
        break
      }


      case 'error': {
        setState('ERROR')
        setStatusMessage(msg.data.message || 'Error occurred')
        notifyNative('ERROR', { error: msg.data.message })
        scheduleReturnToIdle(3500)
        break
      }
    }
  }, [keepActive, scheduleReturnToIdle, notifyNative, state])

  // Poke handler
  const handlePoke = useCallback(() => {
    setBlinkCount((b) => b + 1)
  }, [])

  // Wake handler
  const handleWake = useCallback(() => {
    setState('WAKE_DETECTED')
    setStatusMessage("Yeah, I'm here.")
    setCelebrateCount((c) => c + 1)
    notifyNative('WAKE_DETECTED')
    scheduleReturnToIdle(3500)
  }, [notifyNative, scheduleReturnToIdle])

  return {
    state,
    transcript,
    statusMessage,
    structuredInfo,
    audioLevel,
    blinkCount,
    celebrateCount,
    isConnected,
    handlePoke,
    handleWake
  }
}

