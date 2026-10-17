import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { api } from "../api/client";
import { ScreenShell } from "../components/ScreenShell";
import {
  getAuthAccount,
  isSignedIn,
  updateAuthAccount,
  type MobileAccount,
} from "../storage/auth";
import { getProfile, setActiveLoan, setProfile } from "../storage/session";
import { colors } from "../theme";

const AMOUNT_CHIPS = ["5000", "10000", "20000", "50000", "100000"];
const TERM_CHIPS = ["1", "3", "6", "12"];

type Props = {
  onPhase1Complete: (applicationId: string, transactionId: string) => void;
};

export function ApplyScreen({ onPhase1Complete }: Props) {
  const [account, setAccount] = useState<MobileAccount | null>(getAuthAccount());
  const [loadingAccount, setLoadingAccount] = useState(true);
  const [phone, setPhone] = useState("254712345678");
  const [amount, setAmount] = useState("20000");
  const [term, setTerm] = useState("3");
  const [walletProvider, setWalletProvider] = useState<"mpesa" | "airtel_money">("mpesa");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        setLoadingAccount(true);
        try {
          if (!isSignedIn()) {
            if (alive) setAccount(null);
            return;
          }
          const me = await api.mobileMe();
          await updateAuthAccount(me);
          if (alive) setAccount(me);
        } catch {
          if (alive) setAccount(getAuthAccount());
        } finally {
          if (alive) setLoadingAccount(false);
        }
      })();
      return () => {
        alive = false;
      };
    }, []),
  );

  useEffect(() => {
    getProfile().then((profile) => {
      if (!profile) return;
      setPhone(profile.phone);
      setWalletProvider(profile.walletProvider);
    });
  }, []);

  if (loadingAccount) {
    return (
      <ScreenShell title="Get financing" subtitle="Checking your approval status…">
        <ActivityIndicator color={colors.primary} />
      </ScreenShell>
    );
  }

  if (!isSignedIn() || !account) {
    return (
      <ScreenShell title="Sign in required" subtitle="Create or sign in to your secure email account first.">
        <Text style={{ color: colors.muted, lineHeight: 20 }}>
          Buruuj Lend requires verified email + MFA before you can apply for Halal financing.
        </Text>
      </ScreenShell>
    );
  }

  if (!account.can_borrow) {
    return (
      <ScreenShell
        title="Approval required"
        subtitle={account.approval_message || "Your institution must activate your account before borrowing."}
      >
        <Text style={{ color: colors.muted, lineHeight: 20, marginBottom: 12 }}>
          {account.institution_name
            ? `Waiting on ${account.institution_name}. Open Account to claim an invite, or ask them to approve you in the ops portal.`
            : "Open Account to claim an invite code, or wait for your bank/SACCO to approve you in the ops portal."}
        </Text>
        {account.institution_name ? (
          <Text style={{ color: colors.navy, fontWeight: "700", marginBottom: 8 }}>
            Institution: {account.institution_name}
          </Text>
        ) : null}
        <Text style={{ color: colors.foreground, fontWeight: "700" }}>
          Status: {account.approval_status || "pending"}
        </Text>
      </ScreenShell>
    );
  }

  const submit = async () => {
    if (!account) {
      setError("Sign in required");
      return;
    }
    setBusy(true);
    setError(null);
    setProgress(null);
    const fullName = account.full_name;
    try {
      setProgress("Confirming approved profile…");
      await setProfile({ phone, fullName, walletProvider });
      const linked = await api.completeProfile({
        phone,
        wallet_provider: walletProvider,
        wallet_number: phone,
      });
      if (!linked.account.can_borrow || !linked.customer) {
        throw new Error(
          linked.account.approval_message || "Institution approval is required before financing.",
        );
      }
      const customer = linked.customer;

      const maxLimit = Number(
        linked.account.available_limit ?? linked.account.credit_limit ?? account.credit_limit ?? 0,
      );
      if (maxLimit <= 0) {
        throw new Error("Your approved limit is fully utilized. Repay existing financing to unlock more.");
      }
      if (Number(amount) > maxLimit) {
        throw new Error(`Amount exceeds your available limit of KES ${maxLimit.toLocaleString("en-KE")}`);
      }

      setProgress("Submitting your request…");
      const application = await api.createApplication({
        customer_id: customer.id,
        amount_requested: amount,
        term_months: Number(term),
        purpose: "Personal Halal financing",
      });

      setProgress("Running eligibility…");
      const eligibility = await api.runEligibility(application.id);
      if (!eligibility.eligibility_passed) throw new Error("Eligibility failed. Try a lower amount.");

      setProgress("Preparing your Halal financing…");
      const txn = await api.startTransaction(application.id);
      const afterPurchase = await api.purchase(txn.id);
      if (afterPurchase.legs[0]?.status === "awaiting_possession") {
        setProgress("Almost ready. Confirming Shariah possession…");
        await api.verifyPossession(txn.id);
      }

      await setActiveLoan({
        applicationId: application.id,
        transactionId: txn.id,
        amount,
        phone,
        name: fullName,
        stage: "offer",
        updatedAt: new Date().toISOString(),
      });

      setProgress("Preparing your offer…");
      onPhase1Complete(application.id, txn.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenShell
      title="How much do you need?"
      subtitle={`Signed in as ${account?.email || "…"}. Step 1 of 5.`}
      step={1}
      totalSteps={5}
    >
      <ScrollView contentContainerStyle={styles.form} keyboardShouldPersistTaps="handled">
        {account.institution_name ? (
          <Text style={styles.funder}>
            Financing from {account.institution_name}
            {account.agent_dealer_name ? `\nAgent float: ${account.agent_dealer_name}` : ""}
          </Text>
        ) : null}
        <Text style={styles.section}>Amount (KES)</Text>
        <View style={styles.chips}>
          {AMOUNT_CHIPS.map((chip) => (
            <Chip
              key={chip}
              label={Number(chip).toLocaleString("en-KE")}
              active={amount === chip}
              onPress={() => setAmount(chip)}
            />
          ))}
        </View>
        <Field label="Or enter amount" value={amount} onChangeText={setAmount} keyboardType="numeric" />

        <Text style={styles.section}>Repay over</Text>
        <View style={styles.chips}>
          {TERM_CHIPS.map((chip) => (
            <Chip key={chip} label={`${chip} mo`} active={term === chip} onPress={() => setTerm(chip)} />
          ))}
        </View>

        <Field
          label="M-Pesa / Airtel number (254…)"
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
        />

        <Text style={styles.section}>Disburse to</Text>
        <View style={styles.row}>
          <WalletChip label="M-Pesa" active={walletProvider === "mpesa"} onPress={() => setWalletProvider("mpesa")} />
          <WalletChip
            label="Airtel Money"
            active={walletProvider === "airtel_money"}
            onPress={() => setWalletProvider("airtel_money")}
          />
        </View>

        <Pressable style={[styles.button, busy && styles.buttonDisabled]} onPress={submit} disabled={busy}>
          {busy ? <ActivityIndicator color={colors.navy} /> : <Text style={styles.buttonText}>Continue to offer</Text>}
        </Pressable>
        {progress ? <Text style={styles.progress}>{progress}</Text> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </ScrollView>
    </ScreenShell>
  );
}

function Field({
  label,
  value,
  onChangeText,
  keyboardType,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  keyboardType?: "phone-pad" | "numeric";
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput style={styles.input} value={value} onChangeText={onChangeText} keyboardType={keyboardType} />
    </View>
  );
}

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable style={[styles.chip, active && styles.chipActive]} onPress={onPress}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

function WalletChip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable style={[styles.walletChip, active && styles.chipActive]} onPress={onPress}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  form: { paddingBottom: 40 },
  funder: {
    color: colors.navy,
    fontWeight: "700",
    fontSize: 14,
    marginBottom: 14,
  },
  section: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.muted,
    marginBottom: 8,
    marginTop: 4,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 11,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  walletChip: {
    flex: 1,
    padding: 14,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    backgroundColor: colors.surface,
  },
  chipActive: { backgroundColor: colors.navy, borderColor: colors.navy },
  chipText: { color: colors.muted, fontWeight: "700", fontSize: 13 },
  chipTextActive: { color: colors.goldBright },
  field: { marginBottom: 14 },
  label: { fontSize: 13, color: colors.muted, marginBottom: 6, fontWeight: "600" },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 5,
    padding: 14,
    fontSize: 16,
    color: colors.foreground,
  },
  row: { flexDirection: "row", gap: 8, marginBottom: 14 },
  button: {
    backgroundColor: colors.accent,
    borderRadius: 5,
    padding: 16,
    alignItems: "center",
    marginTop: 8,
    minHeight: 52,
    justifyContent: "center",
  },
  buttonDisabled: { opacity: 0.7 },
  buttonText: { color: colors.navy, fontWeight: "800", fontSize: 16 },
  progress: { color: colors.muted, marginTop: 14, fontSize: 13, lineHeight: 20 },
  error: { color: colors.danger, marginTop: 12, fontWeight: "600" },
});
