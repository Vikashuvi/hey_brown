import React from 'react'
import { Sliders, X } from '@geist-ui/icons'

interface OverlayControlsProps {
  onClose: () => void
  onOpenSettings: () => void
}

export const OverlayControls: React.FC<OverlayControlsProps> = ({
  onClose,
  onOpenSettings
}) => {
  return (
    <div className="overlay-controls" role="toolbar" aria-label="Mascot controls">
      {/* Settings trigger button */}
      <button
        type="button"
        className="control-btn control-btn-settings"
        onClick={(e) => {
          e.stopPropagation()
          onOpenSettings()
        }}
        title="Open Control Panel (⌘,)"
        aria-label="Open Control Panel"
      >
        <Sliders size={13} />
      </button>

      {/* Sleep / Close trigger button */}
      <button
        type="button"
        className="control-btn control-btn-close"
        onClick={(e) => {
          e.stopPropagation()
          onClose()
        }}
        title="Sleep / Close Mascot"
        aria-label="Sleep / Close Mascot"
      >
        <X size={13} />
      </button>
    </div>
  )
}

export default OverlayControls
