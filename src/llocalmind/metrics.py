"""Persistent per-response metrics; no inference or Qt dependencies."""
import math


def _number(value):
    if type(value) not in (int,float):
        return None
    try:
        value=float(value)
    except OverflowError:
        return None
    return value if math.isfinite(value) and value>=0 else None


def clean_stats(value):
    if not isinstance(value,dict):
        return None
    tokens=value.get('tokens')
    if type(tokens) is not int or tokens<0:
        return None
    result={'tokens':tokens}
    for key in ('rate','first_token','prefill','decode_seconds'):
        result[key]=_number(value.get(key))
    if tokens<2:
        result['rate']=None
    result['interrupted']=value.get('interrupted') is True
    for key in ('input_seconds','startup_seconds'):
        if key in value:result[key]=_number(value[key])
    for key in ('prompt_tokens','image_max_tokens','evaluated_prompt_tokens','cached_tokens'):
        if type(value.get(key)) is int and value[key]>=0:result[key]=value[key]
    return result


def response_summary(value):
    stats=clean_stats(value)
    if stats is None or not stats['tokens']:
        return ''
    count=stats['tokens']
    if stats['rate'] is None:
        return f'{count} token · tok/s non misurabili'
    rate=f"{stats['rate']:.2f}".replace('.',',')
    return f'{rate} tok/s · {count} token'
