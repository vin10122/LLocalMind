"""Target-PC vision timings using saved settings; no downloads or settings edits."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
import statistics
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
    parser.add_argument('--image-profile',choices=('detail','fast'))
    parser.add_argument('--show-answers',action='store_true',help='Mostra il testo delle risposte nella console, senza salvarlo nel report')
    parser.add_argument('--compare-image-profiles',action='store_true',help='Confronta i profili nello stesso processo disabilitando il riuso del prompt')
    parser.add_argument('--runs',type=int,default=2,choices=range(1,5))
    parser.add_argument('--max-tokens',type=int,default=32)
    args=parser.parse_args(argv)
    engine=None
    report=dict(samples=[],note='Richieste identiche; la seconda può beneficiare della cache. Non confrontare con un test a freddo.')
    result=0
    try:
        values=validate_settings(json.loads(args.settings.read_text(encoding='utf-8')))
        if args.image_profile is not None:values=validate_settings(dict(values,vision_image_profile=args.image_profile))
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
            schedule=[]
            for index in range(args.runs):
                profiles=(('detail','fast') if index%2==0 else ('fast','detail')) if args.compare_image_profiles else (values['vision_image_profile'],)
                schedule.extend((index+1,profile) for profile in profiles)
            report['comparison_mode']=args.compare_image_profiles
            if args.compare_image_profiles:
                report['note']='Profili alternati nello stesso processo; cache del prompt disabilitata. Cache OS, routing e temperatura possono influire. Valutare anche i dettagli delle risposte.'
            for pair,profile in schedule:
                started=time.perf_counter()
                messages=chat_messages(history,directory,cache=cache,language=values['language'],image_profile=profile)
                prepare=time.perf_counter()-started
                stats=dict(engine.generate(messages,max_tokens=args.max_tokens,cache_prompt=not args.compare_image_profiles,
                    on_text=(lambda value:print(value,end='',flush=True)) if args.show_answers else (lambda _:None)))
                if args.show_answers:print(flush=True)
                stats['input_seconds']=prepare
                stats['image_profile']=profile
                stats['input_images']=1
                if stats.get('first_token') is not None:stats['first_token']+=prepare
                sample=dict(run=len(report['samples'])+1,pair=pair,prompt_cache_enabled=not args.compare_image_profiles,
                            total_seconds=time.perf_counter()-started,memory=memory_snapshot(engine.process.pid),
                            **(clean_stats(stats) or {}))
                report['samples'].append(sample)
                print(json.dumps(sample,ensure_ascii=False),flush=True)
            if args.compare_image_profiles:
                comparison={}
                for profile in ('detail','fast'):
                    rows=[sample for sample in report['samples'] if sample['image_profile']==profile]
                    comparison[profile]={}
                    for key in ('first_token','prefill','total_seconds','evaluated_prompt_tokens','cached_tokens'):
                        values_=[sample[key] for sample in rows if type(sample.get(key)) in (float,int)]
                        if values_:comparison[profile][key+'_median']=statistics.median(values_)
                report['comparison']=comparison
                print('Confronto osservato: '+json.dumps(comparison,ensure_ascii=False),flush=True)
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
