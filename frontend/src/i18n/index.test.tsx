import { expect, test } from "vitest";

import i18n from "./index";

test("an untranslated key falls back to English instead of rendering blank", async () => {
  i18n.addResource("en", "translation", "zz_probe", "Fallback");
  i18n.addResource("fr", "translation", "zz_probe", "");

  await i18n.changeLanguage("fr");
  expect(i18n.t("zz_probe")).toBe("Fallback");
  await i18n.changeLanguage("en");
});
