"""Load pinned main code without switching branches or changing service defaults."""
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys

from app.services import llm_direct as shared

SNAPSHOT=Path(__file__).with_name('main_selector_snapshot')


def canonical_hash(data):
    return hashlib.sha256(data.decode('utf-8').replace('\r\n','\n').encode('utf-8')).hexdigest()


def load_main_selector():
    manifest=json.loads((SNAPSHOT/'manifest.json').read_text(encoding='utf-8'))
    root=Path(__file__).resolve().parents[3]
    for path,expected in manifest['shared_files'].items():
        if canonical_hash((root/path).read_bytes())!=expected:
            raise ValueError('Shared code/data changed; main comparison refused: '+path)
    modules={}
    for name,record in manifest['selector_files'].items():
        path=SNAPSHOT/(name+'.py.txt')
        if canonical_hash(path.read_bytes())!=record['sha256_lf']:
            raise ValueError('Main snapshot changed: '+name)
        module_name='app.evaluation._pinned_main_'+name
        loader=importlib.machinery.SourceFileLoader(module_name,str(path))
        specification=importlib.util.spec_from_loader(module_name,loader)
        module=importlib.util.module_from_spec(specification)
        sys.modules[module_name]=module
        try: loader.exec_module(module)
        finally: sys.modules.pop(module_name,None)
        modules[name]=module
    main=modules['llm_direct']
    # The frozen source uses absolute imports. Bind those four names to helpers
    # from the SAME main commit, rather than the improved working-tree helpers.
    main.derive_conditions=modules['recommendation_conditions'].derive_conditions
    main.category_matches=modules['recommendation_conditions'].category_matches
    main.requires_description=modules['taste_evidence'].requires_description
    main.supports_request=modules['taste_evidence'].supports_request
    # Paths refer to the hash-verified shared catalogue, not the snapshot folder.
    main.ROOT=shared.ROOT
    main.DEFAULT_EVIDENCE=shared.DEFAULT_EVIDENCE
    main.baseline_provenance=manifest
    return main
