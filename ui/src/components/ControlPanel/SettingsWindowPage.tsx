import React, { useState } from 'react'
import { useSettings } from '../../context/SettingsContext'
import { AppearanceTab } from './AppearanceTab'
import { GeneralTab } from './GeneralTab'
import { IntelligenceTab } from './IntelligenceTab'
import { NodesTab } from './NodesTab'
import { TimingTab } from './TimingTab'
import { Button, Badge, Dot, Text } from './geist'
import { Sliders, RefreshCw, Check, User, Cpu, Server, Clock } from '@geist-ui/icons'
import './ControlPanel.css'

export const SettingsWindowPage: React.FC = () => {
  const { settings, resetSettings } = useSettings()
  const [tab, setTab] = useState<string>('appearance')

  const handleClose = () => {
    try {
      if ((window as any).webkit?.messageHandlers?.brownNative) {
        (window as any).webkit.messageHandlers.brownNative.postMessage({
          action: 'close_settings_window'
        })
        return
      }
      if ((window as any).pywebview?.api?.close_settings_window) {
        (window as any).pywebview.api.close_settings_window()
        return
      }
    } catch {
      // Ignored
    }

    // Browser fallback
    if (window.opener) {
      window.close()
    }
  }

  const tabs = [
    { id: 'appearance', label: 'Appearance', icon: <Sliders size={14} /> },
    { id: 'identity', label: 'Identity', icon: <User size={14} /> },
    { id: 'intelligence', label: 'Intelligence', icon: <Cpu size={14} /> },
    { id: 'nodes', label: 'Nodes & Devices', icon: <Server size={14} /> },
    { id: 'timing', label: 'Voice & Timing', icon: <Clock size={14} /> },
  ]

  return (
    <div className="geist-settings-window-root">
      {/* Draggable Title Area for macOS */}
      <div className="geist-window-titlebar">
        <div className="geist-window-title-center">
          <Sliders size={13} style={{ marginRight: 6, color: '#888' }} />
          <span>{settings.assistantName} — Control Panel</span>
        </div>
      </div>

      {/* Main Content Card Container */}
      <div className="geist-window-body">
        {/* Header Branding */}
        <div className="geist-window-header">
          <div className="geist-window-brand">
            <div className="geist-header-icon">
              <Sliders size={16} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text b style={{ fontSize: '1.05rem', color: '#ffffff', margin: 0 }}>
                  {settings.assistantName} Assistant
                </Text>
                <Badge type="secondary" scale={0.7} style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Control Panel
                </Badge>
              </div>
              <Text small type="secondary" style={{ fontSize: '0.76rem', margin: 0 }}>
                <Dot type="success" style={{ display: 'inline-flex', padding: 0 }}>
                  Vercel Geist Design System
                </Dot>
              </Text>
            </div>
          </div>
        </div>

        {/* Responsive Geist Nav Bar */}
        <div className="geist-nav-bar" role="tablist">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`geist-nav-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.icon}
              <span>{t.label}</span>
            </button>
          ))}
        </div>

        {/* Unified Tab Scroll Container */}
        <div className="geist-tab-scroll-container">
          {tab === 'appearance' && <AppearanceTab />}
          {tab === 'identity' && <GeneralTab />}
          {tab === 'intelligence' && <IntelligenceTab />}
          {tab === 'nodes' && <NodesTab />}
          {tab === 'timing' && <TimingTab />}
        </div>

        {/* Footer Actions */}
        <div className="geist-window-footer">
          <Button
            auto
            scale={0.82}
            type="abort"
            icon={<RefreshCw size={13} />}
            onClick={resetSettings}
            style={{ color: '#888888', borderColor: '#333333' }}
          >
            Reset Defaults
          </Button>

          <Button
            auto
            scale={0.82}
            type="secondary"
            icon={<Check size={13} />}
            onClick={handleClose}
            style={{
              backgroundColor: '#ffffff',
              color: '#000000',
              fontWeight: 600,
              paddingLeft: 20,
              paddingRight: 20
            }}
          >
            Done
          </Button>
        </div>
      </div>
    </div>
  )
}

export default SettingsWindowPage
