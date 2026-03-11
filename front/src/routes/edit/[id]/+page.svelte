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
      const stored =
        typeof localStorage !== "undefined" ? localStorage.getItem("auth") : null;
      const token = stored ? (JSON.parse(stored).token as string | null) : null;

      const res = await fetch(`${API_URL}/monitors/${id}`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
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
      const stored =
        typeof localStorage !== "undefined" ? localStorage.getItem("auth") : null;
      const token = stored ? (JSON.parse(stored).token as string | null) : null;

      const res = await fetch(`${API_URL}/monitors/${id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
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

<div class="min-h-screen flex items-start justify-center pt-10 pb-12">
  <div
    class="w-full max-w-xl mx-auto
           rounded-3xl bg-white/80 dark:bg-slate-900/90 backdrop-blur-2xl
           border border-white/70 dark:border-slate-800 shadow-[0_0_60px_rgba(56,189,248,0.28)]
           overflow-hidden"
  >
    <div class="flex items-center justify-between px-8 pt-7 pb-4 border-b border-slate-200/80 dark:border-slate-800">
      <div class="flex flex-col gap-1">
        <div class="text-xs uppercase tracking-[0.25em] text-slate-400 dark:text-slate-500">
          GotYeah Monitor
        </div>
        <h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-50">Modifier le monitor</h1>
      </div>
      <button
        type="button"
        class="btn btn-sm btn-secondary"
        on:click={() => goto("/")}
      >
        Retour
      </button>
    </div>

    <div class="px-4 pb-6 pt-4">
      {#if loading}
        <div class="text-sm text-slate-500 dark:text-slate-300">Chargement...</div>
      {:else}
        <form
          class="rounded-3xl border bg-white/80 dark:bg-slate-950/80 backdrop-blur-2xl 
                 shadow-[0_0_35px_rgba(56,189,248,0.28)] dark:shadow-[0_0_45px_rgba(56,189,248,0.4)]
                 flex flex-col gap-4 p-6"
          on:submit|preventDefault={onSubmit}
        >
          <label class="flex flex-col gap-1">
            <span class="text-sm text-slate-600 dark:text-slate-200">Nom</span>
            <input
              class="px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200/70 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
              bind:value={name}
              required
            />
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-sm text-slate-600 dark:text-slate-200">URL</span>
            <input
              class="px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200/70 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
              bind:value={url}
              required
            />
            <span class="text-xs text-slate-400 dark:text-slate-500">Doit être une URL valide (http/https).</span>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-sm text-slate-600 dark:text-slate-200">Type</span>
            <select
              class="px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200/70 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
              bind:value={type}
            >
              <option value="http">HTTP</option>
              <option value="ping">Ping</option>
              <option value="port">Port</option>
            </select>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-sm text-slate-600 dark:text-slate-200">Code HTTP attendu</span>
            <input
              type="number"
              min="100"
              max="599"
              class="px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200/70 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
              bind:value={expectedStatusCode}
            />
          </label>

          {#if error}
            <div class="text-sm text-rose-600 bg-rose-50/90 dark:bg-rose-900/30 border border-rose-200/80 dark:border-rose-500/40 rounded-xl px-3 py-2">
              {error}
            </div>
          {/if}

          <button
            type="submit"
            class="btn btn-md btn-primary mt-2 self-end disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={submitting}
          >
            {submitting ? "Enregistrement..." : "Enregistrer"}
          </button>
        </form>
      {/if}
    </div>
  </div>
</div>

