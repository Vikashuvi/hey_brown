import React, { useMemo, useEffect } from 'react'
import { useBrownState } from './hooks/useBrownState.ts'
import { BrownMascot } from './components/BrownMascot.tsx'
import { SpeechBubble } from './components/SpeechBubble.tsx'
import { StatusPill } from './components/StatusPill.tsx'
import { OverlayControls } from './components/OverlayControls.tsx'
import { ControlPanel } from './components/ControlPanel/ControlPanel.tsx'
import { SettingsWindowPage } from './components/ControlPanel/SettingsWindowPage.tsx'
import { SettingsProvider, useSettings } from './context/SettingsContext.tsx'

const BrownOverlayContent: React.FC = () => {
  const {
    state,
    transcript,
    statusMessage,
    structuredInfo,
    blinkCount,
    celebrateCount,
    isConnected,
    handlePoke,
    handleWake,
    handleSleep
  } = useBrownState('ws://127.0.0.1:8766')

  const { settings, isSettingsOpen, setIsSettingsOpen } = useSettings()

  const handleOpenSettings = () => {
    try {
      if ((window as any).webkit?.messageHandlers?.brownNative) {
        (window as any).webkit.messageHandlers.brownNative.postMessage({
          action: 'open_settings_window'
        })
        return
      }
      // Windows & Linux native pywebview support
      if ((window as any).pywebview?.api?.open_settings_window) {
        (window as any).pywebview.api.open_settings_window()
        return
      }
    } catch {
      // Ignored outside native wrappers
    }

    // In browser: open a separate dedicated popup window
    const popup = window.open('/?view=settings', 'BrownControlPanel', 'width=720,height=660,resizable=yes')
    if (!popup || popup.closed) {
      // Fallback to overlay modal if popup blocker intervened
      setIsSettingsOpen(true)
    }
  }


  // Listen for brown-open-settings custom event from macOS status menu or shortcut
  useEffect(() => {
    const handleOpenSettingsEvent = () => handleOpenSettings()
    window.addEventListener('brown-open-settings', handleOpenSettingsEvent)
    return () => window.removeEventListener('brown-open-settings', handleOpenSettingsEvent)
  }, [])

  const speechText = useMemo<string | null>(() => {
    if (settings.dialogueMode === 'never') return null

    if (state === 'ERROR') {
      return statusMessage ? statusMessage.slice(0, 48) : 'An error occurred'
    }

    if (state === 'SPEAKING' && statusMessage && statusMessage.trim()) {
      const clean = statusMessage.replace(/^"|"$/g, '').trim()
      if (clean.length <= 46) return clean
      const sub = clean.slice(0, 46)
      const lastSpace = sub.lastIndexOf(' ')
      return (lastSpace > 24 ? sub.slice(0, lastSpace) : sub) + '…'
    }

    if (settings.dialogueMode === 'always') {
      if (transcript) return transcript
      if (statusMessage) return statusMessage
    }

    return null
  }, [statusMessage, state, transcript, settings.dialogueMode])

  // Detect if running in pure browser vs native WKWebView
  const isBrowserMode = typeof window !== 'undefined' && !(window as any).webkit?.messageHandlers?.brownNative

  return (
    <div className="brown-overlay-root">
      {/* Prominent Geist toolbar in browser mode */}
      {isBrowserMode && (
        <div className="geist-browser-toolbar">
          <button
            type="button"
            className="geist-browser-btn"
            onClick={handleOpenSettings}
            title="Open Control Panel in Separate Window (⌘,)"
          >
            <span className="geist-btn-dot" />
            <span style={{ fontWeight: 600 }}>{settings.assistantName}</span>
            <span className="geist-sep">/</span>
            <span>Control Panel</span>
            <kbd className="geist-kbd">⌘,</kbd>
          </button>
        </div>
      )}

      {/* Strobi Procedural 3D Avatar Stage */}
      <div className="strobi-stage">
        {/* Hover Micro Controls (Close & Settings) */}
        <OverlayControls
          onClose={handleSleep}
          onOpenSettings={handleOpenSettings}
        />

        <SpeechBubble text={speechText} />
        <BrownMascot
          state={state}
          blinkCount={blinkCount}
          celebrateCount={celebrateCount}
          onPoke={handlePoke}
          onWake={handleWake}
        />
      </div>

      {/* Modal fallback for browser if popup blocked */}
      {isSettingsOpen && <ControlPanel />}
    </div>
  )
}

export const App: React.FC = () => {
  // Check if dedicated standalone settings window route is requested
  const isSettingsWindowRoute = typeof window !== 'undefined' && (
    new URLSearchParams(window.location.search).get('view') === 'settings'
  )

  if (isSettingsWindowRoute) {
    return (
      <SettingsProvider>
        <SettingsWindowPage />
      </SettingsProvider>
    )
  }

  return (
    <SettingsProvider>
      <BrownOverlayContent />
    </SettingsProvider>
  )
}

export default App
