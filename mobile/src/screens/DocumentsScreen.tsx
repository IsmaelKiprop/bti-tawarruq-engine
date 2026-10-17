import { useCallback, useMemo, useState } from "react";
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
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import { WebView } from "react-native-webview";

import { api } from "../api/client";
import { BrandMark } from "../components/BrandMark";
import { ScreenShell } from "../components/ScreenShell";
import { StatusTag } from "../components/ui";
import { t } from "../i18n";
import { colors, radius, space, type as typography } from "../theme";

type DocRow = {
  kind: string;
  label: string;
  group?: string;
  available: boolean;
  filename?: string;
};

type Props = {
  applicationId: string;
};

export function DocumentsScreen({ applicationId }: Props) {
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [statement, setStatement] = useState<Awaited<ReturnType<typeof api.getFacilityStatement>> | null>(
    null,
  );
  const [preview, setPreview] = useState<{ title: string; html: string; filename: string } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [d, s] = await Promise.all([
        api.listFacilityDocuments(applicationId),
        api.getFacilityStatement(applicationId),
      ]);
      setDocs(d.documents || []);
      setStatement(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applicationId]);

  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh]),
  );

  const grouped = useMemo(() => {
    const map = new Map<string, DocRow[]>();
    for (const d of docs) {
      const g = d.group || "Documents";
      const list = map.get(g) || [];
      list.push(d);
      map.set(g, list);
    }
    return [...map.entries()];
  }, [docs]);

  const openDoc = async (doc: DocRow) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const body = await api.getFacilityDocumentHtml(applicationId, doc.kind);
      setPreview({
        title: doc.label,
        html: body,
        filename: doc.filename || `${doc.kind}.html`,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const shareDoc = async (doc?: DocRow) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      let html = preview?.html;
      let filename = preview?.filename || "buruuj-document.html";
      if (doc) {
        html = await api.getFacilityDocumentHtml(applicationId, doc.kind);
        filename = doc.filename || `${doc.kind}.html`;
      }
      if (!html) throw new Error("Nothing to share");
      const dir = FileSystem.cacheDirectory || FileSystem.documentDirectory;
      if (!dir) throw new Error("File storage is not available on this device");
      const path = `${dir}${filename}`;
      await FileSystem.writeAsStringAsync(path, html, {
        encoding: FileSystem.EncodingType.UTF8,
      });
      const canShare = await Sharing.isAvailableAsync();
      if (!canShare) {
        setMessage(`Saved to ${path}`);
        return;
      }
      await Sharing.shareAsync(path, {
        mimeType: "text/html",
        dialogTitle: "Share Buruuj Fintech document",
        UTI: "public.html",
      });
      setMessage("Document ready to share or save.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  if (preview) {
    return (
      <View style={styles.previewRoot}>
        <View style={styles.previewBar}>
          <Pressable onPress={() => setPreview(null)} hitSlop={10} style={styles.backBtn}>
            <Text style={styles.backText}>← Back</Text>
          </Pressable>
          <View style={styles.previewTitleWrap}>
            <Text style={styles.previewEyebrow}>Buruuj Fintech</Text>
            <Text style={styles.previewTitle} numberOfLines={1}>
              {preview.title}
            </Text>
          </View>
          <Pressable style={styles.shareChip} onPress={() => shareDoc()} disabled={busy}>
            {busy ? (
              <ActivityIndicator color={colors.navy} size="small" />
            ) : (
              <Text style={styles.shareChipText}>Share</Text>
            )}
          </Pressable>
        </View>
        <WebView
          originWhitelist={["*"]}
          source={{ html: preview.html, baseUrl: "" }}
          style={styles.webview}
          startInLoadingState
          scalesPageToFit
          setSupportMultipleWindows={false}
          renderLoading={() => (
            <View style={styles.webLoading}>
              <ActivityIndicator color={colors.gold} />
            </View>
          )}
        />
        {error ? <Text style={styles.errorBanner}>{error}</Text> : null}
      </View>
    );
  }

  return (
    <ScreenShell
      title={t("documents")}
      subtitle="Official Buruuj Fintech branded copies — structured, downloadable, audit-ready."
      showBrand={false}
    >
      <ScrollView
        refreshControl={<RefreshControl refreshing={busy} onRefresh={refresh} />}
        contentContainerStyle={styles.content}
      >
        <BrandMark size="compact" showWordmark style={{ marginBottom: space.lg }} />

        {statement ? (
          <View style={styles.card}>
            <Text style={styles.heading}>Facility snapshot</Text>
            <View style={styles.snapRow}>
              <Text style={styles.snapLabel}>Amount</Text>
              <Text style={styles.snapValue}>KES {statement.amount}</Text>
            </View>
            <View style={styles.snapRow}>
              <Text style={styles.snapLabel}>Paid</Text>
              <Text style={styles.snapValue}>
                {statement.installments_paid} / {statement.installments_total}
              </Text>
            </View>
            <View style={styles.snapRow}>
              <Text style={styles.snapLabel}>Outstanding</Text>
              <Text style={styles.snapValue}>KES {statement.outstanding}</Text>
            </View>
            <View style={styles.snapRow}>
              <Text style={styles.snapLabel}>Institution</Text>
              <Text style={styles.snapValue}>{statement.institution_name || "—"}</Text>
            </View>
            <View style={styles.snapRow}>
              <Text style={styles.snapLabel}>Platform</Text>
              <Text style={styles.snapValue}>Buruuj Fintech</Text>
            </View>
          </View>
        ) : null}

        {grouped.map(([group, rows]) => (
          <View key={group} style={styles.group}>
            <Text style={styles.section}>{group}</Text>
            {rows.map((d) => (
              <View key={d.kind} style={[styles.docBtn, !d.available && styles.docDisabled]}>
                <View style={styles.docTop}>
                  <Text style={styles.docTitle}>{d.label}</Text>
                  <StatusTag
                    label={d.available ? "Ready" : "Pending"}
                    tone={d.available ? "success" : "warning"}
                  />
                </View>
                <Text style={styles.docMeta}>
                  {d.available
                    ? "Branded letterhead · aligned sections · share as HTML"
                    : "Issued after the related Shariah step completes"}
                </Text>
                {d.available ? (
                  <View style={styles.docActions}>
                    <Pressable style={styles.secondary} onPress={() => openDoc(d)} disabled={busy}>
                      <Text style={styles.secondaryText}>View</Text>
                    </Pressable>
                    <Pressable style={styles.primary} onPress={() => shareDoc(d)} disabled={busy}>
                      <Text style={styles.primaryText}>Download</Text>
                    </Pressable>
                  </View>
                ) : null}
              </View>
            ))}
          </View>
        ))}

        {busy && docs.length === 0 ? <ActivityIndicator color={colors.primary} /> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {message ? <Text style={styles.ok}>{message}</Text> : null}
      </ScrollView>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: 48 },
  card: {
    backgroundColor: colors.navy,
    borderRadius: radius.default,
    padding: space.xl,
    marginBottom: space.lg,
    borderLeftWidth: 4,
    borderLeftColor: colors.gold,
  },
  heading: { color: colors.goldBright, fontWeight: "800", marginBottom: 12, fontSize: 13 },
  snapRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 6,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "rgba(255,255,255,0.12)",
  },
  snapLabel: { color: "rgba(255,255,255,0.65)", fontSize: 13, fontWeight: "600", width: "40%" },
  snapValue: { color: "#fff", fontSize: 13, fontWeight: "700", flex: 1, textAlign: "right" },
  group: { marginBottom: space.md },
  section: {
    ...typography.overline,
    color: colors.muted,
    marginBottom: 10,
  },
  docBtn: {
    backgroundColor: colors.surface,
    borderRadius: radius.default,
    borderWidth: 1,
    borderColor: colors.border,
    padding: space.lg,
    marginBottom: space.sm,
  },
  docDisabled: { opacity: 0.55 },
  docTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: space.sm,
  },
  docTitle: { fontWeight: "800", color: colors.navy, flex: 1, fontSize: 15 },
  docMeta: { color: colors.muted, marginTop: 6, fontSize: 12, lineHeight: 17 },
  docActions: { flexDirection: "row", gap: 8, marginTop: 12 },
  primary: {
    flex: 1,
    backgroundColor: colors.accent,
    borderRadius: radius.default,
    paddingVertical: 12,
    alignItems: "center",
  },
  primaryText: { color: colors.navy, fontWeight: "800" },
  secondary: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.default,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: colors.background,
  },
  secondaryText: { color: colors.navy, fontWeight: "700" },
  previewRoot: { flex: 1, backgroundColor: colors.background },
  previewBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: colors.navy,
    borderBottomWidth: 3,
    borderBottomColor: colors.gold,
  },
  backBtn: { paddingVertical: 4, paddingRight: 4 },
  previewTitleWrap: { flex: 1, minWidth: 0 },
  previewEyebrow: {
    color: colors.goldBright,
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginBottom: 2,
  },
  previewTitle: { fontWeight: "800", color: "#fff", fontSize: 14 },
  backText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  shareChip: {
    backgroundColor: colors.accent,
    borderRadius: radius.default,
    paddingHorizontal: 12,
    paddingVertical: 8,
    minWidth: 64,
    alignItems: "center",
  },
  shareChipText: { color: colors.navy, fontWeight: "800", fontSize: 13 },
  webview: { flex: 1, backgroundColor: "#dce2ea" },
  webLoading: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  errorBanner: {
    color: colors.danger,
    backgroundColor: colors.dangerSoft,
    padding: 10,
    fontWeight: "600",
  },
  error: { color: colors.danger, marginTop: 12, fontWeight: "600" },
  ok: { color: colors.success, marginTop: 12, fontWeight: "600" },
});
