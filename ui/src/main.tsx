import React from 'react'
import ReactDOM from 'react-dom/client'
import { GeistProvider, CssBaseline } from '@geist-ui/core'
import '@fontsource/geist-sans/index.css'
import '@fontsource/geist-mono/index.css'
import App from './App.tsx'
import './index.css'

const rootElement = document.getElementById('root')
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <GeistProvider themeType="dark">
        <CssBaseline />
        <App />
      </GeistProvider>
    </React.StrictMode>
  )
}

