'use agent';
import { useModel, useSandbox } from '@flue/runtime';
import { local } from '@flue/runtime/node';

export function Coder() {
	useModel('openrouter/qwen/qwen3.7-flash');
	useSandbox(local(), { cwd: '/tmp/hhb-work/flue/gt' });
	return [
		'You are a coding agent working in the current directory.',
		'Task: add a `--version` flag to the CLI (cli.js) that prints the version',
		'from package.json metadata. Edit only cli.js. When done, print DONE_GT.',
	].join(' ');
}
