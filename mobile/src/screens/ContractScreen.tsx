import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { api } from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import { getActiveLoan, getProfile, updateLoanStage } from "../storage/session";
import { colors } from "../theme";

type Props = {
  applicationId: string;
  onSigned: () => void;
};

export function ContractScreen({ applicationId, onSigned }: Props) {
  const [signature, setSignature] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const loan = await getActiveLoan();
      const profile = await getProfile();
      const prefill = loan?.name || profile?.fullName || "";
      if (prefill) setSignature(prefill);
    })();
  }, []);

  const sign = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.createMurabaha(applicationId);
      await api.signMurabaha(applicationId, signature.trim() || `SIG-${Date.now()}`);
      await updateLoanStage("settlement");
      onSigned();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenShell
      title="Confirm your agreement"
      subtitle="Step 3 of 5. Sign once. Disbursement starts automatically next."
      step={3}
      totalSteps={5}
    >
      <View style={styles.card}>
        <Text style={styles.body}>
          You are buying a commodity at a disclosed cost-plus price. After signing, we transfer title, appoint Wakala,
          and send cash to your wallet in one continuous step.
        </Text>
        <Text style={styles.label}>Full name (signature)</Text>
        <TextInput
          style={styles.input}
          value={signature}
          onChangeText={setSignature}
          placeholder="Jane Wanjiku"
          autoCapitalize="words"
          placeholderTextColor={colors.muted}
        />
        <Pressable style={styles.button} onPress={sign} disabled={busy || !signature.trim()}>
          {busy ? (
            <ActivityIndicator color={colors.navy} />
          ) : (
            <Text style={styles.buttonText}>Sign & get funded</Text>
          )}
        </Pressable>
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
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
  body: { color: colors.muted, lineHeight: 22, marginBottom: 16 },
  label: { fontSize: 13, color: colors.muted, marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 5,
    padding: 12,
    marginBottom: 16,
    fontSize: 16,
    color: colors.foreground,
    backgroundColor: colors.surface,
  },
  button: { backgroundColor: colors.accent, borderRadius: 5, padding: 16, alignItems: "center" },
  buttonText: { color: colors.navy, fontWeight: "800" },
  error: { color: colors.danger, marginTop: 12 },
});
