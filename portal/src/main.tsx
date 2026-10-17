import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { OptionalAppLayout, RequireAnyPermission, RequireAuth, RequirePermission, RequireRole } from "./auth/RequireAuth";
import { AppLayout } from "./components/AppLayout";
import { ApplicationDetailPage } from "./pages/ApplicationDetailPage";
import { ApplicationsListPage } from "./pages/ApplicationsListPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { DashboardPage } from "./pages/DashboardPage";
import { InstitutionIntegrationsPage } from "./pages/InstitutionIntegrationsPage";
import { InstitutionsPage } from "./pages/InstitutionsPage";
import { KenyaFlowPage } from "./pages/KenyaFlowPage";
import { LoginPage } from "./pages/LoginPage";
import { MalaysiaManualBridgePage } from "./pages/MalaysiaManualBridgePage";
import { NewApplicationPage } from "./pages/NewApplicationPage";
import { OpsMonitorPage } from "./pages/OpsMonitorPage";
import { RepaymentsPage } from "./pages/RepaymentsPage";
import { ShariahCompliancePage } from "./pages/ShariahCompliancePage";
import { TransactionDetailPage } from "./pages/TransactionPages";
import { TransactionsListPage } from "./pages/TransactionsListPage";
import { UsersPage } from "./pages/UsersPage";
import { WebhooksPage } from "./pages/WebhooksPage";
import { AgentDealerPage } from "./pages/AgentDealerPage";
import { CustomerJourneyPage } from "./pages/CustomerJourneyPage";
import { CustomersPage } from "./pages/CustomersPage";
import { MobileLendApprovalsPage } from "./pages/MobileLendApprovalsPage";
import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/change-password" element={<ChangePasswordPage />} />
          <Route element={<OptionalAppLayout />}>
            <Route path="/customer" element={<CustomerJourneyPage />} />
            <Route path="/customer/:ref" element={<CustomerJourneyPage />} />
            <Route path="/journey" element={<CustomerJourneyPage />} />
            <Route path="/journey/:ref" element={<CustomerJourneyPage />} />
          </Route>
          <Route element={<RequireAuth />}>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route element={<RequireRole roles={["institution_admin", "institution_ops", "read_only"]} />}>
                <Route path="ops" element={<OpsMonitorPage />} />
              </Route>
              <Route element={<RequireAnyPermission permissions={["write_ops", "dealer_desk"]} />}>
                <Route path="agent-dealers" element={<AgentDealerPage />} />
                <Route path="dealers" element={<AgentDealerPage />} />
              </Route>
              <Route element={<RequirePermission permission="write_ops" />}>
                <Route path="customers" element={<CustomersPage />} />
                <Route path="customers/:customerId" element={<CustomersPage />} />
                <Route path="mobile-lend" element={<MobileLendApprovalsPage />} />
                <Route path="malaysia" element={<MalaysiaManualBridgePage />} />
                <Route path="kenya" element={<KenyaFlowPage />} />
                <Route path="repayments" element={<RepaymentsPage />} />
              </Route>
              <Route element={<RequirePermission permission="manage_institutions" />}>
                <Route path="institutions" element={<InstitutionsPage />} />
              </Route>
              <Route element={<RequirePermission permission="manage_credentials" />}>
                <Route path="users" element={<UsersPage />} />
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
