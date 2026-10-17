import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { BrandMark } from "../components/BrandMark";
import { AppButton, StatusTag } from "../components/ui";
import { markOnboardingDone } from "../storage/session";
import { colors, radius, space, type as typography } from "../theme";

const SLIDES = [
  {
    title: "Halal financing, instantly",
    body: "Cash to M-Pesa or Airtel Money. Built on Tawarruq — no interest, every term in the open.",
  },
  {
    title: "See every term upfront",
    body: "Clear Murabaha offer: amount, Halal profit, total to repay. Accept only when you are ready.",
  },
  {
    title: "One continuous journey",
    body: "Apply, accept, sign, and get funded in one flow. Shariah steps run in the background.",
  },
];

type Props = {
  onDone: () => void;
};

export function WelcomeScreen({ onDone }: Props) {
  const insets = useSafeAreaInsets();
  const [index, setIndex] = useState(0);
  const slide = SLIDES[index];
  const last = index === SLIDES.length - 1;

  const next = async () => {
    if (!last) {
      setIndex((i) => i + 1);
      return;
    }
    await markOnboardingDone();
    onDone();
  };

  const skip = async () => {
    await markOnboardingDone();
    onDone();
  };

  return (
    <View style={styles.root}>
      <View style={[styles.hero, { paddingTop: Math.max(insets.top, 20) + 8 }]}>
        <Pressable style={styles.skip} onPress={skip} hitSlop={12}>
          <Text style={styles.skipText}>Skip</Text>
        </Pressable>
        <BrandMark size="hero" showWordmark={false} />
        <Text style={styles.company}>Buruuj Fintech</Text>
        <Text style={styles.product}>Buruuj Lend</Text>
        <StatusTag label="Shariah · Tawarruq" tone="gold" />
      </View>

      <View style={[styles.sheet, { paddingBottom: Math.max(insets.bottom, 28) }]}>
        <View style={styles.goldRule} />
        <Text style={styles.title}>{slide.title}</Text>
        <Text style={styles.body}>{slide.body}</Text>

        <View style={styles.dots}>
          {SLIDES.map((_, i) => (
            <View key={i} style={[styles.dot, i === index && styles.dotActive]} />
          ))}
        </View>

        <AppButton label={last ? "Start lending" : "Continue"} onPress={next} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.navy },
  hero: {
    flex: 1.05,
    backgroundColor: colors.navy,
    paddingHorizontal: space.xxl,
    justifyContent: "center",
    gap: space.sm,
  },
  skip: { position: "absolute", top: 54, right: space.xl, zIndex: 2 },
  skipText: { color: "rgba(255,255,255,0.7)", fontWeight: "700", fontSize: 14 },
  company: {
    ...typography.overline,
    color: colors.goldBright,
    marginTop: space.md,
  },
  product: {
    ...typography.display,
    color: "#fff",
  },
  sheet: {
    backgroundColor: colors.background,
    paddingHorizontal: space.xxl,
    paddingTop: space.xxl,
    borderTopLeftRadius: radius.default,
    borderTopRightRadius: radius.default,
  },
  goldRule: {
    width: 40,
    height: 3,
    backgroundColor: colors.gold,
    borderRadius: radius.default,
    marginBottom: space.lg,
  },
  title: { ...typography.title, color: colors.navy, marginBottom: space.md },
  body: { ...typography.body, color: colors.muted, fontSize: 16, lineHeight: 24, minHeight: 72 },
  dots: { flexDirection: "row", gap: 8, marginVertical: space.xl },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.border },
  dotActive: { width: 24, backgroundColor: colors.gold, borderRadius: radius.pill },
});
