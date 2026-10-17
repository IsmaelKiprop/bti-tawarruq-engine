import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { api } from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import { StatusTag } from "../components/ui";
import { t } from "../i18n";
import {
  clearActiveLoan,
  getActiveLoan,
  updateLoanStage,
  type ActiveLoan,
} from "../storage/session";
import { colors, radius, space } from "../theme";

type Facility = Awaited<ReturnType<typeof api.listFacilities>>[number];

type Props = {
  onRepay: (applicationId: string) => void;
  onStatus: (applicationId: string) => void;
  onDocuments: (applicationId: string) => void;
  onContinue: (loan: ActiveLoan) => void;
  onBorrow: () => void;
};

function formatKes(n: string) {
  const num = Number(n);
  if (Number.isNaN(num)) return n;
  return num.toLocaleString("en-KE");
}

export function LoanHubScreen({
  onRepay,
  onStatus,
  onDocuments,
  onContinue,
  onBorrow,
}: Props) {
  const [loan, setLoan] = useState<ActiveLoan | null>(null);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      let active = await getActiveLoan();
      if (active) {
        try {
          const flow = await api.getStatus(active.applicationId);
          const paidInFull =
            flow.wallet_credited &&
            flow.installments_total > 0 &&
            flow.installments_paid >= flow.installments_total;
          if (paidInFull) {
            await updateLoanStage("complete");
            await clearActiveLoan();
            active = null;
          }
        } catch {
          // keep local mid-journey loan
        }
      }
      setLoan(active);

      try {
        setFacilities(await api.listFacilities());
      } catch {
        setFacilities([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh]),
  );

  const midJourney = Boolean(loan && loan.stage !== "active" && loan.stage !== "complete");

  return (
    <ScreenShell title={t("myLoan")} subtitle="Facilities from your lending institution.">
      <ScrollView
        refreshControl={<RefreshControl refreshing={busy} onRefresh={refresh} />}
        contentContainerStyle={styles.content}
      >
        {midJourney && loan ? (
          <View style={styles.continueCard}>
            <Text style={styles.continueTitle}>Continue application</Text>
            <Text style={styles.continueMeta}>
              KES {formatKes(loan.amount)} · {loan.stage}
            </Text>
            <Pressable style={styles.button} onPress={() => onContinue(loan)}>
              <Text style={styles.buttonText}>Resume</Text>
            </Pressable>
          </View>
        ) : null}

        <Pressable style={styles.borrowBtn} onPress={onBorrow}>
          <Text style={styles.buttonText}>{t("getFinancing")}</Text>
        </Pressable>

        {facilities.length === 0 && !busy ? (
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>{t("noFacilities")}</Text>
            <Text style={styles.emptyBody}>
              When you borrow, active and settled Murabaha facilities appear here.
            </Text>
          </View>
        ) : (
          facilities.map((f) => {
            const tone = f.settled ? "success" : f.installments_total > 0 ? "warning" : "neutral";
            const label = f.settled
              ? t("settled")
              : f.installments_total > 0
                ? t("active")
                : t("open");
            return (
              <View key={f.application_id} style={styles.card}>
                <View style={styles.cardTop}>
                  <Text style={styles.amount}>KES {formatKes(f.amount)}</Text>
                  <StatusTag label={label} tone={tone} />
                </View>
                <Text style={styles.meta}>
                  {f.created_at ? f.created_at.slice(0, 10) : "Facility"} · {f.label}
                </Text>
                {f.institution_name ? (
                  <Text style={styles.party}>Institution: {f.institution_name}</Text>
                ) : null}
                {f.agent_dealer_name ? (
                  <Text style={styles.party}>Agent float: {f.agent_dealer_name}</Text>
                ) : null}
                {!f.settled && f.outstanding && Number(f.outstanding) > 0 ? (
                  <Text style={styles.outstanding}>
                    Outstanding KES {formatKes(f.outstanding)}
                  </Text>
                ) : null}
                <View style={styles.actions}>
                  <Pressable style={styles.secondary} onPress={() => onStatus(f.application_id)}>
                    <Text style={styles.secondaryText}>{t("viewDetails")}</Text>
                  </Pressable>
                  <Pressable style={styles.secondary} onPress={() => onDocuments(f.application_id)}>
                    <Text style={styles.secondaryText}>{t("documents")}</Text>
                  </Pressable>
                  {!f.settled && f.installments_total > 0 ? (
                    <Pressable style={styles.button} onPress={() => onRepay(f.application_id)}>
                      <Text style={styles.buttonText}>{t("repayNow")}</Text>
                    </Pressable>
                  ) : null}
                </View>
              </View>
            );
          })
        )}

        {busy && facilities.length === 0 ? (
          <ActivityIndicator color={colors.primary} style={{ marginTop: 16 }} />
        ) : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </ScrollView>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: 40 },
  continueCard: {
    backgroundColor: colors.navy,
    borderRadius: radius.default,
    padding: space.xl,
    marginBottom: space.md,
    borderLeftWidth: 4,
    borderLeftColor: colors.gold,
  },
  continueTitle: { color: "#fff", fontWeight: "800", fontSize: 17, letterSpacing: -0.2 },
  continueMeta: { color: colors.goldBright, marginTop: 6, marginBottom: 14 },
  borrowBtn: {
    backgroundColor: colors.accent,
    borderRadius: radius.default,
    padding: 15,
    alignItems: "center",
    marginBottom: space.xl,
    minHeight: 52,
    justifyContent: "center",
  },
  empty: {
    backgroundColor: colors.surface,
    borderRadius: radius.default,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 22,
  },
  emptyTitle: { fontSize: 18, fontWeight: "800", color: colors.foreground, letterSpacing: -0.2 },
  emptyBody: { color: colors.muted, marginTop: 8, lineHeight: 21 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.default,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 3,
    borderLeftColor: colors.gold,
    padding: space.lg,
    marginBottom: space.sm,
  },
  cardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: space.sm,
  },
  amount: { fontSize: 20, fontWeight: "800", color: colors.navy, flex: 1, letterSpacing: -0.3 },
  meta: { color: colors.muted, marginTop: 6, fontSize: 13 },
  party: { color: colors.navySoft, marginTop: 4, fontWeight: "600", fontSize: 12 },
  outstanding: { color: colors.warning, marginTop: 8, fontWeight: "700" },
  actions: { marginTop: 14, gap: 8 },
  button: {
    backgroundColor: colors.accent,
    borderRadius: radius.default,
    padding: 12,
    alignItems: "center",
  },
  buttonText: { color: colors.navy, fontWeight: "800" },
  secondary: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.default,
    padding: 12,
    alignItems: "center",
    backgroundColor: colors.background,
  },
  secondaryText: { color: colors.navy, fontWeight: "700" },
  error: { color: colors.danger, marginTop: 12 },
});
