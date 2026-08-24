import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { CustomFieldsSection } from "@/components/custom-fields-section";
import { LinksFormSection } from "@/components/links-form-section";
import type { CustomFieldValues, Link, MyProfile, MyTeamProfile } from "@/lib/api";

/** Form state for the editable half of a user or team profile. */
export function useProfileForm(profile: MyProfile | MyTeamProfile | undefined) {
  const [links, setLinks] = useState<Link[]>([]);
  const [customFields, setCustomFields] = useState<CustomFieldValues>({});
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");

  useEffect(() => {
    if (!profile) return;
    setLinks(profile.links);
    setCustomFields(
      Object.fromEntries(profile.custom_fields.map((f) => [f.definition_id, f.value ?? ""])),
    );
    if ("name" in profile) {
      setName(profile.name);
      setCountry(profile.country ?? "");
    }
  }, [profile]);

  return { links, setLinks, customFields, setCustomFields, name, setName, country, setCountry };
}

export type ProfileForm = ReturnType<typeof useProfileForm>;

/** Links and custom field inputs shared by the user and team profile editors. */
export function ProfileFormSections({ profile, form }: { profile: MyProfile; form: ProfileForm }) {
  const { t } = useTranslation();
  return (
    <>
      <LinksFormSection links={form.links} onChange={form.setLinks} />
      <CustomFieldsSection
        defs={profile.custom_fields.map((f) => ({ ...f, id: f.definition_id }))}
        values={form.customFields}
        onChange={form.setCustomFields}
        title={t("profile.fields_title", { defaultValue: "Details" })}
      />
    </>
  );
}
