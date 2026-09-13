import React, { useState, useEffect } from 'react'
import { useSettings } from '../../context/SettingsContext'
import { Text, Input, Toggle, Slider, Select, Spacer, Badge, Dot, Card, Divider } from './geist'
import { Cpu, Shield, Zap, Activity } from '@geist-ui/icons'

interface WakeDiagnosticData {
  wake_phrase?: string
  detection_score?: number
  threshold?: number
  detected?: boolean
  vad_state?: string
  rms_energy?: number
  false_activations?: number
  missed_activations?: number
}

interface LocalAITelemetry {
  state?: string
  ready?: boolean
  loaded?: boolean
  model?: string
  device?: string
  reason?: string
}

export const IntelligenceTab: React.FC = () => {
  const { settings, updateSettings } = useSettings()
  const [diagnostic, setDiagnostic] = useState<WakeDiagnosticData>({
    wake_phrase: settings.wakePhrases[0] || 'hey brown',
    detection_score: 0.0,
    threshold: settings.wakeThreshold,
    detected: false,
    vad_state: 'SILENCE',
    false_activations: 0,
    missed_activations: 0
  })

  const [localAiTelemetry, setLocalAiTelemetry] = useState<LocalAITelemetry>({
    state: 'READY',
    ready: true,
    loaded: true,
    model: settings.localAiModel,
    device: 'error_boy'
  })

  // Listen for live wake and local AI diagnostic telemetry over WebSocket if connected
  useEffect(() => {
    const handleCustomTelemetry = (e: any) => {
      if (e.detail) {
        setDiagnostic(prev => ({ ...prev, ...e.detail }))
      }
    }
    const handleLocalAiTelemetry = (e: any) => {
      if (e.detail) {
        setLocalAiTelemetry(prev => ({ ...prev, ...e.detail }))
      }
    }
    window.addEventListener('brown-wake-diagnostic', handleCustomTelemetry)
    window.addEventListener('brown-local-ai-state', handleLocalAiTelemetry)
    return () => {
      window.removeEventListener('brown-wake-diagnostic', handleCustomTelemetry)
      window.removeEventListener('brown-local-ai-state', handleLocalAiTelemetry)
    }
  }, [])

  const aiBadge = (() => {
    if (!settings.localAiEnabled) return { type: 'secondary' as const, label: 'Disabled' }
    const st = localAiTelemetry.state || 'OFFLINE'
    switch (st) {
      case 'READY':
        return { type: 'success' as const, label: localAiTelemetry.loaded ? 'READY (WARM)' : 'READY (STANDBY)' }
      case 'MODEL_LOADING':
        return { type: 'warning' as const, label: 'LOADING MODEL' }
      case 'BUSY':
        return { type: 'warning' as const, label: 'BUSY' }
      case 'STARTING':
        return { type: 'warning' as const, label: 'STARTING OLLAMA' }
      case 'RESOURCE_LIMITED':
        return { type: 'error' as const, label: 'VRAM/RAM LIMITED' }
      case 'OLLAMA_UNAVAILABLE':
        return { type: 'error' as const, label: 'OLLAMA DOWN' }
      case 'MODEL_NOT_INSTALLED':
        return { type: 'error' as const, label: 'MODEL NOT FOUND' }
      default:
        return { type: 'secondary' as const, label: st }
    }
  })()

  return (
    <div className="geist-tab-content" style={{ maxHeight: '420px', overflowY: 'auto', paddingRight: '4px' }}>
      {/* 1. Local AI Section */}
      <div className="geist-form-group">
        <div className="geist-label-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Cpu size={14} color="#7c3aed" />
            <Text small b style={{ color: '#ededed', margin: 0 }}>Local AI Engine (Level 2)</Text>
          </div>
          <Badge type={aiBadge.type} scale={0.7}>
            {aiBadge.label}
          </Badge>
        </div>
        <Spacer h={0.4} />

        <div className="geist-toggle-card" style={{ marginBottom: 10 }}>
          <div className="geist-toggle-info">
            <Text b small style={{ color: '#ededed', display: 'block' }}>Enable Local AI</Text>
            <Text small type="secondary" style={{ fontSize: '0.78rem', margin: 0 }}>
              Run vision-language models locally on secondary device or accelerator node.
            </Text>
          </div>
          <Toggle
            checked={settings.localAiEnabled}
            onChange={(e: any) => updateSettings({ localAiEnabled: e.target.checked })}
          />
        </div>

        {settings.localAiEnabled && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingLeft: 4 }}>
            <div>
              <Text small type="secondary" style={{ fontSize: '0.76rem', display: 'block', marginBottom: 3 }}>
                Local Model Identifier (Ollama / vLLM)
              </Text>
              <Input
                width="100%"
                scale={0.85}
                value={settings.localAiModel}
                onChange={(e: any) => updateSettings({ localAiModel: e.target.value })}
                placeholder="e.g. qwen3-vl:2b"
              />
            </div>
            <div>
              <Text small type="secondary" style={{ fontSize: '0.76rem', display: 'block', marginBottom: 3 }}>
                Local Vision Model (Image/Screen Understanding)
              </Text>
              <Input
                width="100%"
                scale={0.85}
                value={settings.localAiVisionModel || settings.localAiModel}
                onChange={(e: any) => updateSettings({ localAiVisionModel: e.target.value })}
                placeholder="e.g. qwen3-vl:2b"
              />
            </div>
            <div>
              <Text small type="secondary" style={{ fontSize: '0.76rem', display: 'block', marginBottom: 3 }}>
                Remote Agent Endpoint (Host URL)
              </Text>
              <Input
                width="100%"
                scale={0.85}
                value={settings.localAiUrl}
                onChange={(e: any) => updateSettings({ localAiUrl: e.target.value })}
                placeholder="http://error-boy.local:8765"
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
              <div>
                <Text b small style={{ color: '#ededed', display: 'block' }}>Auto-Warm on Boot</Text>
                <Text small type="secondary" style={{ fontSize: '0.75rem', margin: 0 }}>
                  Preload model weights into accelerator memory on startup for zero-lag first response.
                </Text>
              </div>
              <Toggle
                checked={settings.localAiAutoWarm ?? true}
                onChange={(e: any) => updateSettings({ localAiAutoWarm: e.target.checked })}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
              <div>
                <Text b small style={{ color: '#ededed', display: 'block' }}>Keep Warm in VRAM</Text>
                <Text small type="secondary" style={{ fontSize: '0.75rem', margin: 0 }}>
                  Keep weights resident in memory across conversation turns.
                </Text>
              </div>
              <Toggle
                checked={settings.localAiKeepWarm}
                onChange={(e: any) => updateSettings({ localAiKeepWarm: e.target.checked })}
              />
            </div>
            <div style={{ marginTop: 2 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text small style={{ color: '#ccc', fontSize: '0.76rem' }}>Idle Unload Window</Text>
                <Text small b style={{ color: '#fff' }}>{settings.localAiKeepAliveMinutes || 15}m</Text>
              </div>
              <Slider
                min={5}
                max={60}
                step={5}
                value={settings.localAiKeepAliveMinutes || 15}
                onChange={(val: any) => updateSettings({ localAiKeepAliveMinutes: Number(val) })}
              />
            </div>
          </div>
        )}
      </div>

      <Divider style={{ margin: '14px 0', borderColor: '#222' }} />

      {/* 2. Cloud AI & Privacy Section */}
      <div className="geist-form-group">
        <div className="geist-label-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Shield size={14} color="#06b6d4" />
            <Text small b style={{ color: '#ededed', margin: 0 }}>Cloud AI & Privacy (Level 3)</Text>
          </div>
          <Badge type={settings.privacyMode === 'local_only' ? 'warning' : 'secondary'} scale={0.7}>
            {settings.privacyMode.toUpperCase()}
          </Badge>
        </div>
        <Spacer h={0.4} />

        <div style={{ marginBottom: 10 }}>
          <Text small type="secondary" style={{ fontSize: '0.76rem', display: 'block', marginBottom: 4 }}>
            Authoritative Privacy Policy
          </Text>
          <div style={{ display: 'flex', gap: 6 }}>
            {(['local_only', 'private', 'normal'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => updateSettings({ privacyMode: mode })}
                style={{
                  flex: 1,
                  padding: '6px 8px',
                  borderRadius: 6,
                  border: `1px solid ${settings.privacyMode === mode ? '#7c3aed' : '#333'}`,
                  backgroundColor: settings.privacyMode === mode ? 'rgba(124, 58, 237, 0.15)' : '#111',
                  color: settings.privacyMode === mode ? '#fff' : '#888',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em'
                }}
              >
                {mode.replace('_', ' ')}
              </button>
            ))}
          </div>
          <Text small type="secondary" style={{ fontSize: '0.74rem', marginTop: 4, display: 'block' }}>
            {settings.privacyMode === 'local_only'
              ? 'Zero network transmission to cloud AI. Screen & text stay strictly on local LAN.'
              : settings.privacyMode === 'private'
              ? 'Aggressively redacts API keys, credentials, and tokens before cloud calls.'
              : 'Standard cloud transmission governed by routing policy.'}
          </Text>
        </div>

        {settings.privacyMode !== 'local_only' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingLeft: 4 }}>
            <div className="geist-toggle-card">
              <div className="geist-toggle-info">
                <Text b small style={{ color: '#ededed', display: 'block' }}>Cloud Fallback</Text>
                <Text small type="secondary" style={{ fontSize: '0.76rem', margin: 0 }}>
                  Use Cloud AI if local model is busy, offline, or overloaded.
                </Text>
              </div>
              <Toggle
                checked={settings.cloudFallbackEnabled}
                onChange={(e: any) => updateSettings({ cloudFallbackEnabled: e.target.checked })}
              />
            </div>

            <div>
              <Text small type="secondary" style={{ fontSize: '0.76rem', display: 'block', marginBottom: 3 }}>
                Cloud Provider
              </Text>
              <div style={{ display: 'flex', gap: 6 }}>
                {(['gemini', 'openai'] as const).map((prov) => (
                  <button
                    key={prov}
                    type="button"
                    onClick={() => updateSettings({ cloudAiProvider: prov })}
                    style={{
                      flex: 1,
                      padding: '5px 8px',
                      borderRadius: 6,
                      border: `1px solid ${settings.cloudAiProvider === prov ? '#06b6d4' : '#333'}`,
                      backgroundColor: settings.cloudAiProvider === prov ? 'rgba(6, 182, 212, 0.15)' : '#111',
                      color: settings.cloudAiProvider === prov ? '#fff' : '#888',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      textTransform: 'uppercase'
                    }}
                  >
                    {prov === 'gemini' ? 'Gemini 2.0 Flash' : 'OpenAI (GPT-4o-mini)'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <Text small type="secondary" style={{ fontSize: '0.76rem', display: 'block', marginBottom: 3 }}>
                Multimodal Vision Routing
              </Text>
              <div style={{ display: 'flex', gap: 6 }}>
                {(['auto', 'local_only', 'cloud_only'] as const).map((vMode) => (
                  <button
                    key={vMode}
                    type="button"
                    onClick={() => updateSettings({ visionRouting: vMode })}
                    style={{
                      flex: 1,
                      padding: '5px 8px',
                      borderRadius: 6,
                      border: `1px solid ${(settings.visionRouting || 'auto') === vMode ? '#10b981' : '#333'}`,
                      backgroundColor: (settings.visionRouting || 'auto') === vMode ? 'rgba(16, 185, 129, 0.15)' : '#111',
                      color: (settings.visionRouting || 'auto') === vMode ? '#fff' : '#888',
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      textTransform: 'uppercase'
                    }}
                  >
                    {vMode.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>


      <Divider style={{ margin: '14px 0', borderColor: '#222' }} />

      {/* 3. Wake Word & Calibration Mode */}
      <div className="geist-form-group">
        <div className="geist-label-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Activity size={14} color="#10b981" />
            <Text small b style={{ color: '#ededed', margin: 0 }}>Wake Detection & Calibration</Text>
          </div>
          <Badge type={settings.wakeCalibrationMode ? 'error' : 'secondary'} scale={0.7}>
            {settings.wakeCalibrationMode ? 'Calibration ON' : 'Normal'}
          </Badge>
        </div>
        <Spacer h={0.5} />

        {/* Wake Threshold Slider */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <Text small style={{ color: '#ccc', fontSize: '0.8rem' }}>Detection Sensitivity Threshold</Text>
            <Text small b style={{ color: '#fff' }}>{settings.wakeThreshold.toFixed(2)}</Text>
          </div>
          <Slider
            min={0.2}
            max={0.9}
            step={0.05}
            value={settings.wakeThreshold}
            onChange={(val: any) => updateSettings({ wakeThreshold: Number(val) })}
          />
        </div>

        {/* Activation Cooldown Slider */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <Text small style={{ color: '#ccc', fontSize: '0.8rem' }}>Activation Cooldown</Text>
            <Text small b style={{ color: '#fff' }}>{settings.wakeCooldownSeconds.toFixed(1)}s</Text>
          </div>
          <Slider
            min={0.5}
            max={4.0}
            step={0.5}
            value={settings.wakeCooldownSeconds}
            onChange={(val: any) => updateSettings({ wakeCooldownSeconds: Number(val) })}
          />
        </div>

        {/* Calibration Mode Toggle */}
        <div className="geist-toggle-card" style={{ marginBottom: 10 }}>
          <div className="geist-toggle-info">
            <Text b small style={{ color: '#ededed', display: 'block' }}>Developer Calibration Mode</Text>
            <Text small type="secondary" style={{ fontSize: '0.76rem', margin: 0 }}>
              Inspect live acoustic score and VAD telemetry to tune environment thresholds.
            </Text>
          </div>
          <Toggle
            checked={settings.wakeCalibrationMode}
            onChange={(e: any) => updateSettings({ wakeCalibrationMode: e.target.checked })}
          />
        </div>

        {/* Live Calibration Telemetry Monitor Card */}
        {settings.wakeCalibrationMode && (
          <Card style={{ backgroundColor: '#09090b', borderColor: '#27272a', padding: '10px 12px', borderRadius: 8 }}>
            <Text b small style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
              <Dot type="success" style={{ padding: 0 }} /> Live Diagnostic Telemetry
            </Text>
            <Spacer h={0.4} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', fontSize: '0.74rem' }}>
              <div>
                <span style={{ color: '#71717a' }}>Wake Phrase: </span>
                <span style={{ color: '#fff', fontWeight: 600 }}>"{settings.wakePhrases[0] || 'hey brown'}"</span>
              </div>
              <div>
                <span style={{ color: '#71717a' }}>Detection Score: </span>
                <span style={{ color: (diagnostic.detection_score || 0) >= settings.wakeThreshold ? '#10b981' : '#f59e0b', fontWeight: 600 }}>
                  {(diagnostic.detection_score || 0).toFixed(2)}
                </span>
              </div>
              <div>
                <span style={{ color: '#71717a' }}>VAD State: </span>
                <span style={{ color: diagnostic.vad_state === 'SPEECH' ? '#38bdf8' : '#71717a', fontWeight: 600 }}>
                  {diagnostic.vad_state || 'SILENCE'}
                </span>
              </div>
              <div>
                <span style={{ color: '#71717a' }}>Wake Triggered: </span>
                <span style={{ color: diagnostic.detected ? '#10b981' : '#71717a', fontWeight: 600 }}>
                  {diagnostic.detected ? 'YES' : 'NO'}
                </span>
              </div>
              <div>
                <span style={{ color: '#71717a' }}>False Activations: </span>
                <span style={{ color: '#fff' }}>{diagnostic.false_activations || 0}</span>
              </div>
              <div>
                <span style={{ color: '#71717a' }}>Missed Activations: </span>
                <span style={{ color: '#fff' }}>{diagnostic.missed_activations || 0}</span>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}

export default IntelligenceTab
