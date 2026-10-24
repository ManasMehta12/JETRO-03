import type {Session,Turn,SessionEvent,VoiceEvent} from './types';
export class ApiError extends Error {status:number;code:string;details:Record<string,unknown>;}
export interface ApiOptions {method?:string;body?:unknown;idempotencyKey?:string;signal?:AbortSignal;headers?:Record<string,string>;blob?:boolean}
export function apiRequest<T=unknown>(path:string,options?:ApiOptions,config?:{base?:string;token?:string;fetcher?:typeof fetch}):Promise<T>;
export function normalizeSession(value:Session | {session:Session}):Session;
export function mergeTurns(oldTurns?:Turn[],newTurns?:Turn[]):Turn[];
export function applyEvents(session:Session,events?:SessionEvent[]):Session;
export function formatTime(seconds:number):string;
export function readVoiceEvent(event:Record<string,unknown>):VoiceEvent | null;
export function sourcePath(document:{id:string},releaseId:string):string;
export function confirmMediaReady(options:{request:<T>(path:string,options?:ApiOptions)=>Promise<T>;session:Session;connectionId:string;isCurrent:()=>boolean;activate:()=>void;onSession:(session:Session)=>void}):Promise<boolean>;
