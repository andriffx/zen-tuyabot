import tailwindcss from '@tailwindcss/vite';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// Pure SPA: the operator's nginx serves index.html for every route.
			adapter: adapter({
				fallback: 'index.html',
				strict: false
			})
		})
	],
	server: {
		proxy: {
			// changeOrigin:false keeps Host equal to the browser origin, which is
			// what the backend's OriginMiddleware compares against.
			'/api': { target: 'http://127.0.0.1:8080', changeOrigin: false }
		}
	}
});
