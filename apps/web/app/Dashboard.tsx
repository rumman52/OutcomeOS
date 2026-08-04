type DashboardData = {
  tenant: string;
  campaigns: Array<{ name: string; spend_minor: number; currency: string }>;
  ads: Array<{ label: string }>;
  profit: { contribution_profit_minor: number; performance_fee_minor: number; currency: string };
  funnel: { conversations: number; leads: number; orders: number; outcomes: number; disputes: number };
};

async function getDashboard(): Promise<DashboardData> {
  const origin = process.env.NEXT_PUBLIC_API_ORIGIN ?? "http://localhost:8000";
  try {
    const response = await fetch(`${origin}/api/v1/dashboard`, { cache: "no-store" });
    if (response.ok) return response.json() as Promise<DashboardData>;
  } catch {
    // The static build still renders a clearly labeled sandbox shell when the API is offline.
  }
  return {
    tenant: "Dhaka Demo Commerce",
    campaigns: [
      { name: "SANDBOX Facebook commerce campaign", spend_minor: 20000, currency: "BDT" },
    ],
    ads: [{ label: "SANDBOX / NOT CONNECTED" }],
    profit: { contribution_profit_minor: 0, performance_fee_minor: 0, currency: "BDT" },
    funnel: { conversations: 1, leads: 0, orders: 0, outcomes: 0, disputes: 0 },
  };
}

const bdt = (minor: number) =>
  new Intl.NumberFormat("en-BD", { style: "currency", currency: "BDT" }).format(minor / 100);

export async function Dashboard() {
  const dashboard = await getDashboard();
  const nav = [
    "Overview",
    "Agent inbox",
    "Leads",
    "Orders",
    "Outcomes",
    "Profit",
    "Disputes",
    "Integrations",
  ];

  return (
    <main className="shell">
      <aside className="side">
        <h1>
          Outcome<span>OS</span>
        </h1>
        <nav aria-label="Primary">
          {nav.map((item) => (
            <a key={item} href={`#${item.toLowerCase().replaceAll(" ", "-")}`}>
              {item}
            </a>
          ))}
        </nav>
        <footer>
          Sandbox / Demo
          <br />
          Real providers NOT CONNECTED
        </footer>
      </aside>
      <section className="content">
        <header>
          <div>
            <p className="eyebrow">Bangladesh e-commerce vertical</p>
            <h2>{dashboard.tenant}</h2>
          </div>
          <strong className="badge">SANDBOX / DEMO</strong>
        </header>
        <div className="notice">
          <b>No live provider calls.</b> Meta, WhatsApp, TikTok, Google, courier and payment
          adapters are deterministic sandbox boundaries.
        </div>
        <div className="metrics">
          <article>
            <label>Conversations</label>
            <strong>{dashboard.funnel.conversations}</strong>
          </article>
          <article>
            <label>Verified outcomes</label>
            <strong>{dashboard.funnel.outcomes}</strong>
          </article>
          <article>
            <label>Performance fee</label>
            <strong>{bdt(dashboard.profit.performance_fee_minor)}</strong>
          </article>
          <article>
            <label>Contribution profit</label>
            <strong>{bdt(dashboard.profit.contribution_profit_minor)}</strong>
          </article>
        </div>
        <article className="panel">
          <h3>Campaigns and attribution</h3>
          <table>
            <tbody>
              {dashboard.campaigns.map((campaign) => (
                <tr key={campaign.name}>
                  <td>{campaign.name}</td>
                  <td>{bdt(campaign.spend_minor)}</td>
                  <td>
                    <span className="provider">{dashboard.ads[0]?.label}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="inbox" id="agent-inbox">
          <h3>Agent inbox</h3>
          <p className="incoming">আপনার sage green linen set আছে? COD হবে?</p>
          <div className="proposal">
            <b>Grounded AI proposal</b>
            <span>Evidence: product/price/stock/delivery/COD policy</span>
            <code>create_lead → create_order (human approval required)</code>
            <button>Review &amp; approve in API demo</button>
          </div>
        </article>
      </section>
    </main>
  );
}
