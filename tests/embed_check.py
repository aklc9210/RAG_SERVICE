import sys, traceback
sys.path.insert(0, '.')
try:
    from sentence_transformers import SentenceTransformer
    print('Loading...')
    m = SentenceTransformer('intfloat/multilingual-e5-large', device='cpu')
    print('dim:', m.get_sentence_embedding_dimension())
    print('DONE')
except Exception:
    traceback.print_exc()
