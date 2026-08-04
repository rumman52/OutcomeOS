"use client";

import { FormEvent, useEffect, useState } from "react";

type Product = { id:string; name_en:string; name_bn:string; sku:string; price_minor:number; currency:string; on_hand:number };
type Message = { role:string; body:string };
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [products,setProducts]=useState<Product[]>([]);
  const [messages,setMessages]=useState<Message[]>([]);
  const [text,setText]=useState("");
  const [session]=useState(() => typeof window === "undefined" ? "loading-session" : (localStorage.getItem("dhakastyle-session") ?? crypto.randomUUID()));
  useEffect(() => {
    localStorage.setItem("dhakastyle-session",session);
    fetch(`${API}/api/demo/products`).then(r=>r.json()).then(setProducts).catch(()=>setProducts([]));
    fetch(`${API}/api/demo/conversations/${session}`).then(r=>r.ok?r.json():null).then(data=>data&&setMessages(data.messages)).catch(()=>undefined);
  },[session]);
  async function send(event:FormEvent) {
    event.preventDefault(); if(!text.trim()) return;
    const outgoing=text; setText(""); setMessages(current=>[...current,{role:"customer",body:outgoing}]);
    const response=await fetch(`${API}/api/demo/chat`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({tenant_id:"tenant_dhakastyle",session_id:session,message:outgoing})});
    const data=await response.json(); setMessages(current=>[...current,{role:"assistant",body:data.reply}]);
  }
  return <main>
    <header><div><p className="eyebrow">DhakaStyle • ঢাকা স্টাইল</p><h1>Wear the story of Bengal.</h1><p className="lede">Thoughtful local craft, delivered across Bangladesh.</p></div><span className="demo">DEMO STORE</span></header>
    <section className="catalog"><div className="sectionTitle"><h2>New arrivals</h2><p>নতুন কালেকশন</p></div><div className="grid">{products.length ? products.map((p,i)=><article key={p.id}><div className={`art art${i+1}`}><span>{p.name_bn.slice(0,1)}</span></div><p className="sku">{p.sku} · {p.on_hand} in stock</p><h3>{p.name_en}</h3><p>{p.name_bn}</p><strong>৳{(p.price_minor/100).toLocaleString("en-BD")}</strong></article>) : <p className="offline">Start the API to load the demo catalog.</p>}</div></section>
    <aside className="chat"><div className="chatHead"><div className="avatar">দ</div><div><strong>DhakaStyle সহায়ক</strong><small>Demo AI • মানব সহায়তা উপলব্ধ</small></div></div><div className="messages"><div className="assistant">আসসালামু আলাইকুম! পণ্য, স্টক বা অর্ডার নিয়ে কীভাবে সাহায্য করতে পারি?</div>{messages.map((m,i)=><div key={i} className={m.role}>{m.body}</div>)}</div><form onSubmit={send}><input aria-label="Chat message" value={text} onChange={e=>setText(e.target.value)} placeholder="বাংলা বা English-এ লিখুন…"/><button aria-label="Send">↑</button></form><p className="notice">Demo assistant. Ask for a human any time.</p></aside>
  </main>;
}
