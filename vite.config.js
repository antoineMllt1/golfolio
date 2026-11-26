import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// En développement, Vite sert tout (le film est dans public/frames, le texte dans content/site.json).
// Le serveur Express (npm start) n'est nécessaire que pour la version construite.
export default defineConfig({
  plugins: [react()],
  build: { target: 'es2022', chunkSizeWarningLimit: 900 },
});
