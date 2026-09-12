export interface ColorPreset {
  id: string
  name: string
  body: string
  eyes: string
  glow: string
}

export const COLOR_PRESETS: ColorPreset[] = [
  {
    id: 'electric-violet',
    name: 'Electric Violet',
    body: '#7c3aed',
    eyes: '#0f0926',
    glow: 'rgba(124, 58, 237, 0.45)'
  },
  {
    id: 'cyber-cyan',
    name: 'Cyber Cyan',
    body: '#06b6d4',
    eyes: '#041620',
    glow: 'rgba(6, 182, 212, 0.45)'
  },
  {
    id: 'cyber-emerald',
    name: 'Cyber Emerald',
    body: '#10b981',
    eyes: '#061d15',
    glow: 'rgba(16, 185, 129, 0.45)'
  },
  {
    id: 'sunset-coral',
    name: 'Sunset Coral',
    body: '#f43f5e',
    eyes: '#20050d',
    glow: 'rgba(244, 63, 94, 0.45)'
  },
  {
    id: 'warm-amber',
    name: 'Warm Caramel',
    body: '#e07a38',
    eyes: '#150f0b',
    glow: 'rgba(224, 122, 56, 0.45)'
  },
  {
    id: 'obsidian-minimal',
    name: 'Obsidian Minimal',
    body: '#3b4252',
    eyes: '#0f1117',
    glow: 'rgba(59, 66, 82, 0.45)'
  }
]

export type DialogueMode = 'necessary_only' | 'always' | 'never'

export interface BrownSettings {
  assistantName: string
  wakePhrases: string[]
  primaryColor: string
  eyeColor: string
  mascotSize: number
  glossyEffect: boolean
  sleepTimeoutSeconds: number
  speechCadenceMs: number
  dialogueMode: DialogueMode
  bargeInEnabled: boolean
}

export const DEFAULT_SETTINGS: BrownSettings = {
  assistantName: 'Brown',
  wakePhrases: ['hey brown', 'brown', 'wake up brown'],
  primaryColor: '#7c3aed',
  eyeColor: '#0f0926',
  mascotSize: 110,
  glossyEffect: true,
  sleepTimeoutSeconds: 8,
  speechCadenceMs: 300,
  dialogueMode: 'necessary_only',
  bargeInEnabled: false
}
