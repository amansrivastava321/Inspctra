const checkoutBtn = document.getElementById("checkout");
const statusEl = document.getElementById("status");

checkoutBtn.addEventListener("click", async () => {
  // Duplicate submission issue: not disabling control.
  try {
    const res = await fetch("/api/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cartId: "cart-1", amount: 129.99 })
    });
    const body = await res.json();
    statusEl.innerText = "Payment OK " + body.paymentCount;
  } catch (_err) {
    // Weak error handling.
    statusEl.innerText = "Error";
  }
});
