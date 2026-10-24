export function latestReviewByDimension(reviews=[]) {
 const result={};for(const review of [...reviews].sort((a,b)=>a.version-b.version))for(const assessment of review.overrides||[])result[assessment.dimension]={review,assessment};return result;
}
export function buildReviewPayload({report,version,reason,dimension,status,score,rationale,turnIds=[],sources=[]}) {
 if(!reason?.trim())throw new Error('A review reason is required.');
 if(!rationale?.trim())throw new Error('Explain the assessment rationale.');
 if(!report.assessments.some(item=>item.dimension===dimension))throw new Error('Choose an assessed rubric dimension.');
 if(!['assessed','not_assessed','needs_review'].includes(status))throw new Error('Choose a valid assessment status.');
 if(!Number.isInteger(version)||version<0)throw new Error('Reload the current review version.');
 const learnerIds=new Set(report.transcript.filter(turn=>turn.speaker==='learner').map(turn=>turn.id));
 if(turnIds.some(id=>!learnerIds.has(id)))throw new Error('Select existing learner answers for the review.');
 const documents=new Set(report.source_index.map(item=>item.document.id));
 if(sources.some(source=>!documents.has(source.document_id)||source.release_id!==report.release_id||!source.excerpt?.trim()||!source.evidence_id))throw new Error('Select evidence from this approved release.');
 if(status==='assessed'){
  if(!Number.isInteger(score)||score<0||score>4)throw new Error('Choose an integer score from 0 to 4.');
  if(!turnIds.length)throw new Error('Select at least one learner answer supporting the score.');
  if(!sources.length)throw new Error('Select at least one approved source supporting the score.');
 }
 return {expected_review_version:version,reason:reason.trim(),overrides:[{dimension,status,score:status==='assessed'?score:null,rationale:rationale.trim(),answer_turn_ids:[...new Set(turnIds)],sources:sources.map(source=>({...source}))}]};
}
