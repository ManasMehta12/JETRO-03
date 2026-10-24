'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {confirmMediaReady,readVoiceEvent} from './interview.mjs';
import type {PersonaState,Session} from './types';
type Request=<T>(path:string,options?:{method?:string;body?:unknown;idempotencyKey?:string})=>Promise<T>;
export function useVoice(request:Request,onSession:(s:Session)=>void){
 const [status,setStatus]=useState('disconnected');const [muted,setMuted]=useState(false);const [caption,setCaption]=useState('');const [learnerCaption,setLearnerCaption]=useState('');const [error,setError]=useState('');const [persona,setPersona]=useState<PersonaState>('idle');const [amplitude,setAmplitude]=useState(0);
 const peer=useRef<RTCPeerConnection|null>(null);const stream=useRef<MediaStream|null>(null);const channel=useRef<RTCDataChannel|null>(null);const audio=useRef<HTMLAudioElement|null>(null);const context=useRef<AudioContext|null>(null);const animation=useRef(0);const disposed=useRef(false);const generation=useRef(0);const playbackStart=useRef(0);const outputItem=useRef<string|null>(null);
 const disconnect=useCallback(()=>{generation.current++;disposed.current=true;cancelAnimationFrame(animation.current);channel.current?.close();peer.current?.close();stream.current?.getTracks().forEach(t=>t.stop());if(audio.current){audio.current.pause();audio.current.srcObject=null}void context.current?.close().catch(()=>{});context.current=null;peer.current=null;stream.current=null;channel.current=null;setStatus('disconnected');setAmplitude(0);setPersona('paused')},[]);
 const connect=useCallback(async(session:Session)=>{
  disconnect();disposed.current=false;const ownGeneration=generation.current;setError('');setCaption('');setLearnerCaption('');setStatus('connecting');setMuted(false);
  try{
   if(!navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection)throw new Error('This browser cannot start voice. You can continue in text mode.');
   const mic=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
   if(disposed.current || generation.current!==ownGeneration){mic.getTracks().forEach(t=>t.stop());return}
   stream.current=mic;mic.getAudioTracks().forEach(t=>{t.enabled=false});
   const pc=new RTCPeerConnection();let negotiated:{session:Session;connection_id:string}|null=null;let readinessRequested=false;peer.current=pc;mic.getTracks().forEach(t=>pc.addTrack(t,mic));
   const player=new Audio();player.autoplay=true;audio.current=player;
   player.onplaying=()=>{if(!disposed.current){playbackStart.current=performance.now();setPersona('speaking')}};
   player.onpause=()=>{if(!disposed.current)setPersona('listening')};
   pc.ontrack=event=>{const remote=event.streams[0] || new MediaStream([event.track]);player.srcObject=remote;void player.play().catch(()=>setError('Your browser paused interview audio. Select Enable audio to hear the interviewer.'));
    try{const ac=new AudioContext();context.current=ac;const source=ac.createMediaStreamSource(remote);const analyser=ac.createAnalyser();analyser.fftSize=256;source.connect(analyser);const values=new Uint8Array(analyser.frequencyBinCount);const tick=()=>{if(disposed.current)return;analyser.getByteTimeDomainData(values);const rms=Math.sqrt(values.reduce((sum,n)=>sum+Math.pow((n-128)/128,2),0)/values.length);setAmplitude(Math.min(1,rms*6));if(rms>.008)setPersona('speaking');animation.current=requestAnimationFrame(tick)};tick()}catch{/* Speech still plays when analysis is unsupported. */}
   };
   const dc=pc.createDataChannel('oai-events');channel.current=dc;
   dc.onmessage=event=>{try{const data=JSON.parse(event.data);if(data.type==='response.output_item.added'&&data.item?.id)outputItem.current=data.item.id;if(data.item_id && ['response.audio.delta','response.output_audio.delta'].includes(data.type))outputItem.current=data.item_id;const normalized=readVoiceEvent(data);if(!normalized)return;if(normalized.kind==='interviewer_caption')setCaption(old=>normalized.append?old+normalized.text:normalized.text||'');if(normalized.kind==='learner_caption')setLearnerCaption(normalized.text||'');if(normalized.kind==='speaking'){playbackStart.current=performance.now();setPersona('speaking')}if(normalized.kind==='listening')setPersona('listening');if(normalized.kind==='thinking')setPersona('thinking');if(normalized.kind==='error')setError(normalized.text||'Voice interrupted.')}catch{/* Ignore malformed provider UI events; server owns durable turns. */}};
   pc.onconnectionstatechange=()=>{if(disposed.current||generation.current!==ownGeneration)return;if(pc.connectionState==='connected'&&negotiated&&!readinessRequested){readinessRequested=true;void confirmMediaReady({request,session:negotiated.session,connectionId:negotiated.connection_id,isCurrent:()=>!disposed.current&&generation.current===ownGeneration&&pc.connectionState==='connected',onSession,activate:()=>{mic.getAudioTracks().forEach(t=>{t.enabled=true});setStatus('connected');setPersona('listening')}}).catch(reason=>{if(generation.current!==ownGeneration)return;disconnect();setStatus('error');setPersona('error');setError(reason instanceof Error?reason.message:'The server could not confirm the voice connection.')})}if(['failed','disconnected'].includes(pc.connectionState)){mic.getAudioTracks().forEach(t=>{t.enabled=false});setStatus('interrupted');setPersona('paused');setError('Voice connection interrupted. Your completed answers are saved. Reconnect or continue in text.')}};
   const offer=await pc.createOffer();await pc.setLocalDescription(offer);
   const result=await request<{session:Session;connection_id:string;sdp_answer:string}>(`/viva/sessions/${session.id}/connection`,{method:'POST',body:{expected_revision:session.revision,sdp_offer:offer.sdp,microphone_consent:true}});
   if(disposed.current || generation.current!==ownGeneration)return;
   negotiated=result;onSession(result.session);await pc.setRemoteDescription({type:'answer',sdp:result.sdp_answer});
  }catch(reason){disconnect();setStatus('error');setPersona('error');setError(reason instanceof Error?reason.message:'Voice setup failed. Continue in text mode or retry.');throw reason}
 },[disconnect,onSession,request]);
 const muteInput=useCallback(()=>{stream.current?.getAudioTracks().forEach(t=>{t.enabled=false});setMuted(true)},[]);
 const toggleMute=useCallback(()=>{setMuted(old=>{stream.current?.getAudioTracks().forEach(t=>{t.enabled=old});return !old})},[]);
 const interrupt=useCallback(()=>{if(channel.current?.readyState==='open'){channel.current.send(JSON.stringify({type:'response.cancel'}));channel.current.send(JSON.stringify({type:'output_audio_buffer.clear'}));if(outputItem.current)channel.current.send(JSON.stringify({type:'conversation.item.truncate',item_id:outputItem.current,content_index:0,audio_end_ms:Math.max(0,Math.floor(performance.now()-playbackStart.current))}))}setPersona('listening');setCaption('Interviewer interrupted. Use Repeat question if needed.')},[]);
 const enableAudio=useCallback(()=>{void audio.current?.play().then(()=>setError('')).catch(()=>setError('Audio playback is still blocked. Check browser sound permissions.'));void context.current?.resume()},[]);
 useEffect(()=>()=>disconnect(),[disconnect]);
 return {status,muted,caption,learnerCaption,error,persona,amplitude,connect,disconnect,muteInput,toggleMute,interrupt,enableAudio};
}
