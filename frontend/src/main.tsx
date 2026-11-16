import '@fontsource-variable/public-sans/index.css'
import '@fontsource-variable/source-serif-4/opsz.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './estilos.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
