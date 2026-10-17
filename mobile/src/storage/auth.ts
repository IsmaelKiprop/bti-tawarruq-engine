import AsyncStorage from "@react-native-async-storage/async-storage";

const ACCESS_KEY = "bti_mobile_access_token";
const REFRESH_KEY = "bti_mobile_refresh_token";
const ACCOUNT_KEY = "bti_mobile_account";

export type MobileAccount = {
  id: string;
  email: string;
  full_name: string;
  email_verified: boolean;
  customer_id: string | null;
  institution_id?: string | null;
  institution_name?: string | null;
  agent_dealer_name?: string | null;
  agent_float_available?: string | null;
  kyc_status?: string | null;
  national_id?: string | null;
  unread_notifications?: number;
  has_customer_profile: boolean;
  approval_status?: string;
  phone?: string | null;
  credit_limit?: string | null;
  credit_utilized?: string | null;
  available_limit?: string | null;
  can_borrow?: boolean;
  approval_message?: string | null;
  rejection_reason?: string | null;
  has_invite?: boolean;
};

let accessToken: string | null = null;
let refreshToken: string | null = null;
let account: MobileAccount | null = null;
let ready = false;

export async function initAuthSession(): Promise<MobileAccount | null> {
  if (ready) return account;
  try {
    const [access, refresh, rawAccount] = await Promise.all([
      AsyncStorage.getItem(ACCESS_KEY),
      AsyncStorage.getItem(REFRESH_KEY),
      AsyncStorage.getItem(ACCOUNT_KEY),
    ]);
    accessToken = access;
    refreshToken = refresh;
    account = rawAccount ? (JSON.parse(rawAccount) as MobileAccount) : null;
  } catch {
    accessToken = null;
    refreshToken = null;
    account = null;
  }
  ready = true;
  return account;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function getRefreshToken(): string | null {
  return refreshToken;
}

export function getAuthAccount(): MobileAccount | null {
  return account;
}

export function isSignedIn(): boolean {
  return Boolean(accessToken && account);
}

export function canBorrowNow(acc: MobileAccount | null = account): boolean {
  return Boolean(acc?.can_borrow);
}

export async function saveAuthSession(payload: {
  access_token: string;
  refresh_token: string;
  account: MobileAccount;
}): Promise<void> {
  accessToken = payload.access_token;
  refreshToken = payload.refresh_token;
  account = payload.account;
  ready = true;
  await AsyncStorage.multiSet([
    [ACCESS_KEY, payload.access_token],
    [REFRESH_KEY, payload.refresh_token],
    [ACCOUNT_KEY, JSON.stringify(payload.account)],
  ]);
}

export async function updateAuthAccount(next: MobileAccount): Promise<void> {
  account = next;
  await AsyncStorage.setItem(ACCOUNT_KEY, JSON.stringify(next));
}

export async function clearAuthSession(): Promise<void> {
  accessToken = null;
  refreshToken = null;
  account = null;
  await AsyncStorage.multiRemove([ACCESS_KEY, REFRESH_KEY, ACCOUNT_KEY]);
}
