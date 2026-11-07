"""CLI multimodal path: select it before allocating the native text model."""
from pathlib import Path
import sys
import tempfile
from flash_moe.multimodal import LocalVisionModel
from .app_paths import data_root
from .images import chat_messages,import_image
from .metrics import response_summary


def run(args,model_path):
    if not args.mmproj:
        print('errore: --image e --llama-server richiedono --mmproj.',file=sys.stderr)
        return 1
    engine=None
    try:
        with tempfile.TemporaryDirectory(prefix='llocalmind-image-') as directory:
            images=[import_image(args.image,directory)] if args.image else []
            engine=LocalVisionModel(model_path,args.mmproj,args.llama_server,
                max_seq=args.max_seq,threads=args.expert_workers,prefill_threads=args.prefill_threads,
                log_path=data_root()/'logs/vision.log',image_max_tokens=args.vision_image_tokens,
                batch_tokens=args.vision_batch,ubatch_tokens=args.vision_ubatch,
                cache_mib=args.vision_cache_mib,warmup=not args.vision_no_warmup)
            print('[Vision] Encoder immagini e modello su CPU. Il motore testo OpenVINO non viene caricato.',flush=True)
            engine.start(progress=lambda _,label:print(label,flush=True))
            def ask(prompt):
                print('  ',end='',flush=True)
                stats=engine.generate(chat_messages([dict(role='user',content=prompt,images=images)],directory),
                    max_tokens=args.max_tokens,temperature=args.temp,seed=args.seed,
                    on_text=lambda text:print(text,end='',flush=True))
                print('\n'+(response_summary(stats) or 'Conteggio token non disponibile')+'\n',flush=True)
            prompt=' '.join(args.prompt).strip()
            if prompt:
                ask(prompt)
            else:
                print('Vision pronta. /exit per uscire. L’immagine indicata resta associata a ogni domanda.')
                while True:
                    try:prompt=input('> ').strip()
                    except EOFError:break
                    if prompt in ('/exit','/quit','/esce'):break
                    if prompt:ask(prompt)
        return 0
    except KeyboardInterrupt:
        print('\ninterrotto')
        return 0
    except (OSError,ValueError,RuntimeError) as error:
        print('errore vision: '+str(error),file=sys.stderr)
        return 1
    finally:
        if engine is not None:engine.close()
