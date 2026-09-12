import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import {
  type BrownSettings,
  DEFAULT_SETTINGS,
  COLOR_PRESETS
} from '../types/settings'
import { strobiDefinition } from '../avatar'

interface SettingsContextType {
  settings: BrownSettings
  updateSettings: (partial: Partial<BrownSettings>) => void
  resetSettings: () => void
  isSettingsOpen: boolean
  setIsSettingsOpen: (open: boolean) => void
  activePresetId?: string
}

const SETTINGS_STORAGE_KEY = 'brown_user_settings_v1'

const SettingsContext = createContext<SettingsContextType | undefined>(undefined)

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settings, setSettings] = useState<BrownSettings>(() => {
    try {
      const stored = localStorage.getItem(SETTINGS_STORAGE_KEY)
      if (stored) {
        return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) }
      }
    } catch {
      // Ignore localStorage read errors
    }
    return DEFAULT_SETTINGS
  })

  const [isSettingsOpen, setIsSettingsOpen] = useState(() => {
    try {
      if (typeof window !== 'undefined') {
        const urlParams = new URLSearchParams(window.location.search)
        if (urlParams.get('settings') === 'true' || window.location.hash.includes('settings')) {
          return true
        }
      }
    } catch {
      // Ignore
    }
    return false
  })

  // Global keyboard shortcut: Cmd+, (macOS) or Ctrl+, (Windows/Linux)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === ',') {
        e.preventDefault()
        try {
          if ((window as any).webkit?.messageHandlers?.brownNative) {
            (window as any).webkit.messageHandlers.brownNative.postMessage({
              action: 'open_settings_window'
            })
            return
          }
        } catch {
          // Ignore
        }
        window.dispatchEvent(new CustomEvent('brown-open-settings'))
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])


  // Sync avatar definition colors directly for 60fps real-time updates
  useEffect(() => {
    if (strobiDefinition && strobiDefinition.colors) {
      (strobiDefinition.colors as any).body = settings.primaryColor;
      (strobiDefinition.colors as any).eyes = settings.eyeColor;
    }
  }, [settings.primaryColor, settings.eyeColor])

  // Broadcast settings update to Python backend via WebSocket if connected
  const broadcastSettingsToBackend = useCallback((newSettings: BrownSettings) => {
    try {
      if ((window as any).__brownWs && (window as any).__brownWs.readyState === WebSocket.OPEN) {
        (window as any).__brownWs.send(JSON.stringify({
          action: 'save_settings',
          settings: newSettings
        }))
      }
    } catch {
      // WebSocket send optional
    }
  }, [])

  const updateSettings = useCallback((partial: Partial<BrownSettings>) => {
    setSettings(prev => {
      const next = { ...prev, ...partial }
      try {
        localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(next))
      } catch {
        // Ignore localStorage write error
      }
      broadcastSettingsToBackend(next)
      return next
    })
  }, [broadcastSettingsToBackend])

  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS)
    try {
      localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(DEFAULT_SETTINGS))
    } catch {
      // Ignore
    }
    broadcastSettingsToBackend(DEFAULT_SETTINGS)
  }, [broadcastSettingsToBackend])

  // Identify matching preset if any
  const activePresetId = COLOR_PRESETS.find(
    p => p.body.toLowerCase() === settings.primaryColor.toLowerCase()
  )?.id

  return (
    <SettingsContext.Provider
      value={{
        settings,
        updateSettings,
        resetSettings,
        isSettingsOpen,
        setIsSettingsOpen,
        activePresetId
      }}
    >
      {children}
    </SettingsContext.Provider>
  )
}

export const useSettings = (): SettingsContextType => {
  const context = useContext(SettingsContext)
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider')
  }
  return context
}
