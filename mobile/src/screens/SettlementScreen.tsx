import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import { updateLoanStage } from "../storage/session";
import { colors } from "../theme";

type Props = {
  applicationId: string;
  transactionId: string;
  onComplete: (installmentCount: number) => void;
};

export function SettlementScreen({ applicationId, transactionId, onComplete }: Props) {
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState("Starting disbursement…");
  const [step, setStep] = useState<"idle" | "transferred" | "wakala" | "done">("idle");
  const started = useRef(false);

  const runAll = async () => {
    setBusy(true);
    setError(null);
    try {
      setProgress("Transferring ownership to you…");
      await api.transfer(transactionId);
      setStep("transferred");

      setProgress("Appointing Wakala agent…");
      await api.appointWakala(
        applicationId,
        `WAKALA-${Date.now()}`,
        "I appoint Buruuj as my agent to sell the commodity to an independent broker so cash can reach my wallet.",
      );
      setStep("wakala");

      setProgress("Sending cash to your wallet…");
      const result = await api.completeSettlement(applicationId);
      setStep("done");
      await updateLoanStage("active");
      setProgress("Wallet credited. Finishing up…");
      onComplete(result.installment_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    runAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ScreenShell
      title="Getting your money"
      subtitle="Step 4 of 5. Sit tight. We are completing your Halal disbursement."
      step={4}
      totalSteps={5}
    >
      <ScrollView>
        <View style={styles.card}>
          <Text style={styles.note}>
            No extra taps needed. Ownership, Wakala, independent broker sale, and wallet credit run in sequence.
          </Text>
          <Checklist done={step !== "idle"} label="Ownership transferred to you" />
          <Checklist done={step === "wakala" || step === "done"} label="Wakala agent appointed" />
          <Checklist done={step === "done"} label="Cash sent to your wallet" />
        </View>

        {busy ? (
          <View style={styles.busyRow}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.progress}>{progress}</Text>
          </View>
        ) : null}

        {error ? (
          <View>
            <Text style={styles.error}>{error}</Text>
            <Pressable
              style={styles.button}
              onPress={() => {
                started.current = false;
                started.current = true;
                runAll();
              }}
            >
              <Text style={styles.buttonText}>Retry disbursement</Text>
            </Pressable>
          </View>
        ) : null}
      </ScrollView>
    </ScreenShell>
  );
}

function Checklist({ done, label }: { done: boolean; label: string }) {
  return (
    <View style={styles.checkRow}>
      <View style={[styles.dot, done && styles.dotDone]}>
        <Text style={styles.dotText}>{done ? "✓" : ""}</Text>
      </View>
      <Text style={[styles.checkLabel, done && styles.checkDone]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 5,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 16,
  },
  note: { color: colors.muted, fontSize: 13, lineHeight: 20, marginBottom: 16 },
  checkRow: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 12 },
  dot: {
    width: 22,
    height: 22,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  dotDone: { backgroundColor: colors.navy, borderColor: colors.navy },
  dotText: { color: colors.goldBright, fontSize: 12, fontWeight: "800" },
  checkLabel: { color: colors.muted, fontSize: 14, flex: 1 },
  checkDone: { color: colors.foreground, fontWeight: "600" },
  busyRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  progress: { color: colors.muted, fontSize: 13, lineHeight: 20, flex: 1 },
  error: { color: colors.danger, marginBottom: 12 },
  button: {
    backgroundColor: colors.accent,
    borderRadius: 5,
    padding: 16,
    alignItems: "center",
  },
  buttonText: { color: colors.navy, fontWeight: "800", fontSize: 16 },
});
