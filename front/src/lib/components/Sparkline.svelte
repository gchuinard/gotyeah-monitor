<script lang="ts">
  export let values: number[] = [];
  export let width = 120;
  export let height = 30;

  // Normalisation des valeurs
  let min = Math.min(...values);
  let max = Math.max(...values);
  let range = max - min || 1;

  let points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");
</script>

<svg {width} {height} class="overflow-visible">
  <polyline
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    points={points}
    class="text-blue-400"
  />
</svg>
