export const format = {
	watts(value: number | null | undefined): string {
		return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(1)} W` : '--';
	},
	volts(value: number | null | undefined): string {
		return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(0)} V` : '--';
	},
	amps(value: number | null | undefined): string {
		return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)} A` : '--';
	},
	age(seconds: number | null | undefined): string {
		if (typeof seconds !== 'number' || !Number.isFinite(seconds)) return 'belum ada data';
		const rounded = Math.max(0, Math.round(seconds));
		if (rounded < 60) return `${rounded} detik lalu`;
		if (rounded < 3600) return `${Math.round(rounded / 60)} menit lalu`;
		if (rounded < 86400) return `${Math.round(rounded / 3600)} jam lalu`;
		return `${Math.round(rounded / 86400)} hari lalu`;
	},
	bytes(value: number | null | undefined): string {
		if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
		const units = ['B', 'KB', 'MB', 'GB'];
		let size = value;
		let index = 0;
		while (size >= 1024 && index < units.length - 1) {
			size /= 1024;
			index += 1;
		}
		return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
	},
	dateTime(value: string | null | undefined): string {
		if (!value) return '--';
		// Backend timestamps are local time without a zone suffix.
		const parsed = new Date(value.replace(' ', 'T'));
		return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('id-ID');
	},
	relative(value: string | null | undefined): string {
		if (!value) return '--';
		const parsed = new Date(value.replace(' ', 'T'));
		if (Number.isNaN(parsed.getTime())) return value;
		return format.age((Date.now() - parsed.getTime()) / 1000);
	}
};
