import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import fr from "./locales/fr.json";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      fr: { translation: fr },
    },
    fallbackLng: "en",
    // Untranslated keys are generated as "" so they stand out in the catalog;
    // without this they would render blank instead of falling back to English.
    returnEmptyString: false,
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
