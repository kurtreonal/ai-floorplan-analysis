"""Private hash-bound recovery checkpoints under the existing worker lease.

These are advisory pixel proposals, never reviews or canonical publications.
Checkpoint files are append-only. Cancellation/retry keeps their best geometry.
"""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from time import monotonic, time_ns
from uuid import uuid4
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload, InferenceParameter
from app.ai.floor_plan_interpretation.wiring_recovery import recover_wiring, RecoveryLimits, VERSION
from app.ai.floor_plan_interpretation.input_profile import inspect_input_pixels


class RecoveryCheckpointStore:
    def __init__(self,root,*,job_id,page_id,source_sha256,payload,limits):
        if type(job_id) is not int or type(page_id) is not int or min(job_id,page_id)<=0:
            raise ValueError('Invalid recovery identity.')
        self.root=Path(root).resolve(strict=True)
        identity=dict(source=source_sha256,base=sha256(payload.model_dump_json().encode()).hexdigest(),
                      version=VERSION,limits=asdict(limits))
        self.fingerprint=sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        # Keep Windows paths below legacy MAX_PATH for ordinary configured
        # storage roots. Full source/config/base hashes still bind the wrapper.
        self.directory=self.root/'wiring-recovery'/f'j{job_id}-p{page_id}'/self.fingerprint[:32]
        self.directory.mkdir(parents=True,exist_ok=True)
        if self.directory.resolve(strict=True)!=self.directory or not self.directory.is_relative_to(self.root):
            raise ValueError('Unsafe recovery checkpoint directory.')
        self.reference=None

    def load(self):
        for path in sorted(self.directory.glob('checkpoint-*.json'),reverse=True)[:1024]:
            try:
                if path.resolve()!=path or not 0<path.stat().st_size<=2_000_000:continue
                wrapper=json.loads(path.read_text(encoding='utf-8'))
                state=wrapper['state']
                raw=json.dumps(state,sort_keys=True,separators=(',',':')).encode()
                if wrapper['fingerprint']!=self.fingerprint or sha256(raw).hexdigest()!=wrapper['sha256']:continue
                FloorPlanInterpretationPayload.model_validate(state['payload'])
                if (type(state['cursor']) is not int or not 0<=state['cursor']<=512
                    or type(state['method_index']) is not int or not 0<=state['method_index']<=2
                    or type(state['windows']) is not int or not 0<=state['windows']<=512
                    or not 0<=state['spent_seconds']<=900 or len(state['passes'])>2):continue
                self.reference=path
                return state
            except (ValueError,KeyError,TypeError,OSError):continue
        return None

    def save(self,state):
        raw=json.dumps(state,sort_keys=True,separators=(',',':')).encode()
        wrapper=dict(fingerprint=self.fingerprint,sha256=sha256(raw).hexdigest(),state=state)
        path=self.directory/f'checkpoint-{time_ns():020d}-{uuid4().hex[:8]}.json'
        with path.open('x',encoding='utf-8') as stream:json.dump(wrapper,stream,separators=(',',':'))
        self.reference=path


def recover_worker_wiring(payload,image,*,root,job_id,page_id,source_sha256,settings,heartbeat):
    limits=RecoveryLimits(maximum_windows=getattr(settings,'wiring_recovery_maximum_windows',64),
                          maximum_seconds=getattr(settings,'wiring_recovery_maximum_seconds',90))
    store=RecoveryCheckpointStore(root,job_id=job_id,page_id=page_id,source_sha256=source_sha256,payload=payload,limits=limits)
    previous=store.load();last=[0.]
    def check():
        if monotonic()-last[0]>.5:
            heartbeat();last[0]=monotonic()
    heartbeat()
    result=recover_wiring(payload,image,limits=limits,check=check,checkpoint=store.save,resume=previous)
    heartbeat()
    parameters=(InferenceParameter(name='wiring-recovery-version',value=VERSION),
        InferenceParameter(name='input-pixel-profile',value=json.dumps(inspect_input_pixels(image,payload),sort_keys=True)),
        InferenceParameter(name='wiring-recovery-limits',value=json.dumps(asdict(limits),sort_keys=True)),
        InferenceParameter(name='wiring-recovery-reference',value=store.reference.relative_to(store.root).as_posix()),
        InferenceParameter(name='wiring-recovery-sha256',value=sha256(store.reference.read_bytes()).hexdigest()))
    return result,parameters
