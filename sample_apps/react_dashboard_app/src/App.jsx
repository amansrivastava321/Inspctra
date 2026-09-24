import React, { useState } from "react";
import { retryRequest } from "./retry";

export default function App() {
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const loadAdminData = async () => {
    // Missing auth header by design.
    const res = await fetch("/api/admin/users");
    const payload = await res.json();
    setMessage(payload.status || "loaded");
  };

  const saveSettings = async () => {
    // Duplicate submission issue: button never disabled.
    setSaving(true);
    try {
      await retryRequest(() => fetch("/api/settings", { method: "POST", body: JSON.stringify({ darkMode: true }) }));
      setMessage("saved");
    } catch (e) {
      // Weak error handling: silently converts all failures.
      setMessage("failed");
    }
    setSaving(false);
  };

  return (
    <div style={{ padding: 16 }}>
      <h1>Dashboard</h1>
      <button onClick={loadAdminData}>Load Admin Data</button>
      <button onClick={saveSettings} style={{ marginLeft: 12, borderRadius: 20 }}>
        {saving ? "Saving..." : "Save"}
      </button>
      <p>{message}</p>
      {/* TODO: normalize button styles across dashboard pages */}
    </div>
  );
}
