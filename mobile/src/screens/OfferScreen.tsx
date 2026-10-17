import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { api, OfferSummary } from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import { updateLoanStage } from "../storage/session";
import { colors } from "../theme";

type Props = {
  applicationId: string;
  onAccepted: () => void;
};

function formatKes(value: string) {
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return n.toLocaleString("en-KE");
}

export function OfferScreen({ applicationId, onAccepted }: Props) {
  const [offer, setOffer] = useState<OfferSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        await api.createOffer(applicationId);
        const summary = await api.getOffer(applicationId);
        setOffer(summary);
        await updateLoanStage("offer");
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, [applicationId]);

  const accept = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.acceptOffer(applicationId);
      await updateLoanStage("contract");
      onAccepted();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenShell
      title="Your financing offer"
      subtitle="Step 2 of 5. Murabaha cost-plus terms. Profit, not interest."
      step={2}
      totalSteps={5}
    >
      {loading ? <ActivityIndicator size="large" color={colors.primary} /> : null}
      {offer ? (
        <View style={styles.card}>
          <View style={styles.hero}>
            <Text style={styles.heroLabel}>You receive</Text>
            <Text style={styles.heroValue}>KES {formatKes(offer.cost_price)}</Text>
          </View>
          <Row label="Profit margin (Halal)" value={`KES ${formatKes(offer.profit_amount)}`} />
          <Row label="Total you repay" value={`KES ${formatKes(offer.total_payable)}`} highlight />
          <Row label="Installments" value={`${offer.installment_count} months`} />
          <Text style={styles.legal}>
            Accept to continue. Next you will sign, then we disburse automatically to your wallet.
          </Text>
          <Pressable style={styles.button} onPress={accept} disabled={busy}>
            {busy ? (
              <ActivityIndicator color={colors.navy} />
            ) : (
              <Text style={styles.buttonText}>Accept & continue</Text>
            )}
          </Pressable>
        </View>
      ) : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </ScreenShell>
  );
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, highlight && styles.highlight]}>{value}</Text>
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
  },
  hero: {
    backgroundColor: colors.navy,
    borderRadius: 5,
    padding: 16,
    marginBottom: 8,
  },
  heroLabel: { color: "rgba(255,255,255,0.7)", fontSize: 13, fontWeight: "600" },
  heroValue: { color: "#FFFFFF", fontSize: 28, fontWeight: "800", marginTop: 4 },
  row: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  rowLabel: { color: colors.muted, fontSize: 14 },
  rowValue: { color: colors.foreground, fontSize: 18, fontWeight: "700", marginTop: 4 },
  highlight: { color: colors.navy },
  legal: { color: colors.muted, fontSize: 13, lineHeight: 20, marginVertical: 16 },
  button: { backgroundColor: colors.accent, borderRadius: 5, padding: 16, alignItems: "center" },
  buttonText: { color: colors.navy, fontWeight: "800" },
  error: { color: colors.danger, marginTop: 12 },
});
