import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import MathPracticeApp from './MathPracticeApp.jsx'
import { Toaster } from 'sonner'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <MathPracticeApp />
    <Toaster richColors position="top-right" />
  </React.StrictMode>,
)
