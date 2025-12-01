<script lang="ts">
  import { onMount } from "svelte";
  import Sparkline from "$lib/components/Sparkline.svelte";

  export let name: string;
  export let status: "up" | "down" | "checking";
  export let type: string = "Service";
  export let latency: number | null = null;
  export let history: number[] = [];

  let showDetails = false;
  let mode = 1;

  // Animations UP/DOWN
  let prevStatus: typeof status;
  let animationClass = "";

  onMount(() => {
    prevStatus = status;
    setTimeout(() => mounted = true, 20);
  });

  $: if (status !== prevStatus) {
    animationClass = status === "up" ? "animate-flashGreen" : "animate-flashRed";
    prevStatus = status;
    setTimeout(() => (animationClass = ""), 600);
  }

  const statusColor = {
    up: "text-gotyeah-400",
    down: "text-red-400",
    checking: "text-gotyeah-200 animate-pulse"
  };

  const statusIcon = {
    up: "🟢",
    down: "🔴",
    checking: "⏳"
  };

  function latencyColor(lat: number | null) {
    if (lat === null) return "text-gray-400";
    if (lat < 150) return "text-gotyeah-400";
    if (lat < 400) return "text-yellow-400";
    return "text-red-500";
  }

  // Animation fade+slide
  let mounted = false;
</script>


<!-- CARD -->
<div class={`p-5 rounded-xl border 
    backdrop-blur-md bg-white/5 
    shadow-[0_0_20px_rgba(0,0,0,0.25)]
    hover:scale-[1.02] hover:shadow-[0_0_25px_rgba(41,117,255,0.4)]
    transition-all duration-300
    ${mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-3"}
    ${animationClass}
    flex flex-col gap-3
    ${status === 'up'
        ? 'border-gotyeah-500/40'
        : status === 'down'
        ? 'border-red-500/40'
        : 'border-gotyeah-300/40'}`}>

  <!-- HEADER -->
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class="text-xl">{statusIcon[status]}</span>
      <h2 class="font-semibold text-lg">{name}</h2>
    </div>

    <span class="px-2 py-1 text-xs rounded bg-gotyeah-600/20 text-gotyeah-200 border border-gotyeah-600/30">
      {type}
    </span>
  </div>

  <!-- STATUS -->
  <div class="flex items-center gap-2">
    <span class={statusColor[status]}>
      {status === "up" ? "Online" : status === "down" ? "Offline" : "Checking..."}
    </span>
  </div>

  <!-- LATENCY -->
  <div class="flex items-center text-sm">
    <span class="text-gray-400">Latence :</span>
    <span class={`ml-2 font-medium ${latencyColor(latency)}`}>
      {latency !== null ? `${latency} ms` : "N/A"}
    </span>
  </div>

  <!-- DETAILS SECTION -->
  <div class="mt-2 border-t border-white/10 pt-3">
    <button
      class="text-gray-400 hover:text-white transition flex items-center gap-1 text-sm"
      on:click={() => showDetails = !showDetails}
    >
      {#if showDetails}
        🙈 <span>Cacher détails</span>
      {:else}
        👁️ <span>Voir détails</span>
      {/if}
    </button>

    {#if showDetails}
      <div class="mt-3 flex flex-col gap-4">

        <!-- TOGGLE 0 / 1 / 2 -->
        <div class="flex items-center gap-3 text-xs text-gray-300">
          <span>Affichage :</span>

          <div class="relative w-40 h-8 bg-gray-700 rounded-full flex items-center px-1">
            <button
              class={`flex-1 h-full flex items-center justify-center rounded-full transition
                ${mode === 0 ? "bg-gotyeah-500 text-white" : "text-gray-400"}`}
              on:click={() => mode = 0}
            >
              Spark
            </button>

            <button
              class={`flex-1 h-full flex items-center justify-center rounded-full transition
                ${mode === 1 ? "bg-gotyeah-500 text-white" : "text-gray-400"}`}
              on:click={() => mode = 1}
            >
              Les deux
            </button>

            <button
              class={`flex-1 h-full flex items-center justify-center rounded-full transition
                ${mode === 2 ? "bg-gotyeah-500 text-white" : "text-gray-400"}`}
              on:click={() => mode = 2}
            >
              Historique
            </button>
          </div>
        </div>

        <!-- SPARKLINE -->
        {#if mode === 0 || mode === 1}
          <div class="mt-2">
            <Sparkline values={history} />
          </div>
        {/if}

        <!-- HISTORIQUE LISTE -->
        {#if mode === 1 || mode === 2}
          <div class="text-xs text-gray-400 flex flex-wrap gap-1 leading-relaxed">
            {#each history as h}
              <span class="px-2 py-1 bg-gray-800/70 rounded border border-gray-600/30">
                {h} ms
              </span>
            {/each}
          </div>
        {/if}

      </div>
    {/if}
  </div>

</div>
