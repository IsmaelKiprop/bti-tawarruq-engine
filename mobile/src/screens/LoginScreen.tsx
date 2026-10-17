import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

import { api } from "../api/client";
import { BrandMark } from "../components/BrandMark";
import { ScreenShell } from "../components/ScreenShell";
import { AppButton, AppField, SurfaceCard } from "../components/ui";
import { colors, space, type as typography } from "../theme";

type Props = {
  onChallenge: (mfaToken: string, email: string, devCode?: string | null) => void;
  onGoRegister: () => void;
  onForgotPassword: () => void;
};

export function LoginScreen({ onChallenge, onGoRegister, onForgotPassword }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.loginMobile({
        email: email.trim().toLowerCase(),
        password,
      });
      onChallenge(result.mfa_token, result.email, result.dev_code);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenShell
      title="Welcome back"
      subtitle="Sign in to Buruuj Lend — powered by Buruuj Fintech."
      showBrand={false}
    >
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={styles.form}
        showsVerticalScrollIndicator={false}
      >
        <BrandMark size="lockup" showWordmark style={{ marginBottom: space.xl }} />

        <SurfaceCard style={styles.card}>
          <AppField
            label="Email"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            placeholder="you@email.com"
          />
          <AppField
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoCapitalize="none"
            placeholder="••••••••••••"
            containerStyle={{ marginBottom: 0 }}
          />
        </SurfaceCard>

        <AppButton label="Continue" onPress={submit} busy={busy} style={{ marginTop: space.xl }} />
        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable onPress={onForgotPassword} style={styles.linkWrap}>
          <Text style={styles.link}>Forgot password?</Text>
        </Pressable>
        <Pressable onPress={onGoRegister} style={styles.linkWrap}>
          <Text style={styles.linkMuted}>
            New here? <Text style={styles.link}>Create an account</Text>
          </Text>
        </Pressable>
      </ScrollView>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  form: { paddingBottom: 48 },
  card: { paddingBottom: space.md },
  linkWrap: { marginTop: space.lg, alignItems: "center" },
  link: { color: colors.navy, fontWeight: "800", fontSize: 14 },
  linkMuted: { color: colors.muted, fontSize: 14 },
  error: { ...typography.label, color: colors.danger, marginTop: space.md },
});
