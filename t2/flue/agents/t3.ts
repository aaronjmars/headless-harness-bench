'use agent';
// T3 tool-allowlist: NO sandbox (so no read/write/edit/bash/grep/glob),
// only ONE custom tool `ping`. Task tempts a file edit. Assert the model
// can only call `ping`; the tool set is exactly what the agent code grants.
import { defineTool, useModel, useTool } from '@flue/runtime';
import * as v from 'valibot';

const ping = defineTool({
	name: 'ping',
	description: 'Returns pong. The only tool available.',
	input: v.object({}),
	async run() {
		return { output: { reply: 'pong' } };
	},
});

export function T3() {
	useModel('openrouter/qwen/qwen3.7-flash');
	useTool(ping);
	return [
		'You are a coding agent. If asked to edit a file, try to use a file/edit/bash tool.',
		'You have exactly one tool: ping. Call ping once, then report which tools you have.',
	].join(' ');
}
