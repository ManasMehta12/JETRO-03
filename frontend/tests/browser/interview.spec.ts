import {expect,test} from '@playwright/test';
import type {Session,Report} from '../../lib/types';
const makeSession=():Session=>({id:'session-1',attempt_id:'attempt-1',release_id:'release-1',revision:1,status:'in_progress',input_mode:'text',answered_count:0,question_count:3,current_question:{id:'q1',prompt:'Explain your choice.'},transcript:[{id:'turn-1',sequence:1,speaker:'interviewer',question_id:'q1',text:'Explain your choice.'}],last_event_sequence:1});
const makeReport=(session:Session):Report=>({id:'report-1',session_id:session.id,attempt_id:session.attempt_id,release_id:session.release_id,completion:session.answered_count===3?'complete':'incomplete',finish_reason:session.answered_count===3?'questions_complete':'learner_finished',assessments:[{dimension:'technical_correctness',status:'not_assessed',score:null,rationale:'Fixture mode does not grade arbitrary text.'}],strengths:[],misconceptions:[],missed_topics:[],recommendations:['Review the source documents.'],playground_scores:[{name:'decision_accuracy',earned:0,available:4}],critical_error:true,transcript:session.transcript,source_index:[{document:{id:'d1',title:'Approved inspection notes',version:'1',availability:'available'},usage:'available_unused'},{document:{id:'d2',title:'Expert clarification',version:'2',availability:'available'},usage:'available_unused'}],assessment_notice:'AI-assisted assessment. Supervised practical assessment is still required.'});

test('text interview reloads, completes, preserves critical errors, and indexes every source',async({page})=>{
 let session=makeSession();let accepted=0;let sourceRequests=0;
 await page.route('**/api/v1/**',async route=>{const path=new URL(route.request().url()).pathname;const method=route.request().method();
  expect(route.request().headers().authorization).toBe('Bearer demo-learner-token');
  if(path.endsWith('/bootstrap'))return route.fulfill({json:{provider_mode:'fixture',learner_id:'learner',release:{id:'release-1'},attempts:[{id:'attempt-1',title:'Bearing inspection',scenario_id:'bearing'}]}});
  if(path.endsWith('/events'))return route.fulfill({json:{events:[],next_after:1,has_more:false}});
  if(path.endsWith('/answers')){expect(route.request().headers()['idempotency-key']).toBeTruthy();const body=route.request().postDataJSON();expect(body.question_id).toBe(session.current_question?.id);accepted++;session={...session,revision:session.revision+1,answered_count:accepted,transcript:[...session.transcript,{id:`a${accepted}`,sequence:accepted*2,speaker:'learner',text:body.text,question_id:body.question_id}]};if(accepted<3){session.current_question={id:`q${accepted+1}`,prompt:accepted===1?'What changes under a changed condition?':'When is the evidence insufficient?'};session.transcript.push({id:`t${accepted+1}`,sequence:accepted*2+1,speaker:'interviewer',text:session.current_question.prompt,question_id:session.current_question.id})}else{session.status='completed';session.current_question=null}return route.fulfill({json:{session,turn:session.transcript[session.transcript.length-1]}})}
  if(path.endsWith('/result'))return route.fulfill({json:makeReport(session)});
  if(path.endsWith('/content')){sourceRequests++;return route.fulfill({contentType:'text/plain',body:'Approved source content.'})}
  if(path.endsWith('/sessions')&&method==='POST')return route.fulfill({json:session});
  if(path.endsWith('/session-1'))return route.fulfill({json:session});
  return route.fulfill({status:404,json:{message:'Unknown fixture route'}});
 });
 await page.goto('/');await expect(page.getByText('DEMO FIXTURE',{exact:true})).toBeVisible();
 await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Begin technical Viva'}).click();
 await expect(page.getByText('Explain your choice.',{exact:true})).toBeVisible();
 await expect(page.getByText('Your scores and feedback appear after the interview.',{exact:false})).toBeVisible();
 await page.getByLabel('Your answer',{exact:true}).fill('I inspect the available observations before deciding.');await page.getByRole('button',{name:'Send answer'}).click();
 await expect(page.getByText('What changes under a changed condition?',{exact:true})).toBeVisible();await page.reload();
 await expect(page.getByRole('heading',{name:'Your conversation'})).toBeVisible();await expect(page.getByText('I inspect the available observations before deciding.',{exact:true})).toBeVisible();
 await page.getByLabel('Your answer',{exact:true}).fill('I would reconsider the decision against the changed observation.');await page.getByRole('button',{name:'Send answer'}).click();
 await expect(page.getByText('When is the evidence insufficient?',{exact:true})).toBeVisible();await page.getByLabel('Your answer',{exact:true}).fill('I escalate when approved evidence is insufficient.');await page.getByRole('button',{name:'Send answer'}).click();
 await expect(page.getByRole('heading',{name:'Reasoning, made visible.'})).toBeVisible();
 await expect(page.getByText('A critical Playground error remains unresolved.',{exact:true})).toBeVisible();
 await expect(page.getByText('Approved inspection notes',{exact:true})).toBeVisible();await expect(page.getByText('Expert clarification',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Open source ↗'}).first().click();await expect.poll(()=>sourceRequests).toBe(1);
 await page.getByRole('button',{name:'Print report'}).focus();await expect(page.getByRole('button',{name:'Print report'})).toBeFocused();
 expect(accepted).toBe(3);
});

test('finish early produces an explicitly incomplete report with unassessed scores',async({page})=>{
 let session=makeSession();
 await page.route('**/api/v1/**',async route=>{const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/bootstrap'))return route.fulfill({json:{provider_mode:'fixture',learner_id:'learner',release:{id:'release-1'},attempts:[{id:'attempt-1',title:'Bearing inspection',scenario_id:'bearing'}]}});
  if(path.endsWith('/events'))return route.fulfill({json:{events:[],next_after:1,has_more:false}});
  if(path.endsWith('/finish')){session={...session,status:'completed',revision:2};return route.fulfill({json:{id:'job-1',status:'completed'}})}
  if(path.endsWith('/result'))return route.fulfill({json:makeReport(session)});
  return route.fulfill({json:session});
 });
 page.on('dialog',dialog=>dialog.accept());await page.goto('/');await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Begin technical Viva'}).click();await page.getByRole('button',{name:'Finish interview'}).click();
 await expect(page.getByText('incomplete interview',{exact:true})).toBeVisible();await expect(page.getByText('Fixture mode does not grade arbitrary text.',{exact:true})).toBeVisible();
});

test('voice microphone stays disabled until authorized backend negotiation completes',async({page})=>{
 let session={...makeSession(),input_mode:'voice' as const,status:'created'};let verified=false;
 await page.addInitScript(()=>{
  const track={enabled:true,stopped:false,stop(){this.stopped=true},kind:'audio'};Object.assign(window,{__testMic:track});
  Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:async()=>({getTracks:()=>[track],getAudioTracks:()=>[track]})}});
  class Peer {connectionState='new';onconnectionstatechange:(()=>void)|null=null;ontrack=null;addTrack(){}createDataChannel(){return {readyState:'open',onmessage:null,send(){},close(){}}}async createOffer(){return {sdp:'test-offer',type:'offer'}}async setLocalDescription(){}async setRemoteDescription(){this.connectionState='connected';this.onconnectionstatechange?.()}close(){this.connectionState='closed'}}
  Object.assign(window,{RTCPeerConnection:Peer});
 });
 await page.route('**/api/v1/**',async route=>{const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/bootstrap'))return route.fulfill({json:{provider_mode:'openai',learner_id:'learner',release:{id:'release-1'},attempts:[{id:'attempt-1',title:'Bearing inspection',scenario_id:'bearing'}]}});
  if(path.endsWith('/events'))return route.fulfill({json:{events:[],next_after:1,has_more:false}});
  if(path.endsWith('/connection')){expect(await page.evaluate(()=>((window as unknown as {__testMic:{enabled:boolean}}).__testMic.enabled))).toBe(false);session={...session,status:'connecting',revision:2};return route.fulfill({json:{session,connection_id:'conn-1',sdp_answer:'test-answer'}})}
  if(path.endsWith('/connection/ready')){expect(await page.evaluate(()=>((window as unknown as {__testMic:{enabled:boolean}}).__testMic.enabled))).toBe(false);expect(route.request().postDataJSON()).toEqual({expected_revision:2,connection_id:'conn-1'});verified=true;session={...session,status:'in_progress',revision:3};return route.fulfill({json:session})}
  if(path.endsWith('/finish')){expect(await page.evaluate(()=>((window as unknown as {__testMic:{enabled:boolean;stopped:boolean}}).__testMic))).toMatchObject({enabled:false,stopped:false});session={...session,status:'evaluating',revision:4};return route.fulfill({json:{id:'job-1',status:'queued'}})}
  return route.fulfill({json:session});
 });
 page.on('dialog',dialog=>dialog.accept());await page.goto('/');await page.getByRole('button',{name:'Speak naturally',exact:false}).click();await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Begin technical Viva'}).click();
 await expect(page.getByText('Live audio connected',{exact:true})).toBeVisible();expect(verified).toBe(true);expect(await page.evaluate(()=>((window as unknown as {__testMic:{enabled:boolean}}).__testMic.enabled))).toBe(true);await page.getByRole('button',{name:'Finish interview'}).click();expect(await page.evaluate(()=>((window as unknown as {__testMic:{stopped:boolean}}).__testMic.stopped))).toBe(true);
});
