"""Target-PC vision timings using saved settings; no downloads or settings edits."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from flash_moe.multimodal import LocalVisionModel
from .app_paths import data_root,user_data_dir
from .images import ImagePayloadCache,chat_messages,import_image
from .metrics import clean_stats
from .state import validate_settings
from .performance import memory_snapshot


def main(argv=None):
    parser=argparse.ArgumentParser(description='Misura avvio, primo token e prompt vision. Chiudi la GUI prima di eseguire.')
    parser.add_argument('--benchmark-vision',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--settings',type=Path,default=user_data_dir()/'settings.json')
    parser.add_argument('--output',type=Path,default=data_root()/'logs/vision-benchmark.json')
    parser.add_argument('--image-tokens',type=int)
    parser.add_argument('--runs',type=int,default=2,choices=range(1,5))
    parser.add_argument('--max-tokens',type=int,default=32)
    args=parser.parse_args(argv)
    engine=None
    report=dict(samples=[],note='Richieste identiche; la seconda può beneficiare della cache. Non confrontare con un test a freddo.')
    result=0
    try:
        values=validate_settings(json.loads(args.settings.read_text(encoding='utf-8')))
        if args.image_tokens is not None:values=validate_settings(dict(values,vision_image_tokens=args.image_tokens))
        if not 1<=args.max_tokens<values['max_seq']:raise ValueError('Limite token non valido')
        report['model_bytes']=Path(values['model_path']).stat().st_size
        report['projector_bytes']=Path(values['vision_projector']).stat().st_size
        report['profile']={k:v for k,v in values.items() if k.startswith('vision_') and k not in ('vision_projector','vision_executable')}
        report['context']=values['max_seq']
        with tempfile.TemporaryDirectory(prefix='llocalmind-vision-bench-') as directory:
            started=time.perf_counter()
            item=import_image(args.image,directory)
            report['image_prepare_seconds']=time.perf_counter()-started
            cache=ImagePayloadCache()
            history=[dict(role='user',content='Descrivi brevemente questa immagine.',images=[item])]
            engine=LocalVisionModel(values['model_path'],values['vision_projector'],values['vision_executable'],
                max_seq=values['max_seq'],threads=values['vision_threads'],prefill_threads=values['vision_threads'],
                image_max_tokens=values['vision_image_tokens'],batch_tokens=values['vision_batch'],
                ubatch_tokens=values['vision_ubatch'],cache_mib=values['vision_cache_mib'],warmup=values['vision_warmup'],
                log_path=data_root()/'logs/vision-benchmark-server.log')
            print('Caricamento del modello; mantieni la GUI chiusa.',flush=True)
            engine.start()
            report['startup_seconds']=engine.startup_seconds
            for index in range(args.runs):
                started=time.perf_counter()
                messages=chat_messages(history,directory,cache=cache,language=values['language'])
                prepare=time.perf_counter()-started
                stats=dict(engine.generate(messages,max_tokens=args.max_tokens))
                stats['input_seconds']=prepare
                if stats.get('first_token') is not None:stats['first_token']+=prepare
                sample=dict(run=index+1,total_seconds=time.perf_counter()-started,memory=memory_snapshot(engine.process.pid),
                            **(clean_stats(stats) or {}))
                report['samples'].append(sample)
                print(json.dumps(sample,ensure_ascii=False),flush=True)
    except Exception as error:
        report['error']=str(error)
        print(str(error),file=sys.stderr)
        result=1
    finally:
        if engine is not None:engine.close()
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        print('Report: '+str(args.output),flush=True)
    return result
