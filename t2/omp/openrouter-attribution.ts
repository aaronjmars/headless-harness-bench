// openrouter-attribution: omp extension, load with `omp --extension <path>`.
// Swaps omp's OpenRouter app attribution for Aeon's on every request.
const OMP_REFERER = "https://omp.sh/";
const WRAPPED = Symbol.for("aeon.omp.openrouterAttribution");

export default function (pi: any) {
	const base: any = globalThis.fetch;
	if (base[WRAPPED]) return;
	const wrapped: any = (input: any, init?: any) => {
		const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
		if (headers.get("http-referer") !== OMP_REFERER) return base(input, init);
		headers.set("HTTP-Referer", "https://www.aeon.fun");
		headers.set("X-OpenRouter-Title", "Aeon");
		headers.set("X-Title", "Aeon");
		headers.set("X-OpenRouter-Categories", "personal-agent,cloud-agent");
		return base(input, { ...init, headers });
	};
	Object.assign(wrapped, base, { [WRAPPED]: true });
	globalThis.fetch = wrapped;
}
