import { useCallback, useEffect, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";

import { api, RepaymentInstallment } from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import { clearActiveLoan, updateLoanStage } from "../storage/session";
import { colors } from "../theme";

function formatKes(value: string) {
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return n.toLocaleString("en-KE");
}

export function RepaymentsScreen({
  applicationId,
  onBorrowAgain,
}: {
  applicationId: string;
  onBorrowAgain?: () => void;
}) {
  const [installments, setInstallments] = useState<RepaymentInstallment[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stkHint, setStkHint] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const rows = await api.getRepayments(applicationId);
      setInstallments(rows);
      if (rows.length > 0 && rows.every((i) => i.status === "paid")) {
        await updateLoanStage("complete");
        await clearActiveLoan();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applicationId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const pay = async (id: string) => {
    setBusy(true);
    setError(null);
    setStkHint(null);
    try {
      const result = await api.collectRepayment(id);
      if (result.status === "awaiting_payment") {
        setStkHint("STK sent — confirm on your phone. Waiting for M-Pesa…");
        for (let i = 0; i < 12; i++) {
          await new Promise((r) => setTimeout(r, 2500));
          const rows = await api.getRepayments(applicationId);
          setInstallments(rows);
          const row = rows.find((x) => x.id === id);
          if (row?.status === "paid") {
            setStkHint("Payment confirmed.");
            break;
          }
          if (row?.status !== "awaiting_payment") break;
        }
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const nextDue = installments.find((i) => i.status !== "paid");
  const paidCount = installments.filter((i) => i.status === "paid").length;
  const fullyPaid = installments.length > 0 && paidCount === installments.length;

  return (
    <ScreenShell
      title="Repay"
      subtitle={
        installments.length
          ? fullyPaid
            ? "Paid in full. Facility settled"
            : `${paidCount} of ${installments.length} installments paid`
          : "Deferred Murabaha schedule"
      }
    >
      <ScrollView refreshControl={<RefreshControl refreshing={busy} onRefresh={refresh} />}>
        {fullyPaid ? (
          <View style={styles.nextCard}>
            <Text style={styles.nextLabel}>All installments paid</Text>
            <Text style={styles.nextAmount}>JazakAllah khair</Text>
            <Text style={styles.nextMeta}>Your Murabaha facility is settled. You can apply again.</Text>
            {onBorrowAgain ? (
              <Pressable style={styles.payPrimary} onPress={onBorrowAgain}>
                <Text style={styles.payPrimaryText}>Apply again</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}

        {nextDue ? (
          <View style={styles.nextCard}>
            <Text style={styles.nextLabel}>Next payment</Text>
            <Text style={styles.nextAmount}>KES {formatKes(nextDue.amount)}</Text>
            <Text style={styles.nextMeta}>
              Installment #{nextDue.installment_number}
              {nextDue.due_date ? ` · due ${nextDue.due_date.slice(0, 10)}` : ""}
            </Text>
            <Pressable style={styles.payPrimary} onPress={() => pay(nextDue.id)} disabled={busy}>
              <Text style={styles.payPrimaryText}>Pay with STK</Text>
            </Pressable>
            {stkHint ? <Text style={styles.nextMeta}>{stkHint}</Text> : null}
            {nextDue.status === "awaiting_payment" ? (
              <Text style={styles.nextMeta}>Awaiting M-Pesa confirmation…</Text>
            ) : null}
          </View>
        ) : null}

        {installments.map((inst) => (
          <View key={inst.id} style={styles.card}>
            <View style={styles.cardRow}>
              <Text style={styles.title}>
                #{inst.installment_number} · KES {formatKes(inst.amount)}
              </Text>
              <Text style={[styles.badge, inst.status === "paid" ? styles.badgePaid : styles.badgeDue]}>
                {inst.status === "paid" ? "Paid" : "Due"}
              </Text>
            </View>
            {inst.due_date ? <Text style={styles.meta}>{inst.due_date.slice(0, 10)}</Text> : null}
            {inst.status !== "paid" ? (
              <Pressable style={styles.pay} onPress={() => pay(inst.id)} disabled={busy}>
                <Text style={styles.payText}>Pay now</Text>
              </Pressable>
            ) : null}
          </View>
        ))}
        {!installments.length && !busy ? (
          <Text style={styles.empty}>No schedule yet. Disburse your financing first.</Text>
        ) : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </ScrollView>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  nextCard: {
    backgroundColor: colors.navy,
    borderRadius: 5,
    padding: 20,
    marginBottom: 14,
    borderLeftWidth: 4,
    borderLeftColor: colors.gold,
  },
  nextLabel: { color: "rgba(255,255,255,0.7)", fontSize: 13, fontWeight: "600" },
  nextAmount: { color: "#fff", fontSize: 28, fontWeight: "800", marginTop: 6, letterSpacing: -0.4 },
  nextMeta: { color: colors.goldBright, marginTop: 8, fontWeight: "600" },
  payPrimary: {
    marginTop: 14,
    backgroundColor: colors.accent,
    borderRadius: 5,
    padding: 14,
    alignItems: "center",
  },
  payPrimaryText: { color: colors.navy, fontWeight: "800" },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    marginBottom: 10,
  },
  cardRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  title: { fontWeight: "700", color: colors.foreground, flex: 1 },
  badge: { fontSize: 12, fontWeight: "800", paddingHorizontal: 8, paddingVertical: 4, borderRadius: 999 },
  badgePaid: { backgroundColor: colors.successSoft, color: colors.success },
  badgeDue: { backgroundColor: colors.warningSoft, color: colors.warning },
  meta: { color: colors.muted, marginTop: 6, fontSize: 13 },
  pay: {
    marginTop: 10,
    borderWidth: 1,
    borderColor: colors.navy,
    borderRadius: 5,
    padding: 10,
    alignItems: "center",
  },
  payText: { color: colors.navy, fontWeight: "700" },
  empty: { color: colors.muted, marginTop: 20 },
  error: { color: colors.danger, marginTop: 12 },
});
