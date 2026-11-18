"""Bounded supplied-policy pattern review, not IAM authorization evaluation."""
from __future__ import annotations

import json
import math

SOURCES = [
    'https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notaction.html',
    'https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notresource.html',
    'https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html',
    'https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_grammar.html',
]
MAX_BYTES = 512_000
LIMITS = ('Supplied policy pattern review only, not AWS syntax validation, a security audit or effective-permission simulation. '
          'Findings describe individual Allow statements, not final access; explicit denies, conditions, identity/resource policies, '
          'permissions boundaries, session policies, SCPs/RCPs and request context are not evaluated or combined. '
          'Action/resource validity and service support are not verified. Some actions require Resource star; broad patterns are human-review signals, not proof excessive. '
          'NotAction applies only to applicable actions in the statement scope, not automatically every AWS action. '
          'A condition being present is not proof it restricts access safely. Deny statements are shape-checked but not risk-analyzed. '
          'Zero findings never means secure, private or least privilege. Sid, action/resource/principal/condition values are not echoed. '
          'No AWS/API/network call, credential access, policy attachment/edit or remediation is performed.')


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def _strings(value):
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or not 1 <= len(values) <= 1000:
        raise ValueError('Expected a nonempty string or list of at most 1000 strings.')
    if any(not isinstance(item, str) or not item or len(item) > 2048 or any(ord(c) < 32 for c in item) for item in values):
        raise ValueError('Policy strings must be nonempty bounded text without control characters.')
    return values


def _principal(value):
    if value == '*':
        return True
    if not isinstance(value, dict) or not value or set(value) - {'AWS', 'Federated', 'Service', 'CanonicalUser'}:
        raise ValueError('Unsupported principal shape. Supply star or a supported nonempty principal map.')
    wildcard = False
    for key, item in value.items():
        values = _strings(item)
        if key == 'AWS' and '*' in values:
            wildcard = True
    return wildcard


def _condition(value):
    if not isinstance(value, dict) or not value or len(value) > 100:
        raise ValueError('Condition must be a nonempty bounded operator map; conditions are not evaluated.')
    for operator, entries in value.items():
        _strings(operator)
        if not isinstance(entries, dict) or not entries or len(entries) > 100:
            raise ValueError('Each condition operator requires a nonempty bounded key map.')
        for key, values in entries.items():
            _strings(key)
            values = values if isinstance(values, list) else [values]
            if not 1 <= len(values) <= 1000:
                raise ValueError('Condition values must be bounded scalar values or lists.')
            for scalar in values:
                if isinstance(scalar, str):
                    if len(scalar) > 2048 or any(ord(c) < 32 for c in scalar):
                        raise ValueError('Condition text is too long or contains control characters.')
                elif type(scalar) not in (bool, int, float) or (isinstance(scalar, float) and not math.isfinite(scalar)):
                    raise ValueError('Nested/null/non-finite condition values are not supported.')


def _document(policy):
    if isinstance(policy, str):
        if len(policy.encode('utf-8')) > MAX_BYTES:
            raise ValueError('Policy exceeds the 512 KB review limit.')
        doc = json.loads(policy, object_pairs_hook=_unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    else:
        # Serializing caller dictionaries enforces bounds/cycles/finite JSON too.
        encoded = json.dumps(policy, allow_nan=False)
        if len(encoded.encode('utf-8')) > MAX_BYTES:
            raise ValueError('Policy exceeds the 512 KB review limit.')
        doc = json.loads(encoded)
    if not isinstance(doc, dict) or 'Statement' not in doc or set(doc) - {'Version', 'Id', 'Statement'}:
        raise ValueError('Supply a policy object with Statement and only supported top-level fields.')
    if 'Version' in doc and doc['Version'] not in ('2012-10-17', '2008-10-17'):
        raise ValueError('Only policy language versions 2012-10-17 and 2008-10-17 are supported.')
    if 'Id' in doc:
        _strings(doc['Id'])
        if not isinstance(doc['Id'], str):
            raise ValueError('Id must be text.')
    statements = doc['Statement']
    statements = [statements] if isinstance(statements, dict) else statements
    if not isinstance(statements, list) or not 1 <= len(statements) <= 500:
        raise ValueError('Statement must contain 1-500 statement objects.')
    result = []
    for st in statements:
        allowed = {'Sid', 'Effect', 'Action', 'NotAction', 'Resource', 'NotResource', 'Principal', 'NotPrincipal', 'Condition'}
        if not isinstance(st, dict) or set(st) - allowed or st.get('Effect') not in ('Allow', 'Deny'):
            raise ValueError('Every statement requires Allow/Deny Effect and supported fields; malformed rows are not skipped.')
        if ('Action' in st) == ('NotAction' in st):
            raise ValueError('Each statement requires exactly one of Action and NotAction.')
        if 'Resource' in st and 'NotResource' in st:
            raise ValueError('Resource and NotResource cannot both be supplied.')
        if 'Principal' in st and 'NotPrincipal' in st:
            raise ValueError('Principal and NotPrincipal cannot both be supplied.')
        if not any(field in st for field in ('Resource', 'NotResource', 'Principal', 'NotPrincipal')):
            raise ValueError('Supply a supported resource scope or principal for the statement.')
        if 'Sid' in st:
            if not isinstance(st['Sid'], str) or len(st['Sid']) > 2048 or any(ord(c) < 32 for c in st['Sid']):
                raise ValueError('Sid must be bounded text without control characters.')
        actions = _strings(st.get('Action', st.get('NotAction')))
        resources = _strings(st.get('Resource', st.get('NotResource'))) if 'Resource' in st or 'NotResource' in st else []
        public = _principal(st['Principal']) if 'Principal' in st else False
        if 'NotPrincipal' in st:
            _principal(st['NotPrincipal'])
        if 'Condition' in st:
            _condition(st['Condition'])
        result.append((st, actions, resources, public))
    return result


def review_policy(policy):
    try:
        statements = _document(policy)
    except (ValueError, TypeError, RecursionError, OverflowError, UnicodeError):
        return {'success': False, 'error': 'Unsupported, malformed or oversized policy. Supply bounded valid JSON with supported statement shapes; no rows were accepted or skipped. This is not an AWS syntax validator.',
                'limits': LIMITS, 'sources': SOURCES}
    from aether.devops.review import _finding, _summary
    findings = []
    allow = deny = conditions = 0
    for index, (statement, actions, resources, public) in enumerate(statements):
        conditional = 'Condition' in statement
        conditions += int(conditional)
        if statement['Effect'] == 'Deny':
            deny += 1
            continue
        allow += 1
        where = f'Statement[{index}]'
        if 'NotAction' in statement:
            findings.append(_finding('high', 'iam-not-action', 'Allow with NotAction can cover unlisted applicable actions within the resource/condition scope. Review scope; not proof every AWS action is allowed.', where))
        else:
            lowered = [action.lower() for action in actions]
            if '*' in lowered or '*:*' in lowered:
                findings.append(_finding('high', 'iam-admin-action', 'Allow contains an all-action wildcard. Final access depends on applicable scope, conditions and other policies.', where))
            if any(action.endswith(':*') and action != '*:*' for action in lowered):
                findings.append(_finding('medium', 'iam-service-wildcard', 'Allow contains a service-wide action wildcard. Applicability and effective access are not evaluated.', where))
            if any(action in {'iam:passrole', 'iam:*', '*', '*:*'} for action in lowered) and 'Resource' in statement and '*' in resources:
                findings.append(_finding('high', 'iam-passrole-any', 'Allow has a PassRole-capable action pattern with Resource star. Conditions and role/service relationships need human review; exploitability is not established.', where))
            elif any('*' in action or '?' in action for action in lowered) and not any(action in {'*', '*:*'} or action.endswith(':*') for action in lowered):
                findings.append(_finding('medium', 'iam-action-pattern', 'Allow contains action-name wildcards. Expanded actions and effective permissions are not computed.', where))
        if 'NotResource' in statement:
            findings.append(_finding('high', 'iam-not-resource', 'Allow uses NotResource to exclude resources from its applicable scope. Review breadth; excluded resources are not a safe allowlist.', where))
        if 'Resource' in statement and '*' in resources:
            findings.append(_finding('medium', 'iam-resource-wildcard', 'Allow contains Resource star. Some actions require it; conditions and action resource-level support must be reviewed.', where))
        if public:
            findings.append(_finding('medium' if conditional else 'high', 'iam-public-principal', 'Allow contains an all-principals wildcard. Conditions and other policy controls are not evaluated; actual public access is not established.', where))
        if 'NotPrincipal' in statement:
            findings.append(_finding('high', 'iam-not-principal', 'Allow uses a principal complement. Review principal scope and applicable controls; no effective access verdict is made.', where))
    result = _summary(findings, 1)
    result.update({'statements_reviewed': len(statements), 'allow_statements': allow, 'deny_statements': deny,
                   'condition_blocks_present': conditions, 'effective_permissions_verified': False,
                   'aws_syntax_validated': False, 'limits': LIMITS, 'sources': SOURCES})
    return result
