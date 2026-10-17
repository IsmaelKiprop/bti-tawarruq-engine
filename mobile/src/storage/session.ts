import AsyncStorage from "@react-native-async-storage/async-storage";

const ACTIVE_LOAN_KEY = "bti_active_loan";
const PROFILE_KEY = "bti_customer_profile";
const ONBOARDING_KEY = "bti_onboarding_done";

/** Where the customer is in the lending journey. */
export type JourneyStage =
  | "apply"
  | "offer"
  | "contract"
  | "settlement"
  | "active"
  | "complete";

export type ActiveLoan = {
  applicationId: string;
  transactionId: string;
  amount: string;
  phone: string;
  name: string;
  stage: JourneyStage;
  updatedAt: string;
};

export type CustomerProfile = {
  phone: string;
  fullName: string;
  walletProvider: "mpesa" | "airtel_money";
};

export async function getActiveLoan(): Promise<ActiveLoan | null> {
  try {
    const raw = await AsyncStorage.getItem(ACTIVE_LOAN_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ActiveLoan;
    if (!parsed.stage) parsed.stage = "apply";
    return parsed;
  } catch {
    return null;
  }
}

export async function setActiveLoan(loan: ActiveLoan): Promise<void> {
  await AsyncStorage.setItem(ACTIVE_LOAN_KEY, JSON.stringify(loan));
}

export async function updateLoanStage(stage: JourneyStage): Promise<ActiveLoan | null> {
  const loan = await getActiveLoan();
  if (!loan) return null;
  const next = { ...loan, stage, updatedAt: new Date().toISOString() };
  await setActiveLoan(next);
  return next;
}

export async function clearActiveLoan(): Promise<void> {
  await AsyncStorage.removeItem(ACTIVE_LOAN_KEY);
}

export async function getProfile(): Promise<CustomerProfile | null> {
  try {
    const raw = await AsyncStorage.getItem(PROFILE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as CustomerProfile;
  } catch {
    return null;
  }
}

export async function setProfile(profile: CustomerProfile): Promise<void> {
  await AsyncStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

export async function isOnboardingDone(): Promise<boolean> {
  try {
    return (await AsyncStorage.getItem(ONBOARDING_KEY)) === "1";
  } catch {
    return false;
  }
}

export async function markOnboardingDone(): Promise<void> {
  await AsyncStorage.setItem(ONBOARDING_KEY, "1");
}
