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
        'author': string(), 'text': string(), 'media_id': ID,
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
        'evidence': array(ref('Evidence'))}),
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
    'VivaQuestion': obj({'id': ID, 'prompt': string(), 'options': array(obj({'id': ID, 'label': string()}))}),
    'VivaSession': obj({'id': ID, 'attempt_id': ID, 'bundle_id': ID, 'bundle_hash': string(),
        'release_id': ID, 'bank_version': ID, 'revision': REV, 'status': enum('in_progress', 'completed'),
        'answered_count': integer(minimum=0, maximum=3), 'question_count': integer(enum=[3]),
        'current_question': {'allOf': [ref('VivaQuestion')], 'nullable': True},
        'result_id': string(nullable=True)}),
    'AnswerResult': obj({'question_id': ID, 'option_id': ID, 'reflection': string(),
        'feedback': ref('Feedback'), 'scores': array(ref('Dimension'))},
        ['question_id', 'option_id', 'feedback', 'scores']),
    'VivaResult': obj({'id': ID, 'session_id': ID, 'attempt_id': ID, 'release_id': ID,
        'bundle_id': ID, 'answers': array(ref('AnswerResult')), 'viva_scores': array(ref('Dimension')),
        'playground_scores': array(ref('Dimension')), 'critical_error': {'type': 'boolean'},
        'assessment_notice': string()})
}

def response(schema, description='Success'):
    return {'description': description, 'content': {'application/json': {'schema': schema}}}

def operation(name, summary, output, body=None, status='200', roles='learner', multipart=False, mutation=False):
    op = {'operationId': name, 'summary': summary, 'description': 'Required role: ' + roles + '.',
          'responses': {status: response(output)}}
    for code, desc in [('401', 'Invalid session'), ('403', 'Forbidden role or scope'),
                       ('404', 'Unknown or inaccessible resource'), ('409', 'State, revision or idempotency conflict'),
                       ('422', 'Invalid request or unknown referenced value')]:
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
    spec = {'openapi': '3.0.3', 'info': {'title': title, 'version': '1.0.0',
        'description': 'Proposed hackathon contract. See component plan and README for state, fixture and role invariants. All errors are JSON. No deployed implementation is implied.'},
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
     obj({'attempt_id': ID}), mutation=True)},
 '/viva/sessions/{session_id}': {'get': operation('getVivaSession', 'Restore scripted interview state', ref('VivaSession'))},
 '/viva/sessions/{session_id}/answers': {'post': operation('submitVivaAnswer', 'Score selected option and advance fixed question order',
     obj({'session': ref('VivaSession'), 'answer': ref('AnswerResult')}),
     obj({'expected_revision': REV, 'question_id': ID, 'option_id': ID, 'reflection': string(maxLength=5000)},
         ['expected_revision', 'question_id', 'option_id']), mutation=True)},
 '/viva/sessions/{session_id}/result': {'get': operation('getVivaResult', 'Get completed exercise report with authored feedback', ref('VivaResult'))}
}
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
