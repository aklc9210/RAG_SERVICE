import sys, traceback
sys.path.insert(0, '.')
try:
    from sentence_transformers import SentenceTransformer
    print('Trying small model...')
    m = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')
    print('dim:', m.get_sentence_embedding_dimension())
    v = m.encode(['query: pho bo'], normalize_embeddings=True)
    print('vec len:', len(v[0]))
    print('DONE - small model OK')
except Exception:
    traceback.print_exc()
