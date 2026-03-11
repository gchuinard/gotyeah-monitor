<script lang="ts">
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { get } from "svelte/store";

  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  let id = Number(get(page).params.id);

  let name = "";
  let url = "";
  let type = "http";
  let expectedStatusCode = 200;

  let loading = true;
  let submitting = false;
  let error: string | null = null;

  async function loadMonitor() {
    loading = true;
    error = null;
    try {
      const res = await fetch(`${API_URL}/monitors/${id}`);
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `HTTP ${res.status}`);
      }
      const data = await res.json();
      name = data.name;
      url = data.url;
      type = data.type;
      expectedStatusCode = data.expected_status_code ?? 200;
    } catch (e) {
      error = e instanceof Error ? e.message : "Erreur inconnue";
    } finally {
      loading = false;
    }
  }

  loadMonitor();

  async function onSubmit() {
    submitting = true;
    error = null;
    try {
      const res = await fetch(`${API_URL}/monitors/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          url,
          type,
          expected_status_code: expectedStatusCode,
        }),
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `HTTP ${res.status}`);
      }

      await goto("/");
    } catch (e) {
      error = e instanceof Error ? e.message : "Erreur inconnue";
    } finally {
      submitting = false;
    }
  }
</script>

<div class="max-w-xl mx-auto p-6">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-xl font-semibold">Modifier le monitor</h1>
    <button
      type="button"
      class="text-sm text-gray-300 hover:text-white transition"
      on:click={() => goto("/")}
    >
      Retour
    </button>
  </div>

  {#if loading}
    <div class="text-sm text-gray-300">Chargement...</div>
  {:else}
    <form
      class="p-5 rounded-xl border border-white/10 backdrop-blur-md bg-white/5 shadow-[0_0_20px_rgba(0,0,0,0.25)] flex flex-col gap-4"
      on:submit|preventDefault={onSubmit}
    >
      <label class="flex flex-col gap-1">
        <span class="text-sm text-gray-300">Nom</span>
        <input
          class="px-3 py-2 rounded-lg bg-black/30 border border-white/10 focus:outline-none focus:ring-2 focus:ring-gotyeah-500/60"
          bind:value={name}
          required
        />
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-gray-300">URL</span>
        <input
          class="px-3 py-2 rounded-lg bg-black/30 border border-white/10 focus:outline-none focus:ring-2 focus:ring-gotyeah-500/60"
          bind:value={url}
          required
        />
        <span class="text-xs text-gray-500">Doit être une URL valide (http/https).</span>
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-gray-300">Type</span>
        <select
          class="px-3 py-2 rounded-lg bg-black/30 border border-white/10 focus:outline-none focus:ring-2 focus:ring-gotyeah-500/60"
          bind:value={type}
        >
          <option value="http">HTTP</option>
          <option value="ping">Ping</option>
          <option value="port">Port</option>
        </select>
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-gray-300">Code HTTP attendu</span>
        <input
          type="number"
          min="100"
          max="599"
          class="px-3 py-2 rounded-lg bg-black/30 border border-white/10 focus:outline-none focus:ring-2 focus:ring-gotyeah-500/60"
          bind:value={expectedStatusCode}
        />
      </label>

      {#if error}
        <div class="text-sm text-red-300 bg-red-900/20 border border-red-500/30 rounded-lg px-3 py-2">
          {error}
        </div>
      {/if}

      <button
        type="submit"
        class="mt-2 px-3 py-2 rounded-lg bg-gotyeah-500/90 hover:bg-gotyeah-500 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition border border-gotyeah-400/40"
        disabled={submitting}
      >
        {submitting ? "Enregistrement..." : "Enregistrer"}
      </button>
    </form>
  {/if}
</div>

