'use agent';
// T5 env isolation (virtual sandbox): in-memory just-bash cannot see host env.
import { bash, useModel, useSandbox } from '@flue/runtime';
import { Bash, InMemoryFs } from 'just-bash';

export function T5v() {
	useModel('openrouter/qwen/qwen3.7-flash');
	useSandbox(bash(() => new Bash({ fs: new InMemoryFs() })));
	return 'Run this exact bash command and report its raw output verbatim: env | grep DECOY || echo NO_DECOY';
}
