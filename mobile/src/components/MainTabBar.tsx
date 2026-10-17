import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { colors, radius, shadow, space, type as typography } from "../theme";

export type MainTab = "home" | "loan" | "account";

type Props = {
  active: MainTab;
  onChange: (tab: MainTab) => void;
};

const TABS: {
  id: MainTab;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconActive: keyof typeof Ionicons.glyphMap;
}[] = [
  { id: "home", label: "Home", icon: "home-outline", iconActive: "home" },
  { id: "loan", label: "My loan", icon: "wallet-outline", iconActive: "wallet" },
  { id: "account", label: "Account", icon: "person-outline", iconActive: "person" },
];

export function MainTabBar({ active, onChange }: Props) {
  const insets = useSafeAreaInsets();
  const bottomPad = Math.max(insets.bottom, 10);

  return (
    <View style={[styles.bar, { paddingBottom: bottomPad }, shadow.float]}>
      {TABS.map((tab) => {
        const selected = tab.id === active;
        return (
          <Pressable
            key={tab.id}
            style={styles.item}
            onPress={() => onChange(tab.id)}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            accessibilityLabel={tab.label}
          >
            <View style={[styles.iconWrap, selected && styles.iconWrapOn]}>
              <Ionicons
                name={selected ? tab.iconActive : tab.icon}
                size={22}
                color={selected ? colors.navy : colors.mutedSoft}
              />
            </View>
            <Text style={[styles.label, selected && styles.labelOn]}>{tab.label}</Text>
            {selected ? <View style={styles.activeTick} /> : <View style={styles.activeTickSpacer} />}
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
    paddingTop: space.sm,
    paddingHorizontal: space.xs,
    minHeight: 62,
    zIndex: 20,
  },
  item: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 3,
    paddingVertical: 4,
    minHeight: 52,
  },
  iconWrap: {
    width: 44,
    height: 30,
    borderRadius: radius.default,
    alignItems: "center",
    justifyContent: "center",
  },
  iconWrapOn: {
    backgroundColor: colors.goldMuted,
  },
  label: {
    ...typography.caption,
    color: colors.mutedSoft,
    fontSize: 11,
  },
  labelOn: {
    color: colors.navy,
    fontWeight: "800",
  },
  activeTick: {
    width: 16,
    height: 2,
    borderRadius: 1,
    backgroundColor: colors.gold,
    marginTop: 2,
  },
  activeTickSpacer: {
    width: 16,
    height: 2,
    marginTop: 2,
  },
});
