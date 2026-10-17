import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { api } from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import { colors } from "../theme";

type Mode = "verify_email" | "mfa";

type Props = {
  mode: Mode;
  email: string;
  mfaToken?: string;
  initialDevCode?: string | null;
  onVerified: () => void;
  onMfaSuccess: () => void;
};

export function VerifyCodeScreen({
  mode,
  email,
  mfaToken,
  initialDevCode,
  onVerified,
  onMfaSuccess,
}: Props) {
  const [code, setCode] = useState(initialDevCode || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(
    initialDevCode ? `Dev code (SMTP off): ${initialDevCode}` : null,
  );

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (mode === "verify_email") {
        await api.verifyEmail({ email, code: code.trim() });
        onVerified();
      } else {
        if (!mfaToken) throw new Error("Missing MFA challenge");
        await api.verifyMfa({ mfa_token: mfaToken, code: code.trim() });
        onMfaSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    if (mode !== "verify_email") return;
    setBusy(true);
    setError(null);
    try {
      const delivery = await api.resendVerification(email);
      if (delivery.dev_code) {
        setCode(delivery.dev_code);
        setHint(`Dev code (SMTP off): ${delivery.dev_code}`);
      } else {
        setHint("A new code was sent to your email.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenShell
      title={mode === "verify_email" ? "Verify email" : "Security code"}
      subtitle={
        mode === "verify_email"
          ? `Enter the 6-digit code sent to ${email}`
          : `Enter the MFA code sent to ${email}`
      }
    >
      <View style={styles.card}>
        <Text style={styles.label}>6-digit code</Text>
        <TextInput
          style={styles.input}
          value={code}
          onChangeText={setCode}
          keyboardType="number-pad"
          maxLength={8}
          autoFocus
        />
        <Pressable
          style={[styles.button, (busy || code.trim().length < 6) && styles.disabled]}
          onPress={submit}
          disabled={busy || code.trim().length < 6}
        >
          {busy ? (
            <ActivityIndicator color={colors.navy} />
          ) : (
            <Text style={styles.buttonText}>{mode === "verify_email" ? "Verify email" : "Sign in"}</Text>
          )}
        </Pressable>
        {mode === "verify_email" ? (
          <Pressable onPress={resend} disabled={busy} style={styles.resend}>
            <Text style={styles.resendText}>Resend code</Text>
          </Pressable>
        ) : null}
        {hint ? <Text style={styles.hint}>{hint}</Text> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </View>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 5,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  label: { fontSize: 13, color: colors.muted, marginBottom: 6, fontWeight: "600" },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 5,
    padding: 14,
    fontSize: 22,
    letterSpacing: 8,
    textAlign: "center",
    marginBottom: 16,
    color: colors.foreground,
    fontWeight: "700",
  },
  button: {
    backgroundColor: colors.accent,
    borderRadius: 5,
    padding: 16,
    alignItems: "center",
  },
  disabled: { opacity: 0.55 },
  buttonText: { color: colors.navy, fontWeight: "800" },
  resend: { marginTop: 16, alignItems: "center" },
  resendText: { color: colors.primary, fontWeight: "700" },
  hint: { marginTop: 14, color: colors.muted, fontSize: 13, lineHeight: 18 },
  error: { color: colors.danger, marginTop: 12 },
});
