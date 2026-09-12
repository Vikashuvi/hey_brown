import React from 'react'
import { useSettings } from '../../context/SettingsContext'
import type { DialogueMode } from '../../types/settings'
import { Text, Slider, Select, Spacer, Badge } from './geist'

export const TimingTab: React.FC = () => {
  const { settings, updateSettings } = useSettings()

  const cadenceOptions = [
    { label: 'Quick (220ms)', value: '220' },
    { label: 'Natural (300ms)', value: '300' },
    { label: 'Relaxed (420ms)', value: '420' }
  ]

  const dialogueOptions: { label: string; value: DialogueMode; desc: string }[] = [
    {
      label: 'Necessary Only',
      value: 'necessary_only',
      desc: 'Only displays when speaking answers or on error.'
    },
    {
      label: 'Always Show',
      value: 'always',
      desc: 'Shows transcript bubbles and idle status.'
    },
    {
      label: 'Never (Mute)',
      value: 'never',
      desc: 'Completely hides dialogue bubbles.'
    }
  ]

  return (
    <div className="geist-tab-content">
      {/* Sleep Inactivity Timeout */}
      <div className="geist-form-group">
        <div className="geist-label-row">
          <Text small b style={{ color: '#ededed' }}>Inactivity Sleep Timeout</Text>
          <Badge type="secondary" scale={0.7} style={{ fontFamily: 'Geist Mono, monospace' }}>
            {settings.sleepTimeoutSeconds}s
          </Badge>
        </div>
        <Spacer h={0.5} />
        <Slider
          min={3}
          max={25}
          step={1}
          value={settings.sleepTimeoutSeconds}
          onChange={(val: number) => updateSettings({ sleepTimeoutSeconds: Number(val) })}
          width="100%"
        />
        <Spacer h={0.4} />
        <Text small type="secondary" style={{ fontSize: '0.78rem' }}>
          How long Brown remains in follow-up listening before returning to sleep.
        </Text>
      </div>

      <Spacer h={1.2} />

      {/* Speaking Cadence */}
      <div className="geist-form-group">
        <div className="geist-label-row">
          <Text small b style={{ color: '#ededed' }}>Speaking Animation Cadence</Text>
          <Badge type="secondary" scale={0.7} style={{ fontFamily: 'Geist Mono, monospace' }}>
            {settings.speechCadenceMs}ms
          </Badge>
        </div>
        <Spacer h={0.5} />
        <Select
          width="100%"
          scale={0.85}
          value={String(settings.speechCadenceMs)}
          onChange={(val: any) => updateSettings({ speechCadenceMs: Number(val) })}
        >
          {cadenceOptions.map((opt) => (
            <Select.Option key={opt.value} value={opt.value}>
              {opt.label}
            </Select.Option>
          ))}
        </Select>
        <Spacer h={0.4} />
        <Text small type="secondary" style={{ fontSize: '0.78rem' }}>
          Controls how quickly facial expressions cycle while speaking.
        </Text>
      </div>

      <Spacer h={1.2} />

      {/* Dialogue Bubble Mode */}
      <div className="geist-form-group">
        <div className="geist-label-row">
          <Text small b style={{ color: '#ededed' }}>Dialogue Box Visibility</Text>
          <Badge type="secondary" scale={0.7}>
            {settings.dialogueMode}
          </Badge>
        </div>
        <Spacer h={0.5} />
        <Select
          width="100%"
          scale={0.85}
          value={settings.dialogueMode}
          onChange={(val: any) => updateSettings({ dialogueMode: val as DialogueMode })}
        >
          {dialogueOptions.map((opt) => (
            <Select.Option key={opt.value} value={opt.value}>
              {opt.label}
            </Select.Option>
          ))}
        </Select>
        <Spacer h={0.4} />
        <Text small type="secondary" style={{ fontSize: '0.78rem' }}>
          {dialogueOptions.find(o => o.value === settings.dialogueMode)?.desc}
        </Text>
      </div>
    </div>
  )
}

export default TimingTab
