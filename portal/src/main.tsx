import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { OptionalAppLayout, RequireAnyPermission, RequireAuth, RequirePermission } from "./auth/RequireAuth";
import { AppLayout } from "./components/AppLayout";
import { ApplicationDetailPage } from "./pages/ApplicationDetailPage";
import { ApplicationsListPage } from "./pages/ApplicationsListPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { DashboardPage } from "./pages/DashboardPage";
import { InstitutionIntegrationsPage } from "./pages/InstitutionIntegrationsPage";
import { InstitutionManagementPage } from "./pages/InstitutionManagementPage";
import { InstitutionOnboardPage } from "./pages/InstitutionOnboardPage";
import { InstitutionProfilePage } from "./pages/InstitutionProfilePage";
import { InstitutionsPage } from "./pages/InstitutionsPage";
import { KenyaFlowPage } from "./pages/KenyaFlowPage";
import { LoginPage } from "./pages/LoginPage";
import { MalaysiaManualBridgePage } from "./pages/MalaysiaManualBridgePage";
import { NewApplicationPage } from "./pages/NewApplicationPage";
import { OriginationDeskPage } from "./pages/OriginationDeskPage";
import { RepaymentsPage } from "./pages/RepaymentsPage";
import { SedaniaFinancingPage } from "./pages/SedaniaFinancingPage";
import { ShariahCompliancePage } from "./pages/ShariahCompliancePage";
import { TransactionDetailPage } from "./pages/TransactionPages";
import { TransactionsListPage } from "./pages/TransactionsListPage";
import { UserManagementPage } from "./pages/UserManagementPage";
import { UsersPage } from "./pages/UsersPage";
import { WebhooksPage } from "./pages/WebhooksPage";
import { AgentDealerPage } from "./pages/AgentDealerPage";
import { CustomerJourneyPage } from "./pages/CustomerJourneyPage";
import { CustomersPage } from "./pages/CustomersPage";
import { MobileLendApprovalsPage } from "./pages/MobileLendApprovalsPage";
import { BillingPage } from "./pages/BillingPage";
import { ReconciliationPage } from "./pages/ReconciliationPage";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { MfaEnrollPage } from "./pages/MfaEnrollPage";
import { SettingsPage } from "./pages/SettingsPage";
import { OpsMonitorPage } from "./pages/OpsMonitorPage";
import { AuditTrailPage } from "./pages/AuditTrailPage";
import "./styles/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/change-password" element={<ChangePasswordPage />} />
          <Route path="/mfa-enroll" element={<MfaEnrollPage />} />
          <Route element={<OptionalAppLayout />}>
            <Route path="/customer" element={<CustomerJourneyPage />} />
            <Route path="/customer/:ref" element={<CustomerJourneyPage />} />
            <Route path="/journey" element={<CustomerJourneyPage />} />
            <Route path="/journey/:ref" element={<CustomerJourneyPage />} />
          </Route>
          <Route element={<RequireAuth />}>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="institution" element={<InstitutionProfilePage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="documentation" element={<Navigate to="/" replace />} />
              <Route
                element={
                  <RequireAnyPermission
                    permissions={["manage_institutions", "manage_credentials", "view_metrics", "export_data"]}
                  />
                }
              >
                <Route path="audit" element={<AuditTrailPage />} />
              </Route>
              <Route element={<RequirePermission permission="view_metrics" />}>
                <Route path="ops" element={<OpsMonitorPage />} />
              </Route>
              <Route element={<RequirePermission permission="manage_billing" />}>
                <Route path="billing" element={<BillingPage />} />
              </Route>
              <Route element={<RequirePermission permission="reconcile" />}>
                <Route path="reconciliation" element={<ReconciliationPage />} />
              </Route>
              <Route element={<RequireAnyPermission permissions={["write_ops", "dealer_desk"]} />}>
                <Route path="agent-dealers" element={<AgentDealerPage />} />
                <Route path="dealers" element={<AgentDealerPage />} />
              </Route>
              <Route element={<RequireAnyPermission permissions={["write_ops", "approve_txn"]} />}>
                <Route path="mobile-lend" element={<MobileLendApprovalsPage />} />
              </Route>
              <Route element={<RequirePermission permission="approve_txn" />}>
                <Route path="approvals" element={<ApprovalsPage />} />
              </Route>
              <Route element={<RequireAnyPermission permissions={["write_ops", "approve_txn"]} />}>
                <Route path="origination" element={<OriginationDeskPage />} />
              </Route>
              <Route element={<RequirePermission permission="write_ops" />}>
                <Route path="customers" element={<CustomersPage />} />
                <Route path="customers/:customerId" element={<CustomersPage />} />
                <Route path="malaysia" element={<MalaysiaManualBridgePage />} />
                <Route path="sedania" element={<SedaniaFinancingPage />} />
                <Route path="kenya" element={<KenyaFlowPage />} />
                <Route path="repayments" element={<RepaymentsPage />} />
              </Route>
              <Route element={<RequireAnyPermission permissions={["manage_institutions", "write_bti_ops"]} />}>
                <Route path="institutions/onboard" element={<InstitutionOnboardPage />} />
                <Route path="institutions/:institutionId/onboard" element={<InstitutionOnboardPage />} />
                <Route path="institutions" element={<InstitutionsPage />} />
              </Route>
              <Route element={<RequirePermission permission="manage_institutions" />}>
                <Route path="institutions/:institutionId" element={<InstitutionManagementPage />} />
              </Route>
              <Route element={<RequirePermission permission="manage_credentials" />}>
                <Route path="users" element={<UsersPage />} />
                <Route path="users/:userId" element={<UserManagementPage />} />
                <Route path="webhooks" element={<WebhooksPage />} />
              </Route>
              <Route element={<RequirePermission permission="manage_integrations" />}>
                <Route path="integrations" element={<InstitutionIntegrationsPage />} />
              </Route>
              <Route path="applications" element={<ApplicationsListPage />} />
              <Route element={<RequirePermission permission="write_ops" />}>
                <Route path="applications/new" element={<NewApplicationPage />} />
              </Route>
              <Route path="applications/:id" element={<ApplicationDetailPage />} />
              <Route path="transactions" element={<TransactionsListPage />} />
              <Route element={<RequirePermission permission="view_shariah" />}>
                <Route path="shariah" element={<ShariahCompliancePage />} />
              </Route>
              <Route path="transactions/:id" element={<TransactionDetailPage />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
);
