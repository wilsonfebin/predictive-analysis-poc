import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const root = '/Users/admin/Documents/Codex/predictive-analysis-poc';
const skillDir = '/Users/admin/.codex/plugins/cache/openai-primary-runtime/presentations/26.1105.12137/skills/presentations';
const buildDir = path.join(root, '.presentation-build/llm-poc');
const finalPath = path.join(root, '.presentation-output/Marine_AI_Predictive_Maintenance_POC_v2.pptx');
const deck = Presentation.create({slideSize:{width:1280,height:720}});
const C={bg:'#0B1424',panel:'#111E30',panel2:'#162438',line:'#26374D',white:'#EAF1FC',muted:'#91A3BD',blue:'#377CF6',cyan:'#55A8FF',green:'#28C99A',amber:'#FFB81C',red:'#F87171'};
const FONT='Arial';
function shape(slide,geometry,x,y,w,h,fill='none',stroke='none',sw=0){return slide.shapes.add({geometry,position:{left:x,top:y,width:w,height:h},fill,line:{style:'solid',fill:stroke,width:sw}})}
function text(slide,value,x,y,w,h,size,color=C.white,bold=false,opts={}){
 const s=shape(slide,'textbox',x,y,w,h);
 s.text=value;
 s.text.style={fontFamily:FONT,fontSize:size,color,bold,verticalAlignment:'middle',alignment:opts.align||'left',wrap:true};
 return s;
}
function rect(slide,x,y,w,h,fill=C.panel,stroke=C.line,r=18){return slide.shapes.add({geometry:'roundRect',position:{left:x,top:y,width:w,height:h},fill,line:{style:'solid',fill:stroke,width:1},borderRadius:r});}
function base(title,kicker='DG-01 · VESSEL-01'){
 const s=deck.slides.add(); s.background.fill=C.bg;
 text(s,kicker.toUpperCase(),44,26,700,22,12,C.cyan,true);
 text(s,title,44,52,1180,52,32,C.white,true);
 shape(s,'line',44,112,1192,1,'none',C.line,1);
 text(s,'Synthetic POC · Advisory only · No vessel or maintenance system is connected',44,684,1100,20,11,C.muted,false);
 return s;
}
async function imageBytes(p){const b=await fs.readFile(p);return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)}
async function screenshot(slide,p,x,y,w,h,alt){
 rect(slide,x-8,y-8,w+16,h+16,C.panel,C.line,14);
 slide.images.add({blob:await imageBytes(p),contentType:'image/png',alt,fit:'contain',position:{left:x,top:y,width:w,height:h}});
}
function noteBlock(slide,x,y,w,title,body,color=C.blue){
 shape(slide,'roundRect',x,y,4,78,color,'none',2);
 text(slide,title,x+18,y,w-20,22,15,C.white,true);
 text(slide,body,x+18,y+26,w-20,56,14,C.muted,false);
}

// Cover: entirely editable vector shapes, no screenshot reused.
{
 const s=deck.slides.add(); s.background.fill=C.bg;
 shape(s,'ellipse',820,112,340,340,'#10253F','none');
 shape(s,'ellipse',875,167,230,230,'#17365C','none');
 shape(s,'ellipse',940,232,100,100,C.blue,'none');
 shape(s,'line',780,430,390,0,'none',C.green,5);
 shape(s,'line',780,451,320,0,'none',C.cyan,3);
 text(s,'MARINE AI · PREDICTIVE MAINTENANCE',62,72,650,28,14,C.cyan,true);
 text(s,'Generator condition\nmonitoring POC',62,165,690,170,48,C.white,true);
 text(s,'DG-01 · VESSEL-01',66,365,620,32,23,C.muted,true);
 rect(s,64,438,510,74,C.panel,C.line,16);
 text(s,'30 days of synthetic telemetry · 36 signals · 1-minute sampling',84,454,470,42,16,C.white,false);
 text(s,'Predictive findings, sensor diagnostics, engineering review and an auditable workflow',66,550,680,56,18,C.muted,false);
 text(s,'Synthetic demonstration · not validated real-vessel performance',66,666,760,20,12,C.amber,true);
}

const shot1='/Users/admin/Desktop/Screenshot 2026-11-12 at 12.13.11.png';
const shot2='/Users/admin/Desktop/Screenshot 2026-11-12 at 12.13.25.png';
const shot3='/Users/admin/Desktop/Screenshot 2026-11-12 at 12.13.54.png';
const shot4='/Users/admin/Desktop/Screenshot 2026-11-12 at 12.14.53.png';
const shot5='/Users/admin/Desktop/Screenshot 2026-11-12 at 12.15.21.png';
const shot6='/Users/admin/Desktop/Screenshot 2026-11-12 at 12.15.42.png';
const shot7='/Users/admin/Desktop/Screenshot 2026-11-12 at 12.36.10.png';

// Architecture and stack slides appear after the cover and before the UI walkthrough.
{
 const s=base('High-level architecture','SYSTEM DESIGN · BOUNDED AND ADVISORY');
 const card=(x,y,w,h,title,body,accent)=>{
   rect(s,x,y,w,h,C.panel,C.line,15); shape(s,'roundRect',x,y,5,h,accent,'none',2);
   text(s,title,x+18,y+14,w-32,26,17,C.white,true);
   text(s,body,x+18,y+49,w-32,h-56,13,C.muted,false);
 };
 card(48,180,255,148,'Synthetic inputs','Minute telemetry, tags, context, maintenance reference and separate ground truth.',C.blue);
 card(355,180,272,148,'Predictive analytics','Quality filters, running-state checks, healthy baseline, expected values, residual persistence and routing.',C.green);
 card(680,180,250,148,'FastAPI service','Role checks, finding and sensor endpoints, workflow requests and decision recording.',C.cyan);
 card(983,180,248,148,'Streamlit UI','Engineering views for trends, findings, recommendations and human review.',C.amber);
 text(s,'→',308,231,42,40,30,C.cyan,true,{align:'center'});
 text(s,'→',633,231,42,40,30,C.cyan,true,{align:'center'});
 text(s,'→',936,231,42,40,30,C.cyan,true,{align:'center'});
 card(540,405,525,120,'Persistence and wording services','SQLite stores investigations, workflow versions and decisions. LangGraph handles bounded wording; Template fallback and optional OpenAI.',C.amber);
 text(s,'↕',785,337,40,48,27,C.amber,true,{align:'center'});
 text(s,'Optional model use changes wording only. Detection, severity, recommendations and approval remain deterministic or human-controlled.',540,548,525,54,13,C.muted,false);
 text(s,'No live vessel, ERP or PMS connection · No automatic maintenance execution',48,590,1180,34,15,C.amber,true);
}
{
 const s=base('Technology stack','IMPLEMENTATION · SMALL PYTHON APPLICATION');
 const cols=[
  {x:50,title:'Data and analytics',accent:C.blue,rows:['Python 3.11','Standard-library predictive pipeline','Context-aware expected values','Quality, persistence and alarm evaluation']},
  {x:355,title:'API and persistence',accent:C.green,rows:['FastAPI','SQLite','Role enforcement in backend','Investigation and decision audit records']},
  {x:660,title:'User interface',accent:C.cyan,rows:['Streamlit','Plotly','Overview, sensor, findings and review screens','IST display; UTC timestamps retained in data']},
  {x:965,title:'Optional wording',accent:C.amber,rows:['LangGraph bounded workflow','OpenAI API optional','Template mode works without credentials','Validated wording; deterministic fallback']},
 ];
 for(const c of cols){
   rect(s,c.x,170,265,370,C.panel,C.line,18); shape(s,'roundRect',c.x,170,265,7,c.accent,'none',2);
   text(s,c.title,c.x+20,194,225,34,20,C.white,true);
   let y=254;
   for(const row of c.rows){shape(s,'ellipse',c.x+22,y+7,8,8,c.accent,'none');text(s,row,c.x+40,y,202,52,15,C.muted,false);y+=64;}
 }
 text(s,'All results shown in this presentation use synthetic data. The POC is advisory and does not establish real-world predictive performance.',50,585,1150,55,15,C.amber,true);
}

{
 const s=base('Generator overview','01 · OPERATING PICTURE');
 await screenshot(s,shot1,50,138,835,500,'Generator overview showing synthetic operating state, load, findings, severity and review status');
 noteBlock(s,925,165,290,'Operating context','Running state and latest recorded load sit alongside open finding and review counts.',C.blue);
 noteBlock(s,925,270,290,'Finding mix','Severity distribution and the review queue make the active workload visible.',C.amber);
 noteBlock(s,925,375,290,'Audit context','Displayed timestamps use IST. The dashboard labels this as synthetic, advisory data.',C.green);
 text(s,'Dashboard summary for one synthetic generator asset',925,525,290,54,17,C.white,true);
}
{
 const s=base('Predictive signal and fixed-alarm comparison','02 · COOLING TREND');
 await screenshot(s,shot2,48,136,820,495,'Jacket water outlet trend with tolerance residual, alarm threshold, detection time and quality strip');
 noteBlock(s,910,155,310,'Expected vs actual','The trend view overlays the healthy expectation and measured jacket-water outlet temperature.',C.cyan);
 noteBlock(s,910,258,310,'Early warning','The screenshot reports detection 272.9 hours before its configured 96 °C fixed alarm.',C.green);
 noteBlock(s,910,361,310,'Quality evidence','Invalid observations are shown separately; the residual panel shows deviation against tolerance.',C.amber);
 text(s,'Illustrative synthetic evaluation. Alarm settings and model assumptions require domain validation.',910,500,306,78,14,C.muted,false);
}
{
 const s=base('Sensor monitoring','03 · SIGNAL DETAIL');
 await screenshot(s,shot3,45,133,690,525,'Sensor monitoring screen with sensor selection, date range, quality distribution and actual versus expected chart');
 noteBlock(s,780,160,430,'Select and inspect','Choose a signal and date range, then compare the measured value with its expected behaviour.',C.blue);
 noteBlock(s,780,268,430,'Check data quality','Quality distribution and valid-observation counts help reviewers interpret a trend before acting.',C.amber);
 noteBlock(s,780,376,430,'Review residuals','A separate residual panel makes the gap between actual and expected readings easier to assess.',C.green);
 text(s,'Readings, quality flags and timestamps are displayed in IST.',780,530,430,40,15,C.muted,false);
}
{
 const s=base('Findings and severity','04 · REVIEW QUEUE');
 await screenshot(s,shot4,50,138,790,515,'Findings register with type, system, initial and current severity, status and detected IST time');
 noteBlock(s,875,168,340,'Grouped findings','The register distinguishes machinery degradation from sensor faults and identifies the affected system.',C.blue);
 noteBlock(s,875,278,340,'Severity progression','Initial-to-current severity and escalation history show how a finding changed over time.',C.amber);
 noteBlock(s,875,388,340,'Evidence-led review','Affected signals, actual-versus-expected evidence and recommended next actions are visible in the detail view.',C.green);
 text(s,'Human review remains required; findings do not create work orders automatically.',875,535,340,68,14,C.muted,false);
}
{
 const s=base('Maintenance review and optional OpenAI wording','05 · HUMAN DECISION');
 await screenshot(s,shot5,46,132,710,530,'Maintenance review with deterministic finding summary, recommendation, evidence, source label and review actions');
 noteBlock(s,795,155,420,'Deterministic decision support','Finding classification, severity, evidence and recommended action remain rule-based.',C.blue);
 noteBlock(s,795,266,420,'Selectable wording','Reviewer can use Template or OpenAI wording and regenerate wording for an existing run.',C.cyan);
 noteBlock(s,795,377,420,'Safe fallback','When OpenAI is unavailable or output fails validation, template wording is used and labeled.',C.green);
 text(s,'Approval or rejection is a separate human action with a required rationale.',795,530,420,70,14,C.amber,true);
}
{
 const s=base('Maintenance investigation and decision','06 · HUMAN REVIEW');
 await screenshot(s,shot7,48,136,850,536,'Maintenance review showing open finding evidence, investigation note, decision rationale and approval or rejection controls');
 noteBlock(s,945,175,275,'Investigation','Capture checks and observations before preparing a recommendation.',C.blue);
 noteBlock(s,945,285,275,'Decision rationale','Chief Engineer approval or rejection requires a recorded rationale.',C.amber);
 noteBlock(s,945,395,275,'Status in context','The screenshot shows an open machinery finding with evidence and a proposed cooling-water cooler inspection.',C.green);
 text(s,'Approval remains a human decision; the workflow does not execute maintenance.',945,535,270,64,14,C.muted,false);
}
{
 const s=base('Audit history','07 · GOVERNANCE');
 await screenshot(s,shot6,48,150,1182,330,'Audit history table listing investigation, workflow, approval and rejection events with actor and IST timestamps');
 noteBlock(s,65,532,355,'Actor and role','Recorded events show who investigated or made a decision and their assigned role.',C.blue);
 noteBlock(s,455,532,355,'Time and rationale','Timestamps display in IST; decisions retain the recorded rationale or note.',C.amber);
 noteBlock(s,845,532,360,'Append-only trail','Workflow runs and review decisions remain available for later inspection.',C.green);
}

for (const [i,s] of deck.slides.items.entries()) {
 const png=await deck.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(buildDir,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
const pptx=await PresentationFile.exportPptx(deck);
const candidate=path.join(buildDir,'candidate.pptx');
await pptx.save(candidate);
const { finalizePresentation }=await import(pathToFileURL(path.join(skillDir,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({
 explicitTotalSlideCount:10,
 requiredNativeTableOwnerSlides:[],
 requiredNativeChartOwnerSlides:[],
 workspaceDir:root,
 candidatePath:candidate,
 finalPath,
 pythonExecutable:'/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',
 integrityValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 fontPolicy:{basis:'design',families:[FONT]},
 verifyArtifactToolImport:true,
 receiptPath:path.join(buildDir,'validation-v2.json'),
});
console.log(JSON.stringify({finalPath,result,slides:deck.slides.items.length},null,2));
