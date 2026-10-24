"""Pure illustrative demo content; instructor approval remains a deployment gate."""
import hashlib
import json

QUESTIONS = [
 {'id':'question-explanation','objective':'explanation','prompt':'Explain why you chose your inspection check. Which observations support your decision?','is_follow_up':False,'parent_question_id':None},
 {'id':'question-changed-condition','objective':'changed_condition','prompt':'Suppose a new observation conflicts with the earlier inspection. How would you change your decision and why?','is_follow_up':False,'parent_question_id':None},
 {'id':'question-limits','objective':'limits','prompt':'What evidence would be insufficient to proceed, and when would you ask a supervisor for help?','is_follow_up':False,'parent_question_id':None},
]
DOCUMENTS = [
 ('doc-inspection','Inspection decision guide','evidence-inspection','Inspection decisions must connect the selected check to the observed condition. Record observations before deciding whether the available evidence supports proceeding.'),
 ('doc-changed-condition','Changed-condition response','evidence-change','A new observation that conflicts with earlier evidence requires reassessing the decision. Do not assume the earlier decision remains justified; seek clarification before proceeding.'),
 ('doc-limits','Limits and escalation guide','evidence-limits','If evidence is missing, inconsistent, or outside the reviewed task scope, stop the decision and escalate to a supervisor. A simulated reasoning exercise does not establish practical competence.'),
]

def release_data():
    documents=[]; evidence=[]
    for did,title,eid,text in DOCUMENTS:
        documents.append({'id':did,'title':title,'version':'1','checksum':hashlib.sha256(text.encode()).hexdigest(),
            'media_type':'text/plain','resolver_url':f'/api/v1/studio/releases/release-demo-v1/documents/{did}',
            'evidence_ids':[eid],'availability':'available','content':text})
        evidence.append({'id':eid,'document_id':did,'task_id':'task-inspection','type':'expert_response','author':'Illustrative demonstration content','text':text,'locator':'Section 1'})
    dimensions=['technical_correctness','explanation_quality','evidence_use','recognition_of_limits']
    rubric={'version':'rubric-v1','dimensions':[{ 'dimension':d,'descriptors':{
        '0':'Demonstrates a substantial misconception against the reviewed source.',
        '1':'Shows major gaps linking observations to a justified decision.',
        '2':'Explains some relevant reasoning but leaves material gaps.',
        '3':'Explains a sound decision with only minor omissions.',
        '4':'Explains the full reasoning, relevant evidence, and limits for this objective.'}} for d in dimensions]}
    return {'id':'release-demo-v1','task_id':'task-inspection','title':'Inspection reasoning — demonstration release',
        'version':'1','content_status':'illustrative_demo_requires_instructor_review','documents':documents,'evidence':evidence,
        'units':[{'id':'unit-reasoning','action':'Inspect','cue':'Observed condition','interpretation':'Evidence must support a decision','decision':'Proceed only with sufficient evidence','exception':'Escalate uncertainty','evidence_ids':[x['id'] for x in evidence]}],
        'question_plan':QUESTIONS,'question_plan_version':'questions-v1','rubric':rubric,'rubric_version':'rubric-v1'}
