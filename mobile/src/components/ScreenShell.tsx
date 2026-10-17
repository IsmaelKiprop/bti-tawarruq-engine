import type { ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { BrandMark } from "./BrandMark";
import { colors, radius, space, type as typography } from "../theme";

export function ScreenShell({
  title,
  subtitle,
  children,
  step,
  totalSteps = 5,
  showBrand = true,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  step?: number;
  totalSteps?: number;
  /** Show Buruuj Fintech mark above the title (default on for journey screens). */
  showBrand?: boolean;
}) {
  return (
    <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
      <View style={styles.container}>
        {showBrand ? <BrandMark size="compact" showWordmark style={styles.brand} /> : null}
        {typeof step === "number" ? (
          <View style={styles.progressBlock}>
            <View style={styles.progressTrack}>
              <View style={[styles.progressFill, { width: `${(step / totalSteps) * 100}%` }]} />
            </View>
            <Text style={styles.progressLabel}>
              Step {step} of {totalSteps} · powered by Buruuj Fintech
            </Text>
          </View>
        ) : (
          <View style={styles.accentBar} />
        )}
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        <View style={styles.content}>{children}</View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  container: {
    flex: 1,
    minHeight: 0,
    paddingHorizontal: space.xl,
    paddingTop: space.md,
    paddingBottom: space.md,
  },
  brand: { marginBottom: space.md },
  content: { flex: 1, minHeight: 0 },
  accentBar: {
    width: 36,
    height: 3,
    borderRadius: radius.default,
    backgroundColor: colors.gold,
    marginBottom: space.md,
  },
  progressBlock: { marginBottom: space.lg },
  progressTrack: {
    height: 4,
    borderRadius: radius.default,
    backgroundColor: colors.border,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: colors.gold,
    borderRadius: radius.default,
  },
  progressLabel: {
    ...typography.caption,
    color: colors.muted,
    marginTop: space.sm,
  },
  title: {
    ...typography.title,
    color: colors.foreground,
    marginBottom: 6,
  },
  subtitle: {
    ...typography.body,
    color: colors.muted,
    marginBottom: space.xl,
  },
});
