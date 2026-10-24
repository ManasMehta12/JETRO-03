import type {HumanReview,Report,Assessment,SourceReference} from './types';
export function latestReviewByDimension(reviews?:HumanReview[]):Record<string,{review:HumanReview;assessment:Assessment}>;
export function buildReviewPayload(input:{report:Report;version:number;reason:string;dimension:string;status:string;score:number|null;rationale:string;turnIds:string[];sources:SourceReference[]}):{expected_review_version:number;reason:string;overrides:Assessment[]};
