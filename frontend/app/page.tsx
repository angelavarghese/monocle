"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, Bell, ChevronDown, CircleHelp, Eye, Plus, RefreshCw, Search, Star } from "lucide-react";

type Item = { id: number; symbol: string; is_priority: boolean; price: number | null; previous_price: number | null; change_pct: number | null; change: { status: string; confidence: string; reason: string; signals: string[] } };
type Watchlist = { id: number; name: string; last_viewed_at: string | null; item_count: number; items: Item[] };
const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function Home() {
  const [watchlist, setWatchlist] = useState<Watchlist | null>(null);
  const [token, setToken] = useState("");
  const [symbol, setSymbol] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${api}/watchlists`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!response.ok) throw new Error("Connect the Monocle API to load your watchlist.");
      const lists = await response.json();
      if (lists[0]) {
        const detail = await fetch(`${api}/watchlists/${lists[0].id}`, { headers: { Authorization: `Bearer ${token}` } });
        setWatchlist(await detail.json());
      }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Something went wrong."); }
    finally { setLoading(false); }
  }

  useEffect(() => { const saved = window.localStorage.getItem("monocle_token"); if (saved) setToken(saved); }, []);
  useEffect(() => { if (token) load(); else setLoading(false); }, [token]);

  async function addSymbol() {
    if (!watchlist || !symbol.trim()) return;
    await fetch(`${api}/watchlists/${watchlist.id}/items`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ symbol: symbol.trim() }) });
    setSymbol("");
    load();
  }

  const attention = watchlist?.items.filter((item) => item.change.status !== "quiet") ?? [];
  const quiet = watchlist?.items.filter((item) => item.change.status === "quiet") ?? [];

  return <main className="shell">
    <nav className="topbar"><div className="brand"><span className="brand-mark">M</span><span>monocle</span></div><div className="nav-actions"><button className="icon-button" aria-label="Search"><Search size={18} /></button><button className="icon-button" aria-label="Notifications"><Bell size={18} /></button><button className="profile">AK <ChevronDown size={14} /></button></div></nav>
    <section className="intro"><div><p className="eyebrow">MARKET INTELLIGENCE / LIVE VIEW</p><h1>See what changed<br /><em>while you were away.</em></h1><p className="lede">Monocle filters the noise from your watchlist and puts meaningful movement in focus.</p></div><div className="date-stamp"><span>LAST CHECKED</span><strong>{watchlist?.last_viewed_at ? new Date(watchlist.last_viewed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Not yet"}</strong><button onClick={load}><RefreshCw size={14} /> Refresh</button></div></section>
    {error && <div className="notice"><CircleHelp size={17} /> {error}</div>}
    {!token && <div className="connect"><p className="eyebrow">WELCOME TO MONOCLE</p><h2>Connect your account to begin.</h2><p>Use the API's register and login endpoints, then save the returned token as <code>monocle_token</code> to open your private watchlists.</p></div>}
    {token && <>
      <section className="watchlist-head"><div><p className="eyebrow">YOUR WATCHLIST</p><h2>{watchlist?.name ?? "Loading..."}</h2></div><div className="add-symbol"><input value={symbol} onChange={(event) => setSymbol(event.target.value)} onKeyDown={(event) => event.key === "Enter" && addSymbol()} placeholder="Add symbol" /><button onClick={addSymbol} aria-label="Add symbol"><Plus size={18} /></button></div></section>
      {loading ? <div className="empty">Reading the latest snapshots...</div> : <>
        <section className="section-heading"><div><span className="section-kicker"><span className="signal-dot red" /> NEEDS YOUR ATTENTION</span><h2>{attention.length} meaningful {attention.length === 1 ? "change" : "changes"}</h2></div><span className="section-note">Sorted by significance <ArrowUpRight size={14} /></span></section>
        <div className="attention-grid">{attention.map((item) => <article className={`stock-card ${item.change.status}`} key={item.id}><div className="card-top"><div><span className="ticker">{item.symbol}</span><span className="confidence">{item.change.confidence} confidence</span></div><button className="star" aria-label="Priority"><Star size={17} fill={item.is_priority ? "currentColor" : "none"} /></button></div><div className="price">{item.price == null ? "--" : `$${item.price.toFixed(2)}`} <span className={item.change_pct && item.change_pct < 0 ? "negative" : "positive"}>{item.change_pct == null ? "" : `${item.change_pct >= 0 ? "+" : ""}${item.change_pct.toFixed(2)}%`}</span></div><div className="mini-chart"><span /><span /><span /><span /><span /><span /><span /></div><p className="reason">{item.change.reason}</p><div className="card-footer"><span>{item.change.signals.length} signals detected</span><Eye size={14} /></div></article>)}</div>
        <section className="quiet-section"><div className="section-heading"><div><span className="section-kicker"><span className="signal-dot quiet-dot" /> STEADY FOR NOW</span><h2>Nothing meaningful changed</h2></div><span className="quiet-count">{quiet.length} holdings</span></div><div className="quiet-list">{quiet.map((item) => <div className="quiet-row" key={item.id}><span className="ticker">{item.symbol}</span><span className="quiet-price">{item.price == null ? "--" : `$${item.price.toFixed(2)}`}</span><span className="quiet-state">Quiet</span><Star size={15} /></div>)}</div></section>
      </>}
    </>}
    <footer><span>MONOCLE / READ THE FINE PRINT</span><span>Data is delayed and for information only. Not financial advice.</span></footer>
  </main>;
}
