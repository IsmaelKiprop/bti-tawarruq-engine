import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { ScreenShell } from "../components/ScreenShell";
import { colors } from "../theme";

type Props = {
  amount: string;
  installmentCount?: number;
  onGoHome: () => void;
  onRepay: () => void;
};

function formatKes(value: string) {
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return n.toLocaleString("en-KE");
}

export function SuccessScreen({ amount, installmentCount, onGoHome, onRepay }: Props) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setReady(true), 400);
    return () => clearTimeout(t);
  }, []);

  return (
    <ScreenShell title="You're funded" subtitle="Financing is live on your wallet." step={5} totalSteps={5}>
      <View style={styles.card}>
        {!ready ? (
          <ActivityIndicator color={colors.primary} style={{ marginVertical: 24 }} />
        ) : (
          <>
            <Text style={styles.label}>Disbursed</Text>
            <Text style={styles.amount}>KES {formatKes(amount)}</Text>
            <Text style={styles.meta}>
              {installmentCount
                ? `${installmentCount} repayment installments scheduled`
                : "Repayment schedule is ready"}
            </Text>
            <Text style={styles.note}>
              Your Murabaha journey is complete. Pay on time to keep your limit healthy for the next round.
            </Text>
          </>
        )}
      </View>

      <Pressable style={styles.primary} onPress={onRepay}>
        <Text style={styles.primaryText}>View repayments</Text>
      </Pressable>
      <Pressable style={styles.secondary} onPress={onGoHome}>
        <Text style={styles.secondaryText}>Back to home</Text>
      </Pressable>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.navy,
    borderRadius: 5,
    padding: 24,
    marginBottom: 20,
  },
  label: { color: "rgba(255,255,255,0.7)", fontSize: 13, fontWeight: "600" },
  amount: { color: "#FFFFFF", fontSize: 34, fontWeight: "800", marginTop: 8 },
  meta: { color: colors.goldBright, fontSize: 13, marginTop: 10, fontWeight: "600" },
  note: { color: "rgba(255,255,255,0.75)", fontSize: 13, lineHeight: 20, marginTop: 16 },
  primary: {
    backgroundColor: colors.accent,
    borderRadius: 5,
    padding: 16,
    alignItems: "center",
    marginBottom: 10,
  },
  primaryText: { color: colors.navy, fontWeight: "800", fontSize: 16 },
  secondary: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 5,
    padding: 16,
    alignItems: "center",
    backgroundColor: colors.surface,
  },
  secondaryText: { color: colors.foreground, fontWeight: "700", fontSize: 15 },
});
