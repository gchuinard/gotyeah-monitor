/*
 * Build-time : injecte dans le header CSP de nginx les hashes SHA-256 des scripts
 * inline calculés par SvelteKit (présents dans la <meta> CSP de build/index.html).
 *
 * Pourquoi : adapter-static ne peut pas mettre une CSP stricte (avec hash) dans un
 * header HTTP côté SvelteKit (pas de serveur) — elle ne vit que dans une <meta>, que
 * les scanners (ZAP/Sonar) ne créditent pas. On recopie donc ces hashes dans le header
 * nginx. Le hash du script de bootstrap SvelteKit change à chaque build : on l'extrait
 * du HTML réellement émis → header et HTML toujours synchro. Échoue le build si aucun
 * hash n'est trouvé ou si le placeholder subsiste (évite d'expédier une CSP cassée).
 *
 * Lancé depuis /app dans Dockerfile.prod, après `npm run build`.
 */
import fs from 'node:fs';

const INDEX = 'build/index.html';
const TEMPLATE = 'nginx.conf';
const OUTPUT = 'nginx.conf.final';
const PLACEHOLDER = '__CSP_SCRIPT_HASHES__';

const html = fs.readFileSync(INDEX, 'utf8');
const hashes = [...new Set(html.match(/sha256-[A-Za-z0-9+/=]+/g) || [])];
if (hashes.length === 0) {
	console.error(`[inject-csp] aucun hash sha256 dans ${INDEX} (kit.csp cassé ?)`);
	process.exit(1);
}

const scriptSrc = hashes.map((h) => `'${h}'`).join(' ');
let conf = fs.readFileSync(TEMPLATE, 'utf8');
if (!conf.includes(PLACEHOLDER)) {
	console.error(`[inject-csp] placeholder ${PLACEHOLDER} absent de ${TEMPLATE}`);
	process.exit(1);
}
conf = conf.replaceAll(PLACEHOLDER, scriptSrc);
if (conf.includes(PLACEHOLDER)) {
	console.error(`[inject-csp] placeholder encore présent après substitution`);
	process.exit(1);
}

fs.writeFileSync(OUTPUT, conf);
console.log(`[inject-csp] ${hashes.length} hash(es) injecté(s) dans ${OUTPUT}: ${scriptSrc}`);
