import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { api } from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import { getLocale, setLocale, t, type Locale } from "../i18n";
import { getAuthAccount, updateAuthAccount, type MobileAccount } from "../storage/auth";
import { getProfile, setProfile } from "../storage/session";
import { colors } from "../theme";

type Props = {
  onOpenSettings: () => void;
  onOpenNotifications: () => void;
  onSignedOut: () => void;
};

export function AccountScreen({ onOpenSettings, onOpenNotifications, onSignedOut }: Props) {
  const [account, setAccount] = useState<MobileAccount | null>(getAuthAccount());
  const [phone, setPhone] = useState("");
  const [walletProvider, setWalletProvider] = useState<"mpesa" | "airtel_money">("mpesa");
  const [inviteCode, setInviteCode] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [locale, setLocaleState] = useState<Locale>(getLocale());
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshMe = async () => {
    try {
      const me = await api.mobileMe();
      await updateAuthAccount(me);
      setAccount(me);
      if (me.phone) setPhone(me.phone);
      if (me.national_id) setNationalId(me.national_id);
    } catch {
      // keep cached
    }
  };

  useEffect(() => {
    getProfile().then((p) => {
      if (!p) return;
      setPhone(p.phone);
      setWalletProvider(p.walletProvider);
    });
    void refreshMe();
  }, []);

  const saveProfile = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.completeProfile({
        phone,
        wallet_provider: walletProvider,
        wallet_number: phone,
      });
      setAccount(result.account);
      await setProfile({
        phone,
        fullName: result.account.full_name,
        walletProvider,
      });
      setMessage(
        result.account.can_borrow
          ? "Wallet saved. You can borrow."
          : result.account.approval_message || "Phone saved. Waiting for institution approval.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const claimInvite = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await api.claimInvite(inviteCode.trim().toUpperCase());
      setAccount(next);
      setInviteCode("");
      setMessage(next.approval_message || "Invite claimed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const changePassword = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setMessage("Password updated. Use it next time you sign in.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const signOut = async () => {
    setBusy(true);
    try {
      await api.logoutMobile();
    } finally {
      setBusy(false);
      onSignedOut();
    }
  };

  return (
    <ScreenShell title="Account" subtitle={account?.email || "Your secure Buruuj Lend profile"}>
      <ScrollView contentContainerStyle={styles.form} keyboardShouldPersistTaps="handled">
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{account?.full_name || "Customer"}</Text>
          <Text style={styles.cardMeta}>{account?.email}</Text>
          <Text style={styles.badge}>
            {account?.can_borrow
              ? `Approved · limit KES ${Number(account.credit_limit || 0).toLocaleString("en-KE")}`
              : account?.approval_status === "rejected"
                ? "Rejected by institution"
                : "Pending institution approval"}
          </Text>
          {account?.institution_name ? (
            <Text style={styles.cardParty}>Lending institution: {account.institution_name}</Text>
          ) : (
            <Text style={styles.cardMeta}>No institution linked yet — claim an invite below.</Text>
          )}
          {account?.agent_dealer_name ? (
            <Text style={styles.cardParty}>
              Agent float: {account.agent_dealer_name}
              {account.agent_float_available != null
                ? ` · KES ${Number(account.agent_float_available).toLocaleString("en-KE")}`
                : ""}
            </Text>
          ) : null}
          {account?.approval_message ? (
            <Text style={styles.cardMeta}>{account.approval_message}</Text>
          ) : null}
        </View>

        <Text style={styles.section}>{t("kyc")}</Text>
        <Text style={styles.cardMeta}>
          Status:{" "}
          {account?.kyc_status === "verified"
            ? t("kycVerified")
            : account?.kyc_status === "rejected"
              ? t("kycRejected")
              : t("kycPending")}
        </Text>
        <Field label={t("nationalId")} value={nationalId} onChangeText={setNationalId} />
        <Pressable
          style={[styles.button, busy && styles.disabled]}
          disabled={busy}
          onPress={async () => {
            setBusy(true);
            setError(null);
            setMessage(null);
            try {
              const me = await api.submitKyc({ national_id: nationalId.trim() });
              await updateAuthAccount(me);
              setAccount(me);
              setMessage("Identity submitted.");
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err));
            } finally {
              setBusy(false);
            }
          }}
        >
          <Text style={styles.buttonText}>{t("submitKyc")}</Text>
        </Pressable>

        <Text style={styles.section}>{t("language")}</Text>
        <View style={styles.row}>
          <Chip
            label={t("english")}
            active={locale === "en"}
            onPress={async () => {
              await setLocale("en");
              setLocaleState("en");
            }}
          />
          <Chip
            label={t("swahili")}
            active={locale === "sw"}
            onPress={async () => {
              await setLocale("sw");
              setLocaleState("sw");
            }}
          />
        </View>

        <Text style={styles.section}>Institution invite</Text>
        <Field label="Invite code (BL-…)" value={inviteCode} onChangeText={setInviteCode} />
        <Pressable style={[styles.secondary, busy && styles.disabled]} onPress={claimInvite} disabled={busy}>
          <Text style={styles.secondaryText}>Claim invite</Text>
        </Pressable>

        <Text style={styles.section}>Wallet for disbursement</Text>
        <Field label="Phone (254…)" value={phone} onChangeText={setPhone} keyboardType="phone-pad" />
        <View style={styles.row}>
          <Chip
            label="M-Pesa"
            active={walletProvider === "mpesa"}
            onPress={() => setWalletProvider("mpesa")}
          />
          <Chip
            label="Airtel Money"
            active={walletProvider === "airtel_money"}
            onPress={() => setWalletProvider("airtel_money")}
          />
        </View>
        <Pressable style={[styles.button, busy && styles.disabled]} onPress={saveProfile} disabled={busy}>
          {busy ? <ActivityIndicator color={colors.navy} /> : <Text style={styles.buttonText}>Save wallet</Text>}
        </Pressable>

        <Text style={styles.section}>Change password</Text>
        <Field
          label="Current password"
          value={currentPassword}
          onChangeText={setCurrentPassword}
          secureTextEntry
        />
        <Field
          label="New password (12+ strong)"
          value={newPassword}
          onChangeText={setNewPassword}
          secureTextEntry
        />
        <Pressable style={[styles.secondary, busy && styles.disabled]} onPress={changePassword} disabled={busy}>
          <Text style={styles.secondaryText}>Update password</Text>
        </Pressable>

        <Text style={styles.section}>App</Text>
        <Pressable style={styles.secondary} onPress={onOpenNotifications}>
          <Text style={styles.secondaryText}>
            {t("notifications")}
            {account?.unread_notifications
              ? ` · ${account.unread_notifications} unread`
              : ""}
          </Text>
        </Pressable>
        <Pressable style={styles.secondary} onPress={onOpenSettings}>
          <Text style={styles.secondaryText}>API connection</Text>
        </Pressable>
        <Pressable style={[styles.danger, busy && styles.disabled]} onPress={signOut} disabled={busy}>
          <Text style={styles.dangerText}>Sign out</Text>
        </Pressable>

        {message ? <Text style={styles.ok}>{message}</Text> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </ScrollView>
    </ScreenShell>
  );
}

function Field({
  label,
  value,
  onChangeText,
  secureTextEntry,
  keyboardType,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  secureTextEntry?: boolean;
  keyboardType?: "phone-pad";
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChangeText}
        secureTextEntry={secureTextEntry}
        keyboardType={keyboardType}
        autoCapitalize="none"
      />
    </View>
  );
}

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable style={[styles.chip, active && styles.chipOn]} onPress={onPress}>
      <Text style={[styles.chipText, active && styles.chipTextOn]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  form: { paddingBottom: 40 },
  card: {
    backgroundColor: colors.navy,
    borderRadius: 5,
    padding: 20,
    marginBottom: 20,
    overflow: "hidden",
    borderLeftWidth: 4,
    borderLeftColor: colors.gold,
  },
  cardTitle: { color: "#fff", fontSize: 22, fontWeight: "800", letterSpacing: -0.3 },
  cardMeta: { color: "rgba(255,255,255,0.72)", marginTop: 6, lineHeight: 20 },
  cardParty: { color: "#fff", marginTop: 10, fontWeight: "700", fontSize: 13 },
  badge: { color: colors.goldBright, marginTop: 12, fontWeight: "700", fontSize: 12 },
  section: {
    fontSize: 11,
    fontWeight: "800",
    color: colors.muted,
    marginBottom: 10,
    marginTop: 12,
    letterSpacing: 0.7,
    textTransform: "uppercase",
  },
  field: { marginBottom: 12 },
  label: { fontSize: 13, color: colors.muted, marginBottom: 6 },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 5,
    padding: 14,
    fontSize: 16,
    color: colors.foreground,
  },
  row: { flexDirection: "row", gap: 8, marginBottom: 12 },
  chip: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 5,
    padding: 12,
    alignItems: "center",
    backgroundColor: colors.surface,
  },
  chipOn: { backgroundColor: colors.navy, borderColor: colors.navy },
  chipText: { color: colors.muted, fontWeight: "700" },
  chipTextOn: { color: colors.goldBright },
  button: {
    backgroundColor: colors.accent,
    borderRadius: 5,
    padding: 14,
    alignItems: "center",
    marginBottom: 8,
    minHeight: 50,
    justifyContent: "center",
  },
  buttonText: { color: colors.navy, fontWeight: "800" },
  secondary: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 5,
    padding: 14,
    alignItems: "center",
    backgroundColor: colors.surface,
    marginBottom: 10,
  },
  secondaryText: { color: colors.foreground, fontWeight: "700" },
  danger: {
    borderWidth: 1,
    borderColor: "#F0C2C2",
    borderRadius: 5,
    padding: 14,
    alignItems: "center",
    backgroundColor: colors.dangerSoft,
    marginTop: 8,
    marginBottom: 10,
  },
  dangerText: { color: colors.danger, fontWeight: "800" },
  disabled: { opacity: 0.6 },
  ok: { color: colors.success, marginTop: 8 },
  error: { color: colors.danger, marginTop: 8 },
});
