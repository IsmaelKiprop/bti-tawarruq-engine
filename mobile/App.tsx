import { CommonActions, NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { BrandMark } from "./src/components/BrandMark";
import { initApiConfig } from "./src/api/client";
import { initLocale } from "./src/i18n";
import { initCrashReporting } from "./src/monitoring/crash";
import { getActiveLoan } from "./src/storage/session";
import { initAuthSession, isSignedIn } from "./src/storage/auth";
import { isOnboardingDone } from "./src/storage/session";
import type { RootStackParamList } from "./src/navigation/types";
import { ApplyScreen } from "./src/screens/ApplyScreen";
import { ContractScreen } from "./src/screens/ContractScreen";
import { DocumentsScreen } from "./src/screens/DocumentsScreen";
import { ForgotPasswordScreen } from "./src/screens/ForgotPasswordScreen";
import { LoginScreen } from "./src/screens/LoginScreen";
import { MainShellScreen } from "./src/screens/MainShellScreen";
import { NotificationsScreen } from "./src/screens/NotificationsScreen";
import { OfferScreen } from "./src/screens/OfferScreen";
import { RegisterScreen } from "./src/screens/RegisterScreen";
import { RepaymentsScreen } from "./src/screens/RepaymentsScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";
import { SettlementScreen } from "./src/screens/SettlementScreen";
import { StatusScreen } from "./src/screens/StatusScreen";
import { SuccessScreen } from "./src/screens/SuccessScreen";
import { VerifyCodeScreen } from "./src/screens/VerifyCodeScreen";
import { WelcomeScreen } from "./src/screens/WelcomeScreen";
import { colors } from "./src/theme";

export type { RootStackParamList } from "./src/navigation/types";

const Stack = createNativeStackNavigator<RootStackParamList>();

function resetToMain(navigation: { dispatch: (action: unknown) => void }) {
  navigation.dispatch(
    CommonActions.reset({
      index: 0,
      routes: [{ name: "Main" }],
    }),
  );
}

export default function App() {
  const [bootstrapped, setBootstrapped] = useState(false);
  const [showWelcome, setShowWelcome] = useState(true);
  const [signedInAtBoot, setSignedInAtBoot] = useState(false);

  useEffect(() => {
    (async () => {
      initCrashReporting();
      await initApiConfig();
      await initLocale();
      await initAuthSession();
      const done = await isOnboardingDone();
      setShowWelcome(!done);
      setSignedInAtBoot(isSignedIn());
      setBootstrapped(true);
    })();
  }, []);

  if (!bootstrapped) {
    return (
      <SafeAreaProvider>
        <View style={styles.boot}>
          <BrandMark size="hero" showWordmark={false} />
          <Text style={styles.bootCompany}>Buruuj Fintech</Text>
          <Text style={styles.bootName}>Buruuj Lend</Text>
          <ActivityIndicator size="small" color={colors.gold} style={{ marginTop: 20 }} />
        </View>
      </SafeAreaProvider>
    );
  }

  const initialRoute: keyof RootStackParamList = showWelcome
    ? "Welcome"
    : signedInAtBoot
      ? "Main"
      : "Login";

  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <StatusBar style="dark" />
        <Stack.Navigator
          initialRouteName={initialRoute}
          screenOptions={{
            headerTintColor: colors.navy,
            headerTitleStyle: { fontWeight: "700", fontSize: 17 },
            headerShadowVisible: false,
            headerStyle: { backgroundColor: colors.background },
            contentStyle: { backgroundColor: colors.background },
            animation: "slide_from_right",
          }}
        >
          <Stack.Screen name="Welcome" options={{ headerShown: false }}>
            {({ navigation }) => (
              <WelcomeScreen
                onDone={() => {
                  setShowWelcome(false);
                  navigation.replace(isSignedIn() ? "Main" : "Login");
                }}
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="Login" options={{ title: "Sign in", headerBackVisible: false }}>
            {({ navigation }) => (
              <LoginScreen
                onChallenge={(mfaToken, email, devCode) =>
                  navigation.replace("Mfa", { mfaToken, email, devCode })
                }
                onGoRegister={() => navigation.navigate("Register")}
                onForgotPassword={() => navigation.navigate("ForgotPassword")}
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="Register" options={{ title: "Create account" }}>
            {({ navigation }) => (
              <RegisterScreen
                onRegistered={(email, devCode) =>
                  navigation.replace("VerifyEmail", { email, devCode })
                }
                onGoLogin={() => navigation.navigate("Login")}
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="ForgotPassword" options={{ title: "Reset password" }}>
            {({ navigation }) => (
              <ForgotPasswordScreen
                onDone={() => navigation.replace("Login")}
                onBack={() => navigation.goBack()}
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="VerifyEmail" options={{ title: "Verify email" }}>
            {({ navigation, route }) => (
              <VerifyCodeScreen
                mode="verify_email"
                email={route.params.email}
                initialDevCode={route.params.devCode}
                onVerified={() => navigation.replace("Login")}
                onMfaSuccess={() => navigation.replace("Main")}
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="Mfa" options={{ title: "Security code", headerBackVisible: false }}>
            {({ navigation, route }) => (
              <VerifyCodeScreen
                mode="mfa"
                email={route.params.email}
                mfaToken={route.params.mfaToken}
                initialDevCode={route.params.devCode}
                onVerified={() => navigation.replace("Main")}
                onMfaSuccess={() => navigation.replace("Main")}
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="Main" options={{ headerShown: false }}>
            {({ navigation }) => <MainShellScreen navigation={navigation} />}
          </Stack.Screen>

          <Stack.Screen name="Settings" options={{ title: "Connection" }}>
            {({ navigation }) => <SettingsScreen onSaved={() => navigation.navigate("Main")} />}
          </Stack.Screen>

          <Stack.Screen name="Notifications" options={{ title: "Notifications" }}>
            {({ navigation }) => (
              <NotificationsScreen
                onOpenFacility={(applicationId) =>
                  navigation.navigate("Status", { applicationId })
                }
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="Documents" options={{ title: "Documents" }}>
            {({ route }) => <DocumentsScreen applicationId={route.params.applicationId} />}
          </Stack.Screen>

          <Stack.Screen name="Apply" options={{ title: "Get financing" }}>
            {({ navigation }) => (
              <ApplyScreen
                onPhase1Complete={(applicationId, transactionId) =>
                  navigation.replace("Offer", { applicationId, transactionId })
                }
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="Offer" options={{ title: "Your offer" }}>
            {({ navigation, route }) => (
              <OfferScreen
                applicationId={route.params.applicationId}
                onAccepted={() =>
                  navigation.replace("Contract", {
                    applicationId: route.params.applicationId,
                    transactionId: route.params.transactionId,
                  })
                }
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="Contract" options={{ title: "Confirm agreement" }}>
            {({ navigation, route }) => (
              <ContractScreen
                applicationId={route.params.applicationId}
                onSigned={() =>
                  navigation.replace("Settlement", {
                    applicationId: route.params.applicationId,
                    transactionId: route.params.transactionId,
                  })
                }
              />
            )}
          </Stack.Screen>

          <Stack.Screen
            name="Settlement"
            options={{ title: "Funding you", headerBackVisible: false, gestureEnabled: false }}
          >
            {({ navigation, route }) => (
              <SettlementScreen
                applicationId={route.params.applicationId}
                transactionId={route.params.transactionId}
                onComplete={async (installmentCount) => {
                  const loan = await getActiveLoan();
                  navigation.replace("Success", {
                    applicationId: route.params.applicationId,
                    amount: loan?.amount || "0",
                    installmentCount,
                  });
                }}
              />
            )}
          </Stack.Screen>

          <Stack.Screen
            name="Success"
            options={{ title: "Funded", headerBackVisible: false, gestureEnabled: false }}
          >
            {({ navigation, route }) => (
              <SuccessScreen
                amount={route.params.amount}
                installmentCount={route.params.installmentCount}
                onGoHome={() => resetToMain(navigation)}
                onRepay={() => {
                  navigation.dispatch(
                    CommonActions.reset({
                      index: 1,
                      routes: [
                        { name: "Main" },
                        {
                          name: "Repayments",
                          params: { applicationId: route.params.applicationId },
                        },
                      ],
                    }),
                  );
                }}
              />
            )}
          </Stack.Screen>

          <Stack.Screen name="Status" options={{ title: "My loan" }}>
            {({ navigation, route }) => (
              <View style={{ flex: 1 }}>
                <StatusScreen applicationId={route.params.applicationId} />
                <Pressable
                  style={styles.footerBtn}
                  onPress={() =>
                    navigation.navigate("Repayments", { applicationId: route.params.applicationId })
                  }
                >
                  <Text style={styles.footerBtnText}>Repay now</Text>
                </Pressable>
              </View>
            )}
          </Stack.Screen>

          <Stack.Screen name="Repayments" options={{ title: "Repay" }}>
            {({ route, navigation }) => (
              <RepaymentsScreen
                applicationId={route.params.applicationId}
                onBorrowAgain={() => navigation.navigate("Apply")}
              />
            )}
          </Stack.Screen>
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.navy,
    paddingHorizontal: 32,
  },
  bootCompany: {
    marginTop: 16,
    color: colors.goldBright,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  bootName: {
    marginTop: 6,
    color: "#fff",
    fontSize: 26,
    fontWeight: "800",
    letterSpacing: -0.4,
  },
  footerBtn: {
    backgroundColor: colors.accent,
    margin: 16,
    padding: 14,
    borderRadius: 5,
    alignItems: "center",
  },
  footerBtnText: { color: colors.navy, fontWeight: "800" },
});
