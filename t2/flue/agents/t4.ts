'use agent';
// T4 system-prompt injection: the returned string IS the system prompt.
// Inject a sentinel instruction; assert the reply obeys it.
import { useModel } from '@flue/runtime';

export function T4() {
	useModel('openrouter/qwen/qwen3.7-flash');
	return 'You are terse. Always end your final message with the exact token SENTINEL_9Z on its own line.';
}
