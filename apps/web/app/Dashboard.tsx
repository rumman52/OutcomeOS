import { cookies } from "next/headers";

type DashboardData = {
  tenant: string;
  campaigns: Array<{ name: string; spend_minor: number; currency: string }>;
  ads: Array<{ label: string }>;
  profit: { contribution_profit_minor: number; performance_fee_minor: number; currency: string };
  funnel: { conversations: number; leads: number; orders: number; outcomes: number; disputes: number };
};

type Props = { section?: string };

async function getDashboard(): Promise<{ data?: DashboardData; error?: string }> {
  const origin = process.env.NEXT_PUBLIC_API_ORIGIN ?? "http://localhost:8000";
  try {
    const session = (await cookies()).get("outcomeos_session")?.value;
    const response = await fetch(`${origin}/api/v1/dashboard`, {
      cache: "no-store",
      headers: session ? { cookie: `outcomeos_session=${encodeURIComponent(session)}` } : {},
    });
    if (response.ok) return { data: (await response.json()) as DashboardData };
    return { error: `API returned ${response.status}` };
  } catch (error) {
    return { error: error instanceof Error ? error.message : "API unavailable" };
  }
}

const bdt = (minor: number) =>
  new Intl.NumberFormat("en-BD", { style: "currency", currency: "BDT" }).format(minor / 100);

export async function Dashboard({ section = "Overview" }: Props) {
  const result = await getDashboard();
  const nav = ["Overview", "Inbox", "Leads", "Orders", "Outcomes", "Profit", "Disputes", "Integrations", "Settings"];
  if (!result.data) {
    return (
      <main className="shell">
        <aside className="side"><h1>Outcome<span>OS</span></h1><strong>SANDBOX</strong></aside>
        <section className="content"><article className="notice" role="alert"><b>Service unavailable.</b><br />The dashboard cannot load business data from the API. Retry after starting <code>make dev-api</code>. Detail: {result.error}</article></section>
      </main>
    );
  }
  const dashboard = result.data;
  return (
    <main className="shell">
      <aside className="side">
        <h1>Outcome<span>OS</span></h1>
        <nav aria-label="Primary">{nav.map((item) => <a key={item} href={`/${item.toLowerCase()}`}>{item}</a>)}</nav>
        <footer>Sandbox / Demo<br />Real providers NOT CONNECTED</footer>
      </aside>
      <section className="content">
        <header><div><p className="eyebrow">Bangladesh e-commerce vertical</p><h2>{section} · {dashboard.tenant}</h2></div><strong className="badge">SANDBOX / DEMO</strong></header>
        <div className="notice"><b>No live provider calls.</b> Meta, WhatsApp, TikTok, Google, courier and payment adapters are deterministic sandbox boundaries.</div>
        <div className="metrics">
          <article><label>Conversations</label><strong>{dashboard.funnel.conversations}</strong></article>
          <article><label>Verified outcomes</label><strong>{dashboard.funnel.outcomes}</strong></article>
          <article><label>Performance fee</label><strong>{bdt(dashboard.profit.performance_fee_minor)}</strong></article>
          <article><label>Contribution profit</label><strong>{bdt(dashboard.profit.contribution_profit_minor)}</strong></article>
        </div>
        <article className="panel"><h3>Outcome readiness</h3><ul><li>Customer verified</li><li>Attribution eligible</li><li>Order confirmed</li><li>Delivery received</li><li>COD settled</li><li>Contract eligible</li><li>Fee created only by API evaluation</li></ul></article>
        <article className="inbox" id="inbox"><h3>Agent inbox</h3><p className="incoming">আপনার sage green linen set আছে? COD হবে?</p><div className="proposal"><b>Grounded AI proposal</b><span>Evidence: product/price/stock/delivery/COD policy</span><textarea aria-label="Edit AI reply" defaultValue="জি, sage green linen set স্টকে আছে। দাম BDT 1,500। Dhaka delivery BDT 80 এবং COD হবে।" /><button>Approve proposed lead/order</button><button>Reject</button><button>Handoff</button></div></article>
        <article className="panel"><h3>Profit equation</h3><p>Collected revenue − product cost − discounts − allocated ads − courier − COD/payment fee − returns − performance fee = server-calculated contribution profit.</p></article>
      </section>
    </main>
  );
}
