'use agent';
// T6 cancellation: local() sandbox runs a long real subprocess. We kill
// `flue run` mid-flight and assert no orphaned `sleep` survives.
import { useModel, useSandbox } from '@flue/runtime';
import { local } from '@flue/runtime/node';

export function T6() {
	useModel('openrouter/qwen/qwen3.7-flash');
	useSandbox(local());
	return 'Run this exact bash command (it takes a while) and report when done: sleep 30 && echo SLEPT';
}
