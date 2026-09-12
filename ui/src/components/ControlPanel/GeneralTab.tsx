import React, { useState } from 'react'
import { useSettings } from '../../context/SettingsContext'
import { Text, Input, Toggle, Tag, Spacer, Badge } from './geist'
import { Plus, X } from '@geist-ui/icons'

export const GeneralTab: React.FC = () => {
  const { settings, updateSettings } = useSettings()
  const [newPhrase, setNewPhrase] = useState('')

  const handleAddPhrase = (e: React.KeyboardEvent | React.MouseEvent) => {
    if ('key' in e && e.key !== 'Enter') return
    e.preventDefault()
    const clean = newPhrase.trim().toLowerCase()
    if (!clean || settings.wakePhrases.includes(clean)) return
    updateSettings({
      wakePhrases: [...settings.wakePhrases, clean]
    })
    setNewPhrase('')
  }

  const handleRemovePhrase = (phraseToRemove: string) => {
    if (settings.wakePhrases.length <= 1) return // Keep at least one
    updateSettings({
      wakePhrases: settings.wakePhrases.filter(p => p !== phraseToRemove)
    })
  }

  return (
    <div className="geist-tab-content">
      {/* Assistant Name */}
      <div className="geist-form-group">
        <div className="geist-label-row">
          <Text small b style={{ color: '#ededed' }}>Assistant Name</Text>
        </div>
        <Spacer h={0.4} />
        <Input
          width="100%"
          scale={0.9}
          maxLength={24}
          value={settings.assistantName}
          onChange={(e: any) => updateSettings({ assistantName: e.target.value })}
          placeholder="e.g. Brown, Jarvis, Nova"
          clearable
        />
        <Spacer h={0.3} />
        <Text small type="secondary" style={{ fontSize: '0.78rem' }}>
          Display name for greetings and native menu bar titles.
        </Text>
      </div>

      <Spacer h={1.2} />

      {/* Wake Trigger Phrases */}
      <div className="geist-form-group">
        <div className="geist-label-row">
          <Text small b style={{ color: '#ededed' }}>Wake Trigger Phrases</Text>
          <Badge type="secondary" scale={0.7}>
            {settings.wakePhrases.length} active
          </Badge>
        </div>
        <Spacer h={0.5} />
        <div className="geist-tags-wrap">
          {settings.wakePhrases.map((phrase) => (
            <Tag
              key={phrase}
              type="secondary"
              scale={0.85}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                marginRight: 6,
                marginBottom: 6,
                borderColor: '#333',
                backgroundColor: '#111'
              }}
            >
              <span>{phrase}</span>
              {settings.wakePhrases.length > 1 && (
                <button
                  type="button"
                  className="geist-tag-remove-btn"
                  onClick={() => handleRemovePhrase(phrase)}
                  title={`Remove ${phrase}`}
                >
                  <X size={12} />
                </button>
              )}
            </Tag>
          ))}
        </div>
        <Spacer h={0.4} />
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Input
            width="100%"
            scale={0.85}
            placeholder="+ Add wake phrase and press Enter"
            value={newPhrase}
            onChange={(e: any) => setNewPhrase(e.target.value)}
            onKeyDown={handleAddPhrase}
          />
          {newPhrase.trim() && (
            <button
              type="button"
              className="geist-btn-icon-add"
              onClick={handleAddPhrase}
              title="Add phrase"
            >
              <Plus size={14} />
            </button>
          )}
        </div>
        <Spacer h={0.3} />
        <Text small type="secondary" style={{ fontSize: '0.78rem' }}>
          Spoken phrases that wake Brown up from sleep.
        </Text>
      </div>

      <Spacer h={1.2} />

      {/* Acoustic Barge-In Toggle */}
      <div className="geist-toggle-card">
        <div className="geist-toggle-info">
          <Text b small style={{ color: '#ededed', display: 'block' }}>
            Acoustic Barge-In
          </Text>
          <Text small type="secondary" style={{ fontSize: '0.78rem', margin: 0 }}>
            Allow your voice to interrupt Brown while speaking (recommended for headphones).
          </Text>
        </div>
        <Toggle
          checked={settings.bargeInEnabled}
          onChange={(e: any) => updateSettings({ bargeInEnabled: e.target.checked })}
        />
      </div>
    </div>
  )
}

export default GeneralTab
