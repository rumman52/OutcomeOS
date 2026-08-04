"use client";

import { FormEvent, useState } from "react";

export function Sandbox() {
  const [order, setOrder] = useState("");
  const [created, setCreated] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (order.trim()) setCreated(order.trim());
  }

  return (
    <section aria-labelledby="sandbox-heading">
      <h2 id="sandbox-heading">Commerce outcome sandbox</h2>
      <p>Safely exercise an order journey without touching production.</p>
      <form onSubmit={submit}>
        <label htmlFor="order">Order reference</label>
        <input id="order" value={order} onChange={(event) => setOrder(event.target.value)} required />
        <button type="submit">Create sandbox order</button>
      </form>
      {created && (
        <p role="status">
          <strong>{created}</strong> created · pending
        </p>
      )}
    </section>
  );
}
