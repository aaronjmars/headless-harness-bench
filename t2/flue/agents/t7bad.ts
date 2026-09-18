'use agent';
// T7 cascade shape (bad model id): assert the terminal error is machine-readable.
import { useModel } from '@flue/runtime';

export function T7bad() {
	useModel('openrouter/qwen/this-model-does-not-exist-9z');
	return 'You are terse.';
}
