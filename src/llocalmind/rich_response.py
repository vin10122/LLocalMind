"""Small, data-only response protocol. No executable content or remote resources."""
import json
import re

MARKER = '```llocalmind-ui'
BLOCK = re.compile(r'^```llocalmind-ui\s*\n(.*?)\n```\s*$', re.M | re.S)


def _text(value, limit=1200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Invalid widget text')
    return value


def parse_response(text, *, pending=False):
    """Return display prose, validated widgets and clipboard text.

    Accept one terminal block only. Invalid/final truncated blocks stay visible
    as ordinary Markdown; partial protocol is hidden only while streaming.
    """
    position = text.find(MARKER)
    if position < 0 or (position and text[position-1] != '\n'):
        return text, [], text
    if pending:
        return text[:position].rstrip(), [], text
    match = BLOCK.fullmatch(text[position:])
    if not match or len(match[1]) > 24000:
        return text, [], text
    try:
        data = json.loads(match[1])
        if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
            raise ValueError('Invalid version')
        fallback = _text(data.get('fallback'), 12000)
        widgets = data.get('widgets')
        if not isinstance(widgets, list) or not 1 <= len(widgets) <= 4:
            raise ValueError('Invalid widgets')
        result = []
        for widget in widgets:
            if not isinstance(widget, dict):
                raise ValueError('Invalid widget')
            kind = widget.get('type')
            title = _text(widget.get('title'), 120)
            if kind == 'card':
                result.append(dict(type=kind, title=title, text=_text(widget.get('text'))))
            elif kind == 'checklist':
                items = widget.get('items')
                if not isinstance(items, list) or not 1 <= len(items) <= 16:
                    raise ValueError('Invalid checklist')
                result.append(dict(type=kind, title=title, items=[_text(x, 300) for x in items]))
            elif kind == 'table':
                columns, rows = widget.get('columns'), widget.get('rows')
                if not isinstance(columns, list) or not 1 <= len(columns) <= 6:
                    raise ValueError('Invalid columns')
                columns = [_text(x, 120) for x in columns]
                if not isinstance(rows, list) or not 1 <= len(rows) <= 20:
                    raise ValueError('Invalid rows')
                for row in rows:
                    if not isinstance(row, list) or len(row) != len(columns):
                        raise ValueError('Invalid row')
                    for cell in row:
                        _text(cell, 300)
                result.append(dict(type=kind, title=title, columns=columns, rows=rows))
            else:
                raise ValueError('Unknown widget')
        prose = text[:position].rstrip()
        return prose, result, '\n\n'.join(x for x in (prose, fallback) if x)
    except (ValueError, TypeError, RecursionError):
        return text, [], text


UI_INSTRUCTIONS = (
    '\nWhen useful for comparisons or practical steps, you may end your answer with one '
    '```llocalmind-ui fenced JSON block: {"version":1,"fallback":"complete readable text of the widgets",'
    '"widgets":[...]}. Use at most 4 widgets. Types: '
    '{"type":"card","title":"...","text":"..."}, '
    '{"type":"table","title":"...","columns":["..."],"rows":[["..."]]}, '
    '{"type":"checklist","title":"...","items":["..."]}. '
    'Use the answer language, plain strings, max 6 columns/20 rows/16 checklist items. '
    'No code, HTML or actions. Normal prose is preferred when widgets add no value.'
)
