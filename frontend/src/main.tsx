import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import './i18n'
import { applyTheme, getSavedTheme } from './utils/theme'

// Applied before the first render so the saved theme is already on <html>
// when the page paints, rather than flashing the default first.
applyTheme(getSavedTheme())

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
