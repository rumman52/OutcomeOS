import React, { FormEvent, useState } from 'react'

export function Sandbox() {
  const [order, setOrder] = useState('')
  const [created, setCreated] = useState('')
  function submit(event: FormEvent) {
    event.preventDefault()
    if (order.trim()) setCreated(order.trim())
  }
  return <main>
    <p className="eyebrow">OutcomeOS</p><h1>Commerce outcome sandbox</h1>
    <p>Safely exercise an order journey without touching production.</p>
    <form onSubmit={submit}>
      <label htmlFor="order">Order reference</label>
      <input id="order" value={order} onChange={e => setOrder(e.target.value)} required />
      <button>Create sandbox order</button>
    </form>
    {created && <section role="status"><strong>{created}</strong> created · pending</section>}
  </main>
}
