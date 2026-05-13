cd src/chemformer/service

export CHEMFORMER_MODEL=../models/pre-trained/combined/step=1000000.ckpt
export CHEMFORMER_VOCAB=../models/bart_vocab.json
export CHEMFORMER_TASK=backward_prediction

python chemformer_service.py
