import React from 'react'
import { useSettings } from '../../context/SettingsContext'
import { COLOR_PRESETS } from '../../types/settings'
import { Text, Slider, Toggle, Input, Spacer, Badge, Grid } from './geist'

export const AppearanceTab: React.FC = () => {
  const { settings, updateSettings, activePresetId } = useSettings()

  return (
    <div className="geist-tab-content">
      {/* Avatar Color Palette Presets */}
      <div className="geist-form-group">
        <div className="geist-label-row">
          <Text small b style={{ color: '#ededed' }}>Avatar Color Palette</Text>
          <Badge type="secondary" scale={0.7} style={{ fontFamily: 'Geist Mono, monospace' }}>
            {settings.primaryColor}
          </Badge>
        </div>
        <Spacer h={0.5} />
        <Grid.Container gap={1} justify="flex-start">
          {COLOR_PRESETS.map((preset) => {
            const isActive = activePresetId === preset.id
            return (
              <Grid xs={6} key={preset.id}>
                <button
                  type="button"
                  className={`geist-color-chip ${isActive ? 'active' : ''}`}
                  onClick={() =>
                    updateSettings({
                      primaryColor: preset.body,
                      eyeColor: preset.eyes
                    })
                  }
                >
                  <span
                    className="geist-color-dot"
                    style={{ backgroundColor: preset.body }}
                  />
                  <span className="geist-color-name">{preset.name}</span>
                </button>
              </Grid>
            )
          })}
        </Grid.Container>
        <Spacer h={0.6} />

        {/* Custom Hex Color Picker */}
        <div className="geist-custom-color-row">
          <input
            type="color"
            className="geist-color-native-input"
            value={settings.primaryColor}
            onChange={(e) => updateSettings({ primaryColor: e.target.value })}
            title="Choose custom color"
          />
          <Input
            width="100%"
            scale={0.85}
            value={settings.primaryColor}
            onChange={(e: any) => updateSettings({ primaryColor: e.target.value })}
            placeholder="#HEX Color"
            maxLength={7}
            style={{ fontFamily: 'Geist Mono, monospace' }}
          />
        </div>
        <Text small type="secondary" style={{ marginTop: 6, display: 'block', fontSize: '0.78rem' }}>
          Colors update live on the mascot with ambient refraction glow.
        </Text>
      </div>

      <Spacer h={1.2} />

      {/* Mascot Diameter Size Slider */}
      <div className="geist-form-group">
        <div className="geist-label-row">
          <Text small b style={{ color: '#ededed' }}>Mascot Diameter Size</Text>
          <Badge type="secondary" scale={0.7} style={{ fontFamily: 'Geist Mono, monospace' }}>
            {settings.mascotSize}px
          </Badge>
        </div>
        <Spacer h={0.5} />
        <Slider
          min={80}
          max={150}
          step={5}
          value={settings.mascotSize}
          onChange={(val: number) => updateSettings({ mascotSize: Number(val) })}
          width="100%"
        />
        <Spacer h={0.4} />
        <Text small type="secondary" style={{ fontSize: '0.78rem' }}>
          Compact: 90px · Standard: 110px · Prominent: 140px.
        </Text>
      </div>

      <Spacer h={1.2} />

      {/* Glossy 3D Glass Toggle */}
      <div className="geist-toggle-card">
        <div className="geist-toggle-info">
          <Text b small style={{ color: '#ededed', display: 'block' }}>
            Glossy 3D Glass Effect
          </Text>
          <Text small type="secondary" style={{ fontSize: '0.78rem', margin: 0 }}>
            Liquid crystal specular gleam and volumetric depth shading.
          </Text>
        </div>
        <Toggle
          checked={settings.glossyEffect}
          onChange={(e: any) => updateSettings({ glossyEffect: e.target.checked })}
        />
      </div>
    </div>
  )
}

export default AppearanceTab
