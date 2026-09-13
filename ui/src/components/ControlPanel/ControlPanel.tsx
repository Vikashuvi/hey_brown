import React, { useState, useEffect } from 'react'
import { useSettings } from '../../context/SettingsContext'
import { GeneralTab } from './GeneralTab'
import { AppearanceTab } from './AppearanceTab'
import { TimingTab } from './TimingTab'
import { IntelligenceTab } from './IntelligenceTab'
import { NodesTab } from './NodesTab'
import { Card, Button, Badge, Dot, Text } from './geist'
import { Sliders, X, RefreshCw, Check, User, Cpu, Server, Clock } from '@geist-ui/icons'
import './ControlPanel.css'

export const ControlPanel: React.FC = () => {
  const { isSettingsOpen, setIsSettingsOpen, resetSettings, settings } = useSettings()
  const [tab, setTab] = useState<string>('appearance')

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isSettingsOpen) {
        setIsSettingsOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isSettingsOpen, setIsSettingsOpen])

  if (!isSettingsOpen) return null

  const tabs = [
    { id: 'appearance', label: 'Appearance', icon: <Sliders size={14} /> },
    { id: 'identity', label: 'Identity', icon: <User size={14} /> },
    { id: 'intelligence', label: 'Intelligence', icon: <Cpu size={14} /> },
    { id: 'nodes', label: 'Nodes & Devices', icon: <Server size={14} /> },
    { id: 'timing', label: 'Voice & Timing', icon: <Clock size={14} /> },
  ]

  return (
    <div
      className="geist-control-panel-overlay"
      onClick={() => setIsSettingsOpen(false)}
      role="dialog"
      aria-modal="true"
      aria-label={`${settings.assistantName} Control Panel`}
    >
      <div
        className="geist-control-panel-container"
        onClick={(e) => e.stopPropagation()}
      >
        <Card className="geist-control-card">
          {/* Header */}
          <div className="geist-card-header">
            <div className="geist-header-title-group">
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

            <button
              type="button"
              className="geist-close-btn"
              onClick={() => setIsSettingsOpen(false)}
              aria-label="Close Control Panel"
            >
              <X size={16} />
            </button>
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
          <div className="geist-card-footer">
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
              onClick={() => setIsSettingsOpen(false)}
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
        </Card>
      </div>
    </div>
  )
}

export default ControlPanel
