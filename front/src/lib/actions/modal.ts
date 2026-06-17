/**
 * Action de modale accessible, à poser sur le panneau `role="dialog"` :
 *   <div role="dialog" aria-modal="true" use:modal={() => (open = false)}> … </div>
 *
 * - ferme sur Échap (appelle le callback fourni) ;
 * - piège le focus : Tab/Shift+Tab cyclent à l'intérieur de la modale ;
 * - met le focus initial dans la modale à l'ouverture et le restaure à la fermeture.
 *
 * Le listener est posé en JS (pas via on:keydown), ce qui évite aussi les avertissements
 * a11y de l'eslint Svelte sur un élément non interactif.
 */
const FOCUSABLE =
	'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function modal(node: HTMLElement, onClose?: () => void) {
	const previouslyFocused = document.activeElement as HTMLElement | null;

	function focusables(): HTMLElement[] {
		return Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
			(el) => el.getClientRects().length > 0
		);
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.stopPropagation();
			onClose?.();
			return;
		}
		if (e.key !== 'Tab') return;
		const els = focusables();
		if (els.length === 0) {
			e.preventDefault();
			return;
		}
		const first = els[0];
		const last = els[els.length - 1];
		if (e.shiftKey && document.activeElement === first) {
			e.preventDefault();
			last.focus();
		} else if (!e.shiftKey && document.activeElement === last) {
			e.preventDefault();
			first.focus();
		}
	}

	node.addEventListener('keydown', onKeydown);

	// Focus initial : premier élément focusable, sinon la modale elle-même.
	const initial = focusables()[0];
	if (initial) {
		initial.focus();
	} else {
		if (!node.hasAttribute('tabindex')) node.setAttribute('tabindex', '-1');
		node.focus();
	}

	return {
		update(newOnClose?: () => void) {
			onClose = newOnClose;
		},
		destroy() {
			node.removeEventListener('keydown', onKeydown);
			previouslyFocused?.focus?.();
		}
	};
}
