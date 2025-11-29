<script lang="ts">
  import { API_URL } from "./lib/api";

  let status: string = "…loading";

  async function checkHealth() {
    try {
      const res = await fetch(`${API_URL}/health`);
      const data: { status: string } = await res.json();
      status = data.status;
    } catch (e) {
      status = "error";
    }
  }

  checkHealth();
</script>

<main>
  <h1>Monitor Dashboard</h1>
  <p>API Status : <strong>{status}</strong></p>
</main>

<style>
  main { padding: 2rem; font-family: system-ui; }
  strong { color: purple; }
</style>
