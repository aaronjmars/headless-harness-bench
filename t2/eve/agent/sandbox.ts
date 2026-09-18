import { defineSandbox } from "eve/sandbox";
import { docker } from "eve/sandbox/docker";

// Real Linux container (eve's published image ships node + common tools).
// Isolated from host env by default; the workspace/ subtree is seeded in.
export default defineSandbox({ backend: docker() });
