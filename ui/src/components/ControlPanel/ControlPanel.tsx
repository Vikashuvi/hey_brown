import React, { useState, useEffect } from 'react'
import { useSettings } from '../../context/SettingsContext'
import { GeneralTab } from './GeneralTab'
import { AppearanceTab } from './AppearanceTab'
import { TimingTab } from './TimingTab'
import { Card, Tabs, Button, Badge, Dot, Divider, Spacer, Text } from './geist'
import { Sliders, X, RefreshCw, Check } from '@geist-ui/icons'
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
        <Card
          className="geist-control-card"
          style={{
            backgroundColor: '#000000',
            borderColor: '#333333',
            borderRadius: '12px',
            boxShadow: '0 20px 40px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.08)'
          }}
        >
          {/* Header */}
          <div className="geist-card-header">
            <div className="geist-header-title-group">
              <div className="geist-header-icon">
                <Sliders size={15} />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Text b style={{ fontSize: '0.95rem', color: '#ffffff', margin: 0 }}>
                    {settings.assistantName}
                  </Text>
                  <Badge type="secondary" scale={0.65} style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Control Panel
                  </Badge>
                </div>
                <Text small type="secondary" style={{ fontSize: '0.75rem', margin: 0 }}>
                  <Dot type="success" style={{ display: 'inline-flex', padding: 0 }}>
                    Geist Design System
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
              <X size={15} />
            </button>
          </div>

          <Divider style={{ margin: '0 0 8px 0', borderColor: '#222222' }} />

          {/* Geist Tabs Navigation */}
          <Tabs
            value={tab}
            onChange={(val: string) => setTab(val)}
            className="geist-tabs-container"
            align="left"
            leftSpace={0}
          >
            <Tabs.Item label="Appearance" value="appearance">
              <AppearanceTab />
            </Tabs.Item>
            <Tabs.Item label="Identity" value="identity">
              <GeneralTab />
            </Tabs.Item>
            <Tabs.Item label="Timing" value="timing">
              <TimingTab />
            </Tabs.Item>
          </Tabs>

          <Spacer h={0.5} />
          <Divider style={{ margin: '8px 0', borderColor: '#222222' }} />

          {/* Footer Actions */}
          <div className="geist-card-footer">
            <Button
              auto
              scale={0.78}
              type="abort"
              icon={<RefreshCw size={13} />}
              onClick={resetSettings}
              style={{ color: '#888888', borderColor: '#333333' }}
            >
              Reset Defaults
            </Button>
            <Button
              auto
              scale={0.78}
              type="secondary"
              icon={<Check size={13} />}
              onClick={() => setIsSettingsOpen(false)}
              style={{
                backgroundColor: '#ffffff',
                color: '#000000',
                fontWeight: 600
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
