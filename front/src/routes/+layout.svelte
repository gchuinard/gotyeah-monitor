<script>
  import "../app.css";
</script>

<div
  class="min-h-screen text-slate-900 relative overflow-hidden
         bg-gradient-to-br from-[#f4f7ff] via-[#eef3ff] to-white"
>
  <div
    class="pointer-events-none absolute inset-[-20%]
           bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.22),_transparent_60%),radial-gradient(circle_at_bottom,_rgba(148,163,184,0.16),_transparent_55%)]"
  />
  <div class="relative">
    <slot />
  </div>
</div>
