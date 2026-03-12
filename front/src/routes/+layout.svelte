<script lang="ts">
	import '../app.css';
</script>

<div
	class="min-h-screen relative overflow-hidden
         bg-gradient-to-br from-[#f4f7ff] via-[#eef3ff] to-white text-slate-900
         dark:bg-gradient-to-b dark:from-[#020617] dark:via-black dark:to-[#020617] dark:text-slate-100"
>
	<div
		class="pointer-events-none absolute inset-[-20%]
           bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.22),_transparent_60%),radial-gradient(circle_at_bottom,_rgba(148,163,184,0.16),_transparent_55%)]
           dark:inset-[-10%]
           dark:bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.35),_transparent_55%),radial-gradient(circle_at_bottom,_rgba(168,85,247,0.35),_transparent_55%)]"
	></div>

	<div class="relative">
		<slot />
	</div>
</div>
