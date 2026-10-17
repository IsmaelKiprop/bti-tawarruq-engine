export const COMMODITY_EXPLAIN = {
  title: "What the commodity is",
  lead: "On this track the commodity is crude palm oil on Bursa Suq Al-Sila' (BSAS), product code ACPO. It is not a cash loan. Malaysia uses palm oil the way Kenya uses float.",
  dealTitle: "How a deal uses it",
  dealSteps: [
    "The institution instructs Buruuj to buy palm oil on spot (Leg 1). Bursa issues an e-certificate.",
    "The institution owns that commodity (constructive possession) before any sale to the customer.",
    "It sells that same commodity to the customer on Murabaha (cost plus profit, pay later). Title moves on Leg 2.",
    "The customer appoints the bank and Buruuj as wakeel to sell the commodity to an independent buyer.",
    "Leg 3 sells on BSAS. Proceeds are disbursed. The customer repays the Murabaha, not the palm oil.",
  ],
  desk: "Until Buruuj is admitted to Suq Al-Sila', this page writes a desk packet. You send it to BSAS Ops and paste the Islamic Services Receipt. Mock E2E skips that for local testing.",
};

export const MALAYSIA_STEP_GUIDE = [
  { n: 1, title: "Financing request", body: "Pick the onboarded customer. Create the application. The engine records the Wa'd." },
  { n: 2, title: "Murabaha offer", body: "Cost plus disclosed profit. Accept before any Bursa instruction." },
  { n: 3, title: "Purchase instruction", body: "Buruuj writes the Leg 1 desk packet for Suq Al-Sila'." },
  { n: 4, title: "Leg 1 buy", body: "Bursa executes the spot buy. You paste the e-certificate." },
  { n: 5, title: "E-certificate", body: "Islamic Services Receipt proves the buy. Possession is sealed." },
  { n: 6, title: "Bank ownership", body: "Institution owns the commodity. Sale to the customer may start." },
  { n: 7, title: "Sale to customer", body: "Murabaha deferred sale. Leg 2 transfers title." },
  { n: 8, title: "Wakala", body: "Customer appoints the wakeel. Required before Leg 3." },
  { n: 9, title: "Sale instruction", body: "Bank instructs Buruuj to sell on the customer's behalf." },
  { n: 10, title: "Leg 3 sale", body: "Independent sale on BSAS. Not back to the same seller." },
  { n: 11, title: "Sale confirm", body: "Bursa confirms and credits proceeds." },
  { n: 12, title: "Disburse", body: "Cash to the customer. Buruuj issues the Tawarruq certificate." },
];
