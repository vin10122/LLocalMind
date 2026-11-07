"""Packaged runtime smoke check; no model download or GGUF required."""
import json
import os
from pathlib import Path


def probe():
    import numpy as np
    import gguf
    import tokenizers
    import openvino as ov
    import openvino.opset13 as ops
    from flash_moe.native_expert import load_native_expert
    from run_q4k_f16_openvino import dequant_to_f16, _cpp_dequant
    core=ov.Core()
    value=ops.parameter([1,4],ov.Type.f32)
    compiled=core.compile_model(ov.Model([ops.add(value,value)],[value]),'CPU')
    result=compiled([np.ones((1,4),np.float32)])[compiled.output(0)]
    np.testing.assert_array_equal(result,np.full((1,4),2,np.float32))
    types=dict(gate=11,up=11,down=11)
    native=load_native_expert('native',None,'CPU',{0:types})
    raw=np.zeros((256,110),np.uint8)
    raw[:,-2:]=np.frombuffer(np.float16(.001).tobytes(),np.uint8)
    tensors={name:raw.tobytes() for name in types}
    output=native.forward(tensors,types,np.full(256,.001,np.float32),256,256)
    if output.shape!=(256,) or not np.isfinite(output).all():
        raise RuntimeError('Native expert smoke check failed')
    if _cpp_dequant is None:
        raise RuntimeError('Native weight-conversion DLL is missing or unloadable')
    weights=dequant_to_f16(tensors['gate'],11,256*256)
    if weights.size!=256*256 or not np.isfinite(weights).all():
        raise RuntimeError('Native weight-conversion smoke check failed')
    if native.delta is None:
        raise RuntimeError('Native DeltaNet export missing')
    state=np.zeros((2,8,8),np.float32)
    heads=np.full((2,8),.1,np.float32)
    out=native.delta.forward(state,heads,heads,heads,np.full(2,.5,np.float32),np.full(2,-.1,np.float32))
    if not np.isfinite(out).all() or not state.any():
        raise RuntimeError('Native DeltaNet smoke check failed')
    from .vision_runtime import RuntimeInstaller,PACKAGE
    runtime=os.environ.get('LLOCALMIND_TEST_RUNTIME_DIR')
    if runtime:
        # Exercise DLL loading from the actual frozen app/installer as well
        # as from source, without loading or downloading a GGUF.
        RuntimeInstaller(runtime).install()
    return dict(openvino=ov.__version__,devices=core.available_devices,
                numpy=np.__version__,native_expert=True,native_delta=True,
                native_dequant=True,gguf=True,tokenizers=tokenizers.__version__,
                vision_runtime=PACKAGE.tag,vision_runtime_probed=bool(runtime))


def write_report(filename,result):
    if filename:
        path=Path(filename)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,indent=2),encoding='utf-8')
