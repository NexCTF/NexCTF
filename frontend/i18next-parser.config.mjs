export default {
  locales: ["en", "fr"],
  input: ["src/**/*.{ts,tsx}", "!src/**/*.test.{ts,tsx}", "!src/routeTree.gen.ts"],
  output: "src/i18n/locales/$LOCALE.json",
  defaultNamespace: "translation",
  nsSeparator: false,
  // Keys built at runtime are invisible to the parser. Only these families are kept
  // when they no longer appear in the source; everything else is deleted as dead.
  // Add a pattern here when you introduce a new runtime-built key.
  // Patterns are matched against the namespace-prefixed key ("translation:admin.nav.plugins").
  keepRemoved: [
    /(^|:)admin\.nav(\.|$)/, // routes/admin/_admin.tsx — NAV_SECTIONS heading/label
    /(^|:)admin\.challenge\.question\.input_type_/, // challenges_.$challengeId.tsx — INPUT_TYPES
    /(^|:)oauth_consent\.scope(\.|$)/, // routes/oauth.consent.tsx — scopes from the backend
    /(^|:)config(\.|$)/, // routes/admin/_admin/settings.tsx — labels declared in backend/nexctf/settings.py
  ],
  sort: true,
  createOldCatalogs: false,
  indentation: 2,
  lineEnding: "\n",
  defaultValue: (locale, _namespace, _key, value) => (locale === "en" ? (value ?? "") : ""),
};
