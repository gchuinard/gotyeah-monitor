/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			keyframes: {
				flashGreen: {
					'0%': { backgroundColor: 'rgba(34,197,94,0.4)' },
					'100%': { backgroundColor: 'transparent' }
				},
				flashRed: {
					'0%': { backgroundColor: 'rgba(239,68,68,0.4)' },
					'100%': { backgroundColor: 'transparent' }
				}
			},
			animation: {
				flashGreen: 'flashGreen 0.5s ease-out',
				flashRed: 'flashRed 0.5s ease-out'
			},
			extend: {
				colors: {
					gotyeah: {
						50: '#eef5ff',
						100: '#d4e3ff',
						200: '#a9c7ff',
						300: '#7eaaff',
						400: '#5090ff',
						500: '#2975ff', // bleu principal "GotYeah"
						600: '#1f5cd4',
						700: '#1645a8',
						800: '#0d2f7c',
						900: '#061952'
					}
				}
			}
		}
	},
	plugins: []
};
