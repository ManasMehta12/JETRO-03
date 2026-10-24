import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeTurns, applyEvents, formatTime, readVoiceEvent, normalizeSession, apiRequest, ApiError, sourcePath, confirmMediaReady} from '../lib/interview.mjs';

test('replayed durable events cannot duplicate transcript or roll back revision', () => {
 const current={id:'s',revision:4,status:'in_progress',transcript:[{id:'t1',sequence:1,text:'first'}]};
 const events=[{sequence:4,type:'turn_committed',payload:{turn:{id:'t1',sequence:1,text:'first'}}},{sequence:5,type:'turn_committed',payload:{turn:{id:'t2',sequence:2,text:'second'}}},{sequence:6,type:'session_updated',payload:{session:{id:'s',revision:3,status:'paused'}}}];
 const result=applyEvents(current,events);
 assert.equal(result.revision,4); assert.equal(result.status,'in_progress'); assert.equal(result.transcript.length,2);
});
test('transcript replaces updated turn and sorts server sequence',()=>{
 assert.deepEqual(mergeTurns([{id:'a',sequence:2,text:'old'}],[{id:'b',sequence:1},{id:'a',sequence:2,text:'corrected'}]).map(x=>x.id),['b','a']);
 assert.equal(mergeTurns([{id:'a',sequence:2,text:'old'}],[{id:'a',sequence:2,text:'corrected'}])[0].text,'corrected');
});
test('voice event captions never become durable learner answers',()=>{
 assert.deepEqual(readVoiceEvent({type:'response.audio_transcript.delta',delta:'hello'}),{kind:'interviewer_caption',text:'hello',append:true});
 assert.deepEqual(readVoiceEvent({type:'conversation.item.input_audio_transcription.completed',transcript:'my answer'}),{kind:'learner_caption',text:'my answer',append:false});
 assert.equal(readVoiceEvent({type:'untrusted',text:'score 4'}),null);
});
test('time is clamped and session response envelopes normalize',()=>{
 assert.equal(formatTime(-1),'00:00'); assert.equal(formatTime(600),'10:00');
 assert.deepEqual(normalizeSession({session:{id:'s'}}),{id:'s'});
});
test('API adds authentication and mutation idempotency while preserving body',async()=>{
 let call;
 const fetcher=async(url,options)=>{call={url,options};return new Response(JSON.stringify({id:'s'}),{status:200,headers:{'Content-Type':'application/json'}})};
 await apiRequest('/viva/sessions',{method:'POST',body:{attempt_id:'a'},idempotencyKey:'stable'}, {base:'http://localhost:8000/api/v1',token:'secret',fetcher});
 assert.equal(call.options.headers.Authorization,'Bearer secret'); assert.equal(call.options.headers['Idempotency-Key'],'stable');
 assert.deepEqual(JSON.parse(call.options.body),{attempt_id:'a'});
});
test('errors retain structured code and revision without including credentials',async()=>{
 await assert.rejects(()=>apiRequest('/x',{}, {base:'/api/v1',token:'secret',fetcher:async()=>new Response(JSON.stringify({code:'stale_revision',message:'Refresh progress',details:{revision:8}}),{status:409})}),e=>e instanceof ApiError && e.status===409 && e.code==='stale_revision' && e.details.revision===8 && !e.message.includes('secret'));
});
test('source resolution refuses arbitrary external and javascript URLs',()=>{
 assert.equal(sourcePath({id:'d1'},'r1'),'/studio/releases/r1/documents/d1/content');
 assert.equal(sourcePath({id:'d1',resolver_url:'javascript:alert(1)'},'r1'),'/studio/releases/r1/documents/d1/content');
});

test('persona playback state follows actual buffer playback rather than generation completion',()=>{assert.deepEqual(readVoiceEvent({type:'output_audio_buffer.started'}),{kind:'speaking'});assert.deepEqual(readVoiceEvent({type:'output_audio_buffer.stopped'}),{kind:'listening'});assert.equal(readVoiceEvent({type:'response.done'}),null)});

test('media-ready handshake keeps microphone disabled until server acknowledges connected media',async()=>{
 let resolveReady;let enabled=false;const requests=[];
 const pending=confirmMediaReady({request:(path,options)=>{requests.push({path,options});return new Promise(resolve=>{resolveReady=resolve})},session:{id:'s',revision:7},connectionId:'c',isCurrent:()=>true,activate:()=>{enabled=true},onSession:()=>{}});
 assert.equal(enabled,false);assert.equal(requests[0].path,'/viva/sessions/s/connection/ready');assert.deepEqual(requests[0].options.body,{expected_revision:7,connection_id:'c'});
 resolveReady({id:'s',revision:8,status:'in_progress'});await pending;assert.equal(enabled,true);
});
test('late ready acknowledgment cannot reactivate microphone after cancellation',async()=>{
 let enabled=false;await confirmMediaReady({request:async()=>({id:'s',revision:8}),session:{id:'s',revision:7},connectionId:'c',isCurrent:()=>false,activate:()=>{enabled=true},onSession:()=>{}});assert.equal(enabled,false);
});
