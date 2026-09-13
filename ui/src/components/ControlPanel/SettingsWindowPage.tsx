import React, { useState } from 'react'
import { useSettings } from '../../context/SettingsContext'
import { AppearanceTab } from './AppearanceTab'
import { GeneralTab } from './GeneralTab'
import { IntelligenceTab } from './IntelligenceTab'
import { NodesTab } from './NodesTab'
import { TimingTab } from './TimingTab'
import { Tabs, Button, Badge, Dot, Divider, Spacer, Text } from './geist'
import { Sliders, RefreshCw, Check } from '@geist-ui/icons'
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
                <Text b style={{ fontSize: '1.1rem', color: '#ffffff', margin: 0 }}>
                  {settings.assistantName} Assistant
                </Text>
                <Badge type="secondary" scale={0.7} style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Control Panel
                </Badge>
              </div>
              <Text small type="secondary" style={{ fontSize: '0.78rem', margin: 0 }}>
                <Dot type="success" style={{ display: 'inline-flex', padding: 0 }}>
                  Vercel Geist Design System
                </Dot>
              </Text>
            </div>
          </div>
        </div>

        <Spacer h={0.6} />
        <Divider style={{ margin: '0 0 12px 0', borderColor: '#262626' }} />

        {/* Geist Tabs */}
        <Tabs
          value={tab}
          onChange={(val: string) => setTab(val)}
          className="geist-window-tabs"
          align="left"
          leftSpace={0}
        >
          <Tabs.Item label="Appearance" value="appearance">
            <div className="geist-window-tab-scroll">
              <AppearanceTab />
            </div>
          </Tabs.Item>
          <Tabs.Item label="Identity" value="identity">
            <div className="geist-window-tab-scroll">
              <GeneralTab />
            </div>
          </Tabs.Item>
          <Tabs.Item label="Intelligence" value="intelligence">
            <div className="geist-window-tab-scroll">
              <IntelligenceTab />
            </div>
          </Tabs.Item>
          <Tabs.Item label="Nodes" value="nodes">
            <div className="geist-window-tab-scroll">
              <NodesTab />
            </div>
          </Tabs.Item>
          <Tabs.Item label="Timing" value="timing">
            <div className="geist-window-tab-scroll">
              <TimingTab />
            </div>
          </Tabs.Item>
        </Tabs>

        <Divider style={{ margin: '16px 0 12px 0', borderColor: '#262626' }} />

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
              paddingLeft: 18,
              paddingRight: 18
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
