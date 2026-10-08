import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { i18nReady } from './i18n/index'
import { applyTheme, getSavedTheme } from './shared/theme'
import { preloadForPath } from './pages'

// Applied before the first render so the saved theme is already on <html>
// when the page paints, rather than flashing the default first.
applyTheme(getSavedTheme())

// Start this URL's page chunk now, in parallel with the language chunk.
preloadForPath(window.location.pathname)

// Only the active language's strings are downloaded (one small chunk); render
// once they are in, so no raw key ever flashes. index.html has already set the
// direction (RTL for Arabic) and the theme before the first paint.
void i18nReady.finally(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
})
