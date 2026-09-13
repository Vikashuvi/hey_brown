import React, { useState } from 'react'
import { useSettings } from '../../context/SettingsContext'
import { Text, Input, Toggle, Slider, Spacer, Badge, Dot, Card, Divider, Button } from './geist'
import { Server, Activity, RefreshCw, Check, Zap, Cpu } from '@geist-ui/icons'

interface DiscoveredModel {
  id: string
  name: string
  device?: string
  loaded?: boolean
  vision?: boolean
}

interface NodeSystemStats {
  hostname?: string
  platform?: string
  cpu_count?: number
  load1?: number
  ram_total_mb?: number
  ram_used_mb?: number
  ram_available_mb?: number
  ram_usage_pct?: number
  os?: string
}

export const NodesTab: React.FC = () => {
  const { settings, updateSettings } = useSettings()

  const [isProbing, setIsProbing] = useState<boolean>(false)
  const [nodeOnline, setNodeOnline] = useState<boolean | null>(null)
  const [probeError, setProbeError] = useState<string | null>(null)
  const [nodeTelemetry, setNodeTelemetry] = useState<NodeSystemStats | null>(null)
  const [capabilities, setCapabilities] = useState<string[]>([])

  const [isDiscovering, setIsDiscovering] = useState<boolean>(false)
  const [discoveredModels, setDiscoveredModels] = useState<DiscoveredModel[]>([])
  const [actionNotice, setActionNotice] = useState<string | null>(null)

  const handleAliasesChange = (val: string) => {
    const list = val
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    updateSettings({ remoteNodeAliases: list })
  }

  const probeNode = async () => {
    setIsProbing(true)
    setProbeError(null)
    setActionNotice(null)
    try {
      const url = (settings.remoteNodeUrl || 'http://127.0.0.1:8765').replace(/\/+$/, '')
      const headers: Record<string, string> = {
        Accept: 'application/json',
      }
      if (settings.remoteNodeAuthToken) {
        headers['Authorization'] = `Bearer ${settings.remoteNodeAuthToken}`
      }

      const res = await fetch(`${url}/system/status`, {
        method: 'GET',
        headers,
        signal: AbortSignal.timeout((settings.remoteNodeTimeout || 2.0) * 1000),
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }

      const data = await res.json()
      setNodeTelemetry(data.data || data)
      setNodeOnline(true)

      // Also query capabilities
      try {
        const capRes = await fetch(`${url}/capabilities`, {
          headers,
          signal: AbortSignal.timeout(2000),
        })
        if (capRes.ok) {
          const capData = await capRes.json()
          setCapabilities(capData.data?.capabilities || [])
        }
      } catch {
        // Non-critical
      }
    } catch (err: any) {
      setNodeOnline(false)
      setProbeError(err.message || 'Host connection refused or timed out')
    } finally {
      setIsProbing(false)
    }
  }

  const discoverModels = async () => {
    setIsDiscovering(true)
    setActionNotice(null)
    try {
      const url = (settings.remoteNodeUrl || 'http://127.0.0.1:8765').replace(/\/+$/, '')
      const headers: Record<string, string> = {
        Accept: 'application/json',
      }
      if (settings.remoteNodeAuthToken) {
        headers['Authorization'] = `Bearer ${settings.remoteNodeAuthToken}`
      }

      const res = await fetch(`${url}/ai/models`, {
        method: 'GET',
        headers,
        signal: AbortSignal.timeout(4000),
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }

      const data = await res.json()
      const models = data.models || []
      setDiscoveredModels(models)
      setActionNotice(`Found ${models.length} model(s) hosted on node.`)
    } catch (err: any) {
      setActionNotice(`Model discovery error: ${err.message}`)
    } finally {
      setIsDiscovering(false)
    }
  }

  const selectModelAsPrimary = (modelId: string, isVision: boolean) => {
    updateSettings({
      localAiModel: modelId,
      localAiVisionModel: isVision ? modelId : settings.localAiVisionModel,
      localAiUrl: settings.remoteNodeUrl,
    })
    setActionNotice(`Configured '${modelId}' as Brown's active AI model.`)
  }

  const warmModelOnNode = async (modelId: string) => {
    try {
      const url = (settings.remoteNodeUrl || 'http://127.0.0.1:8765').replace(/\/+$/, '')
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (settings.remoteNodeAuthToken) {
        headers['Authorization'] = `Bearer ${settings.remoteNodeAuthToken}`
      }
      setActionNotice(`Warming '${modelId}' into node memory...`)
      const res = await fetch(`${url}/ai/warm`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ model: modelId, keep_alive: '15m' }),
      })
      if (res.ok) {
        setActionNotice(`Model '${modelId}' successfully warmed in node VRAM.`)
        discoverModels()
      } else {
        setActionNotice(`Warm request failed with status ${res.status}.`)
      }
    } catch (err: any) {
      setActionNotice(`Warm error: ${err.message}`)
    }
  }

  const unloadModelOnNode = async (modelId: string) => {
    try {
      const url = (settings.remoteNodeUrl || 'http://127.0.0.1:8765').replace(/\/+$/, '')
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (settings.remoteNodeAuthToken) {
        headers['Authorization'] = `Bearer ${settings.remoteNodeAuthToken}`
      }
      const res = await fetch(`${url}/ai/unload`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ model: modelId }),
      })
      if (res.ok) {
        setActionNotice(`Model '${modelId}' unloaded from memory.`)
        discoverModels()
      }
    } catch (err: any) {
      setActionNotice(`Unload error: ${err.message}`)
    }
  }

  return (
    <div className="geist-tab-content">
      {/* Dynamic Node Enable */}
      <div className="geist-setting-row" style={{ alignItems: 'flex-start' }}>
        <div>
          <Text b style={{ fontSize: '0.85rem', color: '#ffffff', margin: 0 }}>
            Secondary Compute Node
          </Text>
          <Text small type="secondary" style={{ display: 'block', fontSize: '0.75rem', marginTop: 2 }}>
            Enable execution of tools, device actions, and AI acceleration on remote machine.
          </Text>
        </div>
        <Toggle
          checked={settings.remoteNodeEnabled}
          onChange={(e: any) => updateSettings({ remoteNodeEnabled: e.target.checked })}
        />
      </div>

      <Divider style={{ margin: '10px 0', borderColor: '#222222' }} />

      {/* Node Identification */}
      <div style={{ display: 'flex', gap: '8px' }}>
        <div style={{ flex: 1 }}>
          <Text small style={{ color: '#888888', display: 'block', marginBottom: 4 }}>
            Node Display Name
          </Text>
          <Input
            width="100%"
            scale={0.8}
            value={settings.remoteNodeName}
            onChange={(e: any) => updateSettings({ remoteNodeName: e.target.value })}
            placeholder="e.g. Linux Workstation"
          />
        </div>
        <div style={{ width: '120px' }}>
          <Text small style={{ color: '#888888', display: 'block', marginBottom: 4 }}>
            Device ID
          </Text>
          <Input
            width="100%"
            scale={0.8}
            value={settings.remoteNodeId}
            onChange={(e: any) => updateSettings({ remoteNodeId: e.target.value.toLowerCase().replace(/\s+/g, '_') })}
            placeholder="remote_node"
          />
        </div>
      </div>

      <Spacer h={0.6} />

      {/* Connection Endpoint */}
      <div>
        <Text small style={{ color: '#888888', display: 'block', marginBottom: 4 }}>
          Node Daemon URL (LAN / Tailscale)
        </Text>
        <Input
          width="100%"
          scale={0.8}
          value={settings.remoteNodeUrl}
          onChange={(e: any) => updateSettings({ remoteNodeUrl: e.target.value, localAiUrl: e.target.value })}
          placeholder="http://192.168.1.150:8765"
        />
      </div>

      <Spacer h={0.6} />

      {/* Auth Token & Timeout */}
      <div style={{ display: 'flex', gap: '8px' }}>
        <div style={{ flex: 2 }}>
          <Text small style={{ color: '#888888', display: 'block', marginBottom: 4 }}>
            Bearer Token (Optional)
          </Text>
          <Input
            htmlType="password"
            width="100%"
            scale={0.8}
            value={settings.remoteNodeAuthToken}
            onChange={(e: any) => updateSettings({ remoteNodeAuthToken: e.target.value })}
            placeholder="LAN Secret / Token"
          />
        </div>
        <div style={{ flex: 1 }}>
          <Text small style={{ color: '#888888', display: 'block', marginBottom: 4 }}>
            Timeout: {settings.remoteNodeTimeout}s
          </Text>
          <Slider
            min={0.5}
            max={10.0}
            step={0.5}
            value={settings.remoteNodeTimeout}
            onChange={(val: any) => updateSettings({ remoteNodeTimeout: Number(val) })}
          />
        </div>
      </div>

      <Spacer h={0.6} />

      {/* Aliases for Voice / Chat Targeting */}
      <div>
        <Text small style={{ color: '#888888', display: 'block', marginBottom: 4 }}>
          Voice & Chat Aliases (Comma Separated)
        </Text>
        <Input
          width="100%"
          scale={0.8}
          value={settings.remoteNodeAliases?.join(', ') || ''}
          onChange={(e: any) => handleAliasesChange(e.target.value)}
          placeholder="remote, secondary, linux, victus, workstation"
        />
      </div>

      <Spacer h={0.8} />

      {/* Connectivity Probe Section */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Server size={14} color="#888" />
          <Text b style={{ fontSize: '0.8rem', color: '#ffffff', margin: 0 }}>
            Node Health & Telemetry
          </Text>
        </div>
        <Button
          auto
          scale={0.68}
          type="secondary"
          loading={isProbing}
          icon={<RefreshCw size={11} />}
          onClick={probeNode}
          style={{ backgroundColor: '#222', borderColor: '#444', color: '#fff' }}
        >
          Ping & Probe
        </Button>
      </div>

      {nodeOnline !== null && (
        <Card
          style={{
            backgroundColor: '#0a0a0a',
            borderColor: nodeOnline ? '#10b98140' : '#f43f5e40',
            padding: '8px 12px',
            borderRadius: '6px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Dot type={nodeOnline ? 'success' : 'error'} />
              <Text small b style={{ color: nodeOnline ? '#10b981' : '#f43f5e', margin: 0 }}>
                {nodeOnline ? 'ONLINE & REACHABLE' : 'UNREACHABLE'}
              </Text>
            </div>
            {nodeTelemetry?.hostname && (
              <Badge type="secondary" scale={0.7}>
                {nodeTelemetry.hostname}
              </Badge>
            )}
          </div>

          {nodeOnline && nodeTelemetry && (
            <div style={{ marginTop: 8, fontSize: '0.72rem', color: '#888' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <span>OS / Kernel:</span>
                <span style={{ color: '#fff' }}>{nodeTelemetry.os || nodeTelemetry.platform || 'Linux'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <span>CPU / Cores:</span>
                <span style={{ color: '#fff' }}>
                  {nodeTelemetry.cpu_count} Cores (Load: {nodeTelemetry.load1 || 0.0})
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <span>System RAM:</span>
                <span style={{ color: '#fff' }}>
                  {nodeTelemetry.ram_used_mb}MB / {nodeTelemetry.ram_total_mb}MB ({nodeTelemetry.ram_usage_pct || 0}%)
                </span>
              </div>
              {capabilities.length > 0 && (
                <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {capabilities.map((cap) => (
                    <Badge key={cap} type="lite" scale={0.55} style={{ background: '#191919', color: '#a1a1a1' }}>
                      {cap}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          )}

          {probeError && (
            <Text small type="error" style={{ display: 'block', marginTop: 4, fontSize: '0.72rem' }}>
              {probeError}
            </Text>
          )}
        </Card>
      )}

      <Spacer h={0.8} />

      {/* Dynamic Model Discovery on Node */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Cpu size={14} color="#888" />
          <Text b style={{ fontSize: '0.8rem', color: '#ffffff', margin: 0 }}>
            Model Discovery
          </Text>
        </div>
        <Button
          auto
          scale={0.68}
          type="abort"
          loading={isDiscovering}
          icon={<Zap size={11} />}
          onClick={discoverModels}
          style={{ borderColor: '#333', color: '#a1a1a1' }}
        >
          Scan Node Models
        </Button>
      </div>

      {actionNotice && (
        <div style={{ marginBottom: 8, padding: '4px 8px', background: '#111', borderRadius: '4px', border: '1px solid #262626' }}>
          <Text small style={{ color: '#a1a1a1', fontSize: '0.72rem', margin: 0 }}>
            {actionNotice}
          </Text>
        </div>
      )}

      {discoveredModels.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {discoveredModels.map((m) => {
            const isCurrent = settings.localAiModel === m.id
            return (
              <div
                key={m.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  background: isCurrent ? 'rgba(124, 58, 237, 0.12)' : '#0d0d0d',
                  border: isCurrent ? '1px solid #7c3aed66' : '1px solid #222',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Text b style={{ fontSize: '0.78rem', color: isCurrent ? '#a78bfa' : '#fff', margin: 0 }}>
                      {m.name || m.id}
                    </Text>
                    {m.vision && (
                      <Badge type="warning" scale={0.55}>
                        Vision
                      </Badge>
                    )}
                    {m.loaded && (
                      <Badge type="success" scale={0.55}>
                        Loaded in VRAM
                      </Badge>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  <Button
                    auto
                    scale={0.58}
                    type={isCurrent ? 'success' : 'secondary'}
                    icon={<Check size={10} />}
                    onClick={() => selectModelAsPrimary(m.id, !!m.vision)}
                    style={{ padding: '0 8px' }}
                  >
                    {isCurrent ? 'Active' : 'Use'}
                  </Button>
                  {m.loaded ? (
                    <Button
                      auto
                      scale={0.58}
                      type="abort"
                      onClick={() => unloadModelOnNode(m.id)}
                      style={{ padding: '0 8px', color: '#888' }}
                    >
                      Unload
                    </Button>
                  ) : (
                    <Button
                      auto
                      scale={0.58}
                      type="abort"
                      onClick={() => warmModelOnNode(m.id)}
                      style={{ padding: '0 8px', color: '#a78bfa' }}
                    >
                      Warm
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <Text small type="secondary" style={{ fontSize: '0.72rem', fontStyle: 'italic', display: 'block' }}>
          Click "Scan Node Models" to query models installed in Ollama on the remote node.
        </Text>
      )}
    </div>
  )
}

export default NodesTab
