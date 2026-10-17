import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { api } from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import { colors } from "../theme";

type Props = {
  applicationId: string;
};

export function StatusScreen({ applicationId }: Props) {
  const [status, setStatus] = useState<Awaited<ReturnType<typeof api.getStatus>> | null>(null);
  const [auditCount, setAuditCount] = useState(0);
  const [institutionName, setInstitutionName] = useState<string | null>(null);
  const [agentName, setAgentName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [flowStatus, audit, facilities] = await Promise.all([
        api.getStatus(applicationId),
        api.getShariahAudit(applicationId),
        api.listFacilities().catch(() => []),
      ]);
      setStatus(flowStatus);
      setAuditCount(audit.length);
      const match = facilities.find((f) => f.application_id === applicationId);
      setInstitutionName(match?.institution_name ?? null);
      setAgentName(match?.agent_dealer_name ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applicationId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const headline = !status
    ? "Loading…"
    : status.wallet_credited
      ? "Active financing"
      : status.murabaha_signed
        ? "Awaiting disbursement"
        : status.offer_accepted
          ? "Offer accepted"
          : "Application in progress";

  return (
    <ScreenShell title="My loan" subtitle={headline} step={5} totalSteps={5}>
      <ScrollView
        refreshControl={<RefreshControl refreshing={busy} onRefresh={refresh} />}
        contentContainerStyle={styles.content}
      >
        <Pressable style={styles.button} onPress={refresh} disabled={busy}>
          {busy ? (
            <ActivityIndicator color={colors.navy} />
          ) : (
            <Text style={styles.buttonText}>Refresh</Text>
          )}
        </Pressable>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        {status ? (
          <View style={styles.card}>
            {institutionName ? <Row label="Institution" value={institutionName} /> : null}
            {agentName ? <Row label="Agent float" value={agentName} /> : null}
            <Row label="Eligibility" value={status.eligibility_passed ? "Passed" : "Pending"} />
            <Row label="Offer" value={status.offer_accepted ? "Accepted" : "Pending"} />
            <Row label="Contract signed" value={status.murabaha_signed ? "Yes" : "No"} />
            <Row label="Wakala" value={status.wakala_appointed ? "Appointed" : "Pending"} />
            <Row label="Wallet credited" value={status.wallet_credited ? "Yes" : "Not yet"} />
            <Row
              label="Repayments"
              value={`${status.installments_paid} of ${status.installments_total} paid`}
            />
            <Row label="Shariah audit trail" value={`${auditCount} entries`} />
            <Text style={styles.ref}>Ref {applicationId.slice(0, 8)}…</Text>
          </View>
        ) : (
          <Text style={styles.hint}>Pull to refresh to load your loan status.</Text>
        )}
      </ScrollView>
    </ScreenShell>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: 40 },
  button: {
    backgroundColor: colors.accent,
    borderRadius: 5,
    padding: 14,
    alignItems: "center",
    marginBottom: 16,
  },
  buttonText: { color: colors.navy, fontWeight: "800" },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 5,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  rowLabel: { color: colors.muted, fontSize: 14 },
  rowValue: {
    color: colors.foreground,
    fontWeight: "600",
    fontSize: 14,
    maxWidth: "55%",
    textAlign: "right",
  },
  ref: { marginTop: 12, color: colors.muted, fontSize: 12 },
  hint: { color: colors.muted, marginTop: 8 },
  error: { color: colors.danger, marginBottom: 12 },
});
