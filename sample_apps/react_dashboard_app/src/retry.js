export async function retryRequest(fn) {
  let attempts = 0;
  while (attempts < 2) {
    try {
      return await fn();
    } catch (err) {
      // Broken retry: no backoff, no telemetry, and only two attempts.
      attempts += 1;
    }
  }
  throw new Error("request_failed");
}

// FIXME: add jitter and exponential backoff.
