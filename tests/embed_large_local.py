import sys, traceback, os
sys.path.insert(0, '.')
print('Python:', sys.version)
print('Testing LARGE model from cache...')
try:
    from sentence_transformers import SentenceTransformer
    import os
    # Point directly to cached model
    cache = os.path.expanduser(r'~/.cache/huggingface/hub/models--intfloat--multilingual-e5-large')
    # Find snapshot dir
    snapshots = os.path.join(cache, 'snapshots')
    if os.path.isdir(snapshots):
        snap = os.listdir(snapshots)
        if snap:
            model_path = os.path.join(snapshots, snap[0])
            print('Loading from local path:', model_path)
            m = SentenceTransformer(model_path, device='cpu')
            print('dim:', m.get_sentence_embedding_dimension())
            v = m.encode(['query: pho bo'], normalize_embeddings=True)
            print('vec len:', len(v[0]))
            print('DONE - large model OK from cache')
        else:
            print('No snapshot dir found')
    else:
        print('Snapshots dir not found at', snapshots)
except Exception:
    traceback.print_exc()
