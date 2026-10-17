import { useCallback, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { api } from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import { t } from "../i18n";
import { colors, radius, space } from "../theme";

type Props = {
  onOpenFacility?: (applicationId: string) => void;
};

export function NotificationsScreen({ onOpenFacility }: Props) {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof api.listNotifications>>>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setRows(await api.listNotifications());
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

  const markAll = async () => {
    setBusy(true);
    try {
      await api.markNotificationsRead();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <ScreenShell title={t("notifications")} subtitle="Approvals, offers, repayments, and disbursements.">
      <ScrollView
        refreshControl={<RefreshControl refreshing={busy} onRefresh={refresh} />}
        contentContainerStyle={styles.content}
      >
        <Pressable style={styles.mark} onPress={markAll} disabled={busy}>
          <Text style={styles.markText}>{t("markAllRead")}</Text>
        </Pressable>

        {rows.length === 0 && !busy ? (
          <Text style={styles.empty}>{t("emptyInbox")}</Text>
        ) : (
          rows.map((n) => (
            <Pressable
              key={n.id}
              style={[styles.card, !n.read && styles.cardUnread]}
              onPress={async () => {
                if (!n.read) {
                  try {
                    await api.markNotificationsRead(n.id);
                  } catch {
                    // ignore
                  }
                }
                if (n.application_id && onOpenFacility) onOpenFacility(n.application_id);
                else refresh();
              }}
            >
              <Text style={styles.title}>{n.title}</Text>
              <Text style={styles.body}>{n.body}</Text>
              <Text style={styles.meta}>
                {n.created_at ? n.created_at.slice(0, 16).replace("T", " ") : n.kind}
                {n.sms_queued ? " · SMS queued" : ""}
                {n.push_queued ? " · Push queued" : ""}
              </Text>
            </Pressable>
          ))
        )}
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </ScrollView>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: 40 },
  mark: { alignSelf: "flex-end", marginBottom: space.md },
  markText: { color: colors.navy, fontWeight: "700", fontSize: 13 },
  empty: { color: colors.muted, marginTop: 24 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.default,
    borderWidth: 1,
    borderColor: colors.border,
    padding: space.lg,
    marginBottom: space.sm,
  },
  cardUnread: { borderColor: colors.navy, backgroundColor: colors.goldMuted },
  title: { fontWeight: "800", color: colors.navy, fontSize: 15 },
  body: { color: colors.muted, marginTop: 6, lineHeight: 20 },
  meta: { color: colors.mutedSoft, marginTop: 8, fontSize: 11 },
  error: { color: colors.danger, marginTop: 12 },
});
