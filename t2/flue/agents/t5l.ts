'use agent';
// T5 env isolation (local sandbox): local() binds host shell, so host env leaks.
import { useModel, useSandbox } from '@flue/runtime';
import { local } from '@flue/runtime/node';

export function T5l() {
	useModel('openrouter/qwen/qwen3.7-flash');
	useSandbox(local());
	return 'Run this exact bash command and report its raw output verbatim: env | grep DECOY || echo NO_DECOY';
}
