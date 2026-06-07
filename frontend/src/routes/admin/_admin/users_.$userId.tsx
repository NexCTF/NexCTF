import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Ban, ExternalLink, KeyRound, Pencil, ShieldCheck, ShieldOff } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { CustomFieldInput } from "@/components/custom-field-input";
import { CustomFieldValuesList } from "@/components/custom-field-values-list";
import { DataTable, useTableState } from "@/components/data-table";
import { DetailPageShell, DetailSection } from "@/components/detail-page";
import { LinksFormSection } from "@/components/links-form-section";
import { TeamSingleSelect } from "@/components/team-single-select";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type Link as ApiLink,
  adminCreatePasswordResetToken,
  adminResetUserTotp,
  apiErrorMessage,
  getAdminCustomFields,
  getAdminUser,
  getAdminUserEvents,
  setAdminCustomFieldValue,
  updateAdminUser,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, copyToClipboard } from "@/lib/utils";
import { COLUMNS } from "@/routes/admin/_admin/events";

export const Route = createFileRoute("/admin/_admin/users_/$userId")({
  component: UserDetailPage,
});

const ROLES = ["user", "moderator", "admin"] as const;

function EditUserDialog({
  userId,
  user,
  onSaved,
}: {
  userId: string;
  user: Awaited<ReturnType<typeof getAdminUser>>;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [username, setUsername] = useState(user.username);
  const [email, setEmail] = useState(user.email ?? "");
  const [role, setRole] = useState(user.role);
  const [teamId, setTeamId] = useState<string | null>(user.team_id);
  const [links, setLinks] = useState<ApiLink[]>(user.links);
  const [cfValues, setCfValues] = useState<Record<string, string>>(
    Object.fromEntries(user.custom_field_values.map((cfv) => [cfv.definition.id, cfv.value ?? ""])),
  );

  const { data: defsResponse } = useQuery({
    queryKey: ["admin", "custom-fields", "all"],
    queryFn: () => getAdminCustomFields("items_per_page=100"),
    enabled: open,
  });
  const userDefs = (defsResponse?.data ?? []).filter((d) => d.target === "user");

  const existingDefIds = new Set(user.custom_field_values.map((cfv) => cfv.definition.id));

  const mutation = useMutation({
    mutationFn: async () => {
      await updateAdminUser(userId, {
        username,
        email: email || null,
        role,
        team_id: teamId,
        links,
      });
      await Promise.all(
        userDefs
          .filter((def) => cfValues[def.id] || existingDefIds.has(def.id))
          .map((def) =>
            setAdminCustomFieldValue({
              definition_id: def.id,
              user_id: userId,
              value: cfValues[def.id] || null,
            }),
          ),
      );
    },
    onSuccess: () => {
      toast.success(t("admin.users.saved"));
      setOpen(false);
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.users.save_error"))),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <Pencil className="size-3.5 mr-1.5" />
            {t("common.edit")}
          </Button>
        }
      />
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("admin.users.edit_title")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2 max-h-[70vh] overflow-y-auto pr-1"
        >
          <div className="space-y-1.5">
            <Label>{t("admin.users.field_username")} *</Label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>

          <div className="space-y-1.5">
            <Label>{t("admin.users.field_email")}</Label>
            <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" />
          </div>

          <div className="space-y-1.5">
            <Label>{t("admin.users.field_role")}</Label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring capitalize"
            >
              {ROLES.map((r) => (
                <option key={r} value={r} className="capitalize">
                  {r}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label>{t("admin.users.field_team")}</Label>
            <TeamSingleSelect value={teamId} onChange={setTeamId} />
          </div>

          <LinksFormSection links={links} onChange={setLinks} />

          {userDefs.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {t("admin.custom_fields.values_title")}
              </p>
              {userDefs.map((def) => (
                <div key={def.id} className="space-y-1.5">
                  <Label>
                    {def.label}
                    {def.is_required && <span className="text-destructive ml-0.5">*</span>}
                  </Label>
                  <CustomFieldInput
                    fieldType={def.field_type}
                    value={cfValues[def.id] ?? ""}
                    onChange={(v) => setCfValues((prev) => ({ ...prev, [def.id]: v }))}
                  />
                </div>
              ))}
            </div>
          )}

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ResetTotpButton({ userId, onSuccess }: { userId: string; onSuccess: () => void }) {
  const { t } = useTranslation();
  const mutation = useMutation({
    mutationFn: () => adminResetUserTotp(userId),
    onSuccess: () => {
      toast.success(t("admin.users.totp_reset_success"));
      onSuccess();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.users.totp_reset_error"))),
  });

  function handleClick() {
    if (!confirm(t("admin.users.totp_reset_confirm"))) return;
    mutation.mutate();
  }

  return (
    <Button variant="outline" size="sm" onClick={handleClick} disabled={mutation.isPending}>
      <ShieldOff className="size-3.5 mr-1.5" />
      {t("admin.users.totp_reset_btn")}
    </Button>
  );
}

function PasswordResetTokenDialog({ userId }: { userId: string }) {
  const { t } = useTranslation();
  const [token, setToken] = useState<string | null>(null);

  const resetLink = token ? `${window.location.origin}/reset-password?token=${token}` : null;

  const mutation = useMutation({
    mutationFn: () => adminCreatePasswordResetToken(userId),
    onSuccess: setToken,
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.users.pwd_reset_error"))),
  });

  function handleCopy() {
    if (!resetLink) return;
    copyToClipboard(resetLink);
    toast.success(t("admin.users.pwd_reset_copied"));
  }

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
      >
        <KeyRound className="size-3.5 mr-1.5" />
        {t("admin.users.pwd_reset_btn")}
      </Button>
      <Dialog
        open={token !== null}
        onOpenChange={(open) => {
          if (!open) setToken(null);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{t("admin.users.pwd_reset_dialog_title")}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">{t("admin.users.pwd_reset_dialog_desc")}</p>
          <div className="flex items-center gap-2">
            <Input value={resetLink ?? ""} readOnly className="font-mono text-xs" />
            <Button variant="outline" size="sm" onClick={handleCopy}>
              {t("common.copy")}
            </Button>
          </div>
          <DialogFooter>
            <Button onClick={() => setToken(null)}>{t("common.close")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center gap-4 px-4 py-3 text-sm">
      <span className="w-36 shrink-0 text-muted-foreground">{label}</span>
      <span className="flex-1">{value}</span>
    </div>
  );
}

function UserDetailPage() {
  const { t } = useTranslation();
  const { userId } = Route.useParams();
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();

  function invalidateUser() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "user", userId] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
  }

  const eventsTable = useTableState();

  const { data: user, isLoading } = useQuery({
    queryKey: ["admin", "user", userId],
    queryFn: () => getAdminUser(userId),
  });

  const {
    data: eventsResponse,
    isLoading: eventsLoading,
    isFetching: eventsFetching,
    refetch: refetchEvents,
  } = useQuery({
    queryKey: ["admin", "user", userId, "events", eventsTable.queryString],
    queryFn: () => getAdminUserEvents(userId, eventsTable.queryString),
    placeholderData: (prev) => prev,
  });

  const mutation = useMutation({
    mutationFn: (data: Parameters<typeof updateAdminUser>[1]) => updateAdminUser(userId, data),
    onSuccess: invalidateUser,
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.users.update_error"))),
  });

  if (!isLoading && !user) {
    return (
      <DetailPageShell backTo="/admin/users" backLabel={t("admin.users.detail_back")}>
        <p className="text-muted-foreground">{t("admin.users.not_found")}</p>
      </DetailPageShell>
    );
  }

  const isSelf = currentUser?.id === userId;

  function handleToggleActive() {
    if (!user) return;
    if (user.is_active) {
      if (!confirm(t("admin.users.disable_confirm"))) return;
      mutation.mutate(
        { is_active: false },
        { onSuccess: () => toast.success(t("admin.users.disabled")) },
      );
    } else {
      mutation.mutate(
        { is_active: true },
        { onSuccess: () => toast.success(t("admin.users.enabled")) },
      );
    }
  }

  return (
    <DetailPageShell
      backTo="/admin/users"
      backLabel={t("admin.users.detail_back")}
      title={user?.username}
      isLoading={isLoading}
      badge={
        user && (
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
              user.role === "admin"
                ? "bg-primary/10 text-primary"
                : "bg-muted text-muted-foreground",
            )}
          >
            {user.role === "admin" && <ShieldCheck className="size-3" />}
            {user.role}
          </span>
        )
      }
      actions={
        user && (
          <Button
            variant={user.is_active ? "destructive" : "default"}
            onClick={handleToggleActive}
            disabled={mutation.isPending || isSelf}
            title={isSelf ? t("admin.users.self_action_hint") : undefined}
          >
            {user.is_active ? (
              <>
                <Ban className="size-4 mr-1.5" />
                {t("admin.users.disable_btn")}
              </>
            ) : (
              <>
                <ShieldCheck className="size-4 mr-1.5" />
                {t("admin.users.enable_btn")}
              </>
            )}
          </Button>
        )
      }
    >
      {user && (
        <>
          <DetailSection
            title={t("admin.users.info_title")}
            actions={
              <div className="flex items-center gap-2">
                {user.totp_enabled && (
                  <ResetTotpButton userId={userId} onSuccess={invalidateUser} />
                )}
                <PasswordResetTokenDialog userId={userId} />
                <EditUserDialog userId={userId} user={user} onSaved={invalidateUser} />
              </div>
            }
          >
            <div className="rounded-lg border divide-y">
              <InfoRow
                label={t("admin.users.field_id")}
                value={
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
                    {user.id}
                  </code>
                }
              />
              <InfoRow
                label={t("admin.users.field_email")}
                value={
                  <span className={user.email ? "" : "text-muted-foreground"}>
                    {user.email ?? "—"}
                  </span>
                }
              />
              <InfoRow
                label={t("admin.users.field_role")}
                value={
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                      user.role === "admin"
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    {user.role === "admin" && <ShieldCheck className="size-3" />}
                    {user.role}
                  </span>
                }
              />
              <InfoRow
                label={t("admin.users.field_team")}
                value={
                  user.team_id ? (
                    <Link
                      to="/admin/teams/$teamId"
                      params={{ teamId: user.team_id }}
                      className="text-primary hover:underline underline-offset-2"
                    >
                      {user.team_name}
                    </Link>
                  ) : (
                    <span className="text-muted-foreground">{t("admin.users.no_team")}</span>
                  )
                }
              />
              <InfoRow
                label={t("admin.users.field_totp")}
                value={
                  <span
                    className={
                      user.totp_enabled
                        ? "text-green-600 dark:text-green-400"
                        : "text-muted-foreground"
                    }
                  >
                    {user.totp_enabled
                      ? t("admin.users.totp_enabled")
                      : t("admin.users.totp_disabled")}
                  </span>
                }
              />
              <InfoRow
                label={t("admin.users.field_status")}
                value={
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 text-xs",
                      user.is_active ? "text-green-600 dark:text-green-400" : "text-destructive",
                    )}
                  >
                    <span
                      className={cn(
                        "size-1.5 rounded-full",
                        user.is_active ? "bg-green-500" : "bg-destructive",
                      )}
                    />
                    {user.is_active
                      ? t("admin.users.status_active")
                      : t("admin.users.status_disabled")}
                  </span>
                }
              />
              <InfoRow
                label={t("admin.users.field_last_login_ip")}
                value={
                  user.last_login_ip ? (
                    <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
                      {user.last_login_ip}
                    </code>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )
                }
              />
              <InfoRow
                label={t("admin.users.field_last_login_at")}
                value={
                  user.last_login_at ? (
                    <span className="text-xs text-muted-foreground">
                      {new Date(user.last_login_at).toLocaleString()}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )
                }
              />
              {user.links.length > 0 && (
                <InfoRow
                  label={t("admin.users.field_links")}
                  value={
                    <div className="flex flex-wrap gap-2">
                      {user.links.map((lnk, i) => (
                        <a
                          // biome-ignore lint/suspicious/noArrayIndexKey: display-only, never reorders
                          key={i}
                          href={lnk.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-primary hover:underline underline-offset-2 text-xs"
                        >
                          {lnk.label || lnk.url}
                          <ExternalLink className="size-3 opacity-60" />
                        </a>
                      ))}
                    </div>
                  }
                />
              )}
            </div>
          </DetailSection>

          <CustomFieldValuesList
            entityId={userId}
            entityType="user"
            values={user.custom_field_values}
            onSaved={invalidateUser}
            readOnly
          />

          <DetailSection title={t("admin.users.events_title")}>
            <DataTable
              columns={COLUMNS}
              response={eventsResponse}
              table={eventsTable}
              isLoading={eventsLoading}
              isFetching={eventsFetching}
              rowKey={(e) => e.id}
              onRefresh={() => void refetchEvents()}
            />
          </DetailSection>
        </>
      )}
    </DetailPageShell>
  );
}
