import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { I18nProvider } from './i18n/I18nProvider';
import './index.css';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <I18nProvider defaultLang="fr">
        <App />
      </I18nProvider>
    </BrowserRouter>
  </React.StrictMode>
);

