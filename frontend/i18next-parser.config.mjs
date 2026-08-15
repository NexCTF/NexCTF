export default {
  locales: ["en", "fr"],
  input: ["src/**/*.{ts,tsx}", "!src/**/*.test.{ts,tsx}", "!src/routeTree.gen.ts"],
  output: "src/i18n/locales/$LOCALE.json",
  defaultNamespace: "translation",
  nsSeparator: false,
  // Runtime-built keys (admin nav, oauth scopes, question input types, config labels)
  // are invisible to the parser; without this it would delete them.
  keepRemoved: true,
  sort: true,
  createOldCatalogs: false,
  indentation: 2,
  lineEnding: "\n",
  defaultValue: (locale, _namespace, _key, value) => (locale === "en" ? (value ?? "") : ""),
};
