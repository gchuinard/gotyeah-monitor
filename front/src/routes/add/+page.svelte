<script lang="ts">
  import { goto } from "$app/navigation";

  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  let name = "";
  let url = "";
  let type = "http";
  let expectedStatusCode = 200;

  let submitting = false;
  let error: string | null = null;

  async function onSubmit() {
    submitting = true;
    error = null;

    try {
      const stored = typeof localStorage !== "undefined" ? localStorage.getItem("auth") : null;
      const token = stored ? (JSON.parse(stored).token as string | null) : null;

      const res = await fetch(`${API_URL}/monitors`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ name, url, type, expected_status_code: expectedStatusCode }),
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

<div class="min-h-screen flex items-start justify-center pt-10 pb-12">
  <div
    class="w-full max-w-3xl mx-auto p-8
           rounded-3xl bg-white/85 backdrop-blur-2xl
           border border-white/70 shadow-[0_0_60px_rgba(56,189,248,0.3)]"
  >
    <div class="flex items-center justify-between mb-6">
      <div class="flex flex-col gap-1">
        <div class="text-xs uppercase tracking-[0.25em] text-slate-400">
          GotYeah Monitor
        </div>
        <h1 class="text-2xl font-semibold text-slate-900">Ajouter un monitor</h1>
      </div>
      <button
        type="button"
        class="text-sm px-3 py-1.5 rounded-full border border-slate-200
               bg-white/60 text-slate-600 hover:bg-white transition"
        on:click={() => goto("/")}
      >
        Retour
      </button>
    </div>

    <form
      class="p-5 rounded-2xl border border-slate-200/70 bg-white/80 flex flex-col gap-4"
      on:submit|preventDefault={onSubmit}
    >
    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-600">Nom</span>
      <input
        class="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
        bind:value={name}
        placeholder="Ex: Backend API"
        required
      />
    </label>

    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-600">URL</span>
      <input
        class="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
        bind:value={url}
        placeholder="https://example.com/health"
        required
      />
      <span class="text-xs text-slate-400">Doit être une URL valide (http/https).</span>
    </label>

    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-600">Type</span>
      <select
        class="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
        bind:value={type}
      >
        <option value="http">HTTP</option>
        <option value="ping">Ping</option>
        <option value="port">Port</option>
      </select>
    </label>

    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-600">Code HTTP attendu</span>
      <input
        type="number"
        min="100"
        max="599"
        class="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
        bind:value={expectedStatusCode}
      />
      <span class="text-xs text-slate-400">Par défaut 200 (OK).</span>
    </label>

    {#if error}
      <div class="text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
        {error}
      </div>
    {/if}

      <button
        type="submit"
        class="mt-2 px-4 py-2 rounded-full bg-cyan-500 hover:bg-cyan-400
               disabled:opacity-50 disabled:cursor-not-allowed
               text-sm font-medium text-white transition
               shadow-[0_0_25px_rgba(34,211,238,0.65)] border border-cyan-300"
        disabled={submitting}
      >
        {submitting ? "Ajout..." : "Ajouter"}
      </button>
    </form>
  </div>
</div>

