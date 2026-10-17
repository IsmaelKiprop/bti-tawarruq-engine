import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  checkEngineHealth,
  getApiBaseUrl,
  initApiConfig,
  setApiBaseUrl,
} from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import { colors } from "../theme";

type Props = {
  onSaved?: (url: string) => void;
};

export function SettingsScreen({ onSaved }: Props) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    initApiConfig().then((current) => setUrl(current));
  }, []);

  const test = async () => {
    setBusy(true);
    setMessage(null);
    try {
      if (url.trim() && url.trim() !== getApiBaseUrl()) {
        await setApiBaseUrl(url);
      }
      const health = await checkEngineHealth();
      setOk(health.ok);
      setMessage(health.message);
      if (health.ok) onSaved?.(getApiBaseUrl());
    } catch (err) {
      setOk(false);
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const saved = await setApiBaseUrl(url);
      const health = await checkEngineHealth();
      setOk(health.ok);
      setMessage(health.ok ? `Saved. ${health.message}` : `Saved URL, but: ${health.message}`);
      onSaved?.(saved);
    } catch (err) {
      setOk(false);
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenShell
      title="Connection"
      subtitle="On a real phone use your PC's LAN IP, not localhost. Example: http://192.168.1.20:8000/api/v1"
    >
      <Text style={styles.label}>Engine API base URL</Text>
      <TextInput
        style={styles.input}
        value={url}
        onChangeText={setUrl}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="http://192.168.x.x:8000/api/v1"
      />
      <View style={styles.row}>
        <Pressable style={[styles.button, styles.secondary]} onPress={test} disabled={busy}>
          {busy ? <ActivityIndicator color={colors.primary} /> : <Text style={styles.secondaryText}>Test</Text>}
        </Pressable>
        <Pressable style={styles.button} onPress={save} disabled={busy}>
          <Text style={styles.buttonText}>Save</Text>
        </Pressable>
      </View>
      {message ? (
        <Text style={[styles.message, ok === false ? styles.error : styles.success]}>{message}</Text>
      ) : null}
      <Text style={styles.hint}>
        1. Start the engine with --host 0.0.0.0{"\n"}
        2. Put phone and PC on the same Wi-Fi{"\n"}
        3. Allow Windows Firewall for Python on private networks{"\n"}
        4. Paste http://&lt;your-lan-ip&gt;:8000/api/v1 above and tap Test{"\n\n"}
        Tip: set EXPO_PUBLIC_API_URL before npx expo start so the URL is prefilled.
      </Text>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  label: { fontSize: 13, color: colors.muted, marginBottom: 6, fontWeight: "600" },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 5,
    padding: 12,
    fontSize: 15,
    marginBottom: 14,
  },
  row: { flexDirection: "row", gap: 10 },
  button: {
    flex: 1,
    backgroundColor: colors.primary,
    borderRadius: 5,
    padding: 14,
    alignItems: "center",
  },
  secondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  buttonText: { color: colors.primaryForeground, fontWeight: "700" },
  secondaryText: { color: colors.navy, fontWeight: "700" },
  message: { marginTop: 14, fontSize: 14, lineHeight: 20 },
  success: { color: colors.primary },
  error: { color: colors.danger },
  hint: { marginTop: 24, color: colors.muted, fontSize: 13, lineHeight: 20 },
});
