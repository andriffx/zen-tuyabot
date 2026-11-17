import { mode, setMode } from 'mode-watcher';
import { auth } from '#lib/stores/auth.svelte';

/** The three values mode-watcher accepts at runtime. */
export type ThemeMode = 'light' | 'dark' | 'system';

const labels: Record<ThemeMode, string> = {
	light: 'Terang',
	dark: 'Gelap',
	system: 'Sistem'
};

export const theme = {
	get current(): ThemeMode {
		return mode.current as ThemeMode;
	},
	get label() {
		return labels[this.current];
	},
	set(value: ThemeMode) {
		setMode(value);
	},
	retry: () => auth.hydrate()
};
