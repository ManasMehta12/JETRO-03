export class ApiError extends Error {
  constructor(status, body) {super(body?.message || `Request failed (${status})`); this.name='ApiError';this.status=status;this.code=body?.code || 'request_failed';this.details=body?.details || {};}
}
export async function apiRequest(path, options={}, config={}) {
  const headers={Authorization:`Bearer ${config.token || ''}`, ...options.headers};
  if(options.body!==undefined) headers['Content-Type']='application/json';
  const method=options.method || 'GET';
  if(!['GET','HEAD'].includes(method)) headers['Idempotency-Key']=options.idempotencyKey || globalThis.crypto.randomUUID();
  const response=await (config.fetcher || fetch)(`${config.base || '/api/v1'}${path}`,{method,headers,body:options.body===undefined?undefined:JSON.stringify(options.body),signal:options.signal,cache:'no-store'});
  if(!response.ok){let data;try{data=await response.json()}catch{data={message:'The service could not complete this request.'}}throw new ApiError(response.status,data)}
  if(options.blob)return response.blob();
  return response.status===204 ? null : response.json();
}
export function normalizeSession(value) {return value?.session || value;}
export function mergeTurns(oldTurns=[],newTurns=[]) {
 const turns=new Map(oldTurns.map(t=>[t.id,t]));for(const t of newTurns)if(t?.id)turns.set(t.id,{...turns.get(t.id),...t});
 return [...turns.values()].sort((a,b)=>(a.sequence||0)-(b.sequence||0));
}
export function applyEvents(session,events=[]) {
 if(!session)return session;
 let next={...session,transcript:[...(session.transcript || [])]};
 for(const event of events){const payload=event.payload || {};const update=payload.session || (event.type==='session_updated' && payload.id ? payload : null);
  if(update && (update.revision ?? 0)>=(next.revision ?? 0))next={...next,...update,transcript:mergeTurns(next.transcript,update.transcript)};
  const turn=payload.turn || (event.type==='turn_committed' && payload.id ? payload : null);
  if(turn)next.transcript=mergeTurns(next.transcript,[turn]);
 }
 return next;
}
export function formatTime(seconds) {const value=Math.max(0,Math.floor(seconds || 0));return `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`;}
export function readVoiceEvent(event) {
 if(['response.audio_transcript.delta','response.output_audio_transcript.delta'].includes(event.type))return {kind:'interviewer_caption',text:event.delta || '',append:true};
 if(['response.audio_transcript.done','response.output_audio_transcript.done'].includes(event.type))return {kind:'interviewer_caption',text:event.transcript || '',append:false};
 if(event.type==='conversation.item.input_audio_transcription.completed')return {kind:'learner_caption',text:event.transcript || '',append:false};
 if(event.type==='output_audio_buffer.started')return {kind:'speaking'};
 if(['output_audio_buffer.stopped','output_audio_buffer.cleared'].includes(event.type))return {kind:'listening'};
 if(event.type==='input_audio_buffer.speech_started')return {kind:'listening'};
 if(event.type==='input_audio_buffer.speech_stopped')return {kind:'thinking'};
 if(event.type==='error')return {kind:'error',text:event.error?.message || 'Voice connection interrupted.'};
 return null;
}
export function sourcePath(document,releaseId){return `/studio/releases/${encodeURIComponent(releaseId)}/documents/${encodeURIComponent(document.id)}/content`;}
export async function confirmMediaReady({request,session,connectionId,isCurrent,activate,onSession}) {
 const ready=normalizeSession(await request(`/viva/sessions/${encodeURIComponent(session.id)}/connection/ready`,{method:'POST',idempotencyKey:globalThis.crypto.randomUUID(),body:{expected_revision:session.revision,connection_id:connectionId}}));
 if(!isCurrent())return false;
 onSession(ready);activate();return true;
}
