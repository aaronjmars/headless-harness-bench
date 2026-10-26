const {spawn,spawnSync,execSync}=require("child_process");
const fs=require("fs"),path=require("path");
const OUT=__dirname, TOOL=path.join(OUT,"../../scripts/tier2_sweep.py");
function keeper(args){
  const r=spawnSync("python3",[TOOL,...args],{encoding:"utf8",env:{...process.env,TIER2_AUTH_DIR:process.env.H2||""}});
  if(r.status!==0) throw Error("Tier-2 sweep keeper failed: "+(r.stderr||"unknown error"));
  return r.stdout.trim();
}
const sweep=keeper(["start"]);
let childRc=1,err="",out="",detectedAt=0,killed=false;
process.on("exit",()=>{
  let failed=false;
  try {
    fs.writeFileSync(path.join(OUT,"t6.out"),out);
    fs.writeFileSync(path.join(OUT,"t6.err"),err);
    keeper(["trial","--sweep",sweep,"--out",OUT,"--subject","fx","--name","t6","--rc",String(childRc),...(killed?["--expected-cancel"]:[])]);
  } catch(e){console.error(e.message);failed=true;}
  try {
    keeper(["finish","--sweep",sweep,"--out",OUT,"--rc",String(failed?1:(killed?0:childRc))]);
  } catch(e){console.error(e.message);failed=true;}
  if(failed) process.exitCode=1;
});
const BASE=process.env.BASE,H2=process.env.H2;
const fx=spawn("fx",["ask","--json","--yolo","--no-save",
  "Use your shell tool to run the command `sleep 60` and wait for it to complete, then say done."],
  {cwd:BASE+"/fixture",env:{...process.env,HOME:H2}});
fx.stdout.on("data",d=>out+=d);
fx.stderr.on("data",d=>err+=d);
fx.on("exit",(c,s)=>{childRc=c===null?1:c;console.log("[fx exit] code="+c+" signal="+s+" at +"+(Date.now()-t0)+"ms");});
const t0=Date.now();
// exact-cmdline match: only the real child whose full argv == "sleep 60"
const realSleep=()=>{try{return execSync("pgrep -x -f 'sleep 60'").toString().trim()}catch(e){return""}};
const iv=setInterval(()=>{
  const el=Date.now()-t0;
  const child=realSleep();
  if(child && !detectedAt){detectedAt=el;console.log("[+"+el+"ms] REAL sleep 60 child pid(s): "+child.replace(/\n/g,","));}
  // operator cancels ~5s after the sleep actually starts (no --timeout flag exists)
  if(detectedAt && !killed && el>=detectedAt+5000){
    killed=true;fx.kill("SIGKILL");
    console.log("[+"+el+"ms] SIGKILL fx (pid "+fx.pid+") ~5s after sleep began");
    setTimeout(()=>{
      const after=realSleep();
      console.log("[orphan check +2s] sleep 60 still alive? "+(after?("YES ORPHAN -> "+after.replace(/\n/g,",")):"NO (clean kill)"));
      try{execSync("pkill -x -f 'sleep 60'")}catch(e){}
      clearInterval(iv);
    },2000);
  }
  if(el>50000){console.log("[timeout] no real sleep child in 50s; capture_bytes="+out.length);fx.kill("SIGKILL");try{execSync("pkill -x -f 'sleep 60'")}catch(e){}clearInterval(iv);}
},400);
function interrupt(code){
  process.exitCode=code;
  clearInterval(iv);
  if(fx.exitCode!==null || fx.signalCode!==null) return;
  fx.once("close",()=>process.exit(code));
  fx.kill("SIGKILL");
}
process.once("SIGINT",()=>interrupt(130));
process.once("SIGTERM",()=>interrupt(143));
