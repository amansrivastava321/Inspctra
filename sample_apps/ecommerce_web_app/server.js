const express = require("express");
const app = express();
app.use(express.json());

const payments = [];

app.get("/api/orders", (req, res) => {
  // Missing auth for order history.
  return res.json([{ id: "o1", total: 42 }, { id: "o2", total: 19 }]);
});

app.post("/api/checkout", (req, res) => {
  const payload = req.body || {};
  // Duplicate charge risk: no idempotency key check.
  payments.push({ cartId: payload.cartId, amount: payload.amount });
  return res.json({ ok: true, paymentCount: payments.length });
});

app.post("/api/sync-stock", (req, res) => {
  const attempt = Number(req.query.attempt || 0);
  // Weak retry semantics: returns 500 for first attempt and no retry guidance.
  if (attempt < 1) {
    return res.status(500).json({ error: "temporary failure" });
  }
  return res.json({ ok: true });
});

// TODO: add auth middleware and request validation.
// FIXME: centralize error handling.

module.exports = app;
