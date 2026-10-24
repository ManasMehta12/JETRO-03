"""Generate the three proposed demo contracts using only the standard library."""
import json
from pathlib import Path

ROOT = Path(__file__).parent / 'openapi'
ROOT.mkdir(exist_ok=True)

def string(**kw): return {'type': 'string', **kw}
def enum(*values): return string(enum=list(values))
def integer(**kw): return {'type': 'integer', **kw}
def array(items): return {'type': 'array', 'items': items}
def ref(name): return {'$ref': '#/components/schemas/' + name}
def obj(fields, required=None):
    return {'type': 'object', 'additionalProperties': False, 'properties': fields,
            'required': list(fields) if required is None else required}

ID = string(minLength=1)
REV = integer(minimum=0)
S = {
    'Error': obj({'code': string(), 'message': string(), 'details': {'type': 'object', 'additionalProperties': True}}),
    'Evidence': obj({'id': ID, 'task_id': ID, 'type': enum('video', 'expert_response'),
        'author': string(), 'text': string(), 'media_id': ID, 'document_id': ID, 'locator': string(),
        'start_ms': integer(minimum=0), 'end_ms': integer(minimum=1)}, ['id', 'task_id', 'type', 'author']),
    'Task': obj({'id': ID, 'title': string(), 'equipment_context': string(), 'language': string()}),
    'Unit': obj({'id': ID, **{key: string(nullable=True) for key in
        ['action', 'cue', 'interpretation', 'decision', 'exception']},
        'support': array(obj({'field': enum('action', 'cue', 'interpretation', 'decision', 'exception'),
            'evidence_ids': array(ID), 'review': enum('pending', 'supported', 'unsupported')}))}),
    'Question': obj({'id': ID, 'unit_id': ID, 'prompt': string(),
        'status': enum('open', 'answered', 'rejected', 'deferred')}),
    'Job': obj({'id': ID, 'state': enum('queued', 'running', 'awaiting_expert', 'completed', 'failed'),
        'stage': enum('queued', 'media_preparation', 'extraction', 'gap_detection', 'awaiting_expert', 'revision', 'validation', 'completed', 'failed'),
        'draft_id': string(nullable=True), 'error': string(nullable=True)}),
    'Draft': obj({'id': ID, 'task_id': ID, 'revision': REV,
        'status': enum('editing', 'review', 'published'), 'units': array(ref('Unit')),
        'questions': array(ref('Question')), 'evidence': array(ref('Evidence'))}),
    'Release': obj({'id': ID, 'task_id': ID, 'content_hash': string(),
        'reviewer_id': ID, 'approved_at': string(format='date-time'), 'units': array(ref('Unit')),
        'evidence': array(ref('Evidence')), 'documents': array(ref('SourceDocument'))}),
    'Scenario': obj({'id': ID, 'title': string(), 'version': ID, 'bundle_id': ID, 'release_id': ID,
        'scene_template': string(), 'component_ids': array(ID)}),
    'Action': obj({'id': ID, 'label': string(), 'target_id': ID}, ['id', 'label']),
    'Observation': obj({'id': ID, 'text': string(), 'component_id': ID}),
    'Feedback': obj({'text': string(), 'evidence_ids': array(ID)}),
    'Dimension': obj({'name': enum('decision_accuracy', 'evidence_gathering', 'recognition_of_limits', 'explanation_quality'),
        'earned': integer(minimum=0), 'available': integer(minimum=0)}),
    'Attempt': obj({'id': ID, 'scenario_id': ID, 'scenario_version': ID,
        'bundle_id': ID, 'bundle_hash': string(), 'release_id': ID,
        'mode': enum('guided', 'assessment'), 'revision': REV,
        'status': enum('in_progress', 'completed'), 'state': string(),
        'available_actions': array(ref('Action')), 'observations': array(ref('Observation')),
        'feedback': array(ref('Feedback')), 'scores': array(ref('Dimension')),
        'critical_error': {'type': 'boolean'}, 'outcome': string(nullable=True)}),
    'SourceDocument': obj({'id': ID, 'title': string(), 'version': ID, 'checksum': string(),
        'media_type': string(), 'resolver_url': string(), 'evidence_ids': array(ID),
        'availability': enum('available', 'unavailable')}),
    'SourceReference': obj({'release_id': ID, 'document_id': ID, 'evidence_id': ID,
        'locator': string(), 'excerpt': string()}),
    'VivaQuestion': obj({'id': ID, 'objective': enum('explanation', 'changed_condition', 'limits'),
        'prompt': string(), 'is_follow_up': {'type': 'boolean'}, 'parent_question_id': string(nullable=True)}),
    'InterviewTurn': obj({'id': ID, 'sequence': integer(minimum=1), 'question_id': string(nullable=True),
        'speaker': enum('learner', 'interviewer'), 'text': string(), 'input_mode': enum('voice', 'text'),
        'delivery': enum('completed', 'interrupted', 'unconfirmed'), 'replacement_id': string(nullable=True), 'quality_flag': string(nullable=True), 'created_at': string(format='date-time')}),
    'QuestionCoverage': obj({'question_id': ID, 'objective': enum('explanation', 'changed_condition', 'limits'), 'status': enum('unanswered', 'answered', 'not_assessed'),
        'answer_turn_ids': array(ID), 'follow_up_count': integer(minimum=0, maximum=1)}),
    'VivaSession': obj({'id': ID, 'attempt_id': ID, 'learner_id': ID, 'bundle_id': ID, 'bundle_hash': string(),
        'release_id': ID, 'rubric_version': ID, 'prompt_version': ID, 'model_config_version': ID,
        'revision': REV, 'status': enum('created', 'connecting', 'in_progress', 'paused', 'evaluating', 'completed', 'failed'),
        'input_mode': enum('voice', 'text'), 'question_count': integer(enum=[3]),
        'answered_count': integer(minimum=0, maximum=3), 'follow_up_count': integer(minimum=0, maximum=3),
        'current_question': {'allOf': [ref('VivaQuestion')], 'nullable': True},
        'last_event_sequence': REV, 'evaluation_job_id': string(nullable=True), 'result_id': string(nullable=True),
        'active_seconds': {'type':'number','minimum':0}, 'max_active_seconds': integer(minimum=1),
        'transcript': array(ref('InterviewTurn')), 'created_at': string(format='date-time'), 'expires_at': string(format='date-time')}),
    'EvaluationJob': obj({'id': ID, 'session_id': ID, 'status': enum('queued', 'running', 'completed', 'failed'),
        'attempt_count': integer(minimum=0, maximum=3), 'result_id': string(nullable=True),
        'error_code': string(nullable=True), 'retryable': {'type': 'boolean'}}),
    'RubricAssessment': obj({'dimension': enum('technical_correctness', 'explanation_quality', 'evidence_use', 'recognition_of_limits'),
        'status': enum('assessed', 'not_assessed', 'needs_review'), 'score': integer(minimum=0, maximum=4, nullable=True),
        'rationale': string(), 'answer_turn_ids': array(ID), 'sources': array(ref('SourceReference'))}),
    'QuestionAssessment': obj({'question_id': ID, 'answer_turn_ids': array(ID), 'feedback': string(),
        'sources': array(ref('SourceReference'))}),
    'ReportSource': obj({'document': ref('SourceDocument'), 'usage': enum('cited', 'available_unused', 'unavailable')}),
    'VivaReport': obj({'id': ID, 'version': integer(minimum=1), 'session_id': ID, 'attempt_id': ID,
        'release_id': ID, 'bundle_id': ID, 'bundle_hash': string(), 'rubric_version': ID,
        'prompt_version': ID, 'model_config_version': ID, 'created_at': string(format='date-time'),
        'snapshot_hash': string(), 'completion': enum('complete', 'incomplete'), 'finish_reason': enum('questions_complete', 'learner_finished', 'time_limit', 'expired'),
        'assessments': array(ref('RubricAssessment')), 'questions': array(ref('QuestionAssessment')),
        'coverage': array(ref('QuestionCoverage')), 'strengths': array(string()), 'misconceptions': array(string()),
        'missed_topics': array(string()), 'recommendations': array(string()),
        'playground_scores': array(ref('Dimension')), 'critical_error': {'type': 'boolean'},
        'transcript': array(ref('InterviewTurn')), 'source_index': array(ref('ReportSource')),
        'assessment_notice': string()})
}

# Closed event variants match the application's discriminated event payloads.
_event_variants = []
for _kind, _payload_name, _schema_name in [
    ('session_updated', 'session', 'VivaSession'), ('turn_committed', 'turn', 'InterviewTurn'),
    ('question_presented', 'question', 'VivaQuestion'), ('evaluation_updated', 'evaluation', 'EvaluationJob'),
    ('error', 'error', 'Error')]:
    _name = ''.join(word.title() for word in _kind.split('_')) + 'Event'
    S[_name] = obj({'id': ID, 'sequence': integer(minimum=1), 'session_revision': REV,
        'type': enum(_kind), 'created_at': string(format='date-time'),
        'payload': obj({_payload_name: ref(_schema_name)})})
    _event_variants.append(ref(_name))
S['PublicKnowledgeRelease'] = obj({'id':ID,'task_id':ID,'title':string(),'content_hash':string(),'content_status':string(nullable=True),'documents':array(ref('SourceDocument')),'evidence':array(ref('Evidence')),'units':array({'type':'object','additionalProperties':True})})
S['SessionEvent'] = {'oneOf': _event_variants, 'discriminator': {'propertyName': 'type',
    'mapping': {S[item['$ref'].split('/')[-1]]['properties']['type']['enum'][0]: item['$ref'] for item in _event_variants}}}

def response(schema, description='Success'):
    return {'description': description, 'content': {'application/json': {'schema': schema}}}

def operation(name, summary, output, body=None, status='200', roles='learner', multipart=False, mutation=False):
    op = {'operationId': name, 'summary': summary, 'description': 'Required role: ' + roles + '.',
          'responses': {status: response(output)}}
    for code, desc in [('401', 'Invalid session'), ('403', 'Forbidden role or scope'),
                       ('404', 'Unknown or inaccessible resource'), ('409', 'State, revision or idempotency conflict'),
                       ('413', 'Request body too large'), ('422', 'Invalid request or unknown referenced value'), ('429', 'Rate or usage limit')]:
        op['responses'][code] = response(ref('Error'), desc)
    if mutation:
        op['parameters'] = [{'name': 'Idempotency-Key', 'in': 'header', 'required': True,
            'schema': string(minLength=1, maxLength=128),
            'description': 'Persist response by actor, route and key. Replay identical payload; reject changed payload with 409. Deduplicate before revision validation.'}]
    if body:
        op['requestBody'] = {'required': True, 'content': {
            'multipart/form-data' if multipart else 'application/json': {'schema': body}}}
    return op

def save(filename, title, paths):
    for path, item in paths.items():
        names = [part[1:-1] for part in path.split('/') if part.startswith('{')]
        if names:
            item['parameters'] = [{'name': name, 'in': 'path', 'required': True, 'schema': ID} for name in names]
    spec = {'openapi': '3.0.3', 'info': {'title': title, 'version': '2.0.0',
        'description': 'Technical Viva v2 contract and adjacent Studio/Playground interfaces. The repository implements Viva and scoped source resolution; Studio authoring and Playground execution remain adjacent component plans. See the implementation coverage document. All errors are JSON.'},
        'servers': [{'url': '/api/v1'}], 'security': [{'DemoSession': []}], 'paths': paths,
        'components': {'securitySchemes': {'DemoSession': {'type': 'http', 'scheme': 'bearer',
            'description': 'Preprovisioned opaque demo session; server resolves role and identity.'}}, 'schemas': S}}
    (ROOT / filename).write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')

studio = {
 '/studio/tasks': {'post': operation('createStudioTask', 'Create task', ref('Task'),
     obj({'title': string(minLength=1), 'equipment_context': string(minLength=1), 'language': string(minLength=2)}),
     status='201', roles='expert', mutation=True)},
 '/studio/tasks/{task_id}/media': {'post': operation('uploadStudioMedia', 'Validate media and enqueue extraction',
     obj({'media_id': ID, 'job': ref('Job')}), obj({'file': string(format='binary')}),
     status='202', roles='expert', multipart=True, mutation=True)},
 '/studio/jobs/{job_id}': {'get': operation('getStudioJob', 'Poll persisted agent stage', ref('Job'), roles='expert or reviewer')},
 '/studio/drafts/{draft_id}': {
     'get': operation('getStudioDraft', 'Read draft with evidence and questions', ref('Draft'), roles='expert or reviewer'),
     'patch': operation('editStudioDraft', 'Replace editable units with revision check', ref('Draft'),
         obj({'expected_revision': REV, 'units': array(ref('Unit'))}), roles='expert or reviewer', mutation=True)},
 '/studio/drafts/{draft_id}/answers': {'post': operation('answerStudioQuestion', 'Store attributed answer and enqueue revision',
     obj({'evidence_id': ID, 'draft_revision': REV, 'job': ref('Job')}),
     obj({'expected_revision': REV, 'question_id': ID, 'disposition': enum('answered', 'rejected', 'deferred'),
          'text': string(minLength=1, maxLength=10000)}), status='202', roles='expert', mutation=True)},
 '/studio/drafts/{draft_id}/publish': {'post': operation('publishStudioRelease', 'Publish reviewed immutable snapshot', ref('Release'),
     obj({'expected_revision': REV}), status='201', roles='reviewer', mutation=True)},
 '/studio/evidence/{evidence_id}': {'get': operation('getStudioEvidence', 'Resolve authorized source evidence', ref('Evidence'), roles='learner for bound approved evidence; expert or reviewer for draft evidence')},
 '/studio/media/{media_id}': {'get': {
     'operationId': 'streamStudioMedia', 'summary': 'Stream authorized source media',
     'description': 'Validate session and task/release access. Support browser byte ranges. Media source content type follows validated asset.',
     'parameters': [{'name': 'Range', 'in': 'header', 'schema': string(), 'description': 'Optional bytes range'}],
     'responses': {'200': {'description': 'Full media', 'headers': {'Accept-Ranges': {'schema': string(enum=['bytes'])}},
         'content': {'application/octet-stream': {'schema': string(format='binary')}}},
         '206': {'description': 'Partial media', 'headers': {'Content-Range': {'schema': string()}, 'Accept-Ranges': {'schema': string(enum=['bytes'])}},
             'content': {'application/octet-stream': {'schema': string(format='binary')}}},
         **{code: response(ref('Error'), text) for code, text in [('401', 'Invalid session'), ('403', 'Forbidden'), ('404', 'Missing media'), ('416', 'Unsatisfiable byte range')]}}}}
}
studio['/studio/tasks/{task_id}/media']['post']['responses']['413'] = response(ref('Error'), 'Media exceeds 100 MB')
studio['/studio/drafts/{draft_id}']['patch']['description'] += ' Experts can correct content; only reviewers may set support review to supported. Edits to published drafts are rejected; fork support is outside this minimal API and handled by a new capture.'
studio['/studio/releases/{release_id}'] = {'get': operation('getStudioRelease', 'Read authorized immutable knowledge and document manifest', ref('PublicKnowledgeRelease'), roles='learner for bound release; expert or reviewer for task')}
studio['/studio/releases/{release_id}/documents/{document_id}'] = {'get': operation('resolveStudioDocument', 'Resolve document and evidence within approved release',
    obj({'document': ref('SourceDocument'), 'evidence': array(ref('Evidence'))}), roles='learner for bound release; expert or reviewer for task')}
studio['/studio/releases/{release_id}/documents/{document_id}/content'] = {'get': {
    'operationId': 'readStudioDocumentContent', 'summary': 'Read authorized source bytes',
    'responses': {'200': {'description': 'Original source content', 'content': {'application/octet-stream': {'schema': string(format='binary')}}},
        **{code: response(ref('Error'), detail) for code, detail in [('401', 'Invalid session'), ('403', 'Forbidden'), ('404', 'Missing or inaccessible source')]}}}}
save('expert-studio.openapi.json', 'Takumi Expert Studio', studio)

playground = {
 '/playground/scenarios': {'get': operation('listPlaygroundScenarios', 'List active public scenarios', array(ref('Scenario')))},
 '/playground/attempts': {'post': operation('startPlaygroundAttempt', 'Bind approved versions and start practice', ref('Attempt'),
     obj({'scenario_id': ID, 'mode': enum('guided', 'assessment')}), status='201', mutation=True)},
 '/playground/attempts/{attempt_id}': {'get': operation('getPlaygroundAttempt', 'Restore public attempt state', ref('Attempt'))},
 '/playground/attempts/{attempt_id}/actions': {'post': operation('submitPlaygroundAction', 'Apply one reviewed deterministic transition', ref('Attempt'),
     obj({'action_id': ID, 'expected_revision': REV}), mutation=True)}
}
save('apprentice-playground.openapi.json', 'Takumi Apprentice Playground', playground)

viva = {
 '/viva/sessions': {'post': operation('startVivaSession', 'Get or create interview for completed owned attempt', ref('VivaSession'),
     obj({'attempt_id': ID, 'input_mode': enum('voice', 'text')}, ['attempt_id']), mutation=True)},
 '/viva/sessions/{session_id}': {'get': operation('getVivaSession', 'Restore interview state without private rubric', ref('VivaSession'))},
 '/viva/sessions/{session_id}/connection': {'post': operation('connectVivaVoice', 'Negotiate authorized WebRTC connection',
     obj({'session': ref('VivaSession'), 'connection_id': ID, 'sdp_answer': string()}),
     obj({'expected_revision': REV, 'sdp_offer': string(minLength=1, maxLength=100000),
          'microphone_consent': {'type': 'boolean', 'enum': [True]}}), mutation=True)},
 '/viva/sessions/{session_id}/answers': {'post': operation('submitVivaAnswer', 'Commit typed answer and queue interviewer response',
     obj({'session': ref('VivaSession'), 'turn': ref('InterviewTurn')}),
     obj({'expected_revision': REV, 'question_id': ID, 'client_turn_id': ID,
          'text': string(minLength=1, maxLength=10000)}), status='202', mutation=True)},
 '/viva/sessions/{session_id}/events': {'get': operation('getVivaEvents', 'Read ordered durable events after cursor',
     obj({'events': array(ref('SessionEvent')), 'next_after': REV, 'has_more': {'type': 'boolean'}}))},
 '/viva/sessions/{session_id}/pause': {'post': operation('pauseVivaSession', 'Pause active interview and close media connection',
     ref('VivaSession'), obj({'expected_revision': REV}), mutation=True)},
 '/viva/sessions/{session_id}/resume': {'post': operation('resumeVivaSession', 'Resume interview in chosen input mode',
     ref('VivaSession'), obj({'expected_revision': REV, 'input_mode': enum('voice', 'text')}), mutation=True)},
 '/viva/sessions/{session_id}/finish': {'post': operation('finishVivaSession', 'Freeze transcript and get or create evaluation job',
     ref('EvaluationJob'), obj({'expected_revision': REV}), status='202', mutation=True)},
 '/viva/sessions/{session_id}/evaluation': {'get': operation('getVivaEvaluation', 'Read evaluation job status', ref('EvaluationJob'))},
 '/viva/sessions/{session_id}/result': {'get': operation('getVivaResult', 'Read completed evidence-linked assessment', ref('VivaReport'))}
}
viva['/viva/sessions/{session_id}/connection/ready'] = {'post': operation('confirmVivaMediaReady', 'Enable first question only after browser media is connected', ref('VivaSession'),
    obj({'expected_revision': REV, 'connection_id': ID}), mutation=True)}
viva['/viva/sessions/{session_id}/repeat'] = {'post': operation('repeatVivaQuestion', 'Repeat current question without changing grading', ref('VivaSession'),
    obj({'expected_revision': REV, 'question_id': ID}), status='202', mutation=True)}
viva['/viva/sessions/{session_id}/transcript-flags'] = {'post': operation('flagVivaTranscript', 'Flag unclear learner transcription and request replacement when possible',
    obj({'session': ref('VivaSession'), 'turn': ref('InterviewTurn'), 'replacement_requested': {'type': 'boolean'}}),
    obj({'expected_revision': REV, 'turn_id': ID, 'reason': string(minLength=1, maxLength=500)}), mutation=True)}
viva['/viva/sessions/{session_id}/events']['get']['parameters'] = [
    {'name': 'after', 'in': 'query', 'schema': integer(minimum=0, default=0)},
    {'name': 'limit', 'in': 'query', 'schema': integer(minimum=1, maximum=100, default=100)}]
viva['/viva/sessions/{session_id}/events']['get']['description'] += ' Poll every 500 ms while active and 2 s while evaluating. Only completed turns are durable; partial captions are provider UI events. Event type requires its corresponding payload, and no other payload.'
viva['/viva/sessions/{session_id}/connection']['post']['description'] += ' Only created/paused sessions in voice mode may connect. Backend attaches control channel, then browser confirms /connection/ready before microphone activation and the first spoken question. Replay returns original SDP; an expired connection requires a new key and negotiation. No provider secret is returned.'
viva['/viva/sessions/{session_id}/answers']['post']['description'] += ' Text mode only; question must be current and fully delivered. Unique client_turn_id per session; changed content for an existing turn ID conflicts. Server serializes voice and text acceptance.'
viva['/viva/sessions/{session_id}/finish']['post']['description'] += ' Existing evaluation job is returned before revision checks, even with a new idempotency key. Otherwise freeze committed transcript and enqueue once; incomplete coverage is reported. Committed turns are frozen atomically; unfinished speech is not graded.'
viva['/viva/sessions/{session_id}/result']['get']['description'] += ' Returns 409 until evaluation is complete. Source index is the entire bound release manifest, not retrieval results. No future question keys or private rubric are exposed during the interview.'
for suffix in ('connection', 'answers'):
    viva[f'/viva/sessions/{{session_id}}/{suffix}']['post']['responses']['503'] = response(ref('Error'), 'Provider unavailable; retain progress')
save('technical-viva.openapi.json', 'Takumi Technical Viva', viva)

# Dependency-free structural checks, not a substitute for an OpenAPI validator.
for file in ROOT.glob('*.json'):
    spec = json.loads(file.read_text(encoding='utf-8'))
    ids = set()
    def walk(node):
        if isinstance(node, dict):
            if '$ref' in node:
                name = node['$ref'].split('/')[-1]
                assert name in spec['components']['schemas'], name
            if node.get('type') == 'object' and 'properties' in node:
                assert set(node.get('required', [])) <= node['properties'].keys()
            for value in node.values(): walk(value)
        elif isinstance(node, list):
            for value in node: walk(value)
    walk(spec)
    count = 0
    for path, item in spec['paths'].items():
        for method, op in item.items():
            if method == 'parameters': continue
            assert op['operationId'] not in ids
            ids.add(op['operationId'])
            assert any(code.startswith('2') for code in op['responses'])
            count += 1
    print(f'{file.name}: {count} operations; local references and required fields valid')
