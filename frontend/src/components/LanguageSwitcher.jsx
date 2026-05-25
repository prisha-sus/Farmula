import React from 'react';
import { useTranslation } from 'react-i18next';
import { Languages } from 'lucide-react';

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'mr', label: 'मराठी' }
];

export default function LanguageSwitcher() {
  const { i18n } = useTranslation();

  function changeLanguage(code) {
    i18n.changeLanguage(code);
    localStorage.setItem('farmula:language', code);
  }

  return (
    <div className="language-switcher">
      <Languages size={16} />
      <select
        value={i18n.language?.split('-')[0] || 'en'}
        onChange={(e) => changeLanguage(e.target.value)}
        aria-label="Select language"
      >
        {LANGUAGES.map(lang => (
          <option key={lang.code} value={lang.code}>{lang.label}</option>
        ))}
      </select>
    </div>
  );
}
