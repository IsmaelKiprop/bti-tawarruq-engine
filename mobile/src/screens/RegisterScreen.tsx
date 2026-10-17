import { useState } from "react";
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
import { colors } from "../theme";

type Props = {
  onRegistered: (email: string, devCode?: string | null) => void;
  onGoLogin: () => void;
};

export function RegisterScreen({ onRegistered, onGoLogin }: Props) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setBusy(true);
    try {
      const result = await api.registerMobile({
        email: email.trim().toLowerCase(),
        password,
        full_name: fullName.trim(),
      });
      onRegistered(result.email, result.dev_code);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenShell
      title="Create account"
      subtitle="High-security email signup. Strong password required. We will verify your email, then MFA on every login."
    >
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.form}>
        <Field label="Full name" value={fullName} onChangeText={setFullName} autoCapitalize="words" />
        <Field
          label="Email"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
        />
        <Field
          label="Password (12+ chars, upper, lower, number, symbol)"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />
        <Field label="Confirm password" value={confirm} onChangeText={setConfirm} secureTextEntry />

        <Pressable style={[styles.button, busy && styles.disabled]} onPress={submit} disabled={busy}>
          {busy ? <ActivityIndicator color={colors.navy} /> : <Text style={styles.buttonText}>Create account</Text>}
        </Pressable>
        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable onPress={onGoLogin} style={styles.linkWrap}>
          <Text style={styles.link}>Already have an account? Sign in</Text>
        </Pressable>
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
  autoCapitalize,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  secureTextEntry?: boolean;
  keyboardType?: "email-address" | "default";
  autoCapitalize?: "none" | "words";
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
        autoCapitalize={autoCapitalize || "none"}
        autoCorrect={false}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  form: { paddingBottom: 40 },
  field: { marginBottom: 14 },
  label: { fontSize: 13, color: colors.muted, marginBottom: 6, fontWeight: "600" },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 5,
    padding: 12,
    fontSize: 16,
    color: colors.foreground,
  },
  button: {
    backgroundColor: colors.accent,
    borderRadius: 5,
    padding: 16,
    alignItems: "center",
    marginTop: 8,
  },
  disabled: { opacity: 0.7 },
  buttonText: { color: colors.navy, fontWeight: "800", fontSize: 16 },
  error: { color: colors.danger, marginTop: 12 },
  linkWrap: { marginTop: 20, alignItems: "center" },
  link: { color: colors.primary, fontWeight: "700" },
});
