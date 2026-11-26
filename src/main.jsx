import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import App from './App.jsx';

// Le serveur a écrit une version texte du site dans #root (pour les robots et sans JavaScript) :
// React la remplace ici.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
